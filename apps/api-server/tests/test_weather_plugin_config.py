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

    def test_switch_provider_requires_matching_api_key(self) -> None:
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
        self.assertEqual(400, response.status_code)
        payload = response.json()["detail"]
        self.assertEqual("plugin_config_validation_failed", payload["error_code"])
        self.assertEqual("切换到 OpenWeather 时必须填写 API Key", payload["field_errors"]["openweather_api_key"])

    def test_switch_provider_with_key_can_be_saved(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
