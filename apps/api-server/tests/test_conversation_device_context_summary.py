import unittest

from app.db.utils import dump_json, new_uuid, utc_now_iso
from app.modules.conversation.device_context_summary import (
    ConversationDeviceContextSummary,
    build_conversation_device_context_summary,
)
from app.modules.conversation.models import ConversationMessage


class ConversationDeviceContextSummaryTests(unittest.TestCase):
    def test_build_summary_prefers_recent_execution_target(self) -> None:
        device_id = new_uuid()
        query_message = self._build_assistant_message(
            facts=[
                {
                    "type": "device_state",
                    "label": "书房灯",
                    "source": "devices",
                    "extra": {
                        "device_id": device_id,
                        "device_type": "light",
                        "status": "on",
                    },
                }
            ]
        )
        execution_message = self._build_assistant_message(
            facts=[
                {
                    "type": "fast_action_receipt",
                    "label": "设备动作执行结果",
                    "source": "conversation_fast_action",
                    "extra": {
                        "device": {
                            "id": device_id,
                            "name": "书房灯",
                            "device_type": "light",
                        },
                        "entity_id": "light.study_main",
                        "action": "turn_off",
                    },
                }
            ]
        )

        summary = build_conversation_device_context_summary([query_message, execution_message])

        self.assertTrue(summary.can_resume_control)
        self.assertIsNotNone(summary.resume_target)
        assert summary.resume_target is not None
        self.assertEqual("书房灯", summary.resume_target.device_name)
        self.assertEqual("turn_off", summary.resume_target.action)
        self.assertEqual("fast_action_receipt", summary.resume_target.source_type)

    def test_build_summary_marks_multiple_recent_devices_as_ambiguous(self) -> None:
        summary = build_conversation_device_context_summary(
            [
                self._build_assistant_message(
                    facts=[
                        {
                            "type": "device_state",
                            "label": "书房灯",
                            "source": "devices",
                            "extra": {
                                "device_id": new_uuid(),
                                "device_type": "light",
                                "status": "on",
                            },
                        }
                    ]
                ),
                self._build_assistant_message(
                    facts=[
                        {
                            "type": "device_state",
                            "label": "卧室灯",
                            "source": "devices",
                            "extra": {
                                "device_id": new_uuid(),
                                "device_type": "light",
                                "status": "off",
                            },
                        }
                    ]
                ),
            ]
        )

        self.assertFalse(summary.can_resume_control)
        self.assertIsNone(summary.resume_target)
        self.assertIn("2 个设备", summary.resume_reason)

    def test_summary_can_round_trip_from_payload(self) -> None:
        device_id = new_uuid()
        summary = build_conversation_device_context_summary(
            [
                self._build_assistant_message(
                    facts=[
                        {
                            "type": "device_state",
                            "label": "书房灯",
                            "source": "devices",
                            "extra": {
                                "device_id": device_id,
                                "device_type": "light",
                                "status": "on",
                            },
                        }
                    ]
                )
            ]
        )

        restored = ConversationDeviceContextSummary.from_payload(summary.to_payload())

        self.assertTrue(restored.can_resume_control)
        self.assertIsNotNone(restored.resume_target)
        assert restored.resume_target is not None
        self.assertEqual(device_id, restored.resume_target.device_id)
        self.assertEqual("书房灯", restored.resume_target.device_name)

    def test_build_summary_extracts_pending_confirmation_target(self) -> None:
        device_id = new_uuid()
        summary = build_conversation_device_context_summary(
            [
                self._build_assistant_message(
                    facts=[
                        {
                            "type": "fast_action_confirmation_request",
                            "label": "书房灯",
                            "source": "conversation_fast_action",
                            "extra": {
                                "device_id": device_id,
                                "device_name": "书房灯",
                                "device_type": "light",
                                "entity_id": "light.study_main",
                                "action": "turn_off",
                                "confidence": 0.82,
                            },
                        }
                    ]
                )
            ]
        )

        self.assertTrue(summary.can_resume_confirmation)
        self.assertIsNotNone(summary.latest_confirmation_target)
        assert summary.latest_confirmation_target is not None
        self.assertEqual("turn_off", summary.latest_confirmation_target.action)
        self.assertEqual("light.study_main", summary.latest_confirmation_target.entity_id)

    def _build_assistant_message(self, *, facts: list[dict]) -> ConversationMessage:
        now = utc_now_iso()
        return ConversationMessage(
            id=new_uuid(),
            session_id=new_uuid(),
            request_id=new_uuid(),
            seq=1,
            role="assistant",
            message_type="text",
            content="test",
            status="completed",
            effective_agent_id=None,
            ai_provider_code=None,
            ai_trace_id=None,
            degraded=False,
            error_code=None,
            facts_json=dump_json(facts),
            suggestions_json=dump_json([]),
            created_at=now,
            updated_at=now,
        )


if __name__ == "__main__":
    unittest.main()
