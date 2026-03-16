import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.modules.region.providers import BUILTIN_CN_MAINLAND_PROVIDER, region_provider_registry
from app.modules.region.schemas import RegionCatalogImportItem
from app.modules.region.service import import_region_catalog


class RegionProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
        self.db: Session = self.SessionLocal()
        import_region_catalog(
            self.db,
            items=[
                RegionCatalogImportItem(
                    region_code="110000",
                    parent_region_code=None,
                    admin_level="province",
                    name="鍖椾含甯?,
                    full_name="鍖椾含甯?,
                    path_codes=["110000"],
                    path_names=["鍖椾含甯?],
                ),
                RegionCatalogImportItem(
                    region_code="110100",
                    parent_region_code="110000",
                    admin_level="city",
                    name="鍖椾含甯?,
                    full_name="鍖椾含甯?/ 鍖椾含甯?,
                    path_codes=["110000", "110100"],
                    path_names=["鍖椾含甯?, "鍖椾含甯?],
                ),
                RegionCatalogImportItem(
                    region_code="110105",
                    parent_region_code="110100",
                    admin_level="district",
                    name="鏈濋槼鍖?,
                    full_name="鍖椾含甯?/ 鍖椾含甯?/ 鏈濋槼鍖?,
                    path_codes=["110000", "110100", "110105"],
                    path_names=["鍖椾含甯?, "鍖椾含甯?, "鏈濋槼鍖?],
                ),
            ],
            source_version="provider-test-v1",
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_builtin_cn_provider_registered(self) -> None:
        provider = region_provider_registry.get(BUILTIN_CN_MAINLAND_PROVIDER)

        self.assertIsNotNone(provider)
        assert provider is not None
        self.assertEqual("CN", provider.country_code)

    def test_builtin_cn_provider_contract(self) -> None:
        provider = region_provider_registry.get(BUILTIN_CN_MAINLAND_PROVIDER)
        assert provider is not None

        provinces = provider.list_children(self.db, parent_region_code=None, admin_level="province")
        matches = provider.search(self.db, keyword="鏈濋槼", admin_level="district")
        district = provider.resolve(self.db, region_code="110105")

        self.assertEqual(["鍖椾含甯?], [item.name for item in provinces])
        self.assertEqual(["鏈濋槼鍖?], [item.name for item in matches])
        assert district is not None

        snapshot = provider.build_snapshot(district)

        self.assertEqual("110105", snapshot["region_code"])
        self.assertEqual("鍖椾含甯?鏈濋槼鍖?, snapshot["display_name"])
        self.assertEqual("鍖椾含甯?, snapshot["province"]["name"])
        self.assertEqual("鏈濋槼鍖?, snapshot["district"]["name"])


if __name__ == "__main__":
    unittest.main()

