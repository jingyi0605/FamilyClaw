import unittest
from types import SimpleNamespace

from app.modules.conversation.orchestrator import (
    ConversationIntent,
    ConversationIntentDetection,
    ConversationIntentLabel,
    ConversationLane,
    select_conversation_lane,
)


class _FakeSemanticRouter:
    def __init__(self, *, lane: str, confidence: float, target_kind: str, reason: str) -> None:
        self._payload = SimpleNamespace(
            enabled=True,
            lane=lane,
            confidence=confidence,
            target_kind=target_kind,
            reason=reason,
            requires_clarification=False,
        )

    def route(self, user_message: str):
        _ = user_message
        return self._payload


class ConversationLaneFoundationTests(unittest.TestCase):
    def test_select_conversation_lane_hits_fast_action_from_semantic_router(self) -> None:
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
            semantic_router=_FakeSemanticRouter(
                lane="fast_action",
                confidence=0.91,
                target_kind="device_action",
                reason="命中设备控制 descriptor。",
            ),
            semantic_router_enabled=True,
        )

        self.assertEqual(ConversationLane.FAST_ACTION, selection.lane)
        self.assertEqual("device_action", selection.target_kind)
        self.assertEqual("semantic_router", selection.source)
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
            semantic_router_enabled=False,
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
                semantic_router_enabled=False,
            )

            self.assertEqual(ConversationLane.FREE_CHAT, selection.lane)
            self.assertEqual("none", selection.target_kind)
            self.assertFalse(selection.requires_clarification)


if __name__ == "__main__":
    unittest.main()
