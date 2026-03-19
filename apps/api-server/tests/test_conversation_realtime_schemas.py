import unittest

from pydantic import ValidationError

from app.modules.ai_gateway.provider_runtime import _build_agent_prompt
from app.modules.realtime.schemas import build_bootstrap_realtime_event


class ConversationRealtimeSchemasTests(unittest.TestCase):
    def test_agent_state_patch_supports_extended_profile_fields(self) -> None:
        event = build_bootstrap_realtime_event(
            event_type="agent.state_patch",
            session_id="session-1",
            request_id="request-1",
            seq=1,
            payload={
                "display_name": "新名字",
                "role_summary": "新的角色摘要",
                "intro_message": "新的欢迎语",
                "speaking_style": "简洁直接",
                "personality_traits": ["冷静", "冷静", "有条理"],
                "service_focus": ["问答", "提醒", "问答"],
            },
        )
        payload = event.payload
        self.assertEqual("新名字", payload.display_name)
        self.assertEqual("新的角色摘要", payload.role_summary)
        self.assertEqual("新的欢迎语", payload.intro_message)
        self.assertEqual(["冷静", "有条理"], payload.personality_traits)
        self.assertEqual(["问答", "提醒"], payload.service_focus)

    def test_agent_state_patch_rejects_empty_payload(self) -> None:
        with self.assertRaises(ValidationError):
            build_bootstrap_realtime_event(
                event_type="agent.state_patch",
                session_id="session-1",
                request_id="request-1",
                seq=1,
                payload={},
            )

    def test_agent_prompt_consumes_only_supported_member_interaction_fields(self) -> None:
        prompt = _build_agent_prompt(
            {
                "agent_runtime_context": {
                    "requester_member_cognition": {
                        "display_address": "老爸",
                        "communication_style": "简短直接",
                        "prompt_notes": "先给结论再解释",
                        "closeness_level": "CLOSENESS_TOKEN",
                        "service_priority": "PRIORITY_TOKEN",
                        "care_notes": {"hidden": "CARE_NOTES_TOKEN"},
                    }
                }
            }
        )
        self.assertIn("老爸", prompt)
        self.assertIn("简短直接", prompt)
        self.assertIn("先给结论再解释", prompt)
        self.assertNotIn("CLOSENESS_TOKEN", prompt)
        self.assertNotIn("PRIORITY_TOKEN", prompt)
        self.assertNotIn("CARE_NOTES_TOKEN", prompt)


if __name__ == "__main__":
    unittest.main()
