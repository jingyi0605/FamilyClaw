"""管家引导服务 - 通过 AI 对话创建首个管家。"""
import logging
from typing import Any, cast

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.agent import repository
from app.modules.agent.models import FamilyAgentBootstrapMessage, FamilyAgentBootstrapSession
from app.modules.agent.schemas import (
    AgentCreate,
    AgentDetailRead,
    ButlerBootstrapConfirm,
    ButlerBootstrapDraft,
    ButlerBootstrapField,
    ButlerBootstrapMessageCreate,
    ButlerBootstrapMessageRead,
    ButlerBootstrapStatus,
    ButlerBootstrapSessionRead,
)
from app.modules.agent.service import create_agent
from app.modules.ai_gateway.service import resolve_capability_route
from app.modules.llm_task import invoke_llm, stream_llm
from app.modules.llm_task.output_models import ButlerBootstrapOutput
from app.modules.member import service as member_service
from app.modules.realtime.connection_manager import RealtimeConnectionManager
from app.modules.realtime.schemas import build_bootstrap_realtime_event

REQUIRED_PROVIDER_CAPABILITY = "qa_generation"
BOOTSTRAP_FIELD_ORDER: tuple[ButlerBootstrapField, ...] = (
    "display_name",
    "personality_traits",
    "speaking_style",
)
logger = logging.getLogger(__name__)


def start_butler_bootstrap_session(
    db: Session,
    *,
    household_id: str,
) -> ButlerBootstrapSessionRead:
    """启动管家引导会话。"""
    _ensure_bootstrap_allowed(db, household_id=household_id)

    existing_session = repository.get_latest_bootstrap_session(
        db,
        household_id=household_id,
        include_completed=False,
    )
    if existing_session is not None:
        return _to_session_read(db, existing_session)

    return restart_butler_bootstrap_session(db, household_id=household_id)


def restart_butler_bootstrap_session(
    db: Session,
    *,
    household_id: str,
) -> ButlerBootstrapSessionRead:
    """重新开始管家引导会话。"""
    _ensure_bootstrap_allowed(db, household_id=household_id)

    existing_session = repository.get_latest_bootstrap_session(
        db,
        household_id=household_id,
        include_completed=False,
    )
    if existing_session is not None:
        _cancel_bootstrap_session(db, session=existing_session, reason="session_restarted")

    draft = ButlerBootstrapDraft(household_id=household_id)
    assistant_message = _build_opening_message(db, household_id=household_id)
    session = FamilyAgentBootstrapSession(
        id=new_uuid(),
        household_id=household_id,
        status="collecting",
        pending_field="display_name",
        draft_json=dump_json(draft.model_dump(mode="json")) or "{}",
        transcript_json=dump_json([{"role": "assistant", "content": assistant_message}]) or "[]",
        current_request_id=None,
        last_event_seq=0,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )
    repository.add_bootstrap_session(db, session)
    db.flush()
    _append_bootstrap_message(
        db,
        session_id=session.id,
        request_id=None,
        role="assistant",
        content=assistant_message,
        created_at=session.created_at,
    )
    return _to_session_read(db, session, assistant_message=assistant_message)


def get_latest_butler_bootstrap_session(
    db: Session,
    *,
    household_id: str,
) -> ButlerBootstrapSessionRead | None:
    """读取最近一次管家引导会话。"""
    _ensure_bootstrap_allowed(db, household_id=household_id)
    session = repository.get_latest_bootstrap_session(db, household_id=household_id)
    if session is None:
        return None
    return _to_session_read(db, session)


def get_butler_bootstrap_session_snapshot(
    db: Session,
    *,
    household_id: str,
    session_id: str,
) -> ButlerBootstrapSessionRead:
    """读取指定引导会话快照，允许已完成会话。"""
    session = repository.get_bootstrap_session(db, household_id=household_id, session_id=session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="引导会话不存在")
    return _to_session_read(db, session)


