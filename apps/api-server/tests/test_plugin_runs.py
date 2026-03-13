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
        self.db.flush()

        result = run_plugin_sync_pipeline(
            self.db,
            household_id=household.id,
            request=PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": "mom"},
            ),
            root_dir=self.builtin_root,
        )
        self.db.commit()

        self.assertEqual("success", result.run.status)
        self.assertEqual(2, result.run.raw_record_count)
        self.assertEqual(2, result.run.memory_card_count)

        run_row = self.db.get(PluginRun, result.run.id)
        assert run_row is not None
        self.assertEqual("success", run_row.status)

        audit_stmt = select(AuditLog).where(AuditLog.target_type == "plugin_run", AuditLog.target_id == result.run.id)
        audit_row = self.db.scalar(audit_stmt)
        assert audit_row is not None
        self.assertEqual("success", audit_row.result)
        details = json.loads(audit_row.details or "{}")
        self.assertEqual(2, details["raw_record_count"])
        self.assertEqual(2, details["memory_card_count"])

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
        self.db.flush()

        success_result = run_plugin_sync_pipeline(
            self.db,
            household_id=household.id,
            request=PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": "mom"},
            ),
            root_dir=self.builtin_root,
        )
        self.db.commit()

        self.assertEqual("success", success_result.run.status)
        self.assertEqual(2, success_result.run.raw_record_count)
        self.assertEqual(2, success_result.run.memory_card_count)

        raw_stmt = select(PluginRawRecord).where(PluginRawRecord.run_id == success_result.run.id)
        raw_rows = list(self.db.scalars(raw_stmt).all())
        self.assertEqual(2, len(raw_rows))

        cards, total = list_memory_cards(
            self.db,
            household_id=household.id,
            page=1,
            page_size=20,
            memory_type="observation",
        )
        self.assertEqual(2, total)
        self.assertTrue(all(card.source_raw_record_id for card in cards))

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


if __name__ == "__main__":
    unittest.main()
