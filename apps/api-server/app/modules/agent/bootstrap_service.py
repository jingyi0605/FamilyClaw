from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.utils import new_uuid
from app.modules.agent import repository
from app.modules.agent.schemas import (
    AgentCreate,
    AgentDetailRead,
    ButlerBootstrapConfirm,
    ButlerBootstrapDraft,
    ButlerBootstrapField,
    ButlerBootstrapMessageCreate,
    ButlerBootstrapSessionRead,
)
from app.modules.agent.service import create_agent
from app.modules.ai_gateway.service import resolve_capability_route

REQUIRED_PROVIDER_CAPABILITY = "qa_generation"
BOOTSTRAP_FIELD_ORDER: tuple[ButlerBootstrapField, ...] = (
    "display_name",
    "role_summary",
    "speaking_style",
    "personality_traits",
    "service_focus",
)


def start_butler_bootstrap_session(
    db: Session,
    *,
    household_id: str,
) -> ButlerBootstrapSessionRead:
    _ensure_bootstrap_allowed(db, household_id=household_id)
    draft = ButlerBootstrapDraft(household_id=household_id)
    return ButlerBootstrapSessionRead(
        session_id=new_uuid(),
        status="collecting",
        pending_field="display_name",
        draft=draft,
        assistant_message=(
            "我们别再填冷冰冰的表了。我用几轮对话帮你把首个管家定下来。"
            "先给这个管家起个名字。"
        ),
        can_confirm=False,
    )


def advance_butler_bootstrap_session(
    db: Session,
    *,
    household_id: str,
    session_id: str,
    payload: ButlerBootstrapMessageCreate,
) -> ButlerBootstrapSessionRead:
    _ensure_bootstrap_allowed(db, household_id=household_id)
    draft = _normalize_draft(payload.draft, household_id=household_id)
    pending_field = payload.pending_field or _next_pending_field(draft) or "display_name"
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message 不能为空")

    _apply_answer(draft, pending_field, message)
    next_field = _next_pending_field(draft)

    if next_field is None:
        return ButlerBootstrapSessionRead(
            session_id=session_id,
            status="reviewing",
            pending_field=None,
            draft=draft,
            assistant_message=_build_review_message(draft),
            can_confirm=True,
        )

    return ButlerBootstrapSessionRead(
        session_id=session_id,
        status="collecting",
        pending_field=next_field,
        draft=draft,
        assistant_message=_build_prompt(next_field, draft),
        can_confirm=False,
    )


def confirm_butler_bootstrap_session(
    db: Session,
    *,
    household_id: str,
    payload: ButlerBootstrapConfirm,
) -> AgentDetailRead:
    _ensure_bootstrap_allowed(db, household_id=household_id)
    draft = _normalize_draft(payload.draft, household_id=household_id)
    missing_fields = [field for field in BOOTSTRAP_FIELD_ORDER if not _field_completed(draft, field)]
    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"首个管家草稿还没补全：{', '.join(missing_fields)}",
        )

    agent_payload = AgentCreate(
        display_name=draft.display_name,
        agent_type="butler",
        self_identity=_build_self_identity(draft),
        role_summary=draft.role_summary,
        intro_message=_build_intro_message(draft),
        speaking_style=draft.speaking_style or None,
        personality_traits=draft.personality_traits,
        service_focus=draft.service_focus,
        service_boundaries=None,
        conversation_enabled=True,
        default_entry=True,
        created_by=payload.created_by,
    )
    return create_agent(db, household_id=household_id, payload=agent_payload)


def _ensure_bootstrap_allowed(db: Session, *, household_id: str) -> None:
    if _has_active_butler(db, household_id=household_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前家庭已经有启用中的管家，不需要再走首个管家引导。",
        )
    route = resolve_capability_route(
        db,
        capability=REQUIRED_PROVIDER_CAPABILITY,
        household_id=household_id,
    )
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


def _normalize_draft(draft: ButlerBootstrapDraft, *, household_id: str) -> ButlerBootstrapDraft:
    return ButlerBootstrapDraft(
        household_id=household_id,
        display_name=draft.display_name.strip(),
        role_summary=draft.role_summary.strip(),
        speaking_style=draft.speaking_style.strip(),
        personality_traits=_normalize_tags(draft.personality_traits),
        service_focus=_normalize_tags(draft.service_focus),
    )


def _normalize_tags(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        trimmed = value.strip()
        if trimmed and trimmed not in result:
            result.append(trimmed)
    return result


def _apply_answer(draft: ButlerBootstrapDraft, field: ButlerBootstrapField, message: str) -> None:
    if field == "display_name":
        draft.display_name = message[:100]
        return
    if field == "role_summary":
        draft.role_summary = message[:2000]
        return
    if field == "speaking_style":
        draft.speaking_style = message[:2000]
        return
    if field == "personality_traits":
        draft.personality_traits = _parse_tags(message)
        return
    draft.service_focus = _parse_tags(message)


def _parse_tags(message: str) -> list[str]:
    separators = [",", "，", "、", "\n", ";", "；", "/", "|"]
    normalized = message.strip()
    for separator in separators:
        normalized = normalized.replace(separator, ",")
    parts = [item.strip() for item in normalized.split(",")]
    tags = [item for item in parts if item]
    if not tags and message.strip():
        return [message.strip()]
    result: list[str] = []
    for tag in tags:
        if tag not in result:
            result.append(tag[:100])
    return result


def _next_pending_field(draft: ButlerBootstrapDraft) -> ButlerBootstrapField | None:
    for field in BOOTSTRAP_FIELD_ORDER:
        if not _field_completed(draft, field):
            return field
    return None


def _field_completed(draft: ButlerBootstrapDraft, field: ButlerBootstrapField) -> bool:
    if field == "display_name":
        return bool(draft.display_name)
    if field == "role_summary":
        return bool(draft.role_summary)
    if field == "speaking_style":
        return bool(draft.speaking_style)
    if field == "personality_traits":
        return len(draft.personality_traits) > 0
    return len(draft.service_focus) > 0


def _build_prompt(field: ButlerBootstrapField, draft: ButlerBootstrapDraft) -> str:
    if field == "role_summary":
        return f"名字收到，就叫“{draft.display_name}”。现在告诉我，这个管家最主要负责什么？用一句人话说清。"
    if field == "speaking_style":
        return "好，职责有了。它跟家人说话时应该是什么风格？比如温和直接、活泼一点、少废话。"
    if field == "personality_traits":
        return "再给我 2 到 4 个性格关键词，最好用逗号隔开，比如“细心，稳重，有边界感”。"
    return "最后说一下它的服务重点。也用逗号隔开，比如“家庭问答，提醒复盘，成员关怀”。"


def _build_review_message(draft: ButlerBootstrapDraft) -> str:
    traits = "、".join(draft.personality_traits)
    focus = "、".join(draft.service_focus)
    return (
        f"草稿已经齐了：名字是“{draft.display_name}”，主要职责是“{draft.role_summary}”，"
        f"说话风格偏“{draft.speaking_style}”，人格特征是“{traits}”，服务重点是“{focus}”。"
        " 你可以先在下面微调，再确认创建。"
    )


def _build_self_identity(draft: ButlerBootstrapDraft) -> str:
    focus = "、".join(draft.service_focus[:3])
    return f"我是{draft.display_name}，这个家的首个 AI 管家，主要负责{draft.role_summary}。我会重点处理{focus}。"


def _build_intro_message(draft: ButlerBootstrapDraft) -> str:
    focus = "、".join(draft.service_focus[:2])
    return f"你好，我是{draft.display_name}。接下来我会先帮你处理{focus}。"
