import tempfile
import unittest
from pathlib import Path

from sqlalchemy import text
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.core.config import settings
from app.modules.household.models import Household
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.storage_cleanup import iter_household_plugin_storage_paths


class HouseholdPluginStorageCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_plugin_storage_root = settings.plugin_storage_root
        self._previous_marketplace_install_root = settings.plugin_marketplace_install_root
        settings.plugin_storage_root = self._tempdir.name
        settings.plugin_marketplace_install_root = self._tempdir.name

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()
        self._align_household_schema_for_current_model()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        settings.plugin_storage_root = self._previous_plugin_storage_root
        settings.plugin_marketplace_install_root = self._previous_marketplace_install_root
        self._tempdir.cleanup()

    def test_commit_delete_household_cleans_plugin_storage_directories(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="删除清理家庭", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.commit()

        tracked_paths = self._create_household_plugin_dirs(household.id)
        self.assertTrue(all(path.exists() for path in tracked_paths))

        self.db.delete(household)
        self.db.commit()

        self.assertTrue(all(not path.exists() for path in tracked_paths))
        self.assertIsNone(self.db.scalar(select(Household).where(Household.id == household.id)))

    def test_rollback_delete_household_keeps_plugin_storage_directories(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="回滚保留家庭", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.commit()

        tracked_paths = self._create_household_plugin_dirs(household.id)
        self.assertTrue(all(path.exists() for path in tracked_paths))

        self.db.delete(household)
        self.db.flush()
        self.db.rollback()
        self.db.commit()

        self.assertTrue(all(path.exists() for path in tracked_paths))
        self.assertIsNotNone(self.db.scalar(select(Household).where(Household.id == household.id)))

    def _create_household_plugin_dirs(self, household_id: str) -> tuple[Path, ...]:
        tracked_paths = iter_household_plugin_storage_paths(household_id)
        for path in tracked_paths:
            path.mkdir(parents=True, exist_ok=True)
            (path / "sentinel.txt").write_text("keep me", encoding="utf-8")
        return tracked_paths

    def _align_household_schema_for_current_model(self) -> None:
        # 当前仓库里 Household ORM 比迁移多了坐标字段。
        # 这里补齐测试库列，避免这次回归被无关漂移噪音打断。
        self.db.execute(
            text(
                """
                ALTER TABLE households
                ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION,
                ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION,
                ADD COLUMN IF NOT EXISTS coordinate_source VARCHAR(32),
                ADD COLUMN IF NOT EXISTS coordinate_precision VARCHAR(32),
                ADD COLUMN IF NOT EXISTS coordinate_updated_at TEXT
                """
            )
        )
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