async def run_butler_bootstrap_realtime_turn(
    db: Session,
    *,
    household_id: str,
    session_id: str,
    request_id: str,
    user_message: str,
    connection_manager: RealtimeConnectionManager,
) -> None:
    """通过 WebSocket 执行一轮管家引导对话。"""
    _ensure_bootstrap_allowed(db, household_id=household_id)
    session = _get_bootstrap_session(db, household_id=household_id, session_id=session_id)

    if session.status in {"completed", "cancelled"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前会话已关闭，不能继续发送消息")
    if session.current_request_id and session.current_request_id != request_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="上一轮还没结束，请稍后再试")

    message = user_message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message 不能为空")

    draft = _load_draft(session, household_id=household_id)
    transcript = _load_transcript(db, session)
    request_started_at = utc_now_iso()

    user_message_row = _append_bootstrap_message(
        db,
        session_id=session.id,
        request_id=request_id,
        role="user",
        content=message,
        created_at=request_started_at,
    )
    request_row = repository.add_bootstrap_request(
        db,
        row=_build_bootstrap_request(
            request_id=request_id,
            session_id=session.id,
            user_message_id=user_message_row.id,
            started_at=request_started_at,
        ),
    )
    session.current_request_id = request_id
    db.flush()

    await _broadcast_realtime_event(
        db,
        connection_manager=connection_manager,
        household_id=household_id,
        session=session,
        event_type="user.message.accepted",
        request_id=request_id,
        payload={},
    )

    final_text = ""
    try:
        for event in stream_llm(
            db,
            task_type="butler_bootstrap",
            variables={
                "collected_info": _format_collected_info(draft),
                "user_message": message,
                "user_context": _build_user_context(db, household_id),
            },
            household_id=household_id,
            conversation_history=transcript,
        ):
            if event.event_type == "chunk" and event.content:
                await _broadcast_realtime_event(
                    db,
                    connection_manager=connection_manager,
                    household_id=household_id,
                    session=session,
                    event_type="agent.chunk",
                    request_id=request_id,
                    payload={"text": event.content},
                )
                continue

            if event.event_type == "done" and event.result is not None:
                final_text = event.result.text.strip()

        next_draft = draft
        state_patch = _extract_bootstrap_state_patch(
            db,
            household_id=household_id,
            draft=draft,
            user_message=message,
            assistant_message=final_text,
        )
        if state_patch is not None:
            next_draft = _merge_extracted_data(draft, state_patch)
            patch_payload = _build_state_patch_payload(draft=draft, next_draft=next_draft)
            if patch_payload:
                await _broadcast_realtime_event(
                    db,
                    connection_manager=connection_manager,
                    household_id=household_id,
                    session=session,
                    event_type="agent.state_patch",
                    request_id=request_id,
                    payload=patch_payload,
                )

        session_read = _build_next_session(
            session_id=session_id,
            draft=next_draft,
            assistant_message=final_text,
        )
        assistant_message_row = _append_bootstrap_message(
            db,
            session_id=session.id,
            request_id=request_id,
            role="assistant",
            content=session_read.assistant_message,
        )
        transcript.append({"role": "user", "content": message})
        transcript.append({"role": "assistant", "content": session_read.assistant_message})
        request_row.status = "succeeded"
        request_row.assistant_message_id = assistant_message_row.id
        request_row.finished_at = utc_now_iso()
        _save_session_state(db, session=session, session_read=session_read, transcript=transcript)

        await _broadcast_realtime_event(
            db,
            connection_manager=connection_manager,
            household_id=household_id,
            session=session,
            event_type="agent.done",
            request_id=request_id,
            payload={},
        )
    except Exception as exc:
        db.rollback()
        db.refresh(session)
        request_row = repository.get_bootstrap_request(db, request_id=request_id)
        if request_row is not None:
            request_row.status = "failed"
            request_row.error_code = _resolve_realtime_error_code(exc)
            request_row.finished_at = utc_now_iso()
        session.current_request_id = None
        session.updated_at = utc_now_iso()
        db.flush()
        error_detail = str(exc.detail) if isinstance(exc, HTTPException) else "这轮对话失败了，请重试"
        await _broadcast_realtime_event(
            db,
            connection_manager=connection_manager,
            household_id=household_id,
            session=session,
            event_type="agent.error",
            request_id=request_id,
            payload={
                "detail": error_detail,
                "error_code": _resolve_realtime_error_code(exc),
            },
        )
        return


