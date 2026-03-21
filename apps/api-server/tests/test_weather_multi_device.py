import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import load_json
from app.modules.device.models import DeviceBinding, DeviceEntity
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.integration.models import IntegrationInstance
from app.modules.integration.schemas import IntegrationInstanceActionRequest, IntegrationInstanceCreateRequest
from app.modules.integration.service import (
    create_integration_instance,
    execute_integration_instance_action,
    sync_plugin_managed_integration_instance,
)
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin.dashboard_service import get_home_dashboard, save_member_dashboard_layout
from app.modules.plugin.schemas import MemberDashboardLayoutItem, MemberDashboardLayoutUpdateRequest, PluginStateUpdateRequest
from app.modules.plugin.startup_sync_service import sync_persisted_plugins_on_startup
from app.modules.plugin.service import get_household_plugin, set_household_plugin_enabled
from official_weather.providers import WeatherProviderError
from official_weather.repository import get_weather_device_binding_for_integration_instance
from official_weather.schemas import WeatherForecastSummary, WeatherSnapshot
from official_weather.service import refresh_weather_device_binding
from tests.weather_test_utils import (
    build_weather_test_region_provider,
    force_weather_plugin_in_process,
    register_region_provider,
)


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
        self._region_provider = build_weather_test_region_provider()
        self._region_provider_context = register_region_provider(self._region_provider)
        self._region_provider_context.__enter__()

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
        sync_persisted_plugins_on_startup(self.db)
        self.db.flush()
        self.member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="天气管理员", role="admin"),
        )
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
        with patch(
            "official_weather.service.get_weather_provider",
            return_value=default_provider,
        ):
            set_household_plugin_enabled(
                self.db,
                household_id=self.household_id,
                plugin_id="official-weather",
                payload=PluginStateUpdateRequest(enabled=True),
                updated_by="test-suite",
            )
            created_default = create_integration_instance(
                self.db,
                payload=IntegrationInstanceCreateRequest(
                    household_id=self.household_id,
                    plugin_id="official-weather",
                    display_name="家庭天气",
                    config={"binding_type": "default_household"},
                ),
                updated_by="test-suite",
            )
            default_instance = self.db.get(IntegrationInstance, created_default.id)
            assert default_instance is not None
            self.db.commit()
            plugin = get_household_plugin(
                self.db,
                household_id=self.household_id,
                plugin_id="official-weather",
            )
            with force_weather_plugin_in_process():
                sync_plugin_managed_integration_instance(
                    self.db,
                    plugin=plugin,
                    instance=default_instance,
                    sync_scope="device_sync",
                )
            self.db.commit()
            self.db.rollback()

        self.suzhou_instance = create_integration_instance(
            self.db,
            payload=IntegrationInstanceCreateRequest(
                household_id=self.household_id,
                plugin_id="official-weather",
                display_name="苏州天气",
                config={
                    "binding_type": "region_node",
                    "provider_code": self._region_provider.provider_code,
                    "province_code": "320000",
                    "city_code": "320500",
                    "district_code": "320505",
                },
            ),
            updated_by="test-suite",
        )
        self.hangzhou_instance = create_integration_instance(
            self.db,
            payload=IntegrationInstanceCreateRequest(
                household_id=self.household_id,
                plugin_id="official-weather",
                display_name="杭州天气",
                config={
                    "binding_type": "region_node",
                    "provider_code": self._region_provider.provider_code,
                    "province_code": "330000",
                    "city_code": "330100",
                    "district_code": "330106",
                },
            ),
            updated_by="test-suite",
        )
        self.db.commit()

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
                    condition_text="小雨",
                ),
            }
        )
        with patch(
            "official_weather.service.get_weather_provider",
            return_value=region_provider,
        ):
            with force_weather_plugin_in_process():
                asyncio.run(
                    execute_integration_instance_action(
                        self.db,
                        instance_id=self.suzhou_instance.id,
                        payload=IntegrationInstanceActionRequest(action="sync", payload={"sync_scope": "device_sync"}),
                    )
                )
                asyncio.run(
                    execute_integration_instance_action(
                        self.db,
                        instance_id=self.hangzhou_instance.id,
                        payload=IntegrationInstanceActionRequest(action="sync", payload={"sync_scope": "device_sync"}),
                    )
                )

        self.db.commit()
        self.db.rollback()

    def tearDown(self) -> None:
        self.db.close()
        self._region_provider_context.__exit__(None, None, None)
        self._db_helper.close()

    def test_refresh_failure_does_not_affect_other_weather_device(self) -> None:
        suzhou_binding = get_weather_device_binding_for_integration_instance(
            self.db,
            integration_instance_id=self.suzhou_instance.id,
        )
        hangzhou_binding = get_weather_device_binding_for_integration_instance(
            self.db,
            integration_instance_id=self.hangzhou_instance.id,
        )
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

        with patch(
            "official_weather.service.get_weather_provider",
            return_value=provider,
        ):
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
        suzhou_capabilities = load_json(suzhou_device_binding.capabilities)
        hangzhou_capabilities = load_json(hangzhou_device_binding.capabilities)
        assert isinstance(suzhou_capabilities, dict)
        assert isinstance(hangzhou_capabilities, dict)
        self.assertTrue(suzhou_capabilities["metadata"]["is_stale"])
        self.assertEqual("weatherapi", hangzhou_capabilities["metadata"]["provider_type"])
        suzhou_condition = self.db.scalar(
            select(DeviceEntity).where(
                DeviceEntity.binding_id == suzhou_device_binding.id,
                DeviceEntity.entity_id == "weather.condition",
            )
        )
        hangzhou_condition = self.db.scalar(
            select(DeviceEntity).where(
                DeviceEntity.binding_id == hangzhou_device_binding.id,
                DeviceEntity.entity_id == "weather.condition",
            )
        )
        assert suzhou_condition is not None
        assert hangzhou_condition is not None
        self.assertTrue(suzhou_condition.metadata_payload["is_stale"])
        self.assertEqual("weatherapi", hangzhou_condition.metadata_payload["provider_type"])
        self.assertNotEqual(suzhou_condition.updated_at, hangzhou_condition.updated_at)

        dashboard = get_home_dashboard(
            self.db,
            household_id=self.household_id,
            member_id=self.member.id,
        )
        weather_cards = {
            card.payload.get("location"): card
            for card in dashboard.cards
            if card.card_ref.startswith("plugin:official-weather:home:weather-")
        }
        self.assertEqual("stale", weather_cards["中国 江苏省 苏州市"].state)
        self.assertTrue(weather_cards["中国 江苏省 苏州市"].payload.get("is_stale"))
        self.assertEqual("ready", weather_cards["中国 浙江省 杭州市"].state)

    def test_cache_isolated_per_weather_device(self) -> None:
        suzhou_binding = get_weather_device_binding_for_integration_instance(
            self.db,
            integration_instance_id=self.suzhou_instance.id,
        )
        hangzhou_binding = get_weather_device_binding_for_integration_instance(
            self.db,
            integration_instance_id=self.hangzhou_instance.id,
        )
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
                    condition_text="小雨",
                ),
            }
        )

        with patch(
            "official_weather.service.get_weather_provider",
            return_value=provider,
        ):
            suzhou_refreshed = refresh_weather_device_binding(self.db, weather_binding=suzhou_binding, force=False)
            hangzhou_refreshed = refresh_weather_device_binding(self.db, weather_binding=hangzhou_binding, force=False)

        self.assertEqual([(31.2989, 120.5853)], provider.calls)
        self.assertEqual("2026-03-18T04:30:00Z", suzhou_refreshed.last_success_at)
        self.assertEqual("2026-03-18T03:12:00Z", hangzhou_refreshed.last_success_at)
        suzhou_device_binding = self.db.scalar(select(DeviceBinding).where(DeviceBinding.device_id == suzhou_binding.device_id))
        hangzhou_device_binding = self.db.scalar(select(DeviceBinding).where(DeviceBinding.device_id == hangzhou_binding.device_id))
        assert suzhou_device_binding is not None
        assert hangzhou_device_binding is not None
        suzhou_updated_at = self.db.scalar(
            select(DeviceEntity.updated_at).where(
                DeviceEntity.binding_id == suzhou_device_binding.id,
                DeviceEntity.entity_id == "weather.updated_at",
            )
        )
        hangzhou_updated_at = self.db.scalar(
            select(DeviceEntity.updated_at).where(
                DeviceEntity.binding_id == hangzhou_device_binding.id,
                DeviceEntity.entity_id == "weather.updated_at",
            )
        )
        self.assertEqual("2026-03-18T04:30:00Z", suzhou_updated_at)
        self.assertEqual("2026-03-18T03:12:00Z", hangzhou_updated_at)

    def test_home_dashboard_shows_one_weather_card_per_instance(self) -> None:
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

        card_refs = {card.card_ref for card in weather_cards}
        self.assertIn("plugin:official-weather:home:weather-default", card_refs)
        payload_locations = {card.payload.get("location") for card in weather_cards}
        self.assertIn("中国 江苏省 苏州市", payload_locations)
        self.assertIn("中国 浙江省 杭州市", payload_locations)

        for card in weather_cards:
            self.assertEqual("weather", card.payload.get("card_kind"))
            self.assertTrue(card.payload.get("device_id"))

    def test_home_dashboard_layout_can_hide_other_weather_instances(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
