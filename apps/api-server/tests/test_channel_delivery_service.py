import json
import sys
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.modules.channel.schemas import ChannelAccountCreate
from app.modules.channel.service import create_channel_account
from app.modules.channel.delivery_service import retry_delivery, send_reply
from app.modules.channel.status_service import summarize_recent_delivery_failures
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.schemas import PluginMountCreate
from app.modules.plugin.service import register_plugin_mount


class ChannelDeliveryServiceTests(unittest.TestCase):
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
            HouseholdCreate(name="Delivery Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        plugin_root = self._create_delivery_channel_plugin(Path(self._tempdir.name), plugin_id="delivery-channel-plugin")
        register_plugin_mount(
            self.db,
            household_id=self.household.id,
            payload=PluginMountCreate(
                source_type="third_party",
                plugin_root=str(plugin_root),
                python_path=sys.executable,
                working_dir=str(plugin_root),
                timeout_seconds=20,
            ),
        )
        self.account = create_channel_account(
            self.db,
            household_id=self.household.id,
            payload=ChannelAccountCreate(
                plugin_id="delivery-channel-plugin",
                account_code="delivery-main",
                display_name="Delivery 主账号",
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

    def test_send_reply_records_sent_delivery(self) -> None:
        result = send_reply(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            external_conversation_key="chat:ok",
            text="你好",
        )
        self.db.flush()

        self.assertTrue(result.sent)
        self.assertEqual("sent", result.delivery.status)
        self.assertEqual("provider-msg-ok", result.provider_message_ref)
        self.assertEqual(1, result.delivery.attempt_count)

    def test_failed_delivery_can_retry_and_status_summary_tracks_failures(self) -> None:
        failed = send_reply(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
            external_conversation_key="chat:fail",
            text="please-fail",
        )
        self.db.flush()

        self.assertFalse(failed.sent)
        self.assertEqual("failed", failed.delivery.status)
        self.assertEqual(1, failed.delivery.attempt_count)
        self.assertIsNotNone(failed.delivery.last_error_code)

        retried = retry_delivery(
            self.db,
            household_id=self.household.id,
            delivery_id=failed.delivery.id,
        )
        self.db.flush()

        self.assertFalse(retried.sent)
        self.assertEqual("failed", retried.delivery.status)
        self.assertEqual(2, retried.delivery.attempt_count)

        summary = summarize_recent_delivery_failures(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account.id,
        )
        self.assertEqual(self.account.id, summary.channel_account_id)
        self.assertEqual("telegram", summary.platform_code)
        self.assertEqual(1, summary.recent_failure_count)
        self.assertEqual(failed.delivery.id, summary.last_delivery_id)
        self.assertEqual(failed.delivery.last_error_code, summary.last_error_code)

    def _create_delivery_channel_plugin(self, root: Path, *, plugin_id: str) -> Path:
        plugin_root = root / plugin_id
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "Delivery 通道插件",
                    "version": "0.1.0",
                    "types": ["channel"],
                    "permissions": ["channel.send"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                    "entrypoints": {"channel": "plugin.channel.handle"},
                    "capabilities": {
                        "channel": {
                            "platform_code": "telegram",
                            "inbound_modes": ["webhook"],
                            "delivery_modes": ["reply", "push"],
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
            "    if data.get('action') != 'send':\n"
            "        return {}\n"
            "    delivery = data.get('delivery', {})\n"
            "    text = delivery.get('text', '')\n"
            "    if text == 'please-fail':\n"
            "        raise RuntimeError('mock send failed')\n"
            "    return {\n"
            "        'provider_message_ref': 'provider-msg-ok',\n"
            "    }\n",
            encoding="utf-8",
        )
        return plugin_root


if __name__ == "__main__":
    unittest.main()
