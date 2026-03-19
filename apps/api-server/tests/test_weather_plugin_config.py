import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, require_admin_actor
from app.api.v1.endpoints.ai_config import router as ai_config_router
from app.core.config import settings
from app.db.session import get_db
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.startup_sync_service import sync_persisted_plugins_on_startup


class WeatherPluginConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.SessionLocal = self._db_helper.SessionLocal

        app = FastAPI()
        app.include_router(ai_config_router, prefix=settings.api_v1_prefix)

        def _override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="Weather Config Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            self.household_id = household.id
            sync_persisted_plugins_on_startup(db)
            db.commit()

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[require_admin_actor] = lambda: ActorContext(
            role="admin",
            actor_type="admin",
            actor_id="admin-001",
            account_id="admin-account-001",
            account_type="member",
            account_status="active",
            username="admin",
            household_id=self.household_id,
            member_id="member-admin-001",
            is_authenticated=True,
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self._db_helper.close()

    def test_switch_provider_without_key_can_still_be_saved(self) -> None:
        response = self.client.put(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/official-weather/config",
            json={
                "scope_type": "plugin",
                "scope_key": "default",
                "values": {
                    "provider_type": "openweather",
                },
            },
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("configured", payload["view"]["state"])
        self.assertEqual("openweather", payload["view"]["values"]["provider_type"])
        self.assertFalse(payload["view"]["secret_fields"]["openweather_api_key"]["has_value"])
        self.assertEqual({}, payload["view"]["field_errors"])

    def test_switch_provider_with_key_keeps_secret_masked(self) -> None:
        response = self.client.put(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/official-weather/config",
            json={
                "scope_type": "plugin",
                "scope_key": "default",
                "values": {
                    "provider_type": "weatherapi",
                    "weatherapi_api_key": "weatherapi-demo-key",
                },
            },
        )
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("configured", payload["view"]["state"])
        self.assertEqual("weatherapi", payload["view"]["values"]["provider_type"])
        self.assertTrue(payload["view"]["secret_fields"]["weatherapi_api_key"]["has_value"])
        self.assertEqual("******", payload["view"]["secret_fields"]["weatherapi_api_key"]["masked"])

    def test_resolve_region_binding_options_follow_provider_and_parent_selection(self) -> None:
        provider_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/official-weather/config/resolve",
            json={
                "scope_type": "integration_instance",
                "values": {
                    "binding_type": "region_node",
                },
            },
        )
        self.assertEqual(200, provider_response.status_code)
        provider_payload = provider_response.json()
        field_map = {
            field["key"]: field
            for field in provider_payload["config_spec"]["config_schema"]["fields"]
        }
        provider_options = {item["value"] for item in field_map["provider_code"]["enum_options"]}
        self.assertIn("builtin.cn-mainland", provider_options)
        self.assertEqual([], field_map["province_code"]["enum_options"])

        province_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/official-weather/config/resolve",
            json={
                "scope_type": "integration_instance",
                "values": {
                    "binding_type": "region_node",
                    "provider_code": "builtin.cn-mainland",
                },
            },
        )
        self.assertEqual(200, province_response.status_code)
        province_field_map = {
            field["key"]: field
            for field in province_response.json()["config_spec"]["config_schema"]["fields"]
        }
        province_options = {item["value"] for item in province_field_map["province_code"]["enum_options"]}
        self.assertIn("310000", province_options)
        self.assertEqual([], province_field_map["city_code"]["enum_options"])

        city_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/official-weather/config/resolve",
            json={
                "scope_type": "integration_instance",
                "values": {
                    "binding_type": "region_node",
                    "provider_code": "builtin.cn-mainland",
                    "province_code": "310000",
                },
            },
        )
        self.assertEqual(200, city_response.status_code)
        city_field_map = {
            field["key"]: field
            for field in city_response.json()["config_spec"]["config_schema"]["fields"]
        }
        city_options = {item["value"] for item in city_field_map["city_code"]["enum_options"]}
        self.assertIn("310100", city_options)
        self.assertEqual([], city_field_map["district_code"]["enum_options"])

        district_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/official-weather/config/resolve",
            json={
                "scope_type": "integration_instance",
                "values": {
                    "binding_type": "region_node",
                    "provider_code": "builtin.cn-mainland",
                    "province_code": "310000",
                    "city_code": "310100",
                },
            },
        )
        self.assertEqual(200, district_response.status_code)
        district_field_map = {
            field["key"]: field
            for field in district_response.json()["config_spec"]["config_schema"]["fields"]
        }
        district_options = {item["value"] for item in district_field_map["district_code"]["enum_options"]}
        self.assertIn("310101", district_options)


if __name__ == "__main__":
    unittest.main()
