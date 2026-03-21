import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.integration.models import IntegrationInstance
from app.modules.integration.schemas import IntegrationInstanceCreateRequest
from app.modules.integration.service import create_integration_instance, sync_plugin_managed_integration_instance
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin.dashboard_service import get_home_dashboard
from app.modules.plugin.schemas import PluginStateUpdateRequest
from app.modules.plugin.startup_sync_service import sync_persisted_plugins_on_startup
from app.modules.plugin.service import get_household_plugin, load_plugin_manifest, set_household_plugin_enabled
from official_weather.schemas import WeatherForecastSummary, WeatherSnapshot


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


class DashboardEncodingTests(unittest.TestCase):
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
        instance = self.db.get(IntegrationInstance, created.id)
        assert instance is not None
        self.db.flush()
        return instance

    def _sync_default_weather_instance(self, *, household_id: str, instance: IntegrationInstance) -> None:
        plugin = get_household_plugin(
            self.db,
            household_id=household_id,
            plugin_id="official-weather",
        )
        sync_plugin_managed_integration_instance(
            self.db,
            plugin=plugin,
            instance=instance,
            sync_scope="device_sync",
        )
        self.db.flush()

    def test_home_dashboard_weather_card_uses_plugin_locale_when_snapshot_missing(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Weather Dashboard Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()
        self._sync_official_plugins()
        self._enable_weather_plugin(household_id=household.id)
        instance = self._create_default_weather_instance(household_id=household.id)
        self._sync_default_weather_instance(household_id=household.id, instance=instance)

        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="Tester", role="admin"),
        )
        self.db.flush()

        dashboard = get_home_dashboard(
            self.db,
            household_id=household.id,
            member_id=member.id,
        )

        weather_card = next(
            card
            for card in dashboard.cards
            if card.card_ref == "plugin:official-weather:home:weather-default"
        )

        self.assertEqual("家庭天气", weather_card.title)
        self.assertEqual("家庭默认天气", weather_card.subtitle)

    def test_home_dashboard_weather_card_uses_readable_snapshot_copy(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Weather Dashboard Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
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

        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="Tester", role="admin"),
        )
        self.db.flush()

        with patch(
            "official_weather.service.get_weather_provider",
            return_value=_FakeWeatherProvider(_build_snapshot()),
        ):
            self._sync_default_weather_instance(household_id=household.id, instance=instance)

        dashboard = get_home_dashboard(
            self.db,
            household_id=household.id,
            member_id=member.id,
        )

        weather_card = next(
            card
            for card in dashboard.cards
            if card.card_ref == "plugin:official-weather:home:weather-default"
        )

        self.assertEqual("家庭天气", weather_card.title)
        self.assertEqual("家庭默认天气", weather_card.subtitle)
        self.assertEqual("多云", weather_card.payload["condition_text"])
        self.assertEqual("°C", weather_card.payload["temperature_unit"])
        self.assertEqual("°", weather_card.payload["wind_direction_unit"])
        self.assertEqual(
            "official_weather.dashboard.fields.humidity",
            weather_card.payload["detail_items"][0]["label_key"],
        )
        self.assertEqual(
            "official_weather.dashboard.fields.updated_at",
            weather_card.payload["footer_items"][-1]["label_key"],
        )

    def test_official_weather_manifest_uses_readable_copy_and_declares_locales(self) -> None:
        manifest = load_plugin_manifest(
            self._official_root() / "official_weather" / "manifest.json"
        )

        self.assertEqual("天气插件", manifest.name)
        assert manifest.capabilities.integration is not None
        self.assertEqual("家庭天气", manifest.capabilities.integration.default_instance_display_name)
        self.assertEqual(
            "official_weather.integration.instance_name_placeholder",
            manifest.capabilities.integration.instance_display_name_placeholder_key,
        )
        self.assertEqual(["zh-CN", "en-US"], [item.id for item in manifest.locales])
        self.assertEqual("official_weather.config.provider.title", manifest.config_specs[0].title_key)
        self.assertEqual(
            "official_weather.config.binding.fields.provider_code.label",
            manifest.config_specs[1].config_schema.fields[1].label_key,
        )

    @staticmethod
    def _official_root() -> Path:
        return Path(__file__).resolve().parents[1] / "data" / "plugins" / "official"


if __name__ == "__main__":
    unittest.main()
