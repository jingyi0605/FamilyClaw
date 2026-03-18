import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin.dashboard_service import _build_builtin_home_cards, get_home_dashboard
from app.modules.plugin.schemas import PluginStateUpdateRequest
from app.modules.plugin.startup_sync_service import sync_persisted_plugins_on_startup
from app.modules.plugin.service import load_plugin_manifest, set_household_plugin_enabled
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

    def test_builtin_home_cards_use_readable_copy(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Dashboard Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        cards, warnings = _build_builtin_home_cards(self.db, household_id=household.id)
        self.assertFalse(warnings)
        card_map = {card.card_ref: card for card in cards}

        self.assertEqual("首页总览", card_map["builtin:weather"].subtitle)
        self.assertEqual("关键指标", card_map["builtin:stats"].title)
        self.assertEqual("内置聚合摘要", card_map["builtin:stats"].subtitle)
        self.assertEqual("快捷操作", card_map["builtin:quick-actions"].title)
        self.assertEqual(
            ["对话", "记忆", "设置", "家庭"],
            [action.label for action in card_map["builtin:quick-actions"].actions],
        )

    def test_home_dashboard_weather_card_uses_plugin_locale_when_snapshot_missing(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Weather Dashboard Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()
        self._sync_official_plugins()

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

        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="Tester", role="admin"),
        )
        self.db.flush()

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
        self.assertEqual("°C", weather_card.payload["temperature_unit"])
        self.assertEqual("°", weather_card.payload["wind_direction_unit"])

    def test_official_weather_manifest_uses_readable_copy_and_declares_locales(self) -> None:
        manifest = load_plugin_manifest(
            self._official_root() / "official_weather" / "manifest.json"
        )

        self.assertEqual("官方天气插件", manifest.name)
        assert manifest.capabilities.integration is not None
        self.assertEqual("家庭天气", manifest.capabilities.integration.default_instance_display_name)
        self.assertEqual(["zh-CN", "en-US"], [item.id for item in manifest.locales])

    @staticmethod
    def _official_root() -> Path:
        return Path(__file__).resolve().parents[1] / "data" / "plugins" / "official"


if __name__ == "__main__":
    unittest.main()
