import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.conversation.orchestrator import detect_conversation_intent


class IntentRecognitionInvokeTests(unittest.TestCase):
    @patch("app.modules.llm_task.invoke.invoke_capability")
    def test_detect_conversation_intent_uses_intent_recognition_capability_and_agent_context(self, invoke_capability_mock) -> None:
        invoke_capability_mock.return_value = SimpleNamespace(
            normalized_output={
                "text": (
                    "<output>"
                    '{"primary_intent":"free_chat","secondary_intents":[],"confidence":0.9,"reason":"普通闲聊","candidate_actions":[]}'
                    "</output>"
                )
            },
            provider_code="mock-provider",
            attempts=[],
        )

        session = SimpleNamespace(
            session_mode="family_chat",
            household_id="household-1",
            active_agent_id="agent-1",
        )

        detect_conversation_intent(
            db=SimpleNamespace(),
            session=session,
            message="帮我看看今天家里怎么样",
        )

        request = invoke_capability_mock.call_args.args[1]
        self.assertEqual("intent_recognition", request.capability)
        self.assertEqual("agent-1", request.agent_id)


if __name__ == "__main__":
    unittest.main()
