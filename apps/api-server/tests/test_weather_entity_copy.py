import unittest
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import dump_json
from app.modules.device.models import Device, DeviceBinding
from app.modules.device.service import list_device_entities
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.schemas import PluginStateUpdateRequest
from app.modules.plugin.service import set_household_plugin_enabled
from app.modules.plugin.startup_sync_service import sync_persisted_plugins_on_startup
from official_weather.schemas import WeatherForecastSummary, WeatherSnapshot
from official_weather.service import get_weather_device_binding_for_device


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
        updated_at="2026-03-18T03:05:00Z",
        is_stale=False,
    )


class WeatherEntityCopyTests(unittest.TestCase):
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

    def test_device_entities_normalize_old_weather_snapshot_copy(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Weather Entity Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        household.latitude = 31.2304
        household.longitude = 121.4737
        household.coordinate_source = "manual_admin"
        household.coordinate_precision = "point"
        household.coordinate_updated_at = "2026-03-18T03:00:00Z"
        self.db.add(household)
        self.db.flush()
        self._sync_official_plugins()

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

        device = self.db.scalar(
            select(Device)
            .join(DeviceBinding, DeviceBinding.device_id == Device.id)
            .where(DeviceBinding.plugin_id == "official-weather")
        )
        assert device is not None
        binding = self.db.scalar(select(DeviceBinding).where(DeviceBinding.device_id == device.id))
        assert binding is not None
        weather_binding = get_weather_device_binding_for_device(self.db, device_id=device.id)
        assert weather_binding is not None

        binding.capabilities = dump_json(
            {
                "adapter_type": "weather",
                "name": device.name,
                "domain": "weather",
                "state": "23.5",
                "primary_entity_id": "weather.temperature",
                "entity_ids": ["weather.temperature"],
                "capability_tags": ["weather"],
                "entities": [
                    {
                        "entity_id": "weather.temperature",
                        "name": "娓╁害",
                        "domain": "weather",
                        "state": "23.5",
                        "state_display": "23.5 掳C",
                        "unit": "掳C",
                        "updated_at": weather_binding.updated_at,
                        "metadata": {"state": "ready", "provider_type": "met_norway"},
                        "control": {"kind": "none"},
                    }
                ],
                "metadata": {"state": "ready", "provider_type": "met_norway"},
            }
        )
        self.db.add(binding)
        self.db.flush()

        response = list_device_entities(self.db, device_id=device.id, view="all")
        self.assertEqual(1, len(response.items))
        self.assertEqual("温度", response.items[0].name)
        self.assertEqual("°C", response.items[0].unit)
        self.assertEqual("23.5 °C", response.items[0].state_display)


if __name__ == "__main__":
    unittest.main()
