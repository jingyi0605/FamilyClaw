import unittest
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import load_json
from app.modules.device.models import Device, DeviceBinding, DeviceEntity
from app.modules.device.service import list_device_entities
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.schemas import PluginStateUpdateRequest
from app.modules.plugin.service import set_household_plugin_enabled
from app.modules.plugin.startup_sync_service import sync_persisted_plugins_on_startup
from official_weather.schemas import WeatherForecastSummary, WeatherSnapshot
from official_weather.service import get_weather_device_binding_for_device, normalize_weather_capabilities_payload


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


def _assert_no_weather_mojibake(text: str) -> None:
    suspicious_markers = ("澶", "鏈€", "鏆", "姘", "鍦", "婀", "椋", "掳")
    assert not any(marker in text for marker in suspicious_markers), text


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

    def test_weather_plugin_refresh_writes_canonical_entities(self) -> None:
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
        capabilities = load_json(binding.capabilities)
        assert isinstance(capabilities, dict)
        self.assertEqual("weather.condition", capabilities["primary_entity_id"])
        self.assertIn("weather.updated_at", capabilities["entity_ids"])
        self.assertNotIn("entities", capabilities)

        entity_rows = list(
            self.db.scalars(
                select(DeviceEntity)
                .where(DeviceEntity.binding_id == binding.id)
                .order_by(DeviceEntity.sort_order.asc(), DeviceEntity.id.asc())
            ).all()
        )
        self.assertEqual(10, len(entity_rows))
        entity_map = {item.entity_id: item for item in entity_rows}
        self.assertEqual("天气状态", entity_map["weather.condition"].name)
        self.assertEqual("多云", entity_map["weather.condition"].state_display)
        self.assertEqual("温度", entity_map["weather.temperature"].name)
        self.assertEqual("°C", entity_map["weather.temperature"].unit)
        self.assertEqual("23.5 °C", entity_map["weather.temperature"].state_display)
        self.assertEqual("未来 6 小时摘要", entity_map["weather.forecast_6h"].name)
        self.assertEqual("小雨 22~26 °C", entity_map["weather.forecast_6h"].state_display)
        self.assertEqual({"kind": "none"}, entity_map["weather.wind_speed"].control)

        for row in entity_rows:
            _assert_no_weather_mojibake(row.name)
            if row.state_display:
                _assert_no_weather_mojibake(row.state_display)

        response = list_device_entities(self.db, device_id=device.id, view="all")
        self.assertEqual(10, len(response.items))
        response_entity_map = {item.entity_id: item for item in response.items}
        self.assertEqual(entity_map["weather.condition"].name, response_entity_map["weather.condition"].name)
        self.assertEqual(entity_map["weather.condition"].state_display, response_entity_map["weather.condition"].state_display)
        self.assertEqual(entity_map["weather.temperature"].unit, response_entity_map["weather.temperature"].unit)
        self.assertEqual(entity_map["weather.forecast_6h"].state_display, response_entity_map["weather.forecast_6h"].state_display)

    def test_normalize_weather_capabilities_payload_repairs_error_message_and_forecast_fallback(self) -> None:
        normalized = normalize_weather_capabilities_payload(
            {
                "entities": [
                    {
                        "entity_id": "weather.condition",
                        "name": "婢垛晜鐨甸悩鑸碉拷锟",
                        "domain": "weather",
                        "state": "error",
                        "state_display": "婢垛晜鐨甸弫鐗堝祦閺嗗倷绗夐崣顖滄暏",
                        "unit": None,
                        "updated_at": "2026-03-18T03:05:00Z",
                        "metadata": {
                            "state": "error",
                            "provider_type": "met_norway",
                            "error_message": "婢垛晜鐨甸弫鐗堝祦閺嗗倷绗夐崣顖滄暏",
                        },
                        "control": {"kind": "none"},
                    },
                    {
                        "entity_id": "weather.forecast_6h",
                        "name": "閺堬拷閺夛拷 6 鐏忓繑妞傞幗妯款洣",
                        "domain": "weather",
                        "state": "rain",
                        "state_display": "鐏忓繘娲?22~26 鎺矯",
                        "unit": None,
                        "updated_at": "2026-03-18T03:05:00Z",
                        "metadata": {
                            "state": "ready",
                            "provider_type": "met_norway",
                            "condition_text": "鐏忓繘娲",
                            "min_temperature": 22.0,
                            "max_temperature": 26.0,
                        },
                        "control": {"kind": "none"},
                    },
                ]
            }
        )
        entity_map = {
            item["entity_id"]: item
            for item in normalized["entities"]
            if isinstance(item, dict) and item.get("entity_id")
        }
        self.assertEqual("天气状态", entity_map["weather.condition"]["name"])
        self.assertEqual("天气数据暂不可用", entity_map["weather.condition"]["state_display"])
        self.assertEqual("天气数据暂不可用", entity_map["weather.condition"]["metadata"]["error_message"])
        self.assertEqual("未来 6 小时摘要", entity_map["weather.forecast_6h"]["name"])
        self.assertEqual("rain 22~26 °C", entity_map["weather.forecast_6h"]["state_display"])


if __name__ == "__main__":
    unittest.main()
