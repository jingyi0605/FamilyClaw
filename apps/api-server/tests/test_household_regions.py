import unittest

from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext
from app.api.v1.endpoints.households import (
    create_household_endpoint,
    update_household_coordinate_endpoint,
)
from app.modules.household.schemas import HouseholdCoordinateUpsert, HouseholdCreate
from app.modules.household.service import build_household_read, create_household, get_household_or_404
from app.modules.region.providers import BUILTIN_CN_MAINLAND_PROVIDER, CnMainlandRegionProvider, region_provider_registry
from app.modules.region.schemas import RegionCatalogImportItem, RegionSelection
from app.modules.region.service import import_region_catalog, resolve_household_region_context
from tests.test_db_support import PostgresTestDatabase


class HouseholdRegionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.engine = self._db_helper.engine
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
                RegionCatalogImportItem(
                    region_code="110108",
                    parent_region_code="110100",
                    admin_level="district",
                    name="Haidian",
                    full_name="Beijing / Beijing City / Haidian",
                    path_codes=["110000", "110100", "110108"],
                    path_names=["Beijing", "Beijing City", "Haidian"],
                    latitude=39.9593,
                    longitude=116.2985,
                    coordinate_precision="district",
                    coordinate_source="provider_builtin",
                    coordinate_updated_at="2026-03-18T00:00:00Z",
                ),
            ],
            source_version="household-test-v1",
        )
        self.db.commit()

        self.admin_actor = ActorContext(
            role="admin",
            actor_type="admin",
            actor_id="admin-001",
            account_type="system",
            is_authenticated=True,
        )

    def tearDown(self) -> None:
        self.db.close()
        if self._original_builtin_provider is not None:
            region_provider_registry.register(self._original_builtin_provider)
        self._db_helper.close()

    def test_migration_adds_coordinate_columns(self) -> None:
        inspector = inspect(self.engine)
        household_columns = {column["name"] for column in inspector.get_columns("households")}
        region_columns = {column["name"] for column in inspector.get_columns("region_nodes")}

        self.assertTrue(
            {"latitude", "longitude", "coordinate_source", "coordinate_precision", "coordinate_updated_at"}.issubset(
                household_columns
            )
        )
        self.assertTrue(
            {"latitude", "longitude", "coordinate_source", "coordinate_precision", "coordinate_updated_at"}.issubset(
                region_columns
            )
        )

    def test_region_binding_returns_region_representative_coordinate(self) -> None:
        created = create_household_endpoint(
            HouseholdCreate(
                name="Region Household",
                timezone="Asia/Shanghai",
                locale="zh-CN",
                region_selection=RegionSelection(
                    provider_code="builtin.cn-mainland",
                    country_code="CN",
                    region_code="110105",
                ),
            ),
            db=self.db,
            actor=self.admin_actor,
        )

        self.assertEqual("configured", created.region.status)
        self.assertTrue(created.region.coordinate.available)
        self.assertEqual("region_representative", created.region.coordinate.source_type)
        self.assertEqual(39.9219, created.region.coordinate.latitude)
        self.assertEqual("Chaoyang", created.region.district.name if created.region.district else None)

    def test_confirmed_household_coordinate_overrides_region_coordinate(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(
                name="Exact Coordinate Household",
                timezone="Asia/Shanghai",
                locale="zh-CN",
                region_selection=RegionSelection(
                    provider_code="builtin.cn-mainland",
                    country_code="CN",
                    region_code="110105",
                ),
            ),
        )
        self.db.commit()

        update_household_coordinate_endpoint(
            household.id,
            HouseholdCoordinateUpsert(
                latitude=39.9001,
                longitude=116.4012,
                coordinate_source="manual_browser",
                confirmed=True,
            ),
            db=self.db,
            actor=self.admin_actor,
        )

        refreshed = build_household_read(self.db, get_household_or_404(self.db, household.id))

        self.assertIsNotNone(refreshed.coordinate_override)
        assert refreshed.coordinate_override is not None
        self.assertEqual("manual_browser", refreshed.coordinate_override.coordinate_source)
        self.assertEqual("household_exact", refreshed.region.coordinate.source_type)
        self.assertEqual(39.9001, refreshed.region.coordinate.latitude)
        self.assertEqual("110105", refreshed.region.coordinate.region_code)

    def test_unconfirmed_household_coordinate_is_rejected(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(
                name="Pending Coordinate Household",
                timezone="Asia/Shanghai",
                locale="zh-CN",
            ),
        )
        self.db.commit()

        with self.assertRaises(HTTPException) as context:
            update_household_coordinate_endpoint(
                household.id,
                HouseholdCoordinateUpsert(
                    latitude=39.9001,
                    longitude=116.4012,
                    coordinate_source="manual_browser",
                    confirmed=False,
                ),
                db=self.db,
                actor=self.admin_actor,
            )

        self.assertEqual("coordinate_unconfirmed", context.exception.detail["error_code"])

    def test_legacy_household_returns_unconfigured_and_unavailable_coordinate(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(
                name="Legacy Household",
                city="Legacy City",
                timezone="Asia/Shanghai",
                locale="zh-CN",
            ),
        )
        self.db.commit()

        context = resolve_household_region_context(self.db, household.id)

        self.assertEqual("unconfigured", context.status)
        self.assertEqual("household_region_unconfigured", context.error_code)
        self.assertEqual("unavailable", context.coordinate.source_type)
        self.assertFalse(context.coordinate.available)


if __name__ == "__main__":
    unittest.main()
