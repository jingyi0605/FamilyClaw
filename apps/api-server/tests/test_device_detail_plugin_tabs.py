import tempfile
import unittest

import app.db.models  # noqa: F401
from app.db.utils import dump_json, new_uuid
from app.modules.device.models import Device, DeviceBinding
from app.modules.device.service import get_device_detail_view
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.config_service import get_plugin_config_form, save_plugin_config_form
from app.modules.plugin.repository import get_plugin_config_instance_for_device
from app.modules.plugin.schemas import PluginConfigUpdateRequest


class DeviceDetailPluginTabsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.SessionLocal = self._db_helper.SessionLocal

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(
                    name="Voice Home",
                    city="Shanghai",
                    timezone="Asia/Shanghai",
                    locale="zh-CN",
                ),
            )
            device = Device(
                id=new_uuid(),
                household_id=household.id,
                room_id=None,
                name="客厅小爱",
                device_type="speaker",
                vendor="xiaomi",
                status="active",
                controllable=1,
                voice_auto_takeover_enabled=1,
                voiceprint_identity_enabled=1,
            )
            device.voice_takeover_prefixes = ["请", "帮我"]
            db.add(device)
            db.flush()

            binding = DeviceBinding(
                id=new_uuid(),
                device_id=device.id,
                integration_instance_id=None,
                platform="open_xiaoai",
                external_entity_id="xiaomi-speaker-001",
                external_device_id="xiaomi-speaker-001",
                plugin_id="open-xiaoai-speaker",
                capabilities=dump_json(
                    {
                        "vendor_code": "xiaomi",
                        "adapter_type": "open_xiaoai",
                        "capability_tags": ["speaker", "voice_terminal"],
                    }
                ),
            )
            db.add(binding)
            db.commit()
            self.household_id = household.id
            self.device_id = device.id

    def tearDown(self) -> None:
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_device_scope_config_reads_legacy_values_and_syncs_back(self) -> None:
        with self.SessionLocal() as db:
            form = get_plugin_config_form(
                db,
                household_id=self.household_id,
                plugin_id="open-xiaoai-speaker",
                scope_type="device",
                scope_key=self.device_id,
            )

            self.assertEqual("configured", form.view.state)
            self.assertEqual(True, form.view.values["voice_auto_takeover_enabled"])
            self.assertEqual("请\n帮我", form.view.values["voice_takeover_prefixes"])

            updated = save_plugin_config_form(
                db,
                household_id=self.household_id,
                plugin_id="open-xiaoai-speaker",
                payload=PluginConfigUpdateRequest(
                    scope_type="device",
                    scope_key=self.device_id,
                    values={
                        "voice_auto_takeover_enabled": False,
                        "voice_takeover_prefixes": "你好\n小管家",
                    },
                    clear_secret_fields=[],
                ),
                updated_by="member-admin-1",
            )
            db.commit()

            device = db.get(Device, self.device_id)
            assert device is not None
            instance = get_plugin_config_instance_for_device(
                db,
                device_id=self.device_id,
                plugin_id="open-xiaoai-speaker",
            )

            self.assertIsNotNone(instance)
            assert instance is not None
            self.assertEqual(self.device_id, instance.device_id)
            self.assertEqual(False, updated.view.values["voice_auto_takeover_enabled"])
            self.assertEqual("你好\n小管家", updated.view.values["voice_takeover_prefixes"])
            self.assertEqual(0, device.voice_auto_takeover_enabled)
            self.assertEqual(["你好", "小管家"], device.voice_takeover_prefixes)

    def test_device_detail_view_exposes_builtin_and_plugin_tabs(self) -> None:
        with self.SessionLocal() as db:
            detail_view = get_device_detail_view(db, device_id=self.device_id)

        self.assertEqual(self.device_id, detail_view.device.id)
        self.assertEqual(True, detail_view.capabilities.supports_voice_terminal)
        self.assertEqual(True, detail_view.capabilities.supports_voiceprint)
        self.assertIn("voiceprint", [tab.key for tab in detail_view.builtin_tabs])
        plugin_tabs = {(tab.plugin_id, tab.tab_key): tab for tab in detail_view.plugin_tabs}
        self.assertIn(("open-xiaoai-speaker", "voice-takeover"), plugin_tabs)
        self.assertEqual(
            "device",
            plugin_tabs[("open-xiaoai-speaker", "voice-takeover")].config_form.view.scope_type,
        )


if __name__ == "__main__":
    unittest.main()