def advance_butler_bootstrap_session(
    db: Session,
    *,
    household_id: str,
    session_id: str,
    payload: ButlerBootstrapMessageCreate,
) -> ButlerBootstrapSessionRead:
    """推进管家引导会话。"""
    _ensure_bootstrap_allowed(db, household_id=household_id)
    session = _get_bootstrap_session(db, household_id=household_id, session_id=session_id)

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message 不能为空")

    draft = _load_draft(session, household_id=household_id)
    transcript = _load_transcript(db, session)
    request_id = new_uuid()
    request_started_at = utc_now_iso()
    user_message = _append_bootstrap_message(
        db,
        session_id=session.id,
        request_id=request_id,
        role="user",
        content=message,
        created_at=request_started_at,
    )
    request_row = repository.add_bootstrap_request(
        db,
        row=_build_bootstrap_request(
            request_id=request_id,
            session_id=session.id,
            user_message_id=user_message.id,
            started_at=request_started_at,
        ),
    )
    session.current_request_id = request_id
    db.flush()

    result = invoke_llm(
        db,
        task_type="butler_bootstrap",
        variables={
            "collected_info": _format_collected_info(draft),
            "user_message": message,
            "user_context": _build_user_context(db, household_id),
        },
        household_id=household_id,
        conversation_history=transcript,
    )

    next_draft = draft
    if isinstance(result.data, ButlerBootstrapOutput):
        next_draft = _merge_extracted_data(draft, result.data)

    assistant_message = _append_bootstrap_message(
        db,
        session_id=session.id,
        request_id=request_id,
        role="assistant",
        content=result.text,
    )
    request_row.status = "succeeded"
    request_row.assistant_message_id = assistant_message.id
    request_row.finished_at = utc_now_iso()

    session_read = _build_next_session(session_id=session_id, draft=next_draft, assistant_message=result.text)
    _save_session_state(db, session=session, session_read=session_read, transcript=transcript)
    return session_read


def confirm_butler_bootstrap_session(
    db: Session,
    *,
    household_id: str,
    session_id: str,
    payload: ButlerBootstrapConfirm,
) -> AgentDetailRead:
    """确认创建管家。"""
    _ensure_bootstrap_allowed(db, household_id=household_id)
    session = _get_bootstrap_session(db, household_id=household_id, session_id=session_id)
    draft = _normalize_draft(payload.draft, household_id=household_id)

    missing_fields = _get_missing_fields(draft)
    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"首个管家草稿还没补全：{', '.join(missing_fields)}",
        )

    agent_payload = AgentCreate(
        display_name=draft.display_name,
        agent_type="butler",
        self_identity=_build_self_identity(draft),
        role_summary="AI管家，协助家庭日常事务",
        intro_message=_build_intro_message(draft),
        speaking_style=draft.speaking_style or None,
        personality_traits=draft.personality_traits,
        service_focus=[],
        service_boundaries=None,
        conversation_enabled=True,
        default_entry=True,
        created_by=payload.created_by,
    )
    result = create_agent(db, household_id=household_id, payload=agent_payload)

    session.status = "completed"
    session.pending_field = None
    session.draft_json = dump_json(draft.model_dump(mode="json")) or "{}"
    session.updated_at = utc_now_iso()
    session.completed_at = utc_now_iso()
    db.flush()
    return result


def _build_opening_message(db: Session, *, household_id: str) -> str:
    members, _ = member_service.list_members(db, household_id=household_id, page=1, page_size=1, status_value="active")
    first_member = members[0] if members else None
    greeting_name = (first_member.nickname or first_member.name) if first_member else "朋友"
    return (
        f"你好，{greeting_name}！我是即将加入你们家庭的 AI 管家，很高兴认识你。\n\n"
        "在正式开始服务之前，我想先了解一下你希望我成为什么样的管家。"
        "首先，你想给我起个什么名字呢？"
    )


