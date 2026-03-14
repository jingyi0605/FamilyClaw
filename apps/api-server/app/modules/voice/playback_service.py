from __future__ import annotations

from app.db.utils import new_uuid
from app.modules.voice.protocol import build_voice_command_event
from app.modules.voice.realtime_service import voice_realtime_service
from app.modules.voice.registry import voice_session_registry


class VoicePlaybackServiceError(RuntimeError):
    pass


class VoicePlaybackService:
    """播放控制先单独收口，后面快慢路径都从这里下发。"""

    async def start_text_playback(
        self,
        *,
        session_id: str,
        terminal_id: str,
        text: str,
        playback_id: str | None = None,
    ):
        session = voice_session_registry.get(session_id)
        if session is None:
            raise VoicePlaybackServiceError("语音会话不存在，无法开始播放")
        if session.terminal_id != terminal_id:
            raise VoicePlaybackServiceError("会话与终端不匹配，拒绝下发播放")

        resolved_playback_id = playback_id or new_uuid()
        seq = voice_session_registry.claim_next_seq(session_id=session_id)
        voice_session_registry.set_active_playback(session_id=session_id, playback_id=resolved_playback_id)
        event = build_voice_command_event(
            event_type="play.start",
            terminal_id=terminal_id,
            session_id=session_id,
            seq=seq,
            payload={
                "playback_id": resolved_playback_id,
                "mode": "tts_text",
                "text": text,
            },
        )
        await voice_realtime_service.send_command(event)
        return event

    async def stop_playback(
        self,
        *,
        session_id: str,
        terminal_id: str,
        playback_id: str | None = None,
        reason: str | None = None,
    ):
        seq = voice_session_registry.claim_next_seq(session_id=session_id)
        event = build_voice_command_event(
            event_type="play.stop",
            terminal_id=terminal_id,
            session_id=session_id,
            seq=seq,
            payload={"playback_id": playback_id, "reason": reason},
        )
        await voice_realtime_service.send_command(event)
        return event

    async def abort_playback(
        self,
        *,
        session_id: str,
        terminal_id: str,
        playback_id: str | None = None,
        reason: str | None = None,
    ):
        seq = voice_session_registry.claim_next_seq(session_id=session_id)
        event = build_voice_command_event(
            event_type="play.abort",
            terminal_id=terminal_id,
            session_id=session_id,
            seq=seq,
            payload={"playback_id": playback_id, "reason": reason},
        )
        await voice_realtime_service.send_command(event)
        return event


voice_playback_service = VoicePlaybackService()
