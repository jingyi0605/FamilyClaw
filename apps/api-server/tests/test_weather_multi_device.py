import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import dump_json, new_uuid
from app.modules.device.models import DeviceBinding
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin.dashboard_service import get_home_dashboard, save_member_dashboard_layout
from app.modules.plugin.schemas import MemberDashboardLayoutItem, MemberDashboardLayoutUpdateRequest, PluginStateUpdateRequest
from app.modules.plugin.service import set_household_plugin_enabled
from app.modules.region.models import RegionNode
from app.modules.weather.models import WeatherDeviceBinding
from app.modules.weather.providers import WeatherProviderError
from app.modules.weather.schemas import WeatherDeviceBindingCreate, WeatherForecastSummary, WeatherSnapshot
from app.modules.weather.service import create_weather_device_binding, refresh_weather_device_binding


class _CoordinateAwareWeatherProvider:
    def __init__(
        self,
        *,
        snapshots: dict[tuple[float, float], WeatherSnapshot],
        failures: dict[tuple[float, float], WeatherProviderError] | None = None,
    ) -> None:
        self._snapshots = snapshots
        self._failures = failures or {}
        self.calls: list[tuple[float, float]] = []

    def fetch_weather(self, *, coordinate, config):  # noqa: ANN001
        key = (round(coordinate.latitude, 4), round(coordinate.longitude, 4))
        self.calls.append(key)
        failure = self._failures.get(key)
        if failure is not None:
            raise failure
        snapshot = self._snapshots.get(key)
        if snapshot is None:
            raise AssertionError(f"missing snapshot for {key}")
        return snapshot


def _build_snapshot(*, source_type: str, updated_at: str, condition_code: str, condition_text: str) -> WeatherSnapshot:
    return WeatherSnapshot(
        source_type=source_type,  # type: ignore[arg-type]
        condition_code=condition_code,
        condition_text=condition_text,
        temperature=22.5,
        humidity=60.0,
        wind_speed=3.8,
        wind_direction=110.0,
        pressure=1011.0,
        cloud_cover=50.0,
        precipitation_next_1h=0.2,
        forecast_6h=WeatherForecastSummary(
            condition_code=condition_code,
            condition_text=condition_text,
            min_temperature=21.0,
            max_temperature=25.0,
        ),
        updated_at=updated_at,
        is_stale=False,
    )


class WeatherMultiDeviceTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()

        household = create_household(
            self.db,
            HouseholdCreate(name="Multi Weather Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        household.latitude = 31.2304
        household.longitude = 121.4737
        household.coordinate_source = "manual_admin"
        household.coordinate_precision = "point"
        household.coordinate_updated_at = "2026-03-18T03:00:00Z"
        self.db.add(household)
        self.db.flush()
        self.household_id = household.id
        self.member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="天气管理员", role="admin"),
        )
        self.db.flush()

        self._insert_region_node("china_mca", "310000", "上海市", "中国 上海市", 31.2304, 121.4737)
        self._insert_region_node("china_mca", "320500", "苏州市", "中国 江苏省 苏州市", 31.2989, 120.5853)
        self._insert_region_node("china_mca", "330100", "杭州市", "中国 浙江省 杭州市", 30.2741, 120.1551)
        self.db.flush()

        default_provider = _CoordinateAwareWeatherProvider(
            snapshots={
                (31.2304, 121.4737): _build_snapshot(
                    source_type="met_norway",
                    updated_at="2026-03-18T03:05:00Z",
                    condition_code="cloudy",
                    condition_text="多云",
                )
            }
        )
        with patch("app.modules.weather.service.get_weather_provider", return_value=default_provider):
            set_household_plugin_enabled(
                self.db,
                household_id=self.household_id,
                plugin_id="official-weather",
                payload=PluginStateUpdateRequest(enabled=True),
                updated_by="test-suite",
            )

        region_provider = _CoordinateAwareWeatherProvider(
            snapshots={
                (31.2989, 120.5853): _build_snapshot(
                    source_type="met_norway",
                    updated_at="2026-03-18T03:10:00Z",
                    condition_code="partlycloudy_day",
                    condition_text="局部多云",
                ),
                (30.2741, 120.1551): _build_snapshot(
                    source_type="met_norway",
                    updated_at="2026-03-18T03:12:00Z",
                    condition_code="rain",
                    condition_text="下雨",
                ),
            }
        )
        with patch("app.modules.weather.service.get_weather_provider", return_value=region_provider):
            self.suzhou_binding = create_weather_device_binding(
                self.db,
                household_id=self.household_id,
                payload=WeatherDeviceBindingCreate(provider_code="china_mca", region_code="320500"),
            )
            self.hangzhou_binding = create_weather_device_binding(
                self.db,
                household_id=self.household_id,
                payload=WeatherDeviceBindingCreate(provider_code="china_mca", region_code="330100"),
            )

        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def test_refresh_failure_does_not_affect_other_weather_device(self) -> None:
        suzhou_binding = self.db.get(WeatherDeviceBinding, self.suzhou_binding.id)
        hangzhou_binding = self.db.get(WeatherDeviceBinding, self.hangzhou_binding.id)
        assert suzhou_binding is not None
        assert hangzhou_binding is not None

        provider = _CoordinateAwareWeatherProvider(
            snapshots={
                (30.2741, 120.1551): _build_snapshot(
                    source_type="weatherapi",
                    updated_at="2026-03-18T04:20:00Z",
                    condition_code="weatherapi_1006",
                    condition_text="Cloudy",
                )
            },
            failures={
                (31.2989, 120.5853): WeatherProviderError(
                    "weather_provider_timeout",
                    "天气源请求超时。",
                    retryable=True,
                )
            },
        )

        with patch("app.modules.weather.service.get_weather_provider", return_value=provider):
            suzhou_refreshed = refresh_weather_device_binding(self.db, weather_binding=suzhou_binding, force=True)
            hangzhou_refreshed = refresh_weather_device_binding(self.db, weather_binding=hangzhou_binding, force=True)

        self.assertEqual("stale", suzhou_refreshed.state)
        self.assertEqual("weather_provider_timeout", suzhou_refreshed.last_error_code)
        self.assertEqual("ready", hangzhou_refreshed.state)
        self.assertEqual("2026-03-18T04:20:00Z", hangzhou_refreshed.last_success_at)

        suzhou_device_binding = self.db.scalar(select(DeviceBinding).where(DeviceBinding.device_id == suzhou_binding.device_id))
        hangzhou_device_binding = self.db.scalar(select(DeviceBinding).where(DeviceBinding.device_id == hangzhou_binding.device_id))
        assert suzhou_device_binding is not None
        assert hangzhou_device_binding is not None
        self.assertIn("局部多云", suzhou_device_binding.capabilities or "")
        self.assertIn("weatherapi_1006", hangzhou_device_binding.capabilities or "")

        dashboard = get_home_dashboard(
            self.db,
            household_id=self.household_id,
            member_id=self.member.id,
        )
        weather_cards = {
            card.title: card
            for card in dashboard.cards
            if card.card_ref.startswith("plugin:official-weather:home:weather-")
        }
        self.assertEqual("stale", weather_cards["中国 江苏省 苏州市"].state)
        self.assertTrue(weather_cards["中国 江苏省 苏州市"].payload.get("is_stale"))
        self.assertEqual("ready", weather_cards["中国 浙江省 杭州市"].state)

    def test_cache_isolated_per_weather_device(self) -> None:
        suzhou_binding = self.db.get(WeatherDeviceBinding, self.suzhou_binding.id)
        hangzhou_binding = self.db.get(WeatherDeviceBinding, self.hangzhou_binding.id)
        assert suzhou_binding is not None
        assert hangzhou_binding is not None

        suzhou_binding.cache_expires_at = (
            datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=1)
        ).isoformat().replace("+00:00", "Z")
        self.db.add(suzhou_binding)
        self.db.flush()

        provider = _CoordinateAwareWeatherProvider(
            snapshots={
                (31.2989, 120.5853): _build_snapshot(
                    source_type="met_norway",
                    updated_at="2026-03-18T04:30:00Z",
                    condition_code="cloudy",
                    condition_text="多云",
                ),
                (30.2741, 120.1551): _build_snapshot(
                    source_type="met_norway",
                    updated_at="2026-03-18T04:31:00Z",
                    condition_code="rain",
                    condition_text="下雨",
                ),
            }
        )

        with patch("app.modules.weather.service.get_weather_provider", return_value=provider):
            suzhou_refreshed = refresh_weather_device_binding(self.db, weather_binding=suzhou_binding, force=False)
            hangzhou_refreshed = refresh_weather_device_binding(self.db, weather_binding=hangzhou_binding, force=False)

        self.assertEqual([(31.2989, 120.5853)], provider.calls)
        self.assertEqual("2026-03-18T04:30:00Z", suzhou_refreshed.last_success_at)
        self.assertEqual("2026-03-18T03:12:00Z", hangzhou_refreshed.last_success_at)

    def test_home_dashboard_shows_one_weather_card_per_device(self) -> None:
        dashboard = get_home_dashboard(
            self.db,
            household_id=self.household_id,
            member_id=self.member.id,
        )

        weather_cards = [
            card
            for card in dashboard.cards
            if card.card_ref.startswith("plugin:official-weather:home:weather-")
        ]
        self.assertEqual(3, len(weather_cards))
        self.assertEqual("plugin:official-weather:home:weather-default", weather_cards[0].card_ref)
        self.assertEqual("家庭天气", weather_cards[0].title)
        self.assertEqual("家庭默认天气", weather_cards[0].subtitle)
        self.assertEqual("weather", weather_cards[0].payload.get("card_kind"))
        self.assertEqual("家庭天气", weather_cards[0].payload.get("location"))

        extra_titles = {card.title for card in weather_cards[1:]}
        self.assertEqual({"中国 江苏省 苏州市", "中国 浙江省 杭州市"}, extra_titles)

    def test_home_dashboard_layout_can_hide_other_weather_devices(self) -> None:
        dashboard = get_home_dashboard(
            self.db,
            household_id=self.household_id,
            member_id=self.member.id,
        )
        target_card_ref = "plugin:official-weather:home:weather-default"
        layout_items = [
            MemberDashboardLayoutItem(
                card_ref=card.card_ref,
                visible=(not card.card_ref.startswith("plugin:official-weather:home:weather-")) or card.card_ref == target_card_ref,
                order=(index + 1) * 10,
                size=card.size,
                height="regular",
            )
            for index, card in enumerate(dashboard.cards)
        ]

        save_member_dashboard_layout(
            self.db,
            household_id=self.household_id,
            member_id=self.member.id,
            payload=MemberDashboardLayoutUpdateRequest(items=layout_items),
        )
        self.db.flush()

        latest_dashboard = get_home_dashboard(
            self.db,
            household_id=self.household_id,
            member_id=self.member.id,
        )
        visible_weather_cards = [
            card.card_ref
            for card in latest_dashboard.cards
            if card.card_ref.startswith("plugin:official-weather:home:weather-")
        ]
        self.assertEqual([target_card_ref], visible_weather_cards)

    def _insert_region_node(
        self,
        provider_code: str,
        region_code: str,
        name: str,
        full_name: str,
        latitude: float,
        longitude: float,
    ) -> None:
        self.db.add(
            RegionNode(
                id=new_uuid(),
                provider_code=provider_code,
                country_code="CN",
                region_code=region_code,
                parent_region_code=None,
                admin_level="city",
                name=name,
                full_name=full_name,
                path_codes=dump_json(["CN", region_code]) or "[]",
                path_names=dump_json(["中国", name]) or "[]",
                timezone="Asia/Shanghai",
                source_version="test",
                imported_at="2026-03-18T03:00:00Z",
                latitude=latitude,
                longitude=longitude,
                coordinate_precision="city",
                coordinate_source="provider_builtin",
                coordinate_updated_at="2026-03-18T03:00:00Z",
                enabled=True,
                extra=None,
            )
        )


if __name__ == "__main__":
    unittest.main()
