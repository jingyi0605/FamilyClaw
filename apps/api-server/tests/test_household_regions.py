import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext
from app.api.v1.endpoints.households import (
    create_household_endpoint,
    get_household_endpoint,
    update_household_endpoint,
)
from app.api.v1.endpoints.regions import list_region_catalog_endpoint, search_region_catalog_endpoint
from app.core.config import settings
from app.modules.household.schemas import HouseholdCreate, HouseholdUpdate
from app.modules.household.service import create_household, get_household_setup_status
from app.modules.region.schemas import RegionCatalogImportItem, RegionSelection
from app.modules.region.service import import_region_catalog, resolve_household_region_context


class HouseholdRegionTests(unittest.TestCase):
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
                RegionCatalogImportItem(
                    region_code="110108",
                    parent_region_code="110100",
                    admin_level="district",
                    name="娴锋穩鍖?,
                    full_name="鍖椾含甯?/ 鍖椾含甯?/ 娴锋穩鍖?,
                    path_codes=["110000", "110100", "110108"],
                    path_names=["鍖椾含甯?, "鍖椾含甯?, "娴锋穩鍖?],
                ),
            ],
            source_version="test-v1",
        )
        self.db.commit()
        self.admin_actor = ActorContext(
            role="admin",
            actor_type="admin",
            actor_id="admin-001",
            account_type="system",
            is_authenticated=True,
        )
        self.member_actor = ActorContext(
            role="member",
            actor_type="member",
            actor_id="member-001",
            account_type="household",
            household_id="placeholder",
            is_authenticated=True,
        )

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_region_tables_exist(self) -> None:
        inspector = inspect(self.engine)
        table_names = set(inspector.get_table_names())
        self.assertTrue({"region_nodes", "household_regions"}.issubset(table_names))

    def test_region_catalog_endpoints_return_expected_nodes(self) -> None:
        provinces = list_region_catalog_endpoint(
            provider_code="builtin.cn-mainland",
            country_code="CN",
            parent_region_code=None,
            admin_level="province",
            db=self.db,
            _actor=self.member_actor,
        )
        districts = search_region_catalog_endpoint(
            provider_code="builtin.cn-mainland",
            country_code="CN",
            keyword="娴锋穩",
            admin_level="district",
            parent_region_code=None,
            db=self.db,
            _actor=self.member_actor,
        )

        self.assertEqual(["鍖椾含甯?], [item.name for item in provinces])
        self.assertEqual(["娴锋穩鍖?], [item.name for item in districts])

    def test_household_endpoints_return_structured_region_and_city_projection(self) -> None:
        created = create_household_endpoint(
            HouseholdCreate(
                name="鍦板尯瀹跺涵",
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
        self.member_actor = ActorContext(
            role="member",
            actor_type="member",
            actor_id="member-001",
            account_type="household",
            household_id=created.id,
            is_authenticated=True,
        )
        fetched = get_household_endpoint(created.id, db=self.db, actor=self.member_actor)

        self.assertEqual("鍖椾含甯?鏈濋槼鍖?, created.city)
        self.assertEqual("configured", created.region.status)
        self.assertEqual("110105", created.region.region_code)
        self.assertEqual("鏈濋槼鍖?, fetched.region.district.name if fetched.region.district else None)

    def test_update_household_region_changes_projection(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(
                name="鍙洿鏂板搴?,
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

        updated = update_household_endpoint(
            household.id,
            HouseholdUpdate(
                region_selection=RegionSelection(
                    provider_code="builtin.cn-mainland",
                    country_code="CN",
                    region_code="110108",
                )
            ),
            db=self.db,
            actor=self.admin_actor,
        )

        self.assertEqual("鍖椾含甯?娴锋穩鍖?, updated.city)
        self.assertEqual("110108", updated.region.region_code)
        self.assertEqual("娴锋穩鍖?, updated.region.district.name if updated.region.district else None)

    def test_new_household_setup_requires_formal_region(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="鏃у叆鍙ｅ搴?, city="鍖椾含", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.commit()

        before_status = get_household_setup_status(self.db, household.id)
        self.assertEqual("family_profile", before_status.current_step)

        update_household_endpoint(
            household.id,
            HouseholdUpdate(
                region_selection=RegionSelection(
                    provider_code="builtin.cn-mainland",
                    country_code="CN",
                    region_code="110105",
                )
            ),
            db=self.db,
            actor=self.admin_actor,
        )
        after_status = get_household_setup_status(self.db, household.id)

        self.assertEqual("first_member", after_status.current_step)

    def test_resolve_household_region_context_returns_unconfigured_for_legacy_household(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="鏃у搴?, city="鍖椾含", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.commit()

        context = resolve_household_region_context(self.db, household.id)

        self.assertEqual("unconfigured", context.status)
        self.assertEqual("household_region_unconfigured", context.error_code)


if __name__ == "__main__":
    unittest.main()

