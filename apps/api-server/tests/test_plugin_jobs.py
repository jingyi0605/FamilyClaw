import unittest
from pathlib import Path
import tempfile

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin import repository
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
from app.modules.plugin.schemas import PluginJobCreate, PluginJobResponseCreate


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
        self.db: Session = self.SessionLocal()
        self.household = create_household(
            self.db,
            HouseholdCreate(name="Plugin Job Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
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


if __name__ == "__main__":
    unittest.main()
