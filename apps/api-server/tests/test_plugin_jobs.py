import unittest
from pathlib import Path
import tempfile
import json
import sys
import asyncio

from alembic import command
from alembic.config import Config
import httpx
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
import app.db.session as db_session_module
from app.core.config import settings
from app.main import app
from app.modules.account.schemas import BootstrapAccountCompleteRequest
from app.modules.account.service import authenticate_account, complete_bootstrap_account, create_account_session, ensure_pending_household_bootstrap_accounts
from app.modules.agent.schemas import AgentCreate, AgentPluginMemoryCheckpointRequest
from app.modules.agent.service import arun_agent_plugin_memory_checkpoint, create_agent
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.realtime.connection_manager import realtime_connection_manager
from app.modules.plugin import repository
from app.modules.plugin.job_notifier import publish_plugin_job_updates
from app.modules.plugin.agent_bridge import invoke_agent_plugin
from app.modules.plugin.job_worker import (
    claim_next_plugin_job,
    enqueue_plugin_execution_job,
    execute_plugin_job,
    recover_plugin_jobs,
    run_plugin_job_worker_cycle,
)
from app.modules.plugin.job_service import (
    PluginJobStateError,
    create_plugin_job,
    create_plugin_job_notification,
    list_allowed_plugin_job_actions,
    mark_plugin_job_attempt_failed,
    mark_plugin_job_attempt_succeeded,
    record_plugin_job_response,
    requeue_plugin_job,
    start_plugin_job_attempt,
)
from app.modules.plugin.schemas import AgentPluginInvokeRequest, PluginExecutionRequest, PluginJobCreate, PluginJobResponseCreate, PluginMountCreate, PluginStateUpdateRequest
from app.modules.plugin.service import register_plugin_mount, set_household_plugin_enabled


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent_messages.append(payload)


class PluginJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        self._previous_worker_enabled = settings.plugin_job_worker_enabled

        db_path = Path(self._tempdir.name) / "test.db"
        settings.database_url = f"sqlite:///{db_path}"
        settings.plugin_job_worker_enabled = False

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(settings.database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self._previous_session_local = db_session_module.SessionLocal
        db_session_module.SessionLocal = self.SessionLocal
        self.db: Session = self.SessionLocal()
        self.builtin_root = Path(__file__).resolve().parents[1] / "app" / "plugins" / "builtin"
        ensure_pending_household_bootstrap_accounts(self.db)
        self.household = create_household(
            self.db,
            HouseholdCreate(name="Plugin Job Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="妈妈", role="admin"),
        )
        self.db.commit()
        bootstrap = authenticate_account(self.db, "user", "user")
        account = complete_bootstrap_account(
            self.db,
            actor=bootstrap,
            payload=BootstrapAccountCompleteRequest(
                household_id=self.household.id,
                member_id=self.member.id,
                username="plugin_owner",
                password="owner123",
            ),
        )
        _, self.session_token = create_account_session(self.db, account.id)
        self.agent = create_agent(
            self.db,
            household_id=self.household.id,
            payload=AgentCreate(
                display_name="笨笨",
                agent_type="butler",
                self_identity="我是笨笨",
                role_summary="家庭助手",
                created_by="test",
            ),
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        db_session_module.SessionLocal = self._previous_session_local
        settings.database_url = self._previous_database_url
        settings.plugin_job_worker_enabled = self._previous_worker_enabled
        self._tempdir.cleanup()

    def test_plugin_job_tables_exist_and_idempotency_reuses_existing_job(self) -> None:
        inspector = inspect(self.engine)
        table_names = set(inspector.get_table_names())
        self.assertTrue({"plugin_jobs", "plugin_job_attempts", "plugin_job_notifications", "plugin_job_responses"}.issubset(table_names))

        first = create_plugin_job(
            self.db,
            payload=PluginJobCreate(
                household_id=self.household.id,
                plugin_id="health-basic-reader",
                plugin_type="connector",
                trigger="manual",
                request_payload={"scope": "daily"},
                payload_summary={"scope": "daily"},
                idempotency_key="job-001",
                max_attempts=2,
            ),
        )
        second = create_plugin_job(
            self.db,
            payload=PluginJobCreate(
                household_id=self.household.id,
                plugin_id="health-basic-reader",
                plugin_type="connector",
                trigger="manual",
                request_payload={"scope": "daily"},
                idempotency_key="job-001",
                max_attempts=2,
            ),
        )
        notification = create_plugin_job_notification(
            self.db,
            job_id=first.id,
            notification_type="state_changed",
            channel="in_app",
            payload={"status": first.status},
        )
        self.db.commit()

        self.assertEqual(first.id, second.id)
        self.assertEqual("queued", first.status)
        self.assertEqual(first.id, notification.job_id)
        self.assertEqual(1, len(repository.list_plugin_jobs(self.db, household_id=self.household.id)))
        self.assertEqual(2, len(repository.list_plugin_job_notifications(self.db, job_id=first.id)))

    def test_plugin_job_state_machine_handles_retry_then_success(self) -> None:
        job = create_plugin_job(
            self.db,
            payload=PluginJobCreate(
                household_id=self.household.id,
                plugin_id="health-basic-reader",
                plugin_type="connector",
                trigger="manual",
                request_payload={"scope": "weekly"},
                max_attempts=2,
            ),
        )

        first_attempt = start_plugin_job_attempt(self.db, job_id=job.id, worker_id="worker-a")
        retried = mark_plugin_job_attempt_failed(
            self.db,
            attempt_id=first_attempt.id,
            error_code="job_execution_failed",
            error_message="上游暂时不可用",
            retryable=True,
        )
        self.assertEqual("retry_waiting", retried.status)

        queued_again = requeue_plugin_job(self.db, job_id=job.id)
        self.assertEqual("queued", queued_again.status)

        second_attempt = start_plugin_job_attempt(self.db, job_id=job.id, worker_id="worker-a")
        succeeded = mark_plugin_job_attempt_succeeded(
            self.db,
            attempt_id=second_attempt.id,
            output_summary={"records": 3},
        )
        self.db.commit()

        attempts = repository.list_plugin_job_attempts(self.db, job_id=job.id)
        self.assertEqual("succeeded", succeeded.status)
        self.assertEqual(2, succeeded.current_attempt)
        self.assertEqual(2, len(attempts))
        self.assertEqual(["failed", "succeeded"], [item.status for item in attempts])

        with self.assertRaises(PluginJobStateError):
            requeue_plugin_job(self.db, job_id=job.id)

    def test_waiting_response_job_accepts_legal_actions_and_rejects_illegal_transition(self) -> None:
        job = create_plugin_job(
            self.db,
            payload=PluginJobCreate(
                household_id=self.household.id,
                plugin_id="homeassistant-device-action",
                plugin_type="action",
                trigger="agent-action",
                request_payload={"target_ref": "door-lock"},
                max_attempts=3,
            ),
        )

        attempt = start_plugin_job_attempt(self.db, job_id=job.id, worker_id="worker-b")
        waiting = mark_plugin_job_attempt_failed(
            self.db,
            attempt_id=attempt.id,
            error_code="job_response_required",
            error_message="需要人工确认",
            response_required=True,
            response_deadline_at="2026-03-15T00:00:00Z",
        )
        self.assertEqual("waiting_response", waiting.status)
        self.assertEqual(["retry", "confirm", "cancel", "provide_input"], list_allowed_plugin_job_actions(self.db, job_id=job.id))

        with self.assertRaises(PluginJobStateError):
            start_plugin_job_attempt(self.db, job_id=job.id, worker_id="worker-c")

        response, queued = record_plugin_job_response(
            self.db,
            job_id=job.id,
            payload=PluginJobResponseCreate(
                action="confirm",
                actor_type="member",
                actor_id="member-001",
                payload={"confirmed": True},
            ),
        )
        self.db.commit()

        responses = repository.list_plugin_job_responses(self.db, job_id=job.id)
        self.assertEqual("confirm", response.action)
        self.assertEqual("queued", queued.status)
        self.assertEqual(1, len(responses))

    def test_worker_cycle_executes_queued_job_and_prevents_double_claim(self) -> None:
        job = enqueue_plugin_execution_job(
            self.db,
            household_id=self.household.id,
            request=PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": self.member.id},
                trigger="manual",
            ),
        )
        self.db.commit()

        first_claim = claim_next_plugin_job(self.db, worker_id="worker-a")
        second_claim = claim_next_plugin_job(self.db, worker_id="worker-b")
        self.db.commit()

        self.assertIsNotNone(first_claim)
        self.assertIsNone(second_claim)
        claimed_job = first_claim
        assert claimed_job is not None

        asyncio.run(execute_plugin_job(job.id, worker_id="worker-a"))

        job_row = repository.get_plugin_job(self.db, job.id)
        assert job_row is not None
        run_rows = repository.list_plugin_runs(self.db, household_id=self.household.id, plugin_id="health-basic-reader")
        self.assertEqual("running", claimed_job.status)
        self.assertEqual("succeeded", job_row.status)
        self.assertEqual(1, len(run_rows))
        self.assertEqual("success", run_rows[0].status)

    def test_worker_cycle_retries_then_marks_terminal_failure(self) -> None:
        job = enqueue_plugin_execution_job(
            self.db,
            household_id=self.household.id,
            request=PluginExecutionRequest(
                plugin_id="not-exists-plugin",
                plugin_type="connector",
                payload={},
                trigger="manual",
            ),
            max_attempts=2,
        )
        self.db.commit()

        asyncio.run(run_plugin_job_worker_cycle(worker_id="worker-r1"))
        self.db.expire_all()
        first_round = repository.get_plugin_job(self.db, job.id)
        assert first_round is not None
        self.assertEqual("retry_waiting", first_round.status)
        self.assertIsNotNone(first_round.retry_after_at)

        first_round.retry_after_at = "2000-01-01T00:00:00Z"
        self.db.commit()

        asyncio.run(run_plugin_job_worker_cycle(worker_id="worker-r2"))
        self.db.expire_all()
        final_job = repository.get_plugin_job(self.db, job.id)
        assert final_job is not None
        attempts = repository.list_plugin_job_attempts(self.db, job_id=job.id)
        self.assertEqual("failed", final_job.status)
        self.assertEqual(2, final_job.current_attempt)
        self.assertEqual(2, len(attempts))

    def test_recovery_marks_stale_running_job_for_retry(self) -> None:
        job = enqueue_plugin_execution_job(
            self.db,
            household_id=self.household.id,
            request=PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": self.member.id},
                trigger="manual",
            ),
            max_attempts=2,
        )
        claimed = claim_next_plugin_job(self.db, worker_id="worker-recover")
        assert claimed is not None
        job_row = repository.get_plugin_job(self.db, job.id)
        assert job_row is not None
        job_row.updated_at = "2000-01-01T00:00:00Z"
        self.db.commit()

        recovered_jobs = recover_plugin_jobs(self.db)
        self.db.commit()

        recovered_job = repository.get_plugin_job(self.db, job.id)
        assert recovered_job is not None
        self.assertEqual(1, len(recovered_jobs))
        self.assertEqual("retry_waiting", recovered_job.status)
        self.assertIsNotNone(recovered_job.retry_after_at)

    def test_worker_marks_timeout_when_plugin_execution_exceeds_limit(self) -> None:
        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_slow_third_party_plugin(Path(plugin_tempdir), plugin_id="slow-sync-plugin")
            register_plugin_mount(
                self.db,
                household_id=self.household.id,
                payload=PluginMountCreate(
                    source_type="third_party",
                    plugin_root=str(plugin_root),
                    python_path=sys.executable,
                    working_dir=str(plugin_root),
                    timeout_seconds=1,
                ),
            )
            self.db.commit()

            job = enqueue_plugin_execution_job(
                self.db,
                household_id=self.household.id,
                request=PluginExecutionRequest(
                    plugin_id="slow-sync-plugin",
                    plugin_type="connector",
                    payload={"member_id": self.member.id},
                    trigger="manual",
                ),
                max_attempts=1,
            )
            self.db.commit()

            asyncio.run(run_plugin_job_worker_cycle(worker_id="worker-timeout"))
            self.db.expire_all()
            final_job = repository.get_plugin_job(self.db, job.id)
            assert final_job is not None
            attempts = repository.list_plugin_job_attempts(self.db, job_id=job.id)
            self.assertEqual("failed", final_job.status)
            self.assertEqual("job_timeout", final_job.last_error_code)
            self.assertEqual("timed_out", attempts[-1].status)

    def _create_slow_third_party_plugin(self, root: Path, *, plugin_id: str) -> Path:
        plugin_root = root / plugin_id
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "慢速同步插件",
                    "version": "0.1.0",
                    "types": ["connector", "memory-ingestor"],
                    "permissions": ["health.read", "memory.write.observation"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                    "entrypoints": {
                        "connector": "plugin.connector.sync",
                        "memory_ingestor": "plugin.ingestor.transform",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package_dir / "connector.py").write_text(
            "import time\n"
            "def sync(payload=None):\n"
            "    time.sleep(2)\n"
            "    return {'records': []}\n",
            encoding="utf-8",
        )
        (package_dir / "ingestor.py").write_text(
            "def transform(payload=None):\n"
            "    return []\n",
            encoding="utf-8",
        )
        return plugin_root

    def test_plugin_job_api_detail_list_and_response(self) -> None:
        waiting_job = create_plugin_job(
            self.db,
            payload=PluginJobCreate(
                household_id=self.household.id,
                plugin_id="homeassistant-device-action",
                plugin_type="action",
                trigger="agent-action",
                request_payload={"target_ref": "door-lock"},
                max_attempts=2,
            ),
        )
        attempt = start_plugin_job_attempt(self.db, job_id=waiting_job.id, worker_id="worker-api")
        mark_plugin_job_attempt_failed(
            self.db,
            attempt_id=attempt.id,
            error_code="job_response_required",
            error_message="需要人工确认",
            response_required=True,
            response_deadline_at="2026-03-16T00:00:00Z",
        )
        failed_job = create_plugin_job(
            self.db,
            payload=PluginJobCreate(
                household_id=self.household.id,
                plugin_id="health-basic-reader",
                plugin_type="connector",
                trigger="manual",
                request_payload={"scope": "api"},
                max_attempts=1,
            ),
        )
        failed_attempt = start_plugin_job_attempt(self.db, job_id=failed_job.id, worker_id="worker-api")
        mark_plugin_job_attempt_failed(
            self.db,
            attempt_id=failed_attempt.id,
            error_code="job_execution_failed",
            error_message="接口测试失败",
        )
        self.db.commit()

        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.session_token)

                detail_response = await client.get(
                    f"/api/v1/plugin-jobs/{waiting_job.id}",
                    params={"household_id": self.household.id},
                )
                self.assertEqual(200, detail_response.status_code)
                detail_payload = detail_response.json()
                self.assertEqual("waiting_response", detail_payload["job"]["status"])
                self.assertEqual(["retry", "confirm", "cancel", "provide_input"], detail_payload["allowed_actions"])
                self.assertTrue(len(detail_payload["recent_notifications"]) >= 1)

                list_response = await client.get(
                    "/api/v1/plugin-jobs",
                    params={"household_id": self.household.id, "status": "failed", "page": 1, "page_size": 10},
                )
                self.assertEqual(200, list_response.status_code)
                list_payload = list_response.json()
                self.assertEqual(1, list_payload["total"])
                self.assertEqual(failed_job.id, list_payload["items"][0]["job"]["id"])

                invalid_response = await client.post(
                    f"/api/v1/plugin-jobs/{failed_job.id}/responses",
                    params={"household_id": self.household.id},
                    json={"action": "confirm", "actor_type": "member", "actor_id": self.member.id},
                )
                self.assertEqual(409, invalid_response.status_code)

                confirm_response = await client.post(
                    f"/api/v1/plugin-jobs/{waiting_job.id}/responses",
                    params={"household_id": self.household.id},
                    json={"action": "confirm", "actor_type": "member", "actor_id": self.member.id, "payload": {"confirmed": True}},
                )
                self.assertEqual(200, confirm_response.status_code)
                confirm_payload = confirm_response.json()
                self.assertEqual("queued", confirm_payload["job"]["status"])

        asyncio.run(run_case())

    def test_plugin_job_update_event_reaches_household_websocket(self) -> None:
        job = create_plugin_job(
            self.db,
            payload=PluginJobCreate(
                household_id=self.household.id,
                plugin_id="health-basic-reader",
                plugin_type="connector",
                trigger="manual",
                request_payload={"scope": "ws"},
                max_attempts=1,
            ),
        )
        self.db.commit()

        websocket = _FakeWebSocket()
        realtime_connection_manager.register(
            household_id=self.household.id,
            session_id="conversation-session-1",
            websocket=websocket,  # type: ignore[arg-type]
        )
        try:
            asyncio.run(publish_plugin_job_updates(self.db, household_id=self.household.id, job_id=job.id))
        finally:
            realtime_connection_manager.unregister(
                household_id=self.household.id,
                session_id="conversation-session-1",
                websocket=websocket,  # type: ignore[arg-type]
            )

        notifications = repository.list_plugin_job_notifications(self.db, job_id=job.id)
        self.assertEqual("plugin.job.updated", websocket.sent_messages[-1]["type"])
        self.assertEqual(job.id, websocket.sent_messages[-1]["payload"]["job"]["id"])
        self.assertTrue(any(item.channel == "websocket" and item.delivered_at is not None for item in notifications))

    def test_create_plugin_job_endpoint_then_worker_then_query(self) -> None:
        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            websocket = _FakeWebSocket()
            realtime_connection_manager.register(
                household_id=self.household.id,
                session_id="session-job-create",
                websocket=websocket,  # type: ignore[arg-type]
            )
            try:
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    client.cookies.set(settings.auth_session_cookie_name, self.session_token)

                    create_response = await client.post(
                        "/api/v1/plugin-jobs",
                        params={"household_id": self.household.id},
                        json={
                            "plugin_id": "health-basic-reader",
                            "plugin_type": "connector",
                            "payload": {"member_id": self.member.id},
                            "trigger": "manual",
                            "idempotency_key": "api-create-001",
                        },
                    )
                    self.assertEqual(201, create_response.status_code)
                    created = create_response.json()
                    job_id = created["job"]["id"]
                    self.assertEqual("queued", created["job"]["status"])

                    await run_plugin_job_worker_cycle(worker_id="worker-e2e")

                    detail_response = await client.get(
                        f"/api/v1/plugin-jobs/{job_id}",
                        params={"household_id": self.household.id},
                    )
                    self.assertEqual(200, detail_response.status_code)
                    detail = detail_response.json()
                    self.assertEqual("succeeded", detail["job"]["status"])
                    self.assertEqual("succeeded", detail["latest_attempt"]["status"])
            finally:
                realtime_connection_manager.unregister(
                    household_id=self.household.id,
                    session_id="session-job-create",
                    websocket=websocket,  # type: ignore[arg-type]
                )

            self.assertTrue(any(message["type"] == "plugin.job.updated" for message in websocket.sent_messages))

        asyncio.run(run_case())

    def test_create_plugin_job_endpoint_returns_structured_error_when_plugin_disabled(self) -> None:
        set_household_plugin_enabled(
            self.db,
            household_id=self.household.id,
            plugin_id="health-basic-reader",
            payload=PluginStateUpdateRequest(enabled=False),
            updated_by="tester",
        )
        self.db.commit()

        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.session_token)
                response = await client.post(
                    "/api/v1/plugin-jobs",
                    params={"household_id": self.household.id},
                    json={
                        "plugin_id": "health-basic-reader",
                        "plugin_type": "connector",
                        "payload": {"member_id": self.member.id},
                        "trigger": "manual",
                    },
                )
                self.assertEqual(409, response.status_code)
                payload = response.json()
                self.assertEqual("plugin_disabled", payload["detail"]["error_code"])
                self.assertEqual("plugin_id", payload["detail"]["field"])

        asyncio.run(run_case())

    def test_existing_agent_plugin_entrypoints_now_enqueue_jobs(self) -> None:
        invoke_result = invoke_agent_plugin(
            self.db,
            household_id=self.household.id,
            agent_id=self.agent.id,
            request=AgentPluginInvokeRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": self.member.id},
                trigger="agent",
            ),
        )
        checkpoint_result = asyncio.run(
            arun_agent_plugin_memory_checkpoint(
                self.db,
                household_id=self.household.id,
                agent_id=self.agent.id,
                payload=AgentPluginMemoryCheckpointRequest(
                    plugin_id="health-basic-reader",
                    payload={"member_id": self.member.id},
                    trigger="agent-checkpoint",
                ),
            )
        )
        self.db.commit()

        invoke_job = repository.get_plugin_job(self.db, invoke_result.job_id or "")
        checkpoint_job = repository.get_plugin_job(self.db, checkpoint_result.job_id or "")
        self.assertTrue(invoke_result.queued)
        self.assertEqual("queued", invoke_result.job_status)
        self.assertIsNotNone(invoke_job)
        self.assertTrue(checkpoint_result.queued)
        self.assertEqual("queued", checkpoint_result.job_status)
        self.assertIsNotNone(checkpoint_job)


if __name__ == "__main__":
    unittest.main()
