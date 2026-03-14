import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext
from app.core.config import settings
from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.account.schemas import HouseholdAccountCreateRequest
from app.modules.account.service import AuthenticatedActor, create_household_account_with_binding
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.models import ConversationMessage
from app.modules.conversation.proposal_pipeline import ProposalPipeline, build_turn_proposal_context
from app.modules.conversation.schemas import ConversationSessionCreate
from app.modules.conversation.service import confirm_conversation_proposal, create_conversation_session, dismiss_conversation_proposal
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.llm_task.output_models import ProposalBatchExtractionOutput
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.scheduler import draft_service as scheduler_draft_service
from app.modules.scheduler.draft_service import preview_draft_from_conversation
from app.modules.scheduler.schemas import ScheduledTaskDefinitionCreate, ScheduledTaskDraftFromConversationRequest
from app.modules.scheduler.service import create_task_definition, get_task_definition_read_or_404, list_task_definitions


class ConversationScheduledTaskProposalTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        db_path = Path(self._tempdir.name) / "test.db"
        settings.database_url = f"sqlite:///{db_path}"

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(settings.database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db: Session = self.SessionLocal()
        scheduler_draft_service._DRAFT_STORE.clear()

        self.household = create_household(self.db, HouseholdCreate(name="Conversation Scheduler Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"))
        self.admin_member = create_member(self.db, MemberCreate(household_id=self.household.id, name="管理员", role="admin"))
        self.user_member = create_member(self.db, MemberCreate(household_id=self.household.id, name="妈妈", role="adult"))
        self.agent = create_agent(
            self.db,
            household_id=self.household.id,
            payload=AgentCreate(
                display_name="笨笨",
                agent_type="butler",
                self_identity="我是家庭管家",
                role_summary="负责家庭提醒",
                personality_traits=["稳重"],
                service_focus=["提醒"],
                default_entry=True,
            ),
        )
        self.admin_account, _ = create_household_account_with_binding(
            self.db,
            HouseholdAccountCreateRequest(household_id=self.household.id, member_id=self.admin_member.id, username="conversation_admin", password="admin123", must_change_password=False),
        )
        self.user_account, _ = create_household_account_with_binding(
            self.db,
            HouseholdAccountCreateRequest(household_id=self.household.id, member_id=self.user_member.id, username="conversation_user", password="user123", must_change_password=False),
        )
        self.db.commit()

        self.admin_actor = self._build_actor_context(self.admin_account.id, self.admin_account.username, self.admin_member.id, "admin")
        self.user_actor = self._build_actor_context(self.user_account.id, self.user_account.username, self.user_member.id, "adult")
        self.admin_auth_actor = self._build_authenticated_actor(self.admin_account.id, self.admin_account.username, self.admin_member.id, "admin")
        self.user_auth_actor = self._build_authenticated_actor(self.user_account.id, self.user_account.username, self.user_member.id, "adult")

    def tearDown(self) -> None:
        scheduler_draft_service._DRAFT_STORE.clear()
        self.db.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_confirm_creates_scheduled_task(self) -> None:
        item = self._create_scheduled_task_proposal("每天晚上九点提醒我吃药", actor=self.user_actor, authenticated_actor=self.user_auth_actor)
        result = confirm_conversation_proposal(self.db, proposal_item_id=item.id, actor=self.user_actor)
        self.db.commit()

        tasks = list_task_definitions(self.db, actor=self.user_auth_actor, household_id=self.household.id)
        self.assertEqual("scheduled_task_create", result.item.proposal_kind)
        self.assertEqual(1, len(tasks))
        self.assertEqual(result.affected_target_id, tasks[0].id)

    def test_dismiss_does_not_create_scheduled_task(self) -> None:
        item = self._create_scheduled_task_proposal("每天晚上九点提醒我吃药", actor=self.user_actor, authenticated_actor=self.user_auth_actor)
        result = dismiss_conversation_proposal(self.db, proposal_item_id=item.id, actor=self.user_actor)
        self.db.commit()

        self.assertEqual("dismissed", result.item.status)
        self.assertEqual([], list_task_definitions(self.db, actor=self.user_auth_actor, household_id=self.household.id))

    def test_incomplete_draft_cannot_confirm(self) -> None:
        item = self._create_scheduled_task_proposal("提醒我吃药", actor=self.user_actor, authenticated_actor=self.user_auth_actor)
        with self.assertRaises(HTTPException) as context:
            confirm_conversation_proposal(self.db, proposal_item_id=item.id, actor=self.user_actor)
        self.assertEqual(409, context.exception.status_code)

    def test_preview_parses_cross_member_owner(self) -> None:
        draft = preview_draft_from_conversation(
            self.db,
            actor=self.admin_auth_actor,
            payload=ScheduledTaskDraftFromConversationRequest(household_id=self.household.id, text="每天晚上九点提醒妈妈吃药"),
        )
        self.assertEqual(self.user_member.id, draft.owner_member_id)
        self.assertTrue(draft.can_confirm)

    def test_preview_parses_presence_rule_task(self) -> None:
        draft = preview_draft_from_conversation(
            self.db,
            actor=self.admin_auth_actor,
            payload=ScheduledTaskDraftFromConversationRequest(household_id=self.household.id, text="如果孩子到家就提醒我收衣服"),
        )
        self.assertEqual("heartbeat", draft.draft_payload["trigger_type"])
        self.assertEqual("presence", draft.draft_payload["rule_type"])

    def test_confirm_creates_once_task(self) -> None:
        item = self._create_scheduled_task_proposal("明天上午10点提醒我开会", actor=self.user_actor, authenticated_actor=self.user_auth_actor)
        result = confirm_conversation_proposal(self.db, proposal_item_id=item.id, actor=self.user_actor)
        self.db.commit()

        task = get_task_definition_read_or_404(self.db, actor=self.user_auth_actor, task_id=str(result.affected_target_id))
        self.assertEqual("once", task.schedule_type)

    def test_confirm_pause_resume_update_delete_task_proposal(self) -> None:
        task = create_task_definition(
            self.db,
            actor=self.user_auth_actor,
            payload=ScheduledTaskDefinitionCreate(
                household_id=self.household.id,
                owner_scope="member",
                owner_member_id=self.user_member.id,
                code="medicine-task",
                name="吃药提醒",
                trigger_type="schedule",
                schedule_type="daily",
                schedule_expr="21:00",
                target_type="agent_reminder",
                target_ref_id=self.agent.id,
            ),
        )
        self.db.commit()

        pause_item = self._create_scheduled_task_proposal("把吃药提醒暂停", actor=self.user_actor, authenticated_actor=self.user_auth_actor)
        pause_result = confirm_conversation_proposal(self.db, proposal_item_id=pause_item.id, actor=self.user_actor)
        self.db.commit()
        paused = get_task_definition_read_or_404(self.db, actor=self.user_auth_actor, task_id=pause_result.affected_target_id or task.id)
        self.assertFalse(paused.enabled)

        resume_item = self._create_scheduled_task_proposal("把吃药提醒恢复", actor=self.user_actor, authenticated_actor=self.user_auth_actor)
        resume_result = confirm_conversation_proposal(self.db, proposal_item_id=resume_item.id, actor=self.user_actor)
        self.db.commit()
        resumed = get_task_definition_read_or_404(self.db, actor=self.user_auth_actor, task_id=resume_result.affected_target_id or task.id)
        self.assertTrue(resumed.enabled)

        update_item = self._create_scheduled_task_proposal("把吃药提醒改成明天上午10点提醒我开会", actor=self.user_actor, authenticated_actor=self.user_auth_actor)
        update_result = confirm_conversation_proposal(self.db, proposal_item_id=update_item.id, actor=self.user_actor)
        self.db.commit()
        updated = get_task_definition_read_or_404(self.db, actor=self.user_auth_actor, task_id=update_result.affected_target_id or task.id)
        self.assertEqual("once", updated.schedule_type)

        delete_item = self._create_scheduled_task_proposal("把吃药提醒删除", actor=self.user_actor, authenticated_actor=self.user_auth_actor)
        confirm_conversation_proposal(self.db, proposal_item_id=delete_item.id, actor=self.user_actor)
        self.db.commit()
        tasks = list_task_definitions(self.db, actor=self.user_auth_actor, household_id=self.household.id)
        self.assertEqual([], tasks)

    def _create_scheduled_task_proposal(self, text: str, *, actor: ActorContext, authenticated_actor: AuthenticatedActor):
        session_read = create_conversation_session(self.db, payload=ConversationSessionCreate(household_id=self.household.id, active_agent_id=self.agent.id), actor=actor)
        session = conversation_repository.get_session(self.db, session_read.id)
        assert session is not None
        now = utc_now_iso()
        user_message = ConversationMessage(id=new_uuid(), session_id=session.id, request_id="req-scheduled-task", seq=1, role="user", message_type="text", content=text, status="completed", effective_agent_id=self.agent.id, ai_provider_code=None, ai_trace_id=None, degraded=False, error_code=None, facts_json=dump_json([]), suggestions_json=dump_json([]), created_at=now, updated_at=now)
        assistant_message = ConversationMessage(id=new_uuid(), session_id=session.id, request_id="req-scheduled-task", seq=2, role="assistant", message_type="text", content="我先给你整理成计划任务提案。", status="completed", effective_agent_id=self.agent.id, ai_provider_code=None, ai_trace_id=None, degraded=False, error_code=None, facts_json=dump_json([]), suggestions_json=dump_json([]), created_at=now, updated_at=now)
        conversation_repository.add_message(self.db, user_message)
        conversation_repository.add_message(self.db, assistant_message)
        self.db.flush()

        result = ProposalPipeline(extractor=lambda db, turn_context, household_id: ProposalBatchExtractionOutput()).run(
            self.db,
            session=session,
            request_id="req-scheduled-task",
            turn_context=build_turn_proposal_context(
                db=self.db,
                session=session,
                request_id="req-scheduled-task",
                authenticated_actor=authenticated_actor,
                user_message=user_message,
                assistant_message=assistant_message,
                conversation_history_excerpt=[],
                lane_result={"lane": "free_chat", "target_kind": "none"},
                main_reply_summary=assistant_message.content,
            ),
            persist=True,
        )
        item = conversation_repository.get_proposal_item(self.db, result.item_ids[0])
        assert item is not None
        _ = load_json(item.payload_json)
        return item

    def _build_actor_context(self, account_id: str, username: str, member_id: str, member_role: str) -> ActorContext:
        return ActorContext(role=member_role, actor_type="member", actor_id=member_id, account_id=account_id, account_type="household", account_status="active", username=username, household_id=self.household.id, member_id=member_id, member_role=member_role, is_authenticated=True)

    def _build_authenticated_actor(self, account_id: str, username: str, member_id: str, member_role: str) -> AuthenticatedActor:
        return AuthenticatedActor(account_id=account_id, username=username, account_type="household", account_status="active", household_id=self.household.id, member_id=member_id, member_role=member_role, must_change_password=False)


if __name__ == "__main__":
    unittest.main()