def _ensure_bootstrap_allowed(db: Session, *, household_id: str) -> None:
    if _has_active_butler(db, household_id=household_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前家庭已经有启用中的管家，不需要再走首个管家引导。",
        )
    route = resolve_capability_route(db, capability=REQUIRED_PROVIDER_CAPABILITY, household_id=household_id)
    if route is None or not route.enabled or not route.primary_provider_profile_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="请先完成 AI 供应商配置，再创建首个管家。",
        )


def _has_active_butler(db: Session, *, household_id: str) -> bool:
    return any(
        agent.agent_type == "butler" and agent.status == "active"
        for agent in repository.list_agents(db, household_id=household_id)
    )


def _get_bootstrap_session(
    db: Session,
    *,
    household_id: str,
    session_id: str,
) -> FamilyAgentBootstrapSession:
    session = repository.get_bootstrap_session(db, household_id=household_id, session_id=session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="引导会话不存在")
    if session.status == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="引导会话已完成")
    return session


def _build_user_context(db: Session, household_id: str) -> str:
    members, _ = member_service.list_members(db, household_id=household_id, page=1, page_size=10, status_value="active")
    if not members:
        return "这是一个新家庭，暂时还没有家庭成员信息。"

    role_map = {
        "admin": "管理员",
        "adult": "成年人",
        "child": "儿童",
        "elder": "长辈",
        "guest": "访客",
    }
    lines: list[str] = []
    for member in members:
        info = f"- {member.name}（{role_map.get(member.role, member.role)}）"
        if member.nickname:
            info += f"，昵称：{member.nickname}"
        lines.append(info)
    return "家庭成员：\n" + "\n".join(lines)


def _format_collected_info(draft: ButlerBootstrapDraft) -> str:
    parts: list[str] = []
    if draft.display_name:
        parts.append(f"- 名字：{draft.display_name}")
    if draft.speaking_style:
        parts.append(f"- 说话风格：{draft.speaking_style}")
    if draft.personality_traits:
        parts.append(f"- 性格特点：{', '.join(draft.personality_traits)}")
    return "\n".join(parts) if parts else "暂无（刚开始对话）"


def _normalize_draft(draft: ButlerBootstrapDraft, *, household_id: str) -> ButlerBootstrapDraft:
    return ButlerBootstrapDraft(
        household_id=household_id,
        display_name=draft.display_name.strip(),
        speaking_style=draft.speaking_style.strip(),
        personality_traits=_normalize_tags(draft.personality_traits),
    )


