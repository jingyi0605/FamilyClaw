import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.db.utils import new_uuid, utc_now_iso
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.channel.gateway_service import process_channel_inbound_event
from app.modules.channel.models import ChannelInboundEvent
from app.modules.channel.schemas import ChannelAccountCreate, MemberChannelBindingCreate
from app.modules.channel.service import create_channel_account, create_member_binding, list_channel_delivery_records
from app.modules.conversation.orchestrator import ConversationIntent, ConversationOrchestratorResult
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin.schemas import PluginMountCreate
from app.modules.plugin.service import register_plugin_mount


class ChannelGatewayThreadDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        db_path = Path(self._tempdir.name) / "test.db"
        settings.database_url = f"sqlite:///{db_path}"

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(settings.database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db: Session = self.SessionLocal()

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Thread Delivery Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="爸爸", role="admin"),
        )
        self.agent = create_agent(
            self.db,
            household_id=self.household.id,
            payload=AgentCreate(
                display_name="阿福",
                agent_type="butler",
                self_identity="我是家庭管家",
                role_summary="负责家庭问答",
                personality_traits=["细心"],
                service_focus=["聊天"],
                default_entry=True,
            ),
        )
        plugin_root = self._create_channel_plugin(Path(self._tempdir.name), plugin_id="thread-delivery-plugin")
        register_plugin_mount(
            self.db,
            household_id=self.household.id,
            payload=PluginMountCreate(
                source_type="third_party",
                plugin_root=str(plugin_root),
                python_path="python",
                working_dir=str(plugin_root),
                timeout_seconds=20,
            ),
        )
        self.account = create_channel_account(
            self.db,
            household_id=self.household.id,
            payload=ChannelAccountCreate(
                plugin_id="thread-delivery-plugin",
                account_code="thread-delivery-main",
                display_name="Thread Delivery 主账号",
                connection_mode="webhook",
                config={},
                status="active",
            ),
        )
        create_member_binding(
            self.db,
            member_id=self.member.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account.id,
                member_id=self.member.id,
                external_user_id="tg-user-thread-gateway",
                external_chat_id="chat:group-thread",
            ),
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_thread_message_delivery_targets_current_thread(self, run_orchestrated_turn_mock) -> None:
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="线程回复已生成。",
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name=self.agent.display_name,
        )

        inbound_event = ChannelInboundEvent(
            id=new_uuid(),
            household_id=self.household.id,
            channel_account_id=self.account.id,
            platform_code="telegram",
            external_event_id="evt-thread-delivery-001",
            event_type="message",
            external_user_id="tg-user-thread-gateway",
            external_conversation_key="chat:group-thread",
            normalized_payload_json=json.dumps(
                {
                    "text": "线程里发一条消息",
                    "chat_type": "group",
                    "thread_key": "9",
                    "metadata": {
                        "chat_id": "group-thread",
                    },
                },
                ensure_ascii=False,
            ),
            status="received",
            conversation_session_id=None,
            error_code=None,
            error_message=None,
            received_at=utc_now_iso(),
            processed_at=None,
        )
        self.db.add(inbound_event)
        self.db.commit()

        result = process_channel_inbound_event(
            self.db,
            account_id=self.account.id,
            inbound_event_id=inbound_event.id,
        )
        self.db.commit()

        self.assertEqual("dispatched", result.processing_status)
        deliveries = list_channel_delivery_records(self.db, household_id=self.household.id)
        self.assertEqual(1, len(deliveries))
        self.assertEqual("chat:group-thread#thread:9", deliveries[0].external_conversation_key)

    def _create_channel_plugin(self, root: Path, *, plugin_id: str) -> Path:
        plugin_root = root / plugin_id
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "Thread Delivery Channel",
                    "version": "0.1.0",
                    "types": ["channel"],
                    "permissions": ["channel.receive"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                    "entrypoints": {"channel": "plugin.channel.handle"},
                    "capabilities": {
                        "channel": {
                            "platform_code": "telegram",
                            "inbound_modes": ["webhook"],
                            "delivery_modes": ["reply"],
                            "reserved": False,
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package_dir / "channel.py").write_text(
            "def handle(payload=None):\n"
            "    data = payload or {}\n"
            "    if data.get('action') == 'send':\n"
            "        delivery = data.get('delivery', {})\n"
            "        return {\n"
            "            'provider_message_ref': delivery.get('external_conversation_key'),\n"
            "        }\n"
            "    raise ValueError('unexpected action')\n",
            encoding="utf-8",
        )
        return plugin_root


if __name__ == "__main__":
    unittest.main()
