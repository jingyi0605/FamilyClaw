import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, require_admin_actor, require_bound_member_actor
from app.api.v1.endpoints.integrations import router as integrations_router
from app.core.config import settings
from app.db.session import get_db
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.integration import service as integration_service
from app.modules.integration.models import IntegrationInstance
from app.modules.plugin.schemas import PluginStateUpdateRequest
from app.modules.plugin.startup_sync_service import sync_persisted_plugins_on_startup
from app.modules.plugin.service import get_household_plugin, set_household_plugin_enabled
from official_weather.schemas import WeatherForecastSummary, WeatherSnapshot
from tests.weather_test_utils import (
    build_weather_test_region_provider,
    force_weather_plugin_in_process,
    register_region_provider,
)


class _FakeWeatherProvider:
    def __init__(self, snapshot: WeatherSnapshot) -> None:
        self._snapshot = snapshot

    def fetch_weather(self, *, coordinate, config):  # noqa: ANN001
        return self._snapshot


def _build_snapshot(*, source_type: str = "met_norway", updated_at: str = "2026-03-18T03:05:00Z") -> WeatherSnapshot:
    return WeatherSnapshot(
        source_type=source_type,  # type: ignore[arg-type]
        condition_code="cloudy" if source_type == "met_norway" else "weatherapi_1006",
        condition_text="多云" if source_type == "met_norway" else "Cloudy",
        temperature=23.5,
        humidity=68.0,
        wind_speed=4.2,
        wind_direction=95.0,
        pressure=1010.0,
        cloud_cover=80.0,
        precipitation_next_1h=0.0,
        forecast_6h=WeatherForecastSummary(
            condition_code="rain" if source_type == "met_norway" else "weatherapi_1183",
            condition_text="小雨" if source_type == "met_norway" else "Light rain",
            min_temperature=22.0,
            max_temperature=26.0,
        ),
        updated_at=updated_at,
        is_stale=False,
    )


class WeatherIntegrationsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.SessionLocal = self._db_helper.SessionLocal
        self._region_provider = build_weather_test_region_provider()
        self._region_provider_context = register_region_provider(self._region_provider)
        self._region_provider_context.__enter__()

        app = FastAPI()
        app.include_router(integrations_router, prefix=settings.api_v1_prefix)

        def _override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        def _build_actor() -> ActorContext:
            return ActorContext(
                role="admin",
                actor_type="admin",
                actor_id="admin-001",
                account_id="admin-account-001",
                account_type="member",
                account_status="active",
                username="admin",
                household_id=getattr(self, "household_id", None),
                member_id="member-admin-001",
                is_authenticated=True,
            )

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[require_admin_actor] = _build_actor
        app.dependency_overrides[require_bound_member_actor] = _build_actor
        self.client = TestClient(app)

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="Weather API Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            household.latitude = 31.2304
            household.longitude = 121.4737
            household.coordinate_source = "manual_admin"
            household.coordinate_precision = "point"
            household.coordinate_updated_at = "2026-03-18T03:00:00Z"
            db.add(household)
            db.flush()
            self.household_id = household.id
            sync_persisted_plugins_on_startup(db)
            db.flush()

            with patch(
                "official_weather.service.get_weather_provider",
                return_value=_FakeWeatherProvider(_build_snapshot()),
            ):
                set_household_plugin_enabled(
                    db,
                    household_id=self.household_id,
                    plugin_id="official-weather",
                    payload=PluginStateUpdateRequest(enabled=True),
                    updated_by="test-suite",
                )
            db.commit()

    def tearDown(self) -> None:
        self.client.close()
        self._region_provider_context.__exit__(None, None, None)
        self._db_helper.close()

    def test_list_create_and_sync_region_weather_instance(self) -> None:
        list_response = self.client.get(
            f"{settings.api_v1_prefix}/integrations/instances",
            params={"household_id": self.household_id},
        )
        self.assertEqual(200, list_response.status_code)
        initial_items = list_response.json()["items"]
        self.assertEqual(0, len(initial_items))

        create_response = self.client.post(
            f"{settings.api_v1_prefix}/integrations/instances",
            json={
                "household_id": self.household_id,
                "plugin_id": "official-weather",
                "display_name": "上海天气",
                "config": {
                    "binding_type": "region_node",
                    "provider_code": self._region_provider.provider_code,
                    "province_code": "310000",
                    "city_code": "310100",
                    "district_code": "310115",
                },
            },
        )
        self.assertEqual(201, create_response.status_code)
        created_payload = create_response.json()
        region_instance_id = created_payload["id"]
        self.assertEqual("official-weather", created_payload["plugin_id"])

        with force_weather_plugin_in_process():
            with patch(
                "official_weather.service.get_weather_provider",
                return_value=_FakeWeatherProvider(
                    _build_snapshot(source_type="weatherapi", updated_at="2026-03-18T04:00:00Z")
                ),
            ):
                candidates_response = self.client.post(
                    f"{settings.api_v1_prefix}/integrations/instances/{region_instance_id}/actions",
                    json={"action": "sync", "payload": {"sync_scope": "device_candidates"}},
                )
                self.assertEqual(200, candidates_response.status_code)
                candidates = candidates_response.json()["output"]["items"]
                self.assertEqual(1, len(candidates))
                self.assertEqual("中国 上海市", candidates[0]["name"])

                sync_response = self.client.post(
                    f"{settings.api_v1_prefix}/integrations/instances/{region_instance_id}/actions",
                    json={"action": "sync", "payload": {"sync_scope": "device_sync"}},
                )

        self.assertEqual(200, sync_response.status_code)
        sync_payload = sync_response.json()
        self.assertEqual("sync", sync_payload["action"])
        self.assertEqual(1, len(sync_payload["output"]["summary"]["devices"]))
        self.assertTrue(sync_payload["output"]["instance_status"]["success"])

        resources_response = self.client.get(
            f"{settings.api_v1_prefix}/integrations/resources",
            params={"household_id": self.household_id, "resource_type": "device"},
        )
        self.assertEqual(200, resources_response.status_code)
        resources = resources_response.json()["items"]
        self.assertEqual(1, len(resources))

    def test_sync_region_instance_without_coordinate_is_rejected(self) -> None:
        create_response = self.client.post(
            f"{settings.api_v1_prefix}/integrations/instances",
            json={
                "household_id": self.household_id,
                "plugin_id": "official-weather",
                "display_name": "无坐标天气",
                "config": {
                    "binding_type": "region_node",
                    "provider_code": self._region_provider.provider_code,
                    "province_code": "990000",
                    "city_code": "990100",
                    "district_code": "990101",
                },
            },
        )
        self.assertEqual(201, create_response.status_code)
        instance_id = create_response.json()["id"]

        with force_weather_plugin_in_process():
            response = self.client.post(
                f"{settings.api_v1_prefix}/integrations/instances/{instance_id}/actions",
                json={"action": "sync", "payload": {"sync_scope": "device_sync"}},
            )
        self.assertEqual(200, response.status_code)
        payload = response.json()["output"]
        self.assertEqual("weather_coordinate_missing", payload["instance_status"]["error_code"])
        self.assertEqual(1, payload["summary"]["failed_entities"])

    def test_plugin_managed_sync_payload_includes_database_url_for_subprocess_plugin(self) -> None:
        create_response = self.client.post(
            f"{settings.api_v1_prefix}/integrations/instances",
            json={
                "household_id": self.household_id,
                "plugin_id": "official-weather",
                "display_name": "家庭天气",
                "config": {
                    "binding_type": "default_household",
                },
            },
        )
        self.assertEqual(201, create_response.status_code)
        instance_id = create_response.json()["id"]

        with self.SessionLocal() as db:
            instance = db.get(IntegrationInstance, instance_id)
            assert instance is not None
            plugin = get_household_plugin(
                db,
                household_id=self.household_id,
                plugin_id="official-weather",
            )
            plugin.execution_backend = "subprocess_runner"
            expected_database_url = integration_service._resolve_database_url(db)

            captured_request: dict[str, object] = {}

            def _fake_run_plugin_sync_pipeline(*args, **kwargs):
                request = kwargs.get("request")
                if request is None and len(args) >= 3:
                    request = args[2]
                captured_request["payload"] = request.payload
                return SimpleNamespace(
                    execution=SimpleNamespace(
                        output={},
                        success=True,
                        error_code=None,
                        error_message=None,
                    )
                )

            with patch(
                "app.modules.integration.service.run_plugin_sync_pipeline",
                side_effect=_fake_run_plugin_sync_pipeline,
            ):
                result = integration_service._execute_plugin_managed_sync_action(
                    db,
                    plugin=plugin,
                    instance=instance,
                    sync_scope="device_sync",
                    selected_external_ids=[],
                    options={},
                )

        self.assertEqual("sync", result.action)
        payload = captured_request["payload"]
        assert isinstance(payload, dict)
        system_context = payload["_system_context"]
        assert isinstance(system_context, dict)
        runtime_context = system_context["integration_runtime"]
        assert isinstance(runtime_context, dict)
        self.assertEqual(expected_database_url, runtime_context["database_url"])
        self.assertNotIn("db_session", runtime_context)


if __name__ == "__main__":
    unittest.main()