def _normalize_tags(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        trimmed = value.strip()
        if trimmed and trimmed not in result:
            result.append(trimmed)
    return result


def _merge_extracted_data(draft: ButlerBootstrapDraft, extracted: ButlerBootstrapOutput) -> ButlerBootstrapDraft:
    return ButlerBootstrapDraft(
        household_id=draft.household_id,
        display_name=(extracted.display_name or draft.display_name).strip(),
        speaking_style=(extracted.speaking_style or draft.speaking_style).strip(),
        personality_traits=_merge_traits(draft.personality_traits, extracted.personality_traits),
    )


def _merge_traits(current: list[str], extracted: list[str]) -> list[str]:
    if extracted:
        return _normalize_tags(extracted)
    return _normalize_tags(current)


def _get_missing_fields(draft: ButlerBootstrapDraft) -> list[ButlerBootstrapField]:
    return [field for field in BOOTSTRAP_FIELD_ORDER if not _field_completed(draft, field)]


def _field_completed(draft: ButlerBootstrapDraft, field: ButlerBootstrapField) -> bool:
    if field == "display_name":
        return bool(draft.display_name)
    if field == "speaking_style":
        return bool(draft.speaking_style)
    if field == "personality_traits":
        return len(draft.personality_traits) >= 2
    return False


def _append_review_hint(message: str, draft: ButlerBootstrapDraft) -> str:
    traits = "、".join(draft.personality_traits) if draft.personality_traits else "无"
    style = draft.speaking_style or "未设定"
    review = (
        "\n\n信息已经收集好了，你可以直接确认，"
        "也可以先手动改一下下面这几个字段。\n"
        f"- 名字：{draft.display_name}\n"
        f"- 说话风格：{style}\n"
        f"- 性格特点：{traits}"
    )
    return (message.strip() + review).strip()


def _build_next_session(
    *,
    session_id: str,
    draft: ButlerBootstrapDraft,
    assistant_message: str,
) -> ButlerBootstrapSessionRead:
    missing_fields = _get_missing_fields(draft)
    if not missing_fields:
        return ButlerBootstrapSessionRead(
            session_id=session_id,
            status="reviewing",
            pending_field=None,
            draft=draft,
            assistant_message=_append_review_hint(assistant_message, draft),
            can_confirm=True,
        )

    return ButlerBootstrapSessionRead(
        session_id=session_id,
        status="collecting",
        pending_field=cast(ButlerBootstrapField, missing_fields[0]),
        draft=draft,
        assistant_message=assistant_message.strip(),
        can_confirm=False,
    )


def _load_draft(session: FamilyAgentBootstrapSession, *, household_id: str) -> ButlerBootstrapDraft:
    data = load_json(session.draft_json) or {}
    if isinstance(data, dict):
        data = {key: value for key, value in data.items() if key != "household_id"}
    return _normalize_draft(ButlerBootstrapDraft(household_id=household_id, **data), household_id=household_id)


def _load_transcript(db: Session, session: FamilyAgentBootstrapSession) -> list[dict[str, str]]:
    message_rows = repository.list_bootstrap_messages(db, session_id=session.id)
    if message_rows:
        transcript: list[dict[str, str]] = []
        for item in message_rows:
            if item.role in {"user", "assistant"} and item.content:
                transcript.append({"role": item.role, "content": item.content})
        return transcript

    items = load_json(session.transcript_json) or []
    transcript: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "")
        if role in {"user", "assistant"} and content:
            transcript.append({"role": role, "content": content})
    return transcript


def _save_session_state(
    db: Session,
    *,
    session: FamilyAgentBootstrapSession,
    session_read: ButlerBootstrapSessionRead,
    transcript: list[dict[str, str]],
) -> None:
    session.status = session_read.status
    session.pending_field = session_read.pending_field
    session.draft_json = dump_json(session_read.draft.model_dump(mode="json")) or "{}"
    session.transcript_json = dump_json(transcript) or "[]"
    session.current_request_id = None
    session.updated_at = utc_now_iso()
    db.flush()


def _to_session_read(
    db: Session,
    session: FamilyAgentBootstrapSession,
    *,
    assistant_message: str | None = None,
) -> ButlerBootstrapSessionRead:
    draft = _load_draft(session, household_id=session.household_id)
    message_rows = repository.list_bootstrap_messages(db, session_id=session.id)
    transcript = _load_transcript(db, session)
    pending_field = cast(ButlerBootstrapField | None, session.pending_field if session.pending_field in BOOTSTRAP_FIELD_ORDER else None)
    status_value: ButlerBootstrapStatus = cast(
        ButlerBootstrapStatus,
        session.status if session.status in {"collecting", "reviewing", "completed", "cancelled"} else "collecting",
    )
    latest_message = assistant_message or next(
        (item["content"] for item in reversed(transcript) if item["role"] == "assistant"),
        "你好，我们开始吧。",
    )
    return ButlerBootstrapSessionRead(
        session_id=session.id,
        status=status_value,
        pending_field=pending_field,
        draft=draft,
        assistant_message=latest_message,
        messages=[
            ButlerBootstrapMessageRead(
                id=item.id,
                request_id=item.request_id,
                role=cast(Any, item.role),
                content=item.content,
                seq=item.seq,
                created_at=item.created_at,
            )
            for item in message_rows
            if item.role in {"assistant", "user"}
        ],
        can_confirm=session.status == "reviewing",
        current_request_id=session.current_request_id,
        last_event_seq=session.last_event_seq,
    )


