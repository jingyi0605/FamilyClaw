from __future__ import annotations

import base64
import logging
import math
import struct
from uuid import uuid4

from app.modules.voice.protocol import VoiceCommandEvent, build_voice_command_event
from app.modules.voiceprint.models import VoiceprintEnrollment
from app.modules.voiceprint.prompt_types import VoiceprintPromptEnrollmentSnapshot

logger = logging.getLogger(__name__)

_PROMPT_BEEP_SAMPLE_RATE = 16000
_PROMPT_BEEP_DURATION_SECONDS = 0.18
_PROMPT_BEEP_FREQUENCY_HZ = 880.0
_PROMPT_BEEP_VOLUME = 0.45
_PROMPT_BEEP_AUDIO_BASE64: str | None = None


def build_voiceprint_round_prompt_text(
    enrollment: VoiceprintEnrollment | VoiceprintPromptEnrollmentSnapshot,
    *,
    retry: bool = False,
) -> str:
    current_round = get_voiceprint_current_round(enrollment)
    if retry:
        return (
            f"刚才这一轮没有录成功。请重新准备第 {current_round} 轮。"
            "三秒后在滴的一声后，开始朗读屏幕上的句子。"
        )
    return (
        f"请准备第 {current_round} 轮声纹录入。"
        "三秒后在滴的一声后，开始朗读屏幕上的句子。"
    )


def get_voiceprint_current_round(enrollment: VoiceprintEnrollment | VoiceprintPromptEnrollmentSnapshot) -> int:
    sample_goal = max(int(enrollment.sample_goal or 1), 1)
    sample_count = max(int(enrollment.sample_count or 0), 0)
    if enrollment.status == "processing":
        return min(sample_goal, sample_count)
    return min(sample_goal, sample_count + 1)


def build_voiceprint_round_prompt_events(
    enrollment: VoiceprintEnrollment | VoiceprintPromptEnrollmentSnapshot,
    *,
    prompt_key: str,
    retry: bool = False,
) -> list[VoiceCommandEvent]:
    session_id = f"voiceprint-prompt:{enrollment.id}:{prompt_key}"
    playback_token = uuid4().hex
    return [
        build_voice_command_event(
            event_type="play.start",
            terminal_id=enrollment.terminal_id,
            session_id=session_id,
            seq=1,
            payload={
                "playback_id": f"{playback_token}-tts",
                "mode": "tts_text",
                "text": build_voiceprint_round_prompt_text(enrollment, retry=retry),
            },
        ),
        build_voice_command_event(
            event_type="play.start",
            terminal_id=enrollment.terminal_id,
            session_id=session_id,
            seq=2,
            payload={
                "playback_id": f"{playback_token}-beep",
                "mode": "audio_bytes",
                "audio_base64": _get_prompt_beep_audio_base64(),
                "content_type": "audio/pcm;rate=16000;channels=1;format=s16le",
            },
        ),
    ]


async def send_voiceprint_round_prompt(
    enrollment: VoiceprintEnrollment | VoiceprintPromptEnrollmentSnapshot,
    *,
    prompt_key: str,
    retry: bool = False,
) -> bool:
    terminal_id = (enrollment.terminal_id or "").strip()
    if not terminal_id:
        return False

    from app.modules.voice.realtime_service import voice_realtime_service

    try:
        for event in build_voiceprint_round_prompt_events(
            enrollment,
            prompt_key=prompt_key,
            retry=retry,
        ):
            await voice_realtime_service.send_command(event)
    except LookupError:
        logger.warning(
            "skip voiceprint round prompt because terminal is offline terminal_id=%s enrollment_id=%s prompt_key=%s",
            terminal_id,
            enrollment.id,
            prompt_key,
        )
        return False

    logger.info(
        "dispatched voiceprint round prompt terminal_id=%s enrollment_id=%s prompt_key=%s retry=%s",
        terminal_id,
        enrollment.id,
        prompt_key,
        retry,
    )

    return True


def _get_prompt_beep_audio_base64() -> str:
    global _PROMPT_BEEP_AUDIO_BASE64
    if _PROMPT_BEEP_AUDIO_BASE64 is None:
        _PROMPT_BEEP_AUDIO_BASE64 = _build_beep_audio_base64()
    return _PROMPT_BEEP_AUDIO_BASE64


def _build_beep_audio_base64() -> str:
    total_frames = int(_PROMPT_BEEP_SAMPLE_RATE * _PROMPT_BEEP_DURATION_SECONDS)
    frames = bytearray()
    for frame_index in range(total_frames):
        progress = frame_index / total_frames
        envelope = min(progress / 0.15, 1.0) * min((1.0 - progress) / 0.2, 1.0)
        sample_value = int(
            32767
            * _PROMPT_BEEP_VOLUME
            * max(envelope, 0.0)
            * math.sin(2.0 * math.pi * _PROMPT_BEEP_FREQUENCY_HZ * (frame_index / _PROMPT_BEEP_SAMPLE_RATE))
        )
        frames.extend(struct.pack("<h", sample_value))
    return base64.b64encode(bytes(frames)).decode("ascii")
