from __future__ import annotations

import logging

from app.core.blocking import BlockingCallPolicy, run_blocking_db
from app.db.session import SessionLocal
from app.modules.voice.binding_service import VoiceTerminalBindingSnapshot, get_voice_terminal_binding_by_terminal_id
from app.modules.voice.protocol import VoiceCommandEvent, build_voice_command_event

logger = logging.getLogger(__name__)


def build_binding_refresh_event(
    *,
    binding: VoiceTerminalBindingSnapshot,
    reason: str | None = None,
) -> VoiceCommandEvent:
    return build_voice_command_event(
        event_type="binding.refresh",
        terminal_id=binding.terminal_id,
        session_id=f"binding-refresh:{binding.terminal_id}",
        seq=0,
        payload={
            "reason": reason,
            "binding": binding.model_dump(mode="json"),
        },
    )


async def refresh_voice_terminal_binding_state(
    *,
    terminal_id: str,
    reason: str | None = None,
) -> bool:
    binding = await run_blocking_db(
        lambda db: get_voice_terminal_binding_by_terminal_id(db, terminal_id=terminal_id),
        session_factory=SessionLocal,
        policy=BlockingCallPolicy(
            label="voice.binding.refresh_snapshot",
            kind="sync_db",
            timeout_seconds=5.0,
        ),
        commit=False,
        logger=logger,
        context={"terminal_id": terminal_id, "reason": reason},
    )
    if binding is None:
        return False

    from app.modules.voice.realtime_service import voice_realtime_service

    try:
        await voice_realtime_service.send_command(
            build_binding_refresh_event(binding=binding, reason=reason),
        )
    except LookupError:
        logger.warning(
            "skip binding refresh because terminal is offline terminal_id=%s reason=%s",
            terminal_id,
            reason,
        )
        return False

    logger.info(
        "dispatched binding refresh terminal_id=%s reason=%s",
        terminal_id,
        reason,
    )

    return True
