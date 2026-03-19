import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.modules.context.service import get_context_overview
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin.dashboard_service import get_home_dashboard
from app.modules.presence.schemas import PresenceEventCreate
from app.modules.presence.service import ingest_presence_event
from app.modules.room.service import create_room


def _utc_iso(*, minutes_ago: int) -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        - timedelta(minutes=minutes_ago)
    ).isoformat().replace("+00:00", "Z")


class HomeDashboardRecentEventsTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()
        household = create_household(
            self.db,
            HouseholdCreate(name="Recent Events Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="Alex", role="admin"),
        )
        self.room = create_room(
            self.db,
            household_id=household.id,
            name="客厅",
            room_type="living_room",
            privacy_level="public",
        )
        self.db.flush()
        self.household_id = household.id

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def _get_card(self, dashboard, card_ref: str):
        return next(card for card in dashboard.cards if card.card_ref == card_ref)

    def test_recent_events_card_stays_empty_when_only_presence_diagnostic_exists(self) -> None:
        dashboard = get_home_dashboard(
            self.db,
            household_id=self.household_id,
            member_id=self.member.id,
        )
        overview = get_context_overview(self.db, self.household_id)

        events_card = self._get_card(dashboard, "builtin:events")
        weather_card = self._get_card(dashboard, "builtin:weather")

        self.assertEqual("empty", events_card.state)
        self.assertEqual([], events_card.payload["items"])
        self.assertEqual("fallback", overview.presence_health.status)
        self.assertIn("实时在家快照缺失", weather_card.payload["message"])

    def test_recent_events_card_prefers_real_presence_events(self) -> None:
        ingest_presence_event(
            self.db,
            PresenceEventCreate(
                household_id=self.household_id,
                member_id=self.member.id,
                room_id=self.room.id,
                source_type="sensor",
                source_ref="sensor-living-room",
                confidence=0.96,
                payload={"status": "home"},
                occurred_at=_utc_iso(minutes_ago=5),
            ),
        )

        dashboard = get_home_dashboard(
            self.db,
            household_id=self.household_id,
            member_id=self.member.id,
        )
        overview = get_context_overview(self.db, self.household_id)
        events_card = self._get_card(dashboard, "builtin:events")

        self.assertEqual("ready", events_card.state)
        self.assertGreaterEqual(len(events_card.payload["items"]), 1)
        self.assertEqual("Alex 已回家", events_card.payload["items"][0]["title"])
        self.assertIn("客厅", events_card.payload["items"][0]["description"])
        self.assertEqual("success", events_card.payload["items"][0]["tone"])
        self.assertEqual("live", overview.presence_health.status)

    def test_stale_presence_snapshot_falls_back_but_keeps_recent_event(self) -> None:
        ingest_presence_event(
            self.db,
            PresenceEventCreate(
                household_id=self.household_id,
                member_id=self.member.id,
                room_id=None,
                source_type="sensor",
                source_ref="sensor-front-door",
                confidence=0.88,
                payload={"status": "away"},
                occurred_at=_utc_iso(minutes_ago=120),
            ),
        )

        dashboard = get_home_dashboard(
            self.db,
            household_id=self.household_id,
            member_id=self.member.id,
        )
        overview = get_context_overview(self.db, self.household_id)
        events_card = self._get_card(dashboard, "builtin:events")
        weather_card = self._get_card(dashboard, "builtin:weather")

        self.assertEqual("stale", overview.presence_health.status)
        self.assertEqual("default", overview.member_states[0].source)
        self.assertEqual("stale_snapshot", overview.member_states[0].source_summary["fallback_reason"])
        self.assertEqual("ready", events_card.state)
        self.assertEqual("Alex 已离家", events_card.payload["items"][0]["title"])
        self.assertIn("实时在家快照已过期", weather_card.payload["message"])


if __name__ == "__main__":
    unittest.main()
