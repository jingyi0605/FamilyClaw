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
from app.modules.channel import repository as channel_repository
from app.modules.channel.conversation_bridge import handle_inbound_message
from app.modules.channel.models import ChannelInboundEvent
from app.modules.channel.schemas import ChannelAccountCreate, MemberChannelBindingCreate
from app.modules.channel.service import create_channel_account, create_member_binding
from app.modules.conversation.orchestrator import ConversationIntent, ConversationOrchestratorResult
from app.modules.conversation.repository import list_turn_sources
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin.schemas import PluginMountCreate
from app.modules.plugin.service import register_plugin_mount


class ChannelConversationBridgeTests(unittest.TestCase):
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
            HouseholdCreate(name="Bridge Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="妈妈", role="admin"),
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
        plugin_root = self._create_channel_plugin(Path(self._tempdir.name), plugin_id="bridge-channel-plugin")
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
                plugin_id="bridge-channel-plugin",
                account_code="bridge-main",
                display_name="Bridge 主账号",
                connection_mode="webhook",
                config={},
                status="active",
            ),
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_unbound_direct_message_is_ignored_with_fixed_prompt(self) -> None:
        inbound_event = self._create_inbound_event(
            external_event_id="evt-unbound",
            external_user_id="tg-user-unbound",
            external_conversation_key="chat:unbound",
            normalized_payload={
                "text": "你好",
                "chat_type": "direct",
            },
        )

        result = handle_inbound_message(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            inbound_event_id=inbound_event.id,
        )
        self.db.flush()

        self.assertEqual("ignored", result.disposition)
        self.assertEqual("direct_unbound_prompt", result.binding_strategy)
        self.assertIn("绑定", result.reply_text or "")

    @patch("app.modules.channel.conversation_bridge.create_conversation_turn", side_effect=AssertionError("command should not create turn"))
    def test_new_command_creates_new_binding_without_running_normal_turn(self, create_turn_mock) -> None:
        create_member_binding(
            self.db,
            member_id=self.member.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account.id,
                member_id=self.member.id,
                external_user_id="tg-user-command",
                external_chat_id="chat:command",
            ),
        )
        self.db.flush()

        command_event = self._create_inbound_event(
            external_event_id="evt-command-new",
            external_user_id="tg-user-command",
            external_conversation_key="chat:command",
            normalized_payload={
                "text": " /new ",
                "chat_type": "direct",
            },
        )

        result = handle_inbound_message(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            inbound_event_id=command_event.id,
        )
        self.db.flush()

        create_turn_mock.assert_not_called()
        self.assertEqual("dispatched", result.disposition)
        self.assertTrue(result.created_session)
        self.assertTrue(result.created_conversation_binding)
        self.assertIsNone(result.request_id)
        self.assertIsNone(result.assistant_message_id)
        self.assertIn("新会话", result.reply_text or "")

        binding = channel_repository.get_channel_conversation_binding_by_external_key(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            external_conversation_key="chat:command",
        )
        self.assertIsNotNone(binding)
        self.assertEqual(result.conversation_session_id, binding.conversation_session_id)

    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_reset_command_switches_existing_binding_to_new_session(self, run_orchestrated_turn_mock) -> None:
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="好的，我记住了。",
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
        create_member_binding(
            self.db,
            member_id=self.member.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account.id,
                member_id=self.member.id,
                external_user_id="tg-user-reset",
                external_chat_id="chat:reset",
            ),
        )
        self.db.flush()

        first_event = self._create_inbound_event(
            external_event_id="evt-reset-001",
            external_user_id="tg-user-reset",
            external_conversation_key="chat:reset",
            normalized_payload={
                "text": "第一条消息",
                "chat_type": "direct",
            },
        )
        first_result = handle_inbound_message(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            inbound_event_id=first_event.id,
        )
        self.db.flush()
        turn_sources_before = list_turn_sources(self.db, session_id=first_result.conversation_session_id)

        with patch(
            "app.modules.channel.conversation_bridge.create_conversation_turn",
            side_effect=AssertionError("command should not create turn"),
        ) as create_turn_mock:
            reset_event = self._create_inbound_event(
                external_event_id="evt-reset-002",
                external_user_id="tg-user-reset",
                external_conversation_key="chat:reset",
                normalized_payload={
                    "text": "/reset",
                    "chat_type": "direct",
                },
            )
            reset_result = handle_inbound_message(
                self.db,
                household_id=self.household.id,
                channel_account_id=self.account.id,
                inbound_event_id=reset_event.id,
            )
            self.db.flush()

        create_turn_mock.assert_not_called()
        self.assertNotEqual(first_result.conversation_session_id, reset_result.conversation_session_id)
        self.assertIn("重置", reset_result.reply_text or "")
        turn_sources_after = list_turn_sources(self.db, session_id=first_result.conversation_session_id)
        self.assertEqual(len(turn_sources_before), len(turn_sources_after))

        binding = channel_repository.get_channel_conversation_binding_by_external_key(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            external_conversation_key="chat:reset",
        )
        self.assertIsNotNone(binding)
        self.assertEqual(reset_result.conversation_session_id, binding.conversation_session_id)

    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_bound_message_reuses_same_conversation_binding(self, run_orchestrated_turn_mock) -> None:
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="你好，我已经收到消息。",
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
        create_member_binding(
            self.db,
            member_id=self.member.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account.id,
                member_id=self.member.id,
                external_user_id="tg-user-001",
                external_chat_id="chat:bound",
            ),
        )
        self.db.flush()

        first_event = self._create_inbound_event(
            external_event_id="evt-001",
            external_user_id="tg-user-001",
            external_conversation_key="chat:bound",
            normalized_payload={
                "text": "第一条消息",
                "chat_type": "direct",
            },
        )
        first_result = handle_inbound_message(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            inbound_event_id=first_event.id,
        )
        self.db.flush()

        second_event = self._create_inbound_event(
            external_event_id="evt-002",
            external_user_id="tg-user-001",
            external_conversation_key="chat:bound",
            normalized_payload={
                "text": "第二条消息",
                "chat_type": "direct",
            },
        )
        second_result = handle_inbound_message(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            inbound_event_id=second_event.id,
        )
        self.db.flush()

        self.assertEqual("dispatched", first_result.disposition)
        self.assertEqual("bound", first_result.binding_strategy)
        self.assertTrue(first_result.created_session)
        self.assertTrue(first_result.created_conversation_binding)
        self.assertEqual("dispatched", second_result.disposition)
        self.assertEqual(first_result.conversation_session_id, second_result.conversation_session_id)
        self.assertFalse(second_result.created_session)
        self.assertFalse(second_result.created_conversation_binding)
        self.assertIn("收到消息", second_result.reply_text or "")

        turn_sources = list_turn_sources(self.db, session_id=first_result.conversation_session_id)
        self.assertEqual(2, len(turn_sources))
        self.assertTrue(all(item.source_kind == "channel" for item in turn_sources))
        self.assertTrue(all(item.channel_account_id == self.account.id for item in turn_sources))
        self.assertTrue(all(item.external_conversation_key == "chat:bound" for item in turn_sources))

    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_group_threads_are_isolated_and_same_thread_reuses_binding(self, run_orchestrated_turn_mock) -> None:
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="线程消息已收到。",
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
        create_member_binding(
            self.db,
            member_id=self.member.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account.id,
                member_id=self.member.id,
                external_user_id="tg-user-thread",
                external_chat_id="chat:group-1",
            ),
        )
        self.db.flush()

        thread_a_first = handle_inbound_message(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            inbound_event_id=self._create_inbound_event(
                external_event_id="evt-thread-a-1",
                external_user_id="tg-user-thread",
                external_conversation_key="chat:group-1",
                normalized_payload={
                    "text": "线程 A 第一条",
                    "chat_type": "group",
                    "thread_key": "101",
                },
            ).id,
        )
        self.db.flush()

        thread_a_second = handle_inbound_message(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            inbound_event_id=self._create_inbound_event(
                external_event_id="evt-thread-a-2",
                external_user_id="tg-user-thread",
                external_conversation_key="chat:group-1",
                normalized_payload={
                    "text": "线程 A 第二条",
                    "chat_type": "group",
                    "thread_key": "101",
                },
            ).id,
        )
        self.db.flush()

        thread_b_first = handle_inbound_message(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            inbound_event_id=self._create_inbound_event(
                external_event_id="evt-thread-b-1",
                external_user_id="tg-user-thread",
                external_conversation_key="chat:group-1",
                normalized_payload={
                    "text": "线程 B 第一条",
                    "chat_type": "group",
                    "thread_key": "202",
                },
            ).id,
        )
        self.db.flush()

        self.assertEqual(thread_a_first.conversation_session_id, thread_a_second.conversation_session_id)
        self.assertNotEqual(thread_a_first.conversation_session_id, thread_b_first.conversation_session_id)

        thread_a_binding = channel_repository.get_channel_conversation_binding_by_external_key(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            external_conversation_key="chat:group-1#thread:101",
        )
        thread_b_binding = channel_repository.get_channel_conversation_binding_by_external_key(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            external_conversation_key="chat:group-1#thread:202",
        )
        self.assertIsNotNone(thread_a_binding)
        self.assertIsNotNone(thread_b_binding)
        self.assertNotEqual(thread_a_binding.conversation_session_id, thread_b_binding.conversation_session_id)

        thread_a_sources = list_turn_sources(self.db, session_id=thread_a_first.conversation_session_id)
        thread_b_sources = list_turn_sources(self.db, session_id=thread_b_first.conversation_session_id)
        self.assertTrue(all(item.external_conversation_key == "chat:group-1" for item in thread_a_sources))
        self.assertTrue(all(item.thread_key == "101" for item in thread_a_sources))
        self.assertTrue(all(item.thread_key == "202" for item in thread_b_sources))

    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_thread_reset_only_switches_current_thread(self, run_orchestrated_turn_mock) -> None:
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="线程消息已收到。",
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
        create_member_binding(
            self.db,
            member_id=self.member.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account.id,
                member_id=self.member.id,
                external_user_id="tg-user-thread-reset",
                external_chat_id="chat:group-2",
            ),
        )
        self.db.flush()

        thread_a_before = handle_inbound_message(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            inbound_event_id=self._create_inbound_event(
                external_event_id="evt-thread-reset-a-1",
                external_user_id="tg-user-thread-reset",
                external_conversation_key="chat:group-2",
                normalized_payload={
                    "text": "线程 A 原消息",
                    "chat_type": "group",
                    "thread_key": "301",
                },
            ).id,
        )
        thread_b_before = handle_inbound_message(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            inbound_event_id=self._create_inbound_event(
                external_event_id="evt-thread-reset-b-1",
                external_user_id="tg-user-thread-reset",
                external_conversation_key="chat:group-2",
                normalized_payload={
                    "text": "线程 B 原消息",
                    "chat_type": "group",
                    "thread_key": "302",
                },
            ).id,
        )
        self.db.flush()

        with patch(
            "app.modules.channel.conversation_bridge.create_conversation_turn",
            side_effect=AssertionError("thread reset should not create turn"),
        ) as create_turn_mock:
            thread_a_reset = handle_inbound_message(
                self.db,
                household_id=self.household.id,
                channel_account_id=self.account.id,
                inbound_event_id=self._create_inbound_event(
                    external_event_id="evt-thread-reset-a-2",
                    external_user_id="tg-user-thread-reset",
                    external_conversation_key="chat:group-2",
                    normalized_payload={
                        "text": "/reset",
                        "chat_type": "group",
                        "thread_key": "301",
                    },
                ).id,
            )
            self.db.flush()

        create_turn_mock.assert_not_called()
        self.assertNotEqual(thread_a_before.conversation_session_id, thread_a_reset.conversation_session_id)

        thread_b_after = handle_inbound_message(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            inbound_event_id=self._create_inbound_event(
                external_event_id="evt-thread-reset-b-2",
                external_user_id="tg-user-thread-reset",
                external_conversation_key="chat:group-2",
                normalized_payload={
                    "text": "线程 B 继续发言",
                    "chat_type": "group",
                    "thread_key": "302",
                },
            ).id,
        )
        self.db.flush()

        self.assertEqual(thread_b_before.conversation_session_id, thread_b_after.conversation_session_id)

    def _create_channel_plugin(self, root: Path, *, plugin_id: str) -> Path:
        plugin_root = root / plugin_id
        plugin_root.mkdir(parents=True, exist_ok=True)
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "Bridge Channel",
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
        return plugin_root

    def _create_inbound_event(
        self,
        *,
        external_event_id: str,
        external_user_id: str,
        external_conversation_key: str,
        normalized_payload: dict,
    ) -> ChannelInboundEvent:
        row = ChannelInboundEvent(
            id=new_uuid(),
            household_id=self.household.id,
            channel_account_id=self.account.id,
            platform_code="telegram",
            external_event_id=external_event_id,
            event_type="message",
            external_user_id=external_user_id,
            external_conversation_key=external_conversation_key,
            normalized_payload_json=json.dumps(normalized_payload, ensure_ascii=False),
            status="received",
            conversation_session_id=None,
            error_code=None,
            error_message=None,
            received_at=utc_now_iso(),
            processed_at=None,
        )
        self.db.add(row)
        self.db.flush()
        return row


if __name__ == "__main__":
    unittest.main()
