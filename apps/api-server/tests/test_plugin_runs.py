import json
import tempfile
import unittest
from pathlib import Path

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
from app.modules.plugin.service import run_plugin_sync_pipeline


class PluginRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        self.builtin_root = Path(__file__).resolve().parents[1] / "app" / "plugins" / "builtin"

        db_path = Path(self._tempdir.name) / "test.db"
        settings.database_url = f"sqlite:///{db_path}"

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(settings.database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db: Session = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_run_plugin_sync_pipeline_records_success_and_audit(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Run Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="妈妈", role="adult"),
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
        self.assertEqual("plugin_execution_failed", result.run.error_code)

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
            MemberCreate(household_id=household.id, name="妈妈", role="adult"),
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
        self.assertEqual("plugin_execution_failed", failed_result.run.error_code)

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
        self.db.flush()

        result = run_plugin_sync_pipeline(
            self.db,
            household_id=household.id,
            request=PluginExecutionRequest(
                plugin_id="homeassistant-device-sync",
                plugin_type="connector",
                payload={"room_id": "living-room"},
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
            MemberCreate(household_id=household.id, name="妈妈", role="adult"),
        )
        self.db.flush()

        smart_home_result = run_plugin_sync_pipeline(
            self.db,
            household_id=household.id,
            request=PluginExecutionRequest(
                plugin_id="homeassistant-device-sync",
                plugin_type="connector",
                payload={"room_id": "living-room"},
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
            {"homeassistant-device-sync", "health-basic-reader"},
            {card.source_plugin_id for card in cards},
        )

        audit_stmt = select(AuditLog).where(AuditLog.target_type == "plugin_run")
        audit_rows = list(self.db.scalars(audit_stmt).all())
        self.assertEqual(2, len(audit_rows))
        self.assertTrue(all(row.result == "success" for row in audit_rows))


if __name__ == "__main__":
    unittest.main()
