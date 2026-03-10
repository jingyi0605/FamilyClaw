from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.family_qa import repository
from app.modules.family_qa.fact_view_service import build_qa_fact_view
from app.modules.family_qa.models import QaQueryLog
from app.modules.family_qa.schemas import (
    FamilyQaQueryRequest,
    FamilyQaQueryResponse,
    FamilyQaSuggestionItem,
    FamilyQaSuggestionsResponse,
    QaFactReference,
    QaFactViewRead,
    QaQueryLogCreate,
    QaQueryLogRead,
)
from app.modules.household.models import Household
from app.modules.member.models import Member
from app.modules.ai_gateway.gateway_service import invoke_capability
from app.modules.ai_gateway.schemas import AiGatewayInvokeRequest


def create_query_log(db: Session, payload: QaQueryLogCreate) -> QaQueryLogRead:
    _ensure_household_exists(db, payload.household_id)
    _validate_requester_member(db, payload.household_id, payload.requester_member_id)

    row = QaQueryLog(
        id=new_uuid(),
        household_id=payload.household_id,
        requester_member_id=payload.requester_member_id,
        question=payload.question,
        answer_type=payload.answer_type,
        answer_summary=payload.answer_summary,
        confidence=payload.confidence,
        degraded=payload.degraded,
        facts_json=dump_json([fact.model_dump(mode="json") for fact in payload.facts]) or "[]",
        created_at=utc_now_iso(),
    )
    repository.add_query_log(db, row)
    db.flush()
    return _to_query_log_read(row)


def list_query_logs(
    db: Session,
    *,
    household_id: str,
    requester_member_id: str | None = None,
    limit: int = 50,
) -> list[QaQueryLogRead]:
    _ensure_household_exists(db, household_id)
    _validate_requester_member(db, household_id, requester_member_id)
    rows = repository.list_query_logs(
        db,
        household_id=household_id,
        requester_member_id=requester_member_id,
        limit=limit,
    )
    return [_to_query_log_read(row) for row in rows]


def query_family_qa(db: Session, payload: FamilyQaQueryRequest) -> FamilyQaQueryResponse:
    _ensure_household_exists(db, payload.household_id)
    _validate_requester_member(db, payload.household_id, payload.requester_member_id)

    fact_view = build_qa_fact_view(
        db,
        household_id=payload.household_id,
        requester_member_id=payload.requester_member_id,
    )
    answer_type, answer_text, confidence, facts, suggestions = _answer_from_fact_view(
        fact_view,
        payload.question,
    )

    ai_trace_id: str | None = None
    ai_provider_code: str | None = None
    ai_degraded = False
    degraded = False

    try:
        ai_response = invoke_capability(
            db,
            AiGatewayInvokeRequest(
                capability="qa_generation",
                household_id=payload.household_id,
                requester_member_id=payload.requester_member_id,
                payload={
                    "question": payload.question,
                    "answer_draft": answer_text,
                    "answer_type": answer_type,
                    "fact_count": len(facts),
                    "channel": payload.channel,
                },
            ),
        )
        answer_text = str(ai_response.normalized_output.get("text") or answer_text)
        ai_trace_id = ai_response.trace_id
        ai_provider_code = ai_response.provider_code
        ai_degraded = ai_response.degraded
        degraded = ai_response.degraded
    except HTTPException:
        degraded = True

    result = FamilyQaQueryResponse(
        answer_type=answer_type,
        answer=answer_text,
        confidence=confidence,
        facts=facts,
        degraded=degraded,
        suggestions=suggestions,
        ai_trace_id=ai_trace_id,
        ai_provider_code=ai_provider_code,
        ai_degraded=ai_degraded,
    )
    create_query_log(
        db,
        QaQueryLogCreate(
            household_id=payload.household_id,
            requester_member_id=payload.requester_member_id,
            question=payload.question,
            answer_type=result.answer_type,
            answer_summary=result.answer[:2000],
            confidence=result.confidence,
            degraded=result.degraded,
            facts=result.facts,
        ),
    )
    return result


def list_family_qa_suggestions(
    db: Session,
    *,
    household_id: str,
    requester_member_id: str | None = None,
) -> FamilyQaSuggestionsResponse:
    _ensure_household_exists(db, household_id)
    _validate_requester_member(db, household_id, requester_member_id)
    fact_view = build_qa_fact_view(
        db,
        household_id=household_id,
        requester_member_id=requester_member_id,
    )
    items: list[FamilyQaSuggestionItem] = []
    if fact_view.active_member is not None:
        items.append(
            FamilyQaSuggestionItem(
                question=f"{fact_view.active_member.name} 现在在哪个房间？",
                answer_type="member_status",
                reason="当前有活跃成员，可直接问位置",
            )
        )
    if fact_view.reminder_summary.recent_items:
        first_item = fact_view.reminder_summary.recent_items[0]
        items.append(
            FamilyQaSuggestionItem(
                question=f"{first_item.title} 处理完了吗？",
                answer_type="reminder_status",
                reason="最近有提醒记录",
            )
        )
    if fact_view.scene_summary.recent_items:
        first_scene = fact_view.scene_summary.recent_items[0]
        items.append(
            FamilyQaSuggestionItem(
                question=f"{first_scene.name} 最近执行了吗？",
                answer_type="scene_status",
                reason="最近有场景模板记录",
            )
        )
    if fact_view.device_states:
        first_device = fact_view.device_states[0]
        items.append(
            FamilyQaSuggestionItem(
                question=f"{first_device.name} 现在是什么状态？",
                answer_type="device_status",
                reason="当前有可查询设备",
            )
        )
    if not items:
        items.append(
            FamilyQaSuggestionItem(
                question="现在家里是什么状态？",
                answer_type="general",
                reason="默认建议问题",
            )
        )
    return FamilyQaSuggestionsResponse(household_id=household_id, items=items[:6])


