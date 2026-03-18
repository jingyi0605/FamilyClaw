import unittest

from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.modules.region.providers import BUILTIN_CN_MAINLAND_PROVIDER, CnMainlandRegionProvider, region_provider_registry
from app.modules.region.schemas import RegionCatalogImportItem
from app.modules.region.service import import_region_catalog
from tests.test_db_support import PostgresTestDatabase


class RegionProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()
        self._original_builtin_provider = region_provider_registry.get(BUILTIN_CN_MAINLAND_PROVIDER)
        region_provider_registry.register(CnMainlandRegionProvider())

        import_region_catalog(
            self.db,
            items=[
                RegionCatalogImportItem(
                    region_code="110000",
                    parent_region_code=None,
                    admin_level="province",
                    name="Beijing",
                    full_name="Beijing",
                    path_codes=["110000"],
                    path_names=["Beijing"],
                ),
                RegionCatalogImportItem(
                    region_code="110100",
                    parent_region_code="110000",
                    admin_level="city",
                    name="Beijing City",
                    full_name="Beijing / Beijing City",
                    path_codes=["110000", "110100"],
                    path_names=["Beijing", "Beijing City"],
                ),
                RegionCatalogImportItem(
                    region_code="110105",
                    parent_region_code="110100",
                    admin_level="district",
                    name="Chaoyang",
                    full_name="Beijing / Beijing City / Chaoyang",
                    path_codes=["110000", "110100", "110105"],
                    path_names=["Beijing", "Beijing City", "Chaoyang"],
                    latitude=39.9219,
                    longitude=116.4436,
                    coordinate_precision="district",
                    coordinate_source="provider_builtin",
                    coordinate_updated_at="2026-03-18T00:00:00Z",
                ),
            ],
            source_version="provider-test-v1",
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        if self._original_builtin_provider is not None:
            region_provider_registry.register(self._original_builtin_provider)
        self._db_helper.close()

    def test_builtin_provider_can_read_region_coordinate_contract(self) -> None:
        provider = region_provider_registry.get(BUILTIN_CN_MAINLAND_PROVIDER)
        self.assertIsNotNone(provider)
        assert provider is not None

        provinces = provider.list_children(self.db, parent_region_code=None, admin_level="province")
        district = provider.resolve(self.db, region_code="110105")

        self.assertEqual(["Beijing"], [item.name for item in provinces])
        assert district is not None
        self.assertIsNone(provinces[0].latitude)
        self.assertEqual(39.9219, district.latitude)
        self.assertEqual(116.4436, district.longitude)
        self.assertEqual("district", district.coordinate_precision)
        self.assertEqual("provider_builtin", district.coordinate_source)

        snapshot = provider.build_snapshot(district)
        representative_coordinate = snapshot.get("representative_coordinate")

        self.assertIsInstance(representative_coordinate, dict)
        assert isinstance(representative_coordinate, dict)
        self.assertEqual(39.9219, representative_coordinate["latitude"])
        self.assertEqual(116.4436, representative_coordinate["longitude"])


if __name__ == "__main__":
    unittest.main()
