import unittest
from unittest.mock import patch

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.integration.models import IntegrationInstance
from app.modules.integration.schemas import IntegrationInstanceCreateRequest
from app.modules.integration.service import create_integration_instance, sync_plugin_managed_integration_instance
from app.modules.plugin.schemas import PluginStateUpdateRequest
from app.modules.plugin.service import get_household_plugin, set_household_plugin_enabled
from app.modules.plugin.startup_sync_service import sync_persisted_plugins_on_startup
from official_weather.models import WeatherDeviceBinding
from official_weather.schemas import WeatherForecastSummary, WeatherSnapshot
from tests.weather_test_utils import force_weather_plugin_in_process


class _FakeWeatherProvider:
    def __init__(self, snapshot: WeatherSnapshot) -> None:
        self._snapshot = snapshot

    def fetch_weather(self, *, coordinate, config):  # noqa: ANN001
        return self._snapshot


def _build_snapshot() -> WeatherSnapshot:
    return WeatherSnapshot(
        source_type="met_norway",  # type: ignore[arg-type]
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
            condition_text="小雨",
            min_temperature=22.0,
            max_temperature=26.0,
        ),
        updated_at="2026-03-19T10:05:00Z",
        is_stale=False,
    )


class WeatherPluginPrivateMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def _has_weather_binding_table(self) -> bool:
        return inspect(self.db.connection()).has_table("weather_device_bindings")

    def test_core_alembic_head_does_not_create_weather_private_table(self) -> None:
        self.assertFalse(self._has_weather_binding_table())

        sync_persisted_plugins_on_startup(self.db)
        self.db.flush()

        self.assertFalse(self._has_weather_binding_table())

    def test_enabling_weather_plugin_applies_private_migration(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Plugin Weather Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        household.latitude = 31.2304
        household.longitude = 121.4737
        household.coordinate_source = "manual_admin"
        household.coordinate_precision = "point"
        household.coordinate_updated_at = "2026-03-19T10:00:00Z"
        self.db.add(household)
        self.db.flush()

        sync_persisted_plugins_on_startup(self.db)
        self.db.flush()
        self.assertFalse(self._has_weather_binding_table())

        with patch(
            "official_weather.service.get_weather_provider",
            return_value=_FakeWeatherProvider(_build_snapshot()),
        ):
            set_household_plugin_enabled(
                self.db,
                household_id=household.id,
                plugin_id="official-weather",
                payload=PluginStateUpdateRequest(enabled=True),
                updated_by="test-suite",
            )
            created = create_integration_instance(
                self.db,
                payload=IntegrationInstanceCreateRequest(
                    household_id=household.id,
                    plugin_id="official-weather",
                    display_name="家庭天气",
                    config={"binding_type": "default_household"},
                ),
                updated_by="test-suite",
            )
            instance = self.db.get(IntegrationInstance, created.id)
            assert instance is not None
            plugin = get_household_plugin(
                self.db,
                household_id=household.id,
                plugin_id="official-weather",
            )
            self.db.commit()
            with force_weather_plugin_in_process():
                sync_plugin_managed_integration_instance(
                    self.db,
                    plugin=plugin,
                    instance=instance,
                    sync_scope="device_sync",
                )
            self.db.commit()
            self.db.rollback()

        self.assertTrue(self._has_weather_binding_table())
        row = self.db.scalar(
            select(WeatherDeviceBinding).where(WeatherDeviceBinding.household_id == household.id)
        )
        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
