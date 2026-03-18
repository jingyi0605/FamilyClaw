import unittest

from app.modules.voiceprint.models import VoiceprintEnrollment
from app.modules.voiceprint.prompt_service import build_voiceprint_round_prompt_events


class VoiceprintPromptServiceTests(unittest.TestCase):
    def test_build_round_prompt_events_contains_tts_and_beep(self) -> None:
        enrollment = VoiceprintEnrollment(
            id="enrollment-1",
            household_id="household-1",
            member_id="member-1",
            terminal_id="terminal-1",
            status="recording",
            expected_phrase="春眠不觉晓",
            sample_goal=3,
            sample_count=1,
        )

        events = build_voiceprint_round_prompt_events(
            enrollment,
            prompt_key="recorded-1",
        )

        self.assertEqual(2, len(events))
        self.assertEqual("play.start", events[0].type)
        self.assertEqual("tts_text", events[0].payload.mode)
        self.assertIn("第 2 轮", events[0].payload.text or "")
        self.assertEqual("play.start", events[1].type)
        self.assertEqual("audio_bytes", events[1].payload.mode)
        self.assertTrue(events[1].payload.audio_base64)

    def test_build_retry_prompt_reuses_current_round(self) -> None:
        enrollment = VoiceprintEnrollment(
            id="enrollment-2",
            household_id="household-1",
            member_id="member-2",
            terminal_id="terminal-1",
            status="pending",
            expected_phrase="明月松间照",
            sample_goal=3,
            sample_count=0,
        )

        events = build_voiceprint_round_prompt_events(
            enrollment,
            prompt_key="rejected-0",
            retry=True,
        )

        self.assertIn("没有录成功", events[0].payload.text or "")
        self.assertIn("第 1 轮", events[0].payload.text or "")


if __name__ == "__main__":
    unittest.main()
