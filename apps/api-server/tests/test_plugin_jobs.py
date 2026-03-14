import unittest
from pathlib import Path
import tempfile
import json
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
import app.db.session as db_session_module
from app.core.config import settings
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin.models import PluginJob
from app.modules.plugin import repository
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
from app.modules.plugin.schemas import PluginExecutionRequest, PluginJobCreate, PluginJobResponseCreate, PluginMountCreate
from app.modules.plugin.service import register_plugin_mount


class PluginJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        db_path = Path(self._tempdir.name) / "test.db"
        settings.database_url = f"sqlite:///{db_path}"

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(settings.database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self._previous_session_local = db_session_module.SessionLocal
        db_session_module.SessionLocal = self.SessionLocal
        self.db: Session = self.SessionLocal()
        self.builtin_root = Path(__file__).resolve().parents[1] / "app" / "plugins" / "builtin"
        self.household = create_household(
            self.db,
            HouseholdCreate(name="Plugin Job Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="妈妈", role="adult"),
        )
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        db_session_module.SessionLocal = self._previous_session_local
        settings.database_url = self._previous_database_url
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
        self.assertEqual(1, len(repository.list_plugin_job_notifications(self.db, job_id=first.id)))

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

        import asyncio

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

        import asyncio

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

        recovered_count = recover_plugin_jobs(self.db)
        self.db.commit()

        recovered_job = repository.get_plugin_job(self.db, job.id)
        assert recovered_job is not None
        self.assertEqual(1, recovered_count)
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

            import asyncio

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


if __name__ == "__main__":
    unittest.main()
