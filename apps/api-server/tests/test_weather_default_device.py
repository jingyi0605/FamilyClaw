import unittest
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.device.models import Device, DeviceBinding
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.config_service import save_plugin_config_form
from app.modules.plugin.schemas import PluginConfigUpdateRequest, PluginStateUpdateRequest
from app.modules.plugin.service import set_household_plugin_enabled
from app.modules.weather.models import WeatherDeviceBinding
from app.modules.weather.schemas import WeatherForecastSummary, WeatherSnapshot
from app.modules.weather.service import get_weather_device_binding_for_device, refresh_weather_device_binding


class _FakeWeatherProvider:
    def __init__(self, snapshot: WeatherSnapshot) -> None:
        self._snapshot = snapshot

    def fetch_weather(self, *, coordinate, config):  # noqa: ANN001
        return self._snapshot


class _TimeoutWeatherProvider:
    def fetch_weather(self, *, coordinate, config):  # noqa: ANN001
        from app.modules.weather.providers import WeatherProviderError

        raise WeatherProviderError(
            "weather_provider_timeout",
            "天气源请求超时。",
            retryable=True,
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

    def test_enable_plugin_creates_default_weather_device_and_refreshes(self) -> None:
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

        snapshot = WeatherSnapshot(
            source_type="met_norway",
            condition_code="cloudy",
            condition_text="多云",
            temperature=23.5,
            humidity=68.0,
            wind_speed=4.2,
            wind_direction=95.0,
            pressure=1010.0,
            cloud_cover=80.0,
            precipitation_next_1h=0.0,
            forecast_6h=WeatherForecastSummary(
                condition_code="rain",
                condition_text="下雨",
                min_temperature=22.0,
                max_temperature=26.0,
            ),
            updated_at="2026-03-18T03:05:00Z",
            is_stale=False,
        )

        with patch("app.modules.weather.service.get_weather_provider", return_value=_FakeWeatherProvider(snapshot)):
            set_household_plugin_enabled(
                self.db,
                household_id=household.id,
                plugin_id="official-weather",
                payload=PluginStateUpdateRequest(enabled=True),
                updated_by="test-suite",
            )

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
        self.assertEqual("weather", device_binding.platform)
        self.assertEqual("official-weather", device_binding.plugin_id)
        self.assertIn("weather.condition", device_binding.capabilities or "")
        self.assertIn("weather.temperature", device_binding.capabilities or "")

    def test_enable_plugin_without_coordinate_marks_pending(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Pending Weather Home", city="Suzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        set_household_plugin_enabled(
            self.db,
            household_id=household.id,
            plugin_id="official-weather",
            payload=PluginStateUpdateRequest(enabled=True),
            updated_by="test-suite",
        )

        row = self.db.scalar(
            select(WeatherDeviceBinding).where(WeatherDeviceBinding.household_id == household.id)
        )
        assert row is not None
        self.assertEqual("pending_coordinate", row.state)
        self.assertEqual("weather_coordinate_missing", row.last_error_code)
        device = self.db.get(Device, row.device_id)
        assert device is not None
        self.assertEqual("inactive", device.status)

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

        snapshot = WeatherSnapshot(
            source_type="met_norway",
            condition_code="partlycloudy_day",
            condition_text="局部多云",
            temperature=21.3,
            humidity=61.0,
            wind_speed=3.6,
            wind_direction=130.0,
            pressure=1012.4,
            cloud_cover=12.0,
            precipitation_next_1h=0.4,
            forecast_6h=WeatherForecastSummary(
                condition_code="cloudy",
                condition_text="多云",
                min_temperature=21.3,
                max_temperature=25.1,
            ),
            updated_at="2026-03-18T03:05:00Z",
            is_stale=False,
        )

        with patch("app.modules.weather.service.get_weather_provider", return_value=_FakeWeatherProvider(snapshot)):
            set_household_plugin_enabled(
                self.db,
                household_id=household.id,
                plugin_id="official-weather",
                payload=PluginStateUpdateRequest(enabled=True),
                updated_by="test-suite",
            )

        device = self.db.scalar(
            select(Device)
            .join(WeatherDeviceBinding, WeatherDeviceBinding.device_id == Device.id)
            .where(WeatherDeviceBinding.household_id == household.id)
        )
        assert device is not None
        weather_binding = get_weather_device_binding_for_device(self.db, device_id=device.id)
        assert weather_binding is not None

        with patch("app.modules.weather.service.get_weather_provider") as provider_factory:
            refreshed = refresh_weather_device_binding(self.db, weather_binding=weather_binding, force=False)
        self.assertEqual("ready", refreshed.state)
        provider_factory.assert_not_called()

        with patch("app.modules.weather.service.get_weather_provider", return_value=_TimeoutWeatherProvider()):
            refreshed = refresh_weather_device_binding(self.db, weather_binding=weather_binding, force=True)

        self.assertEqual("stale", refreshed.state)
        self.assertEqual("weather_provider_timeout", refreshed.last_error_code)
        device_binding = self.db.scalar(select(DeviceBinding).where(DeviceBinding.device_id == device.id))
        assert device_binding is not None
        self.assertIn("局部多云", device_binding.capabilities or "")

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

        initial_snapshot = WeatherSnapshot(
            source_type="met_norway",
            condition_code="cloudy",
            condition_text="多云",
            temperature=23.5,
            humidity=68.0,
            wind_speed=4.2,
            wind_direction=95.0,
            pressure=1010.0,
            cloud_cover=80.0,
            precipitation_next_1h=0.0,
            forecast_6h=WeatherForecastSummary(
                condition_code="rain",
                condition_text="下雨",
                min_temperature=22.0,
                max_temperature=26.0,
            ),
            updated_at="2026-03-18T03:05:00Z",
            is_stale=False,
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

        with patch("app.modules.weather.service.get_weather_provider", return_value=_FakeWeatherProvider(initial_snapshot)):
            set_household_plugin_enabled(
                self.db,
                household_id=household.id,
                plugin_id="official-weather",
                payload=PluginStateUpdateRequest(enabled=True),
                updated_by="test-suite",
            )

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

        with patch("app.modules.weather.service.get_weather_provider", return_value=_FakeWeatherProvider(switched_snapshot)):
            refreshed = refresh_weather_device_binding(self.db, weather_binding=weather_binding, force=True)

        self.assertEqual(original_device_id, refreshed.device_id)
        self.assertEqual("ready", refreshed.state)
        self.assertEqual("2026-03-18T04:00:00Z", refreshed.last_success_at)
        device_binding = self.db.scalar(select(DeviceBinding).where(DeviceBinding.device_id == original_device_id))
        assert device_binding is not None
        self.assertIn("weather.temperature", device_binding.capabilities or "")
        self.assertIn("weatherapi", device_binding.capabilities or "")


if __name__ == "__main__":
    unittest.main()
