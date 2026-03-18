import unittest

from app.modules.context.schemas import ContextOverviewDeviceSummary
from app.modules.conversation.device_context_summary import (
    ConversationDeviceContextSummary,
    ConversationDeviceContextTarget,
)
from app.modules.family_qa.schemas import (
    FamilyQaQueryRequest,
    QaFactDeviceState,
    QaMemorySummary,
    QaPermissionScope,
    QaReminderSummary,
    QaSceneSummary,
    QaFactViewRead,
)
from app.modules.family_qa.service import _answer_from_fact_view, _build_qa_generation_payload, PreparedFamilyQaTurn


class FamilyQaDeviceContextTests(unittest.TestCase):
    def test_answer_from_fact_view_prefers_contextual_device_for_followup_question(self) -> None:
        fact_view = self._build_fact_view()
        device_context_summary = self._build_device_context_summary()

        answer_type, answer_text, confidence, facts, suggestions = _answer_from_fact_view(
            fact_view,
            "它现在什么状态？",
            device_context_summary=device_context_summary,
        )

        self.assertEqual("device_status", answer_type)
        self.assertIn("书房灯", answer_text)
        self.assertGreaterEqual(confidence, 0.9)
        self.assertTrue(facts[0].extra["from_device_context_summary"])
        self.assertIn("继续控制这个设备", suggestions)

    def test_answer_from_fact_view_does_not_force_context_for_device_inventory_question(self) -> None:
        fact_view = self._build_fact_view()
        device_context_summary = self._build_device_context_summary()

        answer_type, answer_text, _, _, _ = _answer_from_fact_view(
            fact_view,
            "家里都有什么设备？",
            device_context_summary=device_context_summary,
        )

        self.assertEqual("device_status", answer_type)
        self.assertIn("书房小爱音箱", answer_text)

    def test_build_qa_generation_payload_includes_device_context_summary(self) -> None:
        prepared = PreparedFamilyQaTurn(
            payload=FamilyQaQueryRequest(
                household_id="household-1",
                requester_member_id="member-1",
                question="它现在什么状态？",
                context={},
            ),
            effective_agent=type("EffectiveAgent", (), {"id": "agent-1", "agent_type": "butler", "display_name": "管家"})(),
            fact_view=self._build_fact_view(),
            answer_type="device_status",
            answer_text="书房灯当前状态是开启。",
            confidence=0.9,
            facts=[],
            suggestions=[],
            agent_runtime_context={},
            conversation_history=[],
            device_context_summary=self._build_device_context_summary(),
        )

        payload = _build_qa_generation_payload(prepared)

        self.assertIn("书房灯", str(payload["device_context_summary_text"]))
        self.assertEqual("书房灯", payload["device_context_summary"]["resume_target"]["device_name"])

    def _build_fact_view(self) -> QaFactViewRead:
        return QaFactViewRead(
            household_id="household-1",
            generated_at="2026-03-17T21:00:00Z",
            requester_member_id="member-1",
            active_member=None,
            member_states=[],
            room_occupancy=[],
            device_summary=ContextOverviewDeviceSummary(
                total=2,
                active=2,
                offline=0,
                inactive=0,
                controllable=2,
                controllable_active=2,
                controllable_offline=0,
            ),
            device_states=[
                QaFactDeviceState(
                    device_id="device-speaker",
                    name="书房小爱音箱",
                    device_type="speaker",
                    room_id="room-study",
                    room_name="书房",
                    status="active",
                    controllable=True,
                ),
                QaFactDeviceState(
                    device_id="device-light",
                    name="书房灯",
                    device_type="light",
                    room_id="room-study",
                    room_name="书房",
                    status="on",
                    controllable=True,
                ),
            ],
            reminder_summary=QaReminderSummary(total_tasks=0, enabled_tasks=0, pending_runs=0, recent_items=[]),
            scene_summary=QaSceneSummary(total_templates=0, enabled_templates=0, running_executions=0, recent_items=[]),
            memory_summary=QaMemorySummary(),
            permission_scope=QaPermissionScope(),
        )

    def _build_device_context_summary(self) -> ConversationDeviceContextSummary:
        target = ConversationDeviceContextTarget(
            source_type="device_state",
            message_id="message-1",
            request_id="request-1",
            created_at="2026-03-17T20:59:00Z",
            device_id="device-light",
            device_name="书房灯",
            device_type="light",
            room_id="room-study",
            room_name="书房",
            status="on",
        )
        return ConversationDeviceContextSummary(
            latest_target=target,
            latest_query_target=target,
            resume_target=target,
            recent_targets=[target],
            unique_device_ids=["device-light"],
            can_resume_control=True,
            resume_reason="最近对话上下文只指向一个设备，可以承接省略式设备控制。",
        )


if __name__ == "__main__":
    unittest.main()
