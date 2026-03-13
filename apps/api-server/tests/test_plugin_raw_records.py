import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.service import execute_plugin, list_saved_plugin_raw_records, save_plugin_raw_records


class PluginRawRecordTests(unittest.TestCase):
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

    def test_save_plugin_raw_records_persists_connector_output(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Plugin Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        execution_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": "mom"},
            ),
            root_dir=self.builtin_root,
        )

        self.assertTrue(execution_result.success)
        assert isinstance(execution_result.output, dict)

        saved_rows = save_plugin_raw_records(
            self.db,
            household_id=household.id,
            execution_result=execution_result,
            raw_records=execution_result.output.get("records", []),
        )
        self.db.commit()

        self.assertEqual(2, len(saved_rows))
        self.assertTrue(all(row.plugin_id == "health-basic-reader" for row in saved_rows))
        self.assertTrue(all(row.run_id == execution_result.run_id for row in saved_rows))

        listed_rows = list_saved_plugin_raw_records(
            self.db,
            household_id=household.id,
            plugin_id="health-basic-reader",
            run_id=execution_result.run_id,
        )
        self.assertEqual(2, len(listed_rows))
        self.assertEqual({"steps", "sleep"}, {row.record_type for row in listed_rows})


if __name__ == "__main__":
    unittest.main()