def _ensure_household_exists(db: Session, household_id: str) -> None:
    if db.get(Household, household_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="household not found",
        )


def _validate_requester_member(db: Session, household_id: str, requester_member_id: str | None) -> None:
    if requester_member_id is None:
        return

    member = db.get(Member, requester_member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="requester member not found",
        )
    if member.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="requester member must belong to the same household",
        )


def _to_query_log_read(row: QaQueryLog) -> QaQueryLogRead:
    return QaQueryLogRead(
        id=row.id,
        household_id=row.household_id,
        requester_member_id=row.requester_member_id,
        question=row.question,
        answer_type=row.answer_type,
        answer_summary=row.answer_summary,
        confidence=row.confidence,
        degraded=row.degraded,
        facts=load_json(row.facts_json) or [],
        created_at=row.created_at,
    )


def _answer_from_fact_view(
    fact_view: QaFactViewRead,
    question: str,
) -> tuple[str, str, float, list[QaFactReference], list[str]]:
    normalized_question = question.strip().lower()

    for member_state in fact_view.member_states:
        if member_state.name and member_state.name.lower() in normalized_question:
            room_name = member_state.current_room_name or "未知房间"
            answer = f"{member_state.name} 当前状态是 {member_state.presence}，位置是 {room_name}。"
            facts = [
                QaFactReference(
                    type="member_state",
                    label=f"{member_state.name} 状态",
                    source="context_overview",
                    occurred_at=member_state.updated_at,
                    inferred=False,
                    extra={
                        "member_id": member_state.member_id,
                        "presence": member_state.presence,
                        "room_name": member_state.current_room_name,
                    },
                )
            ]
            return "member_status", answer, 0.93, facts, ["查看家庭上下文", "查看房间状态"]

    if any(keyword in normalized_question for keyword in ["提醒", "吃药", "服药", "课程", "安排"]):
        if fact_view.reminder_summary.recent_items:
            reminder = fact_view.reminder_summary.recent_items[0]
            answer = (
                f"{reminder.title} 最近一次状态是 {reminder.last_run_status or '未触发'}，"
                f"确认结果是 {reminder.last_ack_action or '还没人确认'}。"
            )
            facts = [
                QaFactReference(
                    type="reminder_run",
                    label=reminder.title,
                    source="reminder_runs",
                    occurred_at=reminder.last_run_planned_at,
                    inferred=False,
                    extra={
                        "task_id": reminder.task_id,
                        "last_run_status": reminder.last_run_status,
                        "last_ack_action": reminder.last_ack_action,
                    },
                )
            ]
            return "reminder_status", answer, 0.9, facts, ["查看提醒详情", "手动再次提醒"]
        return "reminder_status", "当前没有可用的提醒记录。", 0.45, [], ["创建提醒", "查看提醒总览"]

    if any(keyword in normalized_question for keyword in ["场景", "回家", "睡前", "模式"]):
        if fact_view.scene_summary.recent_items:
            scene = fact_view.scene_summary.recent_items[0]
            answer = f"{scene.name} 最近一次执行状态是 {scene.last_execution_status or '未执行'}。"
            facts = [
                QaFactReference(
                    type="scene_execution",
                    label=scene.name,
                    source="scene_executions",
                    occurred_at=scene.last_execution_started_at,
                    inferred=False,
                    extra={
                        "template_id": scene.template_id,
                        "template_code": scene.template_code,
                        "last_execution_status": scene.last_execution_status,
                    },
                )
            ]
            return "scene_status", answer, 0.88, facts, ["查看场景详情", "手动触发场景"]
        return "scene_status", "当前没有场景执行记录。", 0.4, [], ["查看场景模板"]

    if any(keyword in normalized_question for keyword in ["灯", "空调", "窗帘", "门锁", "设备"]):
        if fact_view.device_states:
            device = fact_view.device_states[0]
            answer = f"{device.name} 当前状态是 {device.status}。"
            facts = [
                QaFactReference(
                    type="device_state",
                    label=device.name,
                    source="devices",
                    inferred=False,
                    extra={
                        "device_id": device.device_id,
                        "device_type": device.device_type,
                        "status": device.status,
                    },
                )
            ]
            return "device_status", answer, 0.86, facts, ["查看设备列表", "查看上下文总览"]
        return "device_status", "当前没有可查询的设备状态。", 0.35, [], ["同步设备数据"]

    summary_parts = []
    if fact_view.active_member is not None:
        summary_parts.append(f"当前活跃成员是 {fact_view.active_member.name}")
    summary_parts.append(f"当前有 {fact_view.reminder_summary.pending_runs} 个待处理提醒")
    summary_parts.append(f"当前有 {fact_view.scene_summary.running_executions} 个场景正在运行")
    answer = "；".join(summary_parts) + "。"
    facts: list[QaFactReference] = []
    if fact_view.active_member is not None:
        facts.append(
            QaFactReference(
                type="active_member",
                label=fact_view.active_member.name,
                source="context_overview",
                inferred=False,
                extra={"member_id": fact_view.active_member.member_id},
            )
        )
    return "general", answer, 0.72, facts, ["谁在家", "最近提醒", "最近场景"]
