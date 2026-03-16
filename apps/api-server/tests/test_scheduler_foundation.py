import tempfile
import unittest
import asyncio
import json
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
import httpx
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
import app.db.session as db_session_module
from app.api.dependencies import ActorContext
from app.core.config import settings
from app.db.utils import new_uuid
from app.main import app
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.context.schemas import ContextConfigUpsert
from app.modules.context.service import upsert_context_config
from app.modules.device.models import Device
from app.modules.account.schemas import HouseholdAccountCreateRequest
from app.modules.account.service import AuthenticatedActor, create_account_session, create_household_account_with_binding, ensure_pending_household_bootstrap_accounts
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.presence.schemas import PresenceEventCreate
from app.modules.presence.service import ingest_presence_event
from app.modules.plugin.schemas import PluginMountCreate, PluginMountUpdate
from app.modules.plugin.service import register_plugin_mount, update_plugin_mount
from app.modules.room.service import create_room
from app.modules.scheduler.rules import evaluate_heartbeat_rule
from app.modules.scheduler.schemas import RuleType
from typing import Literal
from app.modules.scheduler.service import (
    build_run_idempotency_key,
    create_task_definition,
    process_due_heartbeat_tick,
    process_due_schedule_tick,
)
from app.modules.scheduler.dispatchers import dispatch_task_run
from app.modules.scheduler.schemas import ScheduledTaskDefinitionCreate


class SchedulerFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
        self._previous_session_local = db_session_module.SessionLocal
        db_session_module.SessionLocal = self.SessionLocal
        self.db: Session = self.SessionLocal()

        ensure_pending_household_bootstrap_accounts(self.db)
        self.household = create_household(
            self.db,
            HouseholdCreate(name="Scheduler Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.admin_member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="绠＄悊鍛?, role="admin"),
        )
        self.user_member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="鏅€氭垚鍛?, role="adult"),
        )
        self.child_member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="灏忔湅鍙?, role="child"),
        )
        self.elder_member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="闀胯緢", role="elder"),
        )
        self.living_room = create_room(
            self.db,
            household_id=self.household.id,
            name="瀹㈠巺",
            room_type="living_room",
            privacy_level="public",
        )
        self.db.commit()
        self.agent = create_agent(
            self.db,
            household_id=self.household.id,
            payload=AgentCreate(
                display_name="瀹跺涵绠″",
                agent_type="butler",
                self_identity="鎴戞槸瀹跺涵绠″",
                role_summary="璐熻矗瀹跺涵涓诲姩鎻愰啋",
                created_by="test",
            ),
        )
        self.db.commit()
        self.admin_account, _ = create_household_account_with_binding(
            self.db,
            HouseholdAccountCreateRequest(
                household_id=self.household.id,
                member_id=self.admin_member.id,
                username="scheduler_admin",
                password="admin123",
                must_change_password=False,
            ),
        )
        self.user_account, _ = create_household_account_with_binding(
            self.db,
            HouseholdAccountCreateRequest(
                household_id=self.household.id,
                member_id=self.user_member.id,
                username="scheduler_user",
                password="user123",
                must_change_password=False,
            ),
        )
        self.db.commit()
        _, self.admin_session_token = create_account_session(self.db, self.admin_account.id)
        _, self.user_session_token = create_account_session(self.db, self.user_account.id)
        self.db.commit()

        self.admin_actor = AuthenticatedActor(
            account_id=self.admin_account.id,
            username=self.admin_account.username,
            account_type=self.admin_account.account_type,
            account_status=self.admin_account.status,
            household_id=self.household.id,
            member_id=self.admin_member.id,
            member_role=self.admin_member.role,
            must_change_password=False,
        )
        self.user_actor = AuthenticatedActor(
            account_id=self.user_account.id,
            username=self.user_account.username,
            account_type=self.user_account.account_type,
            account_status=self.user_account.status,
            household_id=self.household.id,
            member_id=self.user_member.id,
            member_role=self.user_member.role,
            must_change_password=False,
        )

        self.actor_context = ActorContext(
            role=self.admin_actor.role,
            actor_type="account",
            actor_id=self.admin_account.id,
            account_id=self.admin_account.id,
            username=self.admin_account.username,
            account_type=self.admin_account.account_type,
            account_status=self.admin_account.status,
            household_id=self.household.id,
            member_id=self.admin_member.id,
            member_role=self.admin_member.role,
            is_authenticated=True,
            must_change_password=False,
        )

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        db_session_module.SessionLocal = self._previous_session_local
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_scheduler_tables_exist(self) -> None:
        inspector = inspect(self.engine)
        table_names = set(inspector.get_table_names())
        self.assertTrue(
            {"scheduled_task_definitions", "scheduled_task_runs", "scheduled_task_deliveries"}.issubset(table_names)
        )

    def test_admin_can_create_household_task_and_member_task(self) -> None:
        household_task = create_task_definition(
            self.db,
            actor=self.admin_actor,
            payload=ScheduledTaskDefinitionCreate(
                household_id=self.household.id,
                owner_scope="household",
                code="family-daily-sync",
                name="鍏ㄥ鏅氶棿鍚屾",
                trigger_type="schedule",
                schedule_type="daily",
                schedule_expr="21:00",
                target_type="agent_reminder",
                target_ref_id="agent-1",
            ),
            now_iso="2026-03-14T12:00:00Z",
        )
        member_task = create_task_definition(
            self.db,
            actor=self.admin_actor,
            payload=ScheduledTaskDefinitionCreate(
                household_id=self.household.id,
                owner_scope="member",
                owner_member_id=self.user_member.id,
                code="member-heartbeat-check",
                name="鎴愬憳鐘舵€佹鏌?,
                trigger_type="heartbeat",
                heartbeat_interval_seconds=1800,
                target_type="agent_reminder",
                target_ref_id="agent-2",
            ),
            now_iso="2026-03-14T12:00:00Z",
        )
        self.db.commit()

        self.assertEqual("household", household_task.owner_scope)
        self.assertIsNone(household_task.owner_member_id)
        self.assertEqual("member", member_task.owner_scope)
        self.assertEqual(self.user_member.id, member_task.owner_member_id)
        self.assertEqual("2026-03-14T13:00:00Z", household_task.next_run_at)
        self.assertEqual("2026-03-14T12:30:00Z", member_task.next_heartbeat_at)

    def test_non_admin_cannot_create_household_task_or_other_member_task(self) -> None:
        with self.assertRaises(Exception):
            create_task_definition(
                self.db,
                actor=self.user_actor,
                payload=ScheduledTaskDefinitionCreate(
                    household_id=self.household.id,
                    owner_scope="household",
                    code="blocked-household-task",
                    name="涓嶈鎴愬姛",
                    trigger_type="schedule",
                    schedule_type="daily",
                    schedule_expr="08:00",
                    target_type="agent_reminder",
                    target_ref_id="agent-1",
                ),
            )
        with self.assertRaises(Exception):
            create_task_definition(
                self.db,
                actor=self.user_actor,
                payload=ScheduledTaskDefinitionCreate(
                    household_id=self.household.id,
                    owner_scope="member",
                    owner_member_id=self.admin_member.id,
                    code="blocked-other-member-task",
                    name="涓嶈鎴愬姛",
                    trigger_type="heartbeat",
                    heartbeat_interval_seconds=600,
                    target_type="agent_reminder",
                    target_ref_id="agent-1",
                ),
            )

    def test_idempotency_key_is_stable_and_worker_creates_runs(self) -> None:
        schedule_task = create_task_definition(
            self.db,
            actor=self.admin_actor,
            payload=ScheduledTaskDefinitionCreate(
                household_id=self.household.id,
                owner_scope="household",
                code="due-schedule-task",
                name="鍒扮偣浠诲姟",
                trigger_type="schedule",
                schedule_type="interval",
                schedule_expr="300",
                target_type="agent_reminder",
                target_ref_id="agent-1",
            ),
            now_iso="2026-03-14T12:00:00Z",
        )
        heartbeat_task = create_task_definition(
            self.db,
            actor=self.admin_actor,
            payload=ScheduledTaskDefinitionCreate(
                household_id=self.household.id,
                owner_scope="member",
                owner_member_id=self.user_member.id,
                code="due-heartbeat-task",
                name="鍒扮偣宸℃",
                trigger_type="heartbeat",
                heartbeat_interval_seconds=120,
                target_type="agent_reminder",
                target_ref_id="agent-2",
            ),
            now_iso="2026-03-14T12:00:00Z",
        )
        self.db.commit()

        key_a = build_run_idempotency_key(
            task_definition_id=schedule_task.id,
            scheduled_for="2026-03-14T12:05:00Z",
            trigger_source="schedule",
        )
        key_b = build_run_idempotency_key(
            task_definition_id=schedule_task.id,
            scheduled_for="2026-03-14T12:05:00Z",
            trigger_source="schedule",
        )
        self.assertEqual(key_a, key_b)

        schedule_runs = process_due_schedule_tick(self.db, now_iso="2026-03-14T12:05:00Z")
        heartbeat_runs = process_due_heartbeat_tick(self.db, now_iso="2026-03-14T12:02:00Z")
        self.db.commit()

        self.assertEqual(1, len(schedule_runs))
        self.assertEqual(1, len(heartbeat_runs))
        self.assertEqual("schedule", schedule_runs[0].trigger_source)
        self.assertEqual("heartbeat", heartbeat_runs[0].trigger_source)
        self.assertEqual("household", schedule_runs[0].owner_scope)
        self.assertEqual("member", heartbeat_runs[0].owner_scope)

    def test_schedule_run_dispatches_to_plugin_job_with_source_metadata(self) -> None:
        schedule_task = create_task_definition(
            self.db,
            actor=self.admin_actor,
            payload=ScheduledTaskDefinitionCreate(
                household_id=self.household.id,
                owner_scope="household",
                code="plugin-schedule-task",
                name="鎻掍欢鍚屾浠诲姟",
                trigger_type="schedule",
                schedule_type="interval",
                schedule_expr="60",
                target_type="plugin_job",
                target_ref_id="health-basic-reader",
            ),
            now_iso="2026-03-14T12:00:00Z",
        )
        self.db.commit()

        schedule_runs = process_due_schedule_tick(self.db, now_iso="2026-03-14T12:01:00Z")
        self.db.commit()

        dispatched = dispatch_task_run(self.db, task_run_id=schedule_runs[0].id)
        self.db.commit()

        from app.modules.plugin import repository as plugin_repository

        plugin_job = plugin_repository.get_plugin_job(self.db, dispatched.target_run_id or "")
        self.assertIsNotNone(plugin_job)
        assert plugin_job is not None
        self.assertEqual(schedule_task.id, plugin_job.source_task_definition_id)
        self.assertEqual(dispatched.id, plugin_job.source_task_run_id)
        self.assertEqual("succeeded", dispatched.status)
        self.assertEqual("schedule", plugin_job.trigger)

    def test_schedule_dispatch_accepts_homeassistant_connector_plugin(self) -> None:
        task = create_task_definition(
            self.db,
            actor=self.admin_actor,
            payload=ScheduledTaskDefinitionCreate(
                household_id=self.household.id,
                owner_scope="household",
                code="plugin-schedule-homeassistant",
                name="HA 璁″垝鍚屾",
                trigger_type="schedule",
                schedule_type="interval",
                schedule_expr="60",
                target_type="plugin_job",
                target_ref_id="homeassistant",
            ),
            now_iso="2026-03-14T12:00:00Z",
        )
        self.assertEqual("homeassistant", task.target_ref_id)

    def test_scheduled_task_api_filters_member_private_tasks(self) -> None:
        own_task = create_task_definition(
            self.db,
            actor=self.user_actor,
            payload=ScheduledTaskDefinitionCreate(
                household_id=self.household.id,
                owner_scope="member",
                owner_member_id=self.user_member.id,
                code="self-private-task",
                name="鑷繁鐨勪换鍔?,
                trigger_type="heartbeat",
                heartbeat_interval_seconds=600,
                target_type="agent_reminder",
                target_ref_id="agent-1",
            ),
        )
        other_task = create_task_definition(
            self.db,
            actor=self.admin_actor,
            payload=ScheduledTaskDefinitionCreate(
                household_id=self.household.id,
                owner_scope="member",
                owner_member_id=self.admin_member.id,
                code="admin-private-task",
                name="绠＄悊鍛樼鏈変换鍔?,
                trigger_type="heartbeat",
                heartbeat_interval_seconds=900,
                target_type="agent_reminder",
                target_ref_id="agent-2",
            ),
        )
        household_task = create_task_definition(
            self.db,
            actor=self.admin_actor,
            payload=ScheduledTaskDefinitionCreate(
                household_id=self.household.id,
                owner_scope="household",
                code="household-public-task",
                name="瀹跺涵鍏叡浠诲姟",
                trigger_type="schedule",
                schedule_type="interval",
                schedule_expr="1200",
                target_type="agent_reminder",
                target_ref_id="agent-3",
            ),
        )
        self.db.commit()

        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.user_session_token)
                response = await client.get(
                    "/api/v1/scheduled-tasks",
                    params={"household_id": self.household.id},
                )
                self.assertEqual(200, response.status_code)
                items = response.json()
                returned_ids = {item["id"] for item in items}
                self.assertIn(own_task.id, returned_ids)
                self.assertIn(household_task.id, returned_ids)
                self.assertNotIn(other_task.id, returned_ids)

        asyncio.run(run_case())

    def test_scheduled_task_api_rejects_non_admin_household_task_create(self) -> None:
        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.user_session_token)
                response = await client.post(
                    "/api/v1/scheduled-tasks",
                    json={
                        "household_id": self.household.id,
                        "owner_scope": "household",
                        "code": "api-blocked-household",
                        "name": "瀹跺涵浠诲姟",
                        "trigger_type": "schedule",
                        "schedule_type": "interval",
                        "schedule_expr": "300",
                        "target_type": "agent_reminder",
                        "target_ref_id": "agent-1",
                    },
                )
                self.assertEqual(403, response.status_code)

        asyncio.run(run_case())

    def test_scheduled_task_full_chain_reaches_plugin_job_and_query_endpoints(self) -> None:
        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.admin_session_token)
                create_response = await client.post(
                    "/api/v1/scheduled-tasks",
                    json={
                        "household_id": self.household.id,
                        "owner_scope": "household",
                        "code": "api-plugin-chain-task",
                        "name": "璁″垝鍚屾浠诲姟",
                        "trigger_type": "schedule",
                        "schedule_type": "interval",
                        "schedule_expr": "60",
                        "target_type": "plugin_job",
                        "target_ref_id": "health-basic-reader",
                    },
                )
                self.assertEqual(201, create_response.status_code)
                task_id = create_response.json()["id"]
                task_row = self._get_task_model(task_id)
                task_row.next_run_at = "2026-03-14T12:01:00Z"
                self.db.add(task_row)
                self.db.commit()

                runs = process_due_schedule_tick(self.db, now_iso="2026-03-14T12:01:00Z")
                self.db.commit()
                self.assertEqual(1, len(runs))

                dispatched = dispatch_task_run(self.db, task_run_id=runs[0].id)
                self.db.commit()
                self.assertEqual("succeeded", dispatched.status)
                self.assertIsNotNone(dispatched.target_run_id)

                run_response = await client.get(
                    "/api/v1/scheduled-task-runs",
                    params={"household_id": self.household.id, "task_definition_id": task_id},
                )
                self.assertEqual(200, run_response.status_code)
                run_items = run_response.json()
                self.assertEqual(1, len(run_items))
                self.assertEqual(dispatched.id, run_items[0]["id"])
                self.assertEqual(dispatched.target_run_id, run_items[0]["target_run_id"])

                plugin_job_response = await client.get(
                    f"/api/v1/plugin-jobs/{dispatched.target_run_id}",
                    params={"household_id": self.household.id},
                )
                self.assertEqual(200, plugin_job_response.status_code)
                job_detail = plugin_job_response.json()
                self.assertEqual(task_id, job_detail["job"]["source_task_definition_id"])
                self.assertEqual(dispatched.id, job_detail["job"]["source_task_run_id"])

        asyncio.run(run_case())

    def test_scheduled_task_rejects_disabled_plugin_target_and_duplicate_window_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_third_party_schedule_plugin(Path(plugin_tempdir), plugin_id="third-party-schedule-plugin")
            register_plugin_mount(
                self.db,
                household_id=self.household.id,
                payload=PluginMountCreate(
                    source_type="third_party",
                    plugin_root=str(plugin_root),
                    python_path=sys.executable,
                    working_dir=str(plugin_root),
                    timeout_seconds=20,
                ),
            )
            self.db.commit()

            task = create_task_definition(
                self.db,
                actor=self.admin_actor,
                payload=ScheduledTaskDefinitionCreate(
                    household_id=self.household.id,
                    owner_scope="household",
                    code="duplicate-window-task",
                    name="閲嶅绐楀彛浠诲姟",
                    trigger_type="schedule",
                    schedule_type="interval",
                    schedule_expr="60",
                    target_type="plugin_job",
                    target_ref_id="third-party-schedule-plugin",
                ),
                now_iso="2026-03-14T12:00:00Z",
            )
            self.db.commit()

            first_runs = process_due_schedule_tick(self.db, now_iso="2026-03-14T12:01:00Z")
            second_runs = process_due_schedule_tick(self.db, now_iso="2026-03-14T12:01:00Z")
            self.db.commit()
            self.assertEqual(1, len(first_runs))
            self.assertEqual(0, len(second_runs))

            update_plugin_mount(
                self.db,
                household_id=self.household.id,
                plugin_id="third-party-schedule-plugin",
                payload=PluginMountUpdate(enabled=False),
            )
            self.db.commit()

            dispatched = dispatch_task_run(self.db, task_run_id=first_runs[0].id)
            self.db.commit()
            task_row = self._get_task_model(task.id)
            self.assertEqual(task.id, dispatched.task_definition_id)
            self.assertEqual("failed", dispatched.status)
            self.assertEqual("scheduled_task_dispatch_failed", dispatched.error_code)
            self.assertEqual("invalid_dependency", task_row.status)

    def test_heartbeat_rule_evaluator_supports_insight_presence_and_device_summary(self) -> None:
        self._setup_context(
            guest_mode_enabled=False,
            quiet_hours_enabled=False,
            child_protection_enabled=False,
            elder_care_watch_enabled=True,
        )
        self._add_device(name="闂ㄩ攣", status="offline", controllable=1)
        self._mark_member_presence(self.child_member.id, status="home")
        self.db.commit()

        insight_task = self._create_heartbeat_task(
            code="insight-check",
            rule_type="context_insight",
            rule_config={"code": "offline_devices"},
        )
        presence_task = self._create_heartbeat_task(
            code="presence-check",
            rule_type="presence",
            rule_config={"condition": "role_present", "role": "child"},
        )
        device_task = self._create_heartbeat_task(
            code="device-check",
            rule_type="device_summary",
            rule_config={"metric": "offline", "operator": "gte", "value": 1},
        )
        self.db.commit()

        insight_definition = self._get_task_model(insight_task.id)
        presence_definition = self._get_task_model(presence_task.id)
        device_definition = self._get_task_model(device_task.id)
        insight_result = evaluate_heartbeat_rule(self.db, definition=insight_definition, now_iso="2026-03-14T12:00:00Z")
        presence_result = evaluate_heartbeat_rule(self.db, definition=presence_definition, now_iso="2026-03-14T12:00:00Z")
        device_result = evaluate_heartbeat_rule(self.db, definition=device_definition, now_iso="2026-03-14T12:00:00Z")

        self.assertEqual("matched", insight_result.status)
        self.assertEqual("matched", presence_result.status)
        self.assertEqual("matched", device_result.status)

    def test_heartbeat_tick_handles_skipped_suppressed_and_failed_results(self) -> None:
        self._setup_context(
            guest_mode_enabled=False,
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
        )
        self.db.commit()

        skipped_task = self._create_heartbeat_task(
            code="skip-task",
            rule_type="presence",
            rule_config={"condition": "nobody_home"},
            now_iso="2026-03-14T12:00:00Z",
        )
        suppressed_task = self._create_heartbeat_task(
            code="suppress-task",
            rule_type="presence",
            rule_config={"condition": "nobody_home"},
            quiet_hours_policy="suppress",
            now_iso="2026-03-14T15:00:00Z",
        )
        failed_task = self._create_heartbeat_task(
            code="failed-task",
            rule_type="presence",
            rule_config={"condition": "unknown_condition"},
            now_iso="2026-03-14T12:00:00Z",
        )
        self.db.commit()

        first_runs = process_due_heartbeat_tick(self.db, now_iso="2026-03-14T12:01:00Z")
        second_runs = process_due_heartbeat_tick(self.db, now_iso="2026-03-14T15:01:00Z")
        self.db.commit()

        self.assertIn("failed", {item.status for item in first_runs})
        self.assertIn(
            suppressed_task.id,
            {item.task_definition_id for item in second_runs if item.status == "suppressed"},
        )

        skipped_definition = self._get_task_model(skipped_task.id)
        suppressed_definition = self._get_task_model(suppressed_task.id)
        failed_definition = self._get_task_model(failed_task.id)
        self.assertEqual("skipped", skipped_definition.last_result)
        self.assertEqual("suppressed", suppressed_definition.last_result)
        self.assertEqual("failed", failed_definition.last_result)

    def test_agent_reminder_dispatch_creates_delivery_record(self) -> None:
        self._setup_context(guest_mode_enabled=False, quiet_hours_enabled=False)
        self._mark_member_presence(self.child_member.id, status="home")
        reminder_task = self._create_heartbeat_task(
            code="agent-reminder-task",
            rule_type="presence",
            rule_config={"condition": "role_present", "role": "child"},
            target_ref_id=self.agent.id,
        )
        self.db.commit()

        runs = process_due_heartbeat_tick(self.db, now_iso="2026-03-14T12:01:00Z")
        self.db.commit()
        self.assertEqual(1, len(runs))

        dispatched = dispatch_task_run(self.db, task_run_id=runs[0].id)
        self.db.commit()

        from app.modules.scheduler.models import ScheduledTaskDelivery

        delivery = self.db.get(ScheduledTaskDelivery, dispatched.target_run_id or "")
        self.assertIsNotNone(delivery)
        assert delivery is not None
        self.assertEqual(reminder_task.id, dispatched.task_definition_id)
        self.assertEqual("succeeded", dispatched.status)
        self.assertEqual("agent", delivery.recipient_type)
        self.assertEqual(self.agent.id, delivery.recipient_ref)
        self.assertEqual("delivered", delivery.status)

    def test_heartbeat_cooldown_suppresses_repeated_agent_reminder(self) -> None:
        self._setup_context(guest_mode_enabled=False, quiet_hours_enabled=False)
        self._mark_member_presence(self.child_member.id, status="home")
        self._create_heartbeat_task(
            code="cooldown-reminder-task",
            rule_type="presence",
            rule_config={"condition": "role_present", "role": "child"},
            target_ref_id=self.agent.id,
            cooldown_seconds=3600,
        )
        self.db.commit()

        first_runs = process_due_heartbeat_tick(self.db, now_iso="2026-03-14T12:01:00Z")
        self.db.commit()
        self.assertEqual(1, len(first_runs))
        first_dispatch = dispatch_task_run(self.db, task_run_id=first_runs[0].id)
        self.db.commit()
        self.assertEqual("succeeded", first_dispatch.status)

        second_runs = process_due_heartbeat_tick(self.db, now_iso="2026-03-14T12:02:00Z")
        self.db.commit()
        self.assertEqual(1, len(second_runs))
        self.assertEqual("suppressed", second_runs[0].status)
        self.assertEqual("cooldown", second_runs[0].error_code)

    def test_repeated_dispatch_failures_mark_definition_error(self) -> None:
        task = create_task_definition(
            self.db,
            actor=self.admin_actor,
            payload=ScheduledTaskDefinitionCreate(
                household_id=self.household.id,
                owner_scope="household",
                code="failing-system-notice-task",
                name="澶辫触浠诲姟",
                trigger_type="schedule",
                schedule_type="interval",
                schedule_expr="60",
                target_type="system_notice",
                target_ref_id="notice-template-1",
            ),
            now_iso="2026-03-14T12:00:00Z",
        )
        self.db.commit()

        for index in range(3):
            task_row = self._get_task_model(task.id)
            task_row.next_run_at = f"2026-03-14T12:0{index + 1}:00Z"
            self.db.add(task_row)
            self.db.commit()
            runs = process_due_schedule_tick(self.db, now_iso=f"2026-03-14T12:0{index + 1}:00Z")
            self.db.commit()
            self.assertEqual(1, len(runs))
            dispatched = dispatch_task_run(self.db, task_run_id=runs[0].id)
            self.db.commit()
            self.assertEqual("failed", dispatched.status)

        task_row = self._get_task_model(task.id)
        self.assertEqual(3, task_row.consecutive_failures)
        self.assertEqual("error", task_row.status)

    def test_conversation_draft_can_be_created_and_confirmed(self) -> None:
        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.user_session_token)
                draft_response = await client.post(
                    "/api/v1/scheduled-task-drafts/from-conversation",
                    json={
                        "household_id": self.household.id,
                        "text": "姣忓ぉ鏅氫笂涔濈偣鎻愰啋鎴戝悆鑽?,
                    },
                )
                self.assertEqual(200, draft_response.status_code)
                draft = draft_response.json()
                self.assertTrue(draft["can_confirm"])
                self.assertEqual("awaiting_confirm", draft["status"])

                confirm_response = await client.post(
                    f"/api/v1/scheduled-task-drafts/{draft['draft_id']}/confirm",
                    json={},
                )
                self.assertEqual(200, confirm_response.status_code)
                result = confirm_response.json()
                self.assertTrue(result["task_id"])

                task_response = await client.get(
                    f"/api/v1/scheduled-tasks/{result['task_id']}",
                )
                self.assertEqual(200, task_response.status_code)
                task = task_response.json()
                self.assertEqual("member", task["owner_scope"])
                self.assertEqual(self.user_member.id, task["owner_member_id"])
                self.assertEqual("21:00", task["schedule_expr"])

        asyncio.run(run_case())

    def test_conversation_draft_missing_fields_requires_followup(self) -> None:
        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.user_session_token)
                draft_response = await client.post(
                    "/api/v1/scheduled-task-drafts/from-conversation",
                    json={
                        "household_id": self.household.id,
                        "text": "鎻愰啋鎴戝悆鑽?,
                    },
                )
                self.assertEqual(200, draft_response.status_code)
                draft = draft_response.json()
                self.assertFalse(draft["can_confirm"])
                self.assertIn("schedule_expr", draft["missing_fields"])

                confirm_response = await client.post(
                    f"/api/v1/scheduled-task-drafts/{draft['draft_id']}/confirm",
                    json={"schedule_expr": "21:00", "name": "鍚冭嵂"},
                )
                self.assertEqual(200, confirm_response.status_code)
                result = confirm_response.json()
                self.assertTrue(result["task_id"])

        asyncio.run(run_case())

    def test_stage3_checkpoint_rule_to_agent_and_draft_to_task_chains(self) -> None:
        transport = httpx.ASGITransport(app=app)

        async def run_agent_chain() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.admin_session_token)
                create_response = await client.post(
                    "/api/v1/scheduled-tasks",
                    json={
                        "household_id": self.household.id,
                        "owner_scope": "household",
                        "code": "stage3-agent-reminder-checkpoint",
                        "name": "鍎跨鍦ㄥ鎻愰啋",
                        "trigger_type": "heartbeat",
                        "heartbeat_interval_seconds": 60,
                        "target_type": "agent_reminder",
                        "target_ref_id": self.agent.id,
                        "rule_type": "presence",
                        "rule_config": {"condition": "role_present", "role": "child"},
                        "cooldown_seconds": 3600,
                        "quiet_hours_policy": "suppress",
                    },
                )
                self.assertEqual(201, create_response.status_code)
                task_id = create_response.json()["id"]

            self._setup_context(guest_mode_enabled=False, quiet_hours_enabled=False)
            self._mark_member_presence(self.child_member.id, status="home")

            task_row = self._get_task_model(task_id)
            task_row.next_heartbeat_at = "2026-03-14T12:01:00Z"
            self.db.add(task_row)
            self.db.commit()

            first_runs = process_due_heartbeat_tick(self.db, now_iso="2026-03-14T12:01:00Z")
            self.db.commit()
            self.assertEqual(1, len(first_runs))
            dispatched = dispatch_task_run(self.db, task_run_id=first_runs[0].id)
            self.db.commit()
            self.assertEqual("succeeded", dispatched.status)

            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.admin_session_token)
                runs_response = await client.get(
                    "/api/v1/scheduled-task-runs",
                    params={"household_id": self.household.id, "task_definition_id": task_id},
                )
                self.assertEqual(200, runs_response.status_code)
                run_items = runs_response.json()
                self.assertEqual(1, len(run_items))
                self.assertEqual("succeeded", run_items[0]["status"])

            self._setup_context(guest_mode_enabled=False, quiet_hours_enabled=False)
            task_row = self._get_task_model(task_id)
            task_row.next_heartbeat_at = "2026-03-14T12:02:00Z"
            self.db.add(task_row)
            self.db.commit()
            cooldown_runs = process_due_heartbeat_tick(self.db, now_iso="2026-03-14T12:02:00Z")
            self.db.commit()
            self.assertEqual(1, len(cooldown_runs))
            self.assertEqual("suppressed", cooldown_runs[0].status)
            self.assertEqual("cooldown", cooldown_runs[0].error_code)

            self._setup_context(guest_mode_enabled=False, quiet_hours_enabled=True, quiet_hours_start="22:00", quiet_hours_end="07:00")
            task_row = self._get_task_model(task_id)
            task_row.next_heartbeat_at = "2026-03-14T15:01:00Z"
            self.db.add(task_row)
            self.db.commit()
            suppressed_runs = process_due_heartbeat_tick(self.db, now_iso="2026-03-14T15:01:00Z")
            self.db.commit()
            self.assertEqual(1, len(suppressed_runs))
            self.assertEqual("suppressed", suppressed_runs[0].status)

        async def run_draft_chain() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.user_session_token)
                draft_response = await client.post(
                    "/api/v1/scheduled-task-drafts/from-conversation",
                    json={
                        "household_id": self.household.id,
                        "text": "姣忓ぉ鏅氫笂涔濈偣鎻愰啋鎴戝悆鑽?,
                    },
                )
                self.assertEqual(200, draft_response.status_code)
                draft = draft_response.json()
                self.assertTrue(draft["can_confirm"])

                confirm_response = await client.post(
                    f"/api/v1/scheduled-task-drafts/{draft['draft_id']}/confirm",
                    json={},
                )
                self.assertEqual(200, confirm_response.status_code)
                confirmed_task_id = confirm_response.json()["task_id"]

                list_response = await client.get(
                    "/api/v1/scheduled-tasks",
                    params={"household_id": self.household.id},
                )
                self.assertEqual(200, list_response.status_code)
                returned_ids = {item["id"] for item in list_response.json()}
                self.assertIn(confirmed_task_id, returned_ids)

        asyncio.run(run_agent_chain())
        asyncio.run(run_draft_chain())

    def _setup_context(
        self,
        *,
        guest_mode_enabled: bool,
        quiet_hours_enabled: bool,
        quiet_hours_start: str = "22:00",
        quiet_hours_end: str = "07:00",
        child_protection_enabled: bool = True,
        elder_care_watch_enabled: bool = True,
    ) -> None:
        upsert_context_config(
            self.db,
            household_id=self.household.id,
            payload=ContextConfigUpsert(
                guest_mode_enabled=guest_mode_enabled,
                quiet_hours_enabled=quiet_hours_enabled,
                quiet_hours_start=quiet_hours_start,
                quiet_hours_end=quiet_hours_end,
                child_protection_enabled=child_protection_enabled,
                elder_care_watch_enabled=elder_care_watch_enabled,
            ),
            actor=self.actor_context,
        )

    def _mark_member_presence(self, member_id: str, *, status: str) -> None:
        payload = {"status": status}
        ingest_presence_event(
            self.db,
            PresenceEventCreate(
                household_id=self.household.id,
                member_id=member_id,
                room_id=self.living_room.id if status == "home" else None,
                source_type="sensor",
                source_ref=f"presence-{member_id}",
                confidence=0.95,
                payload=payload,
                occurred_at="2026-03-14T12:00:00Z",
            ),
        )

    def _add_device(self, *, name: str, status: str, controllable: int) -> None:
        self.db.add(
            Device(
                id=new_uuid(),
                household_id=self.household.id,
                room_id=self.living_room.id,
                name=name,
                device_type="lock",
                vendor="demo",
                status=status,
                controllable=controllable,
            )
        )

    def _create_heartbeat_task(
        self,
        *,
        code: str,
        rule_type: RuleType,
        rule_config: dict,
        quiet_hours_policy: Literal["allow", "suppress", "delay"] = "allow",
        now_iso: str = "2026-03-14T12:00:00Z",
        target_ref_id: str = "agent-1",
        cooldown_seconds: int = 0,
    ):
        return create_task_definition(
            self.db,
            actor=self.admin_actor,
            payload=ScheduledTaskDefinitionCreate(
                household_id=self.household.id,
                owner_scope="household",
                code=code,
                name=code,
                trigger_type="heartbeat",
                heartbeat_interval_seconds=60,
                target_type="agent_reminder",
                target_ref_id=target_ref_id,
                rule_type=rule_type,
                rule_config=rule_config,
                cooldown_seconds=cooldown_seconds,
                quiet_hours_policy=quiet_hours_policy,
            ),
            now_iso=now_iso,
        )

    def _get_task_model(self, task_id: str):
        from app.modules.scheduler.models import ScheduledTaskDefinition

        row = self.db.get(ScheduledTaskDefinition, task_id)
        self.assertIsNotNone(row)
        assert row is not None
        return row

    def _create_third_party_schedule_plugin(self, root: Path, *, plugin_id: str) -> Path:
        plugin_root = root / plugin_id
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "绗笁鏂硅鍒掓彃浠?,
                    "version": "0.1.0",
                    "types": ["connector"],
                    "permissions": ["health.read"],
                    "risk_level": "low",
                    "triggers": ["manual", "schedule"],
                    "entrypoints": {"connector": "plugin.connector.sync"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package_dir / "connector.py").write_text(
            "def sync(payload=None):\n"
            "    data = payload or {}\n"
            "    return {'source': 'third-party-schedule-plugin', 'records': [], 'echo': data}\n",
            encoding="utf-8",
        )
        return plugin_root

