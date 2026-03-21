import unittest
from unittest.mock import patch

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.db.utils import load_json
from app.modules.device.models import Device, DeviceBinding, DeviceEntity
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.integration.schemas import IntegrationInstanceCreateRequest
from app.modules.integration.service import create_integration_instance, sync_plugin_managed_integration_instance
from app.modules.integration.models import IntegrationInstance
from app.modules.plugin.config_service import save_plugin_config_form
from app.modules.plugin.schemas import PluginConfigUpdateRequest, PluginStateUpdateRequest
from app.modules.plugin.service import get_household_plugin, set_household_plugin_enabled
from app.modules.plugin.startup_sync_service import sync_persisted_plugins_on_startup
from official_weather.models import WeatherDeviceBinding
from official_weather.schemas import WeatherForecastSummary, WeatherSnapshot
from official_weather.service import (
    get_weather_device_binding_for_device,
    refresh_weather_device_binding,
)
from tests.weather_test_utils import force_weather_plugin_in_process


class _FakeWeatherProvider:
    def __init__(self, snapshot: WeatherSnapshot) -> None:
        self._snapshot = snapshot

    def fetch_weather(self, *, coordinate, config):  # noqa: ANN001
        return self._snapshot


class _TimeoutWeatherProvider:
    def fetch_weather(self, *, coordinate, config):  # noqa: ANN001
        from official_weather.providers import WeatherProviderError

        raise WeatherProviderError(
            "weather_provider_timeout",
            "天气源请求超时。",
            retryable=True,
        )


def _build_snapshot(*, source_type: str, updated_at: str, condition_code: str, condition_text: str) -> WeatherSnapshot:
    return WeatherSnapshot(
        source_type=source_type,  # type: ignore[arg-type]
        condition_code=condition_code,
        condition_text=condition_text,
        temperature=23.5,
        humidity=68.0,
        wind_speed=4.2,
        wind_direction=95.0,
        pressure=1010.0,
        cloud_cover=80.0,
        precipitation_next_1h=0.0,
        forecast_6h=WeatherForecastSummary(
            condition_code="rain",
            condition_text="小雨",
            min_temperature=22.0,
            max_temperature=26.0,
        ),
        updated_at=updated_at,
        is_stale=False,
    )


class WeatherDefaultDeviceTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def _sync_official_plugins(self) -> None:
        sync_persisted_plugins_on_startup(self.db)
        self.db.flush()

    def _enable_weather_plugin(self, *, household_id: str) -> None:
        set_household_plugin_enabled(
            self.db,
            household_id=household_id,
            plugin_id="official-weather",
            payload=PluginStateUpdateRequest(enabled=True),
            updated_by="test-suite",
        )
        self.db.flush()

    def _create_default_weather_instance(self, *, household_id: str) -> IntegrationInstance:
        created = create_integration_instance(
            self.db,
            payload=IntegrationInstanceCreateRequest(
                household_id=household_id,
                plugin_id="official-weather",
                display_name="家庭天气",
                config={"binding_type": "default_household"},
            ),
            updated_by="test-suite",
        )
        instance = self.db.scalar(select(IntegrationInstance).where(IntegrationInstance.id == created.id))
        assert instance is not None
        self.db.flush()
        return instance

    def _sync_weather_instance(self, *, household_id: str, instance: IntegrationInstance) -> None:
        self.db.commit()
        plugin = get_household_plugin(
            self.db,
            household_id=household_id,
            plugin_id="official-weather",
        )
        with force_weather_plugin_in_process():
            sync_plugin_managed_integration_instance(
                self.db,
                plugin=plugin,
                instance=instance,
                sync_scope="device_sync",
            )
        self.db.commit()
        self.db.rollback()

    def test_enable_plugin_does_not_create_default_instance_or_weather_device(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Weather Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        household.latitude = 31.2304
        household.longitude = 121.4737
        household.coordinate_source = "manual_admin"
        household.coordinate_precision = "point"
        household.coordinate_updated_at = "2026-03-18T03:00:00Z"
        self.db.add(household)
        self.db.flush()
        self._sync_official_plugins()

        self._enable_weather_plugin(household_id=household.id)

        instance = self.db.scalar(
            select(IntegrationInstance).where(
                IntegrationInstance.household_id == household.id,
                IntegrationInstance.plugin_id == "official-weather",
            )
        )
        self.assertIsNone(instance)

        if inspect(self.db.connection()).has_table("weather_device_bindings"):
            row = self.db.scalar(
                select(WeatherDeviceBinding).where(WeatherDeviceBinding.household_id == household.id)
            )
            self.assertIsNone(row)

    def test_create_default_instance_and_sync_weather_device(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Weather Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        household.latitude = 31.2304
        household.longitude = 121.4737
        household.coordinate_source = "manual_admin"
        household.coordinate_precision = "point"
        household.coordinate_updated_at = "2026-03-18T03:00:00Z"
        self.db.add(household)
        self.db.flush()
        self._sync_official_plugins()
        self._enable_weather_plugin(household_id=household.id)

        instance = self._create_default_weather_instance(household_id=household.id)
        snapshot = _build_snapshot(
            source_type="met_norway",
            updated_at="2026-03-18T03:05:00Z",
            condition_code="cloudy",
            condition_text="多云",
        )

        with patch(
            "official_weather.service.get_weather_provider",
            return_value=_FakeWeatherProvider(snapshot),
        ):
            self._sync_weather_instance(household_id=household.id, instance=instance)

        self.assertEqual("active", instance.status)

        row = self.db.scalar(
            select(WeatherDeviceBinding).where(WeatherDeviceBinding.household_id == household.id)
        )
        assert row is not None
        self.assertEqual("default_household", row.binding_type)
        self.assertEqual("ready", row.state)
        self.assertEqual("2026-03-18T03:05:00Z", row.last_success_at)

        device = self.db.get(Device, row.device_id)
        assert device is not None
        self.assertEqual("sensor", device.device_type)
        self.assertEqual("other", device.vendor)
        self.assertEqual("active", device.status)

        device_binding = self.db.scalar(select(DeviceBinding).where(DeviceBinding.device_id == device.id))
        assert device_binding is not None
        self.assertEqual(instance.id, device_binding.integration_instance_id)
        self.assertEqual("weather", device_binding.platform)
        self.assertEqual("official-weather", device_binding.plugin_id)

        capabilities = load_json(device_binding.capabilities)
        assert isinstance(capabilities, dict)
        self.assertEqual("weather.condition", capabilities["primary_entity_id"])
        self.assertIn("weather.temperature", capabilities["entity_ids"])
        self.assertEqual("met_norway", capabilities["metadata"]["provider_type"])
        entity_ids = list(
            self.db.scalars(
                select(DeviceEntity.entity_id)
                .where(DeviceEntity.binding_id == device_binding.id)
                .order_by(DeviceEntity.sort_order.asc(), DeviceEntity.id.asc())
            ).all()
        )
        self.assertEqual(10, len(entity_ids))
        self.assertIn("weather.condition", entity_ids)
        self.assertIn("weather.updated_at", entity_ids)

    def test_sync_default_instance_without_coordinate_marks_instance_degraded(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Pending Weather Home", city="Suzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()
        self._sync_official_plugins()
        self._enable_weather_plugin(household_id=household.id)
        instance = self._create_default_weather_instance(household_id=household.id)
        self._sync_weather_instance(household_id=household.id, instance=instance)

        self.assertEqual("degraded", instance.status)
        self.assertEqual("weather_coordinate_missing", instance.last_error_code)

        row = self.db.scalar(
            select(WeatherDeviceBinding).where(WeatherDeviceBinding.household_id == household.id)
        )
        assert row is not None
        self.assertEqual("pending_coordinate", row.state)
        self.assertEqual("weather_coordinate_missing", row.last_error_code)

    def test_refresh_weather_device_uses_cache_and_stale_fallback(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Cache Home", city="Beijing", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        household.latitude = 39.9042
        household.longitude = 116.4074
        household.coordinate_source = "manual_admin"
        household.coordinate_precision = "point"
        household.coordinate_updated_at = "2026-03-18T03:00:00Z"
        self.db.add(household)
        self.db.flush()
        self._sync_official_plugins()
        self._enable_weather_plugin(household_id=household.id)
        instance = self._create_default_weather_instance(household_id=household.id)

        snapshot = _build_snapshot(
            source_type="met_norway",
            updated_at="2026-03-18T03:05:00Z",
            condition_code="partlycloudy_day",
            condition_text="局部多云",
        )

        with patch(
            "official_weather.service.get_weather_provider",
            return_value=_FakeWeatherProvider(snapshot),
        ):
            self._sync_weather_instance(household_id=household.id, instance=instance)

        device = self.db.scalar(
            select(Device)
            .join(WeatherDeviceBinding, WeatherDeviceBinding.device_id == Device.id)
            .where(WeatherDeviceBinding.household_id == household.id)
        )
        assert device is not None
        weather_binding = get_weather_device_binding_for_device(self.db, device_id=device.id)
        assert weather_binding is not None

        with patch("official_weather.service.get_weather_provider") as provider_factory:
            refreshed = refresh_weather_device_binding(self.db, weather_binding=weather_binding, force=False)
        self.assertEqual("ready", refreshed.state)
        provider_factory.assert_not_called()

        with patch(
            "official_weather.service.get_weather_provider",
            return_value=_TimeoutWeatherProvider(),
        ):
            refreshed = refresh_weather_device_binding(self.db, weather_binding=weather_binding, force=True)

        self.assertEqual("stale", refreshed.state)
        self.assertEqual("weather_provider_timeout", refreshed.last_error_code)
        device_binding = self.db.scalar(select(DeviceBinding).where(DeviceBinding.device_id == device.id))
        assert device_binding is not None
        capabilities = load_json(device_binding.capabilities)
        assert isinstance(capabilities, dict)
        self.assertTrue(capabilities["metadata"]["is_stale"])
        self.assertEqual("weather_provider_timeout", capabilities["metadata"]["error_code"])
        condition_row = self.db.scalar(
            select(DeviceEntity).where(
                DeviceEntity.binding_id == device_binding.id,
                DeviceEntity.entity_id == "weather.condition",
            )
        )
        assert condition_row is not None
        self.assertTrue(condition_row.metadata_payload["is_stale"])
        self.assertEqual("weather_provider_timeout", condition_row.metadata_payload["error_code"])

    def test_switch_provider_keeps_same_default_device_and_entities(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Switch Provider Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        household.latitude = 31.2304
        household.longitude = 121.4737
        household.coordinate_source = "manual_admin"
        household.coordinate_precision = "point"
        household.coordinate_updated_at = "2026-03-18T03:00:00Z"
        self.db.add(household)
        self.db.flush()
        self._sync_official_plugins()
        self._enable_weather_plugin(household_id=household.id)
        instance = self._create_default_weather_instance(household_id=household.id)

        initial_snapshot = _build_snapshot(
            source_type="met_norway",
            updated_at="2026-03-18T03:05:00Z",
            condition_code="cloudy",
            condition_text="多云",
        )
        switched_snapshot = WeatherSnapshot(
            source_type="weatherapi",
            condition_code="weatherapi_1006",
            condition_text="Cloudy",
            temperature=24.1,
            humidity=63.0,
            wind_speed=5.0,
            wind_direction=120.0,
            pressure=1009.0,
            cloud_cover=70.0,
            precipitation_next_1h=0.3,
            forecast_6h=WeatherForecastSummary(
                condition_code="weatherapi_1183",
                condition_text="Light rain",
                min_temperature=23.0,
                max_temperature=27.0,
            ),
            updated_at="2026-03-18T04:00:00Z",
            is_stale=False,
        )

        with patch(
            "official_weather.service.get_weather_provider",
            return_value=_FakeWeatherProvider(initial_snapshot),
        ):
            self._sync_weather_instance(household_id=household.id, instance=instance)

        weather_binding = self.db.scalar(
            select(WeatherDeviceBinding).where(WeatherDeviceBinding.household_id == household.id)
        )
        assert weather_binding is not None
        original_device_id = weather_binding.device_id

        save_plugin_config_form(
            self.db,
            household_id=household.id,
            plugin_id="official-weather",
            payload=PluginConfigUpdateRequest(
                scope_type="plugin",
                scope_key="default",
                values={
                    "provider_type": "weatherapi",
                    "weatherapi_api_key": "weatherapi-demo-key",
                },
            ),
            updated_by="test-suite",
        )

        with patch(
            "official_weather.service.get_weather_provider",
            return_value=_FakeWeatherProvider(switched_snapshot),
        ):
            refreshed = refresh_weather_device_binding(self.db, weather_binding=weather_binding, force=True)

        self.assertEqual(original_device_id, refreshed.device_id)
        self.assertEqual("ready", refreshed.state)
        self.assertEqual("2026-03-18T04:00:00Z", refreshed.last_success_at)
        device_binding = self.db.scalar(select(DeviceBinding).where(DeviceBinding.device_id == original_device_id))
        assert device_binding is not None
        capabilities = load_json(device_binding.capabilities)
        assert isinstance(capabilities, dict)
        self.assertEqual("weatherapi", capabilities["metadata"]["provider_type"])
        self.assertIn("weather.updated_at", capabilities["entity_ids"])
        condition_row = self.db.scalar(
            select(DeviceEntity).where(
                DeviceEntity.binding_id == device_binding.id,
                DeviceEntity.entity_id == "weather.condition",
            )
        )
        assert condition_row is not None
        self.assertEqual("weatherapi", condition_row.metadata_payload["provider_type"])


if __name__ == "__main__":
    unittest.main()
