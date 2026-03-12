import unittest

from pydantic import ValidationError

from app.modules.realtime import build_bootstrap_realtime_event


class RealtimeProtocolTests(unittest.TestCase):
    def test_agent_chunk_requires_pure_display_text(self) -> None:
        event = build_bootstrap_realtime_event(
            event_type="agent.chunk",
            session_id="session-1",
            request_id="request-1",
            seq=1,
            payload={"text": "你好，我会先了解你的偏好。"},
        )

        self.assertEqual("agent.chunk", event.type)
        self.assertEqual("你好，我会先了解你的偏好。", event.payload.text)

        with self.assertRaises(ValidationError):
            build_bootstrap_realtime_event(
                event_type="agent.chunk",
                session_id="session-1",
                request_id="request-1",
                seq=2,
                payload={"text": "你好\n---\n<config>{}</config>"},
            )

    def test_agent_state_patch_requires_structured_fields(self) -> None:
        event = build_bootstrap_realtime_event(
            event_type="agent.state_patch",
            session_id="session-1",
            request_id="request-1",
            seq=3,
            payload={"display_name": "阿福", "personality_traits": ["细心", "细心", "稳重"]},
        )

        self.assertEqual("阿福", event.payload.display_name)
        self.assertEqual(["细心", "稳重"], event.payload.personality_traits)

        with self.assertRaises(ValidationError):
            build_bootstrap_realtime_event(
                event_type="agent.state_patch",
                session_id="session-1",
                request_id="request-1",
                seq=4,
                payload={},
            )

    def test_request_scoped_events_require_request_id(self) -> None:
        with self.assertRaises(ValidationError):
            build_bootstrap_realtime_event(
                event_type="agent.done",
                session_id="session-1",
                seq=5,
                payload={},
            )


if __name__ == "__main__":
    unittest.main()
