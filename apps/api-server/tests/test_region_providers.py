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

        db_path = Path(self._tempdir.name) / "test.db"
        settings.database_url = f"sqlite:///{db_path}"

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(settings.database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db: Session = self.SessionLocal()
        import_region_catalog(
            self.db,
            items=[
                RegionCatalogImportItem(
                    region_code="110000",
                    parent_region_code=None,
                    admin_level="province",
                    name="北京市",
                    full_name="北京市",
                    path_codes=["110000"],
                    path_names=["北京市"],
                ),
                RegionCatalogImportItem(
                    region_code="110100",
                    parent_region_code="110000",
                    admin_level="city",
                    name="北京市",
                    full_name="北京市 / 北京市",
                    path_codes=["110000", "110100"],
                    path_names=["北京市", "北京市"],
                ),
                RegionCatalogImportItem(
                    region_code="110105",
                    parent_region_code="110100",
                    admin_level="district",
                    name="朝阳区",
                    full_name="北京市 / 北京市 / 朝阳区",
                    path_codes=["110000", "110100", "110105"],
                    path_names=["北京市", "北京市", "朝阳区"],
                ),
            ],
            source_version="provider-test-v1",
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
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
        matches = provider.search(self.db, keyword="朝阳", admin_level="district")
        district = provider.resolve(self.db, region_code="110105")

        self.assertEqual(["北京市"], [item.name for item in provinces])
        self.assertEqual(["朝阳区"], [item.name for item in matches])
        assert district is not None

        snapshot = provider.build_snapshot(district)

        self.assertEqual("110105", snapshot["region_code"])
        self.assertEqual("北京市 朝阳区", snapshot["display_name"])
        self.assertEqual("北京市", snapshot["province"]["name"])
        self.assertEqual("朝阳区", snapshot["district"]["name"])


if __name__ == "__main__":
    unittest.main()
