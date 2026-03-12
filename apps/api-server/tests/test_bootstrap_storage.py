import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.db.utils import new_uuid, utc_now_iso
from app.modules.agent import repository as agent_repository
from app.modules.agent.models import (
    FamilyAgentBootstrapMessage,
    FamilyAgentBootstrapRequest,
    FamilyAgentBootstrapSession,
)
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household


class BootstrapStorageTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_bootstrap_session_message_and_request_tables_support_basic_read_write(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Storage Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        session = FamilyAgentBootstrapSession(
            id=new_uuid(),
            household_id=household.id,
            status="collecting",
            pending_field="display_name",
            draft_json="{}",
            transcript_json="[]",
            current_request_id=None,
            last_event_seq=0,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        agent_repository.add_bootstrap_session(self.db, session)
        self.db.flush()

        user_message = FamilyAgentBootstrapMessage(
            id=new_uuid(),
            session_id=session.id,
            request_id="request-1",
            role="user",
            content="我想叫阿福。",
            seq=1,
            created_at=utc_now_iso(),
        )
        assistant_message = FamilyAgentBootstrapMessage(
            id=new_uuid(),
            session_id=session.id,
            request_id="request-1",
            role="assistant",
            content="好，我先记下这个名字。",
            seq=2,
            created_at=utc_now_iso(),
        )
        agent_repository.add_bootstrap_message(self.db, user_message)
        agent_repository.add_bootstrap_message(self.db, assistant_message)
        agent_repository.add_bootstrap_request(
            self.db,
            FamilyAgentBootstrapRequest(
                id="request-1",
                session_id=session.id,
                status="succeeded",
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                error_code=None,
                started_at=utc_now_iso(),
                finished_at=utc_now_iso(),
            ),
        )
        self.db.commit()

        message_rows = agent_repository.list_bootstrap_messages(self.db, session_id=session.id)
        request_rows = agent_repository.list_bootstrap_requests(self.db, session_id=session.id)

        self.assertEqual([1, 2], [item.seq for item in message_rows])
        self.assertEqual(["user", "assistant"], [item.role for item in message_rows])
        self.assertEqual(1, len(request_rows))
        self.assertEqual("succeeded", request_rows[0].status)
        self.assertEqual(user_message.id, request_rows[0].user_message_id)
        self.assertEqual(3, agent_repository.get_next_bootstrap_message_seq(self.db, session_id=session.id))


if __name__ == "__main__":
    unittest.main()
