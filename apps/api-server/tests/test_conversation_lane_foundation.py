import unittest
from types import SimpleNamespace

from app.modules.conversation.orchestrator import (
    ConversationIntent,
    ConversationIntentDetection,
    ConversationIntentLabel,
    ConversationLane,
    ConversationOrchestratorResult,
    select_conversation_lane,
)
from app.modules.conversation.service import _build_orchestrator_debug_payload


class ConversationLaneFoundationTests(unittest.TestCase):
    def test_select_conversation_lane_hits_fast_action_from_hard_signal(self) -> None:
        detection = ConversationIntentDetection(
            primary_intent=ConversationIntentLabel.FREE_CHAT,
            route_intent=ConversationIntent.FREE_CHAT,
            confidence=0.72,
            reason="旧意图识别先按 free_chat 处理。",
        )
        session = SimpleNamespace(session_mode="normal")

        selection = select_conversation_lane(
            session=session,
            message="把客厅灯关掉",
            detection=detection,
        )

        self.assertEqual(ConversationLane.FAST_ACTION, selection.lane)
        self.assertEqual("device_action", selection.target_kind)
        self.assertEqual("hard_signal", selection.source)
        self.assertIs(detection.lane_selection, selection)

    def test_select_conversation_lane_maps_structured_qa_to_realtime_query(self) -> None:
        detection = ConversationIntentDetection(
            primary_intent=ConversationIntentLabel.STRUCTURED_QA,
            route_intent=ConversationIntent.STRUCTURED_QA,
            confidence=0.88,
            reason="当前问题需要实时查询。",
        )
        session = SimpleNamespace(session_mode="normal")

        selection = select_conversation_lane(
            session=session,
            message="现在家里有人吗",
            detection=detection,
        )

        self.assertEqual(ConversationLane.REALTIME_QUERY, selection.lane)
        self.assertEqual("state_query", selection.target_kind)
        self.assertEqual("intent_mapping", selection.source)

    def test_select_conversation_lane_keeps_config_memory_reminder_under_free_chat_lane(self) -> None:
        for route_intent, primary_intent in (
            (ConversationIntent.CONFIG_EXTRACTION, ConversationIntentLabel.CONFIG_CHANGE),
            (ConversationIntent.MEMORY_EXTRACTION, ConversationIntentLabel.MEMORY_WRITE),
            (ConversationIntent.REMINDER_EXTRACTION, ConversationIntentLabel.REMINDER_CREATE),
        ):
            detection = ConversationIntentDetection(
                primary_intent=primary_intent,
                route_intent=route_intent,
                confidence=0.8,
                reason="旧链路仍然会落到提取分支。",
            )
            session = SimpleNamespace(session_mode="normal")

            selection = select_conversation_lane(
                session=session,
                message="以后提醒我时先发消息",
                detection=detection,
            )

            self.assertEqual(ConversationLane.FREE_CHAT, selection.lane)
            self.assertEqual("none", selection.target_kind)
            self.assertFalse(selection.requires_clarification)


class ConversationDebugPayloadTests(unittest.TestCase):
    def test_build_orchestrator_debug_payload_distinguishes_final_and_detected_intent(self) -> None:
        detection = ConversationIntentDetection(
            primary_intent=ConversationIntentLabel.CONFIG_CHANGE,
            route_intent=ConversationIntent.CONFIG_EXTRACTION,
            confidence=0.9,
            reason="用户要改名字。",
        )
        result = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="好的",
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code=None,
            effective_agent_id=None,
            effective_agent_name=None,
            intent_detection=detection,
        )

        payload = _build_orchestrator_debug_payload(result)

        self.assertEqual("free_chat", payload["final_result_intent"])
        self.assertEqual("config_extraction", payload["detected_route_intent"])
        self.assertNotIn("route_intent", payload)


if __name__ == "__main__":
    unittest.main()
