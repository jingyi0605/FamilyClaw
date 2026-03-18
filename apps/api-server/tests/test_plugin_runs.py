import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.modules.audit.models import AuditLog
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.memory.service import list_memory_cards
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin.models import PluginRawRecord
from app.modules.plugin.models import PluginRun
from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.schemas import PluginMountCreate, PluginRunnerConfig, PluginStateUpdateRequest
from app.modules.plugin.service import register_plugin_mount, run_plugin_sync_pipeline, set_household_plugin_enabled
from tests.homeassistant_test_support import (
    build_homeassistant_sync_payload,
    mock_homeassistant_registry_payloads,
    seed_homeassistant_integration_instance,
)


class PluginRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        self.builtin_root = Path(__file__).resolve().parents[1] / "app" / "plugins" / "builtin"

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
        self.db: Session = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_run_plugin_sync_pipeline_records_success_and_audit(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Run Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="濡堝", role="adult"),
        )
        self.db.flush()

        result = run_plugin_sync_pipeline(
            self.db,
            household_id=household.id,
            request=PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": member.id},
            ),
            root_dir=self.builtin_root,
        )
        self.db.commit()

        self.assertEqual("success", result.run.status)
        self.assertEqual(3, result.run.raw_record_count)
        self.assertEqual(3, result.run.memory_card_count)

        run_row = self.db.get(PluginRun, result.run.id)
        assert run_row is not None
        self.assertEqual("success", run_row.status)

        audit_stmt = select(AuditLog).where(AuditLog.target_type == "plugin_run", AuditLog.target_id == result.run.id)
        audit_row = self.db.scalar(audit_stmt)
        assert audit_row is not None
        self.assertEqual("success", audit_row.result)
        details = json.loads(audit_row.details or "{}")
        self.assertEqual(3, details["raw_record_count"])
        self.assertEqual(3, details["memory_card_count"])

    def test_run_plugin_sync_pipeline_records_failure_and_audit(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Fail Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        result = run_plugin_sync_pipeline(
            self.db,
            household_id=household.id,
            request=PluginExecutionRequest(
                plugin_id="not-exists-plugin",
                plugin_type="connector",
                payload={},
            ),
            root_dir=self.builtin_root,
        )
        self.db.commit()

        self.assertEqual("failed", result.run.status)
        self.assertEqual(0, result.run.raw_record_count)
        self.assertEqual(0, result.run.memory_card_count)
        self.assertEqual("plugin_not_visible_in_household", result.run.error_code)

        audit_stmt = select(AuditLog).where(AuditLog.target_type == "plugin_run", AuditLog.target_id == result.run.id)
        audit_row = self.db.scalar(audit_stmt)
        assert audit_row is not None
        self.assertEqual("fail", audit_row.result)

    def test_stage2_data_pipeline_checkpoint_smoke(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Pipeline Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="濡堝", role="adult"),
        )
        self.db.flush()

        success_result = run_plugin_sync_pipeline(
            self.db,
            household_id=household.id,
            request=PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": member.id},
            ),
            root_dir=self.builtin_root,
        )
        self.db.commit()

        self.assertEqual("success", success_result.run.status)
        self.assertEqual(3, success_result.run.raw_record_count)
        self.assertEqual(3, success_result.run.memory_card_count)

        raw_stmt = select(PluginRawRecord).where(PluginRawRecord.run_id == success_result.run.id)
        raw_rows = list(self.db.scalars(raw_stmt).all())
        self.assertEqual(3, len(raw_rows))

        cards, total = list_memory_cards(
            self.db,
            household_id=household.id,
            page=1,
            page_size=20,
            memory_type="observation",
        )
        self.assertEqual(3, total)
        self.assertTrue(all(card.source_raw_record_id for card in cards))
        self.assertEqual(
            {"daily_steps", "sleep_duration", "heart_rate"},
            {card.content["category"] for card in cards if isinstance(card.content, dict)},
        )

        success_audit_stmt = select(AuditLog).where(
            AuditLog.target_type == "plugin_run",
            AuditLog.target_id == success_result.run.id,
        )
        success_audit = self.db.scalar(success_audit_stmt)
        assert success_audit is not None
        self.assertEqual("success", success_audit.result)

        failed_result = run_plugin_sync_pipeline(
            self.db,
            household_id=household.id,
            request=PluginExecutionRequest(
                plugin_id="not-exists-plugin",
                plugin_type="connector",
                payload={},
            ),
            root_dir=self.builtin_root,
        )
        self.db.commit()

        self.assertEqual("failed", failed_result.run.status)
        self.assertEqual("plugin_not_visible_in_household", failed_result.run.error_code)

        failed_audit_stmt = select(AuditLog).where(
            AuditLog.target_type == "plugin_run",
            AuditLog.target_id == failed_result.run.id,
        )
        failed_audit = self.db.scalar(failed_audit_stmt)
        assert failed_audit is not None
        self.assertEqual("fail", failed_audit.result)

    def test_stage3_smart_home_plugin_pipeline_smoke(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Device Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        instance = self._seed_homeassistant_config(household_id=household.id)
        self.db.commit()

        with mock_homeassistant_registry_payloads():
            result = run_plugin_sync_pipeline(
                self.db,
                household_id=household.id,
                request=PluginExecutionRequest(
                    plugin_id="homeassistant",
                    plugin_type="connector",
                    payload=self._build_homeassistant_sync_payload(
                        household_id=household.id,
                        integration_instance_id=instance.id,
                    ),
                ),
                root_dir=self.builtin_root,
            )
        self.db.commit()

        self.assertEqual("success", result.run.status)
        self.assertEqual(3, result.run.raw_record_count)
        self.assertEqual(3, result.run.memory_card_count)

        raw_stmt = select(PluginRawRecord).where(PluginRawRecord.run_id == result.run.id)
        raw_rows = list(self.db.scalars(raw_stmt).all())
        self.assertEqual(3, len(raw_rows))

        cards, total = list_memory_cards(
            self.db,
            household_id=household.id,
            page=1,
            page_size=20,
            memory_type="observation",
        )
        self.assertEqual(3, total)
        self.assertEqual(
            {"device_power_state", "room_temperature", "room_humidity"},
            {card.content["category"] for card in cards if isinstance(card.content, dict)},
        )

    def test_stage3_sample_plugins_checkpoint_smoke(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Stage3 Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="濡堝", role="adult"),
        )
        instance = self._seed_homeassistant_config(household_id=household.id)
        self.db.flush()
        self.db.commit()

        with mock_homeassistant_registry_payloads():
            smart_home_result = run_plugin_sync_pipeline(
                self.db,
                household_id=household.id,
                request=PluginExecutionRequest(
                    plugin_id="homeassistant",
                    plugin_type="connector",
                    payload=self._build_homeassistant_sync_payload(
                        household_id=household.id,
                        integration_instance_id=instance.id,
                    ),
                ),
                root_dir=self.builtin_root,
            )
        health_result = run_plugin_sync_pipeline(
            self.db,
            household_id=household.id,
            request=PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": member.id},
            ),
            root_dir=self.builtin_root,
        )
        self.db.commit()

        self.assertEqual("success", smart_home_result.run.status)
        self.assertEqual("success", health_result.run.status)
        self.assertEqual(3, smart_home_result.run.raw_record_count)
        self.assertEqual(3, smart_home_result.run.memory_card_count)
        self.assertEqual(3, health_result.run.raw_record_count)
        self.assertEqual(3, health_result.run.memory_card_count)

        smart_home_raw_stmt = select(PluginRawRecord).where(PluginRawRecord.run_id == smart_home_result.run.id)
        health_raw_stmt = select(PluginRawRecord).where(PluginRawRecord.run_id == health_result.run.id)
        smart_home_raw_rows = list(self.db.scalars(smart_home_raw_stmt).all())
        health_raw_rows = list(self.db.scalars(health_raw_stmt).all())
        self.assertEqual(3, len(smart_home_raw_rows))
        self.assertEqual(3, len(health_raw_rows))

        cards, total = list_memory_cards(
            self.db,
            household_id=household.id,
            page=1,
            page_size=20,
            memory_type="observation",
        )
        self.assertEqual(6, total)
        self.assertEqual(
            {
                "device_power_state",
                "room_temperature",
                "room_humidity",
                "daily_steps",
                "sleep_duration",
                "heart_rate",
            },
            {card.content["category"] for card in cards if isinstance(card.content, dict)},
        )
        self.assertEqual(
            {"homeassistant", "health-basic-reader"},
            {card.source_plugin_id for card in cards},
        )

        audit_stmt = select(AuditLog).where(AuditLog.target_type == "plugin_run")
        audit_rows = list(self.db.scalars(audit_stmt).all())
        self.assertEqual(2, len(audit_rows))
        self.assertTrue(all(row.result == "success" for row in audit_rows))

    def _seed_homeassistant_config(self, *, household_id: str):
        return seed_homeassistant_integration_instance(
            self.db,
            household_id=household_id,
        )

    def _build_homeassistant_sync_payload(self, *, household_id: str, integration_instance_id: str) -> dict:
        return {
            **build_homeassistant_sync_payload(
                household_id=household_id,
                integration_instance_id=integration_instance_id,
                sync_scope="device_sync",
            ),
            "_system_context": {
                "device_integration": {
                    "database_url": settings.database_url,
                }
            },
        }

    def test_run_plugin_sync_pipeline_supports_third_party_runner_for_memory_ingestor(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Third Party Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="濡堝", role="adult"),
        )
        self.db.flush()

        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_third_party_sync_plugin(Path(tempdir), plugin_id="third-party-sync-plugin")

            result = run_plugin_sync_pipeline(
                self.db,
                household_id=household.id,
                request=PluginExecutionRequest(
                    plugin_id="third-party-sync-plugin",
                    plugin_type="connector",
                    payload={"member_id": member.id},
                ),
                root_dir=plugin_root,
                source_type="third_party",
                runner_config=PluginRunnerConfig(
                    plugin_root=str(plugin_root),
                    python_path=sys.executable,
                    working_dir=str(plugin_root),
                    timeout_seconds=10,
                ),
            )
            self.db.commit()

        self.assertEqual("success", result.run.status)
        self.assertEqual("subprocess_runner", result.execution.execution_backend)
        self.assertEqual(1, result.run.raw_record_count)
        self.assertEqual(1, result.run.memory_card_count)
        self.assertEqual(1, len(result.written_memory_cards))
        self.assertEqual("daily_steps", result.written_memory_cards[0]["content"]["category"])

    def test_run_plugin_sync_pipeline_stops_when_household_override_disables_plugin(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Disabled Third Party Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="濡堝", role="adult"),
        )
        self.db.flush()

        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_third_party_sync_plugin(Path(tempdir), plugin_id="third-party-sync-plugin")
            register_plugin_mount(
                self.db,
                household_id=household.id,
                payload=PluginMountCreate(
                    source_type="third_party",
                    plugin_root=str(plugin_root),
                    python_path=sys.executable,
                    working_dir=str(plugin_root),
                    timeout_seconds=10,
                ),
            )
            set_household_plugin_enabled(
                self.db,
                household_id=household.id,
                plugin_id="third-party-sync-plugin",
                payload=PluginStateUpdateRequest(enabled=False),
                updated_by="tester",
            )

            result = run_plugin_sync_pipeline(
                self.db,
                household_id=household.id,
                request=PluginExecutionRequest(
                    plugin_id="third-party-sync-plugin",
                    plugin_type="connector",
                    payload={"member_id": member.id},
                ),
            )

        self.assertEqual("failed", result.run.status)
        self.assertEqual("plugin_disabled", result.run.error_code)
        self.assertIn("当前家庭", result.run.error_message or "")
        self.assertIn("停用", result.run.error_message or "")

    def _create_third_party_sync_plugin(self, root: Path, *, plugin_id: str) -> Path:
        plugin_root = root / plugin_id
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "第三方同步插件",
                    "version": "0.1.0",
                    "types": ["connector", "memory-ingestor"],
                    "permissions": ["health.read", "memory.write.observation"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                    "entrypoints": {
                        "connector": "plugin.connector.sync",
                        "memory_ingestor": "plugin.ingestor.transform",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package_dir / "connector.py").write_text(
            "def sync(payload=None):\n"
            "    data = payload or {}\n"
            "    member_id = data.get('member_id', 'member-001')\n"
            "    return {\n"
            "        'source': 'third-party-sync-plugin',\n"
            "        'records': [\n"
            "            {\n"
            "                'record_type': 'steps',\n"
            "                'member_id': member_id,\n"
            "                'value': 1234,\n"
            "                'unit': 'count',\n"
            "                'captured_at': '2026-03-13T07:30:00Z'\n"
            "            }\n"
            "        ]\n"
            "    }\n",
            encoding="utf-8",
        )
        (package_dir / "ingestor.py").write_text(
            "def transform(payload=None):\n"
            "    data = payload or {}\n"
            "    records = data.get('records', [])\n"
            "    if not records:\n"
            "        return []\n"
            "    record = records[0]\n"
            "    source = record.get('payload', {})\n"
            "    return [\n"
            "        {\n"
            "            'type': 'Observation',\n"
            "            'subject_type': 'Person',\n"
            "            'subject_id': source.get('member_id'),\n"
            "            'category': 'daily_steps',\n"
            "            'value': source.get('value'),\n"
            "            'unit': source.get('unit'),\n"
            "            'observed_at': record.get('captured_at'),\n"
            "            'source_plugin_id': 'third-party-sync-plugin',\n"
            "            'source_record_ref': record.get('id')\n"
            "        }\n"
            "    ]\n",
            encoding="utf-8",
        )
        return plugin_root


if __name__ == "__main__":
    unittest.main()