def _append_bootstrap_message(
    db: Session,
    *,
    session_id: str,
    request_id: str | None,
    role: str,
    content: str,
    created_at: str | None = None,
):
    message_row = repository.add_bootstrap_message(
        db,
        FamilyAgentBootstrapMessage(
            id=new_uuid(),
            session_id=session_id,
            request_id=request_id,
            role=role,
            content=content,
            seq=repository.get_next_bootstrap_message_seq(db, session_id=session_id),
            created_at=created_at or utc_now_iso(),
        ),
    )
    db.flush()
    return message_row


def _build_bootstrap_request(
    *,
    request_id: str,
    session_id: str,
    user_message_id: str,
    started_at: str,
):
    from app.modules.agent.models import FamilyAgentBootstrapRequest

    return FamilyAgentBootstrapRequest(
        id=request_id,
        session_id=session_id,
        status="running",
        user_message_id=user_message_id,
        assistant_message_id=None,
        error_code=None,
        started_at=started_at,
        finished_at=None,
    )


def _build_self_identity(draft: ButlerBootstrapDraft) -> str:
    traits = "、".join(draft.personality_traits[:3]) if draft.personality_traits else "友善"
    style = draft.speaking_style or "亲切自然"
    return f"我是{draft.display_name}，这个家的 AI 管家。我性格{traits}，说话风格是{style}。"


def _build_intro_message(draft: ButlerBootstrapDraft) -> str:
    return f"你好，我是{draft.display_name}。很高兴认识你，接下来我会尽力帮助这个家庭。"


def _cancel_bootstrap_session(
    db: Session,
    *,
    session: FamilyAgentBootstrapSession,
    reason: str,
) -> None:
    now = utc_now_iso()
    request_id = session.current_request_id
    session.status = "cancelled"
    session.pending_field = None
    session.current_request_id = None
    session.completed_at = now
    session.updated_at = now

    if request_id:
        request_row = repository.get_bootstrap_request(db, request_id=str(request_id))
        if request_row is not None and request_row.status == "running":
            request_row.status = "cancelled"
            request_row.error_code = reason
            request_row.finished_at = now
    db.flush()


async def _broadcast_realtime_event(
    db: Session,
    *,
    connection_manager: RealtimeConnectionManager,
    household_id: str,
    session: FamilyAgentBootstrapSession,
    event_type: str,
    payload: dict[str, Any],
    request_id: str | None = None,
) -> None:
    seq = repository.claim_next_bootstrap_event_seq(db, session=session)
    db.commit()
    event = build_bootstrap_realtime_event(
        event_type=cast(Any, event_type),
        session_id=session.id,
        request_id=request_id,
        seq=seq,
        payload=payload,
    )
    await connection_manager.broadcast(household_id=household_id, session_id=session.id, event=event)


def _extract_bootstrap_state_patch(
    db: Session,
    *,
    household_id: str,
    draft: ButlerBootstrapDraft,
    user_message: str,
    assistant_message: str,
) -> ButlerBootstrapOutput | None:
    try:
        result = invoke_llm(
            db,
            task_type="butler_bootstrap_extract",
            variables={
                "collected_info": _format_collected_info(draft),
                "user_message": user_message,
                "assistant_message": assistant_message,
            },
            household_id=household_id,
        )
    except Exception as exc:
        logger.warning("bootstrap structured extraction failed: %s", exc)
        return None

    if isinstance(result.data, ButlerBootstrapOutput):
        return result.data
    return None


def _build_state_patch_payload(
    *,
    draft: ButlerBootstrapDraft,
    next_draft: ButlerBootstrapDraft,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if next_draft.display_name != draft.display_name:
        payload["display_name"] = next_draft.display_name
    if next_draft.speaking_style != draft.speaking_style:
        payload["speaking_style"] = next_draft.speaking_style
    if next_draft.personality_traits != draft.personality_traits:
        payload["personality_traits"] = next_draft.personality_traits
    return payload


def _resolve_realtime_error_code(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        if exc.status_code == status.HTTP_409_CONFLICT:
            return "request_conflict"
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return "session_not_found"
        if exc.status_code == status.HTTP_400_BAD_REQUEST:
            return "invalid_event_payload"
    return "provider_stream_failed"
