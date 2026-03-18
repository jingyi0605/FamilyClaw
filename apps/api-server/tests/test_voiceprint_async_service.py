import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.modules.voiceprint.async_service import (
    async_identify_household_member_by_voiceprint,
    async_process_voiceprint_enrollment_sample,
)
from app.modules.voiceprint.service import (
    VoiceprintEnrollmentProcessResult,
    VoiceprintIdentificationRead,
)


class VoiceprintAsyncServiceTests(unittest.TestCase):
    def test_async_enrollment_uses_blocking_db_helper(self) -> None:
        expected = VoiceprintEnrollmentProcessResult(
            outcome="recorded",
            enrollment=object(),  # type: ignore[arg-type]
        )

        with patch(
            "app.modules.voiceprint.async_service.run_blocking_db",
            new=AsyncMock(return_value=expected),
        ) as run_blocking_db_mock:
            result = asyncio.run(
                async_process_voiceprint_enrollment_sample(
                    enrollment_id="enrollment-1",
                    transcript_text="我是妈妈",
                    artifact_id="artifact-1",
                    artifact_path="C:/tmp/artifact-1.wav",
                    artifact_sha256="sha-1",
                    sample_rate=16000,
                    channels=1,
                    sample_width=2,
                    duration_ms=2200,
                )
            )

        self.assertIs(expected, result)
        run_blocking_db_mock.assert_awaited_once()
        self.assertTrue(run_blocking_db_mock.await_args.kwargs["commit"])
        self.assertEqual("voice.voiceprint.enrollment", run_blocking_db_mock.await_args.kwargs["policy"].label)

    def test_async_identify_uses_blocking_db_helper(self) -> None:
        expected = VoiceprintIdentificationRead(
            provider="sherpa_onnx_wespeaker_resnet34",
            status="matched",
            threshold=0.75,
            reason="matched",
            member_id="member-1",
            profile_id="profile-1",
            score=0.91,
            candidate_count=1,
        )

        with patch(
            "app.modules.voiceprint.async_service.run_blocking_db",
            new=AsyncMock(return_value=expected),
        ) as run_blocking_db_mock:
            result = asyncio.run(
                async_identify_household_member_by_voiceprint(
                    household_id="household-1",
                    artifact_path="C:/tmp/query.wav",
                )
            )

        self.assertIs(expected, result)
        run_blocking_db_mock.assert_awaited_once()
        self.assertFalse(run_blocking_db_mock.await_args.kwargs["commit"])
        self.assertEqual("voice.voiceprint.identify", run_blocking_db_mock.await_args.kwargs["policy"].label)


if __name__ == "__main__":
    unittest.main()
