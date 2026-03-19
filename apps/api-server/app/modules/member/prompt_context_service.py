from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.member.models import Member, MemberPreference
from app.modules.member.service import resolve_member_display_name
from app.modules.relationship.models import MemberRelationship


ROLE_LABELS = {
    "admin": "管理员",
    "adult": "成人",
    "child": "儿童",
    "elder": "老人",
    "guest": "访客",
}

GENDER_LABELS = {
    "male": "男",
    "female": "女",
}

AGE_GROUP_LABELS = {
    "toddler": "幼儿",
    "child": "儿童",
    "teen": "青少年",
    "adult": "成人",
    "elder": "老人",
}

RELATION_LABELS = {
    "husband": "丈夫",
    "wife": "妻子",
    "spouse": "配偶",
    "father": "爸爸",
    "mother": "妈妈",
    "son": "儿子",
    "daughter": "女儿",
    "parent": "父母",
    "child": "孩子",
    "older_brother": "哥哥",
    "older_sister": "姐姐",
    "younger_brother": "弟弟",
    "younger_sister": "妹妹",
    "grandfather_paternal": "爷爷",
    "grandmother_paternal": "奶奶",
    "grandfather_maternal": "外公",
    "grandmother_maternal": "外婆",
    "grandson": "孙子",
    "granddaughter": "孙女",
    "guardian": "监护人",
    "ward": "被监护人",
    "caregiver": "照护人",
}


@dataclass(frozen=True)
class MemberPromptRelationship:
    target_member_id: str
    target_member_name: str
    relation_type: str
    relation_label: str


@dataclass(frozen=True)
class MemberPromptProfile:
    member_id: str
    display_name: str
    aliases: tuple[str, ...]
    role: str
    role_label: str
    gender: str | None
    gender_label: str | None
    age_group: str | None
    age_group_label: str | None
    birthday: str | None
    age_years: int | None
    preferred_name: str | None
    guardian_member_id: str | None
    guardian_name: str | None
    relationships: tuple[MemberPromptRelationship, ...]


def list_member_prompt_profiles(
    db: Session,
    *,
    household_id: str,
    status_value: str = "active",
) -> list[MemberPromptProfile]:
    member_statement = (
        select(Member)
        .where(
            Member.household_id == household_id,
            Member.status == status_value,
        )
        .order_by(Member.created_at.asc(), Member.id.asc())
    )
    members = list(db.scalars(member_statement).all())
    if not members:
        return []

    member_ids = [member.id for member in members]
    preference_rows = list(
        db.scalars(select(MemberPreference).where(MemberPreference.member_id.in_(member_ids))).all()
    )
    preference_map = {row.member_id: row for row in preference_rows}

    display_name_map = {
        member.id: resolve_member_display_name(member, preference_map.get(member.id))
        for member in members
    }
    relationship_rows = list(
        db.scalars(
            select(MemberRelationship)
            .where(
                MemberRelationship.household_id == household_id,
                MemberRelationship.source_member_id.in_(member_ids),
                MemberRelationship.target_member_id.in_(member_ids),
            )
            .order_by(
                MemberRelationship.source_member_id.asc(),
                MemberRelationship.created_at.asc(),
                MemberRelationship.id.asc(),
            )
        ).all()
    )

    relationship_map: dict[str, list[MemberPromptRelationship]] = {member_id: [] for member_id in member_ids}
    for relationship in relationship_rows:
        target_name = display_name_map.get(relationship.target_member_id)
        if not target_name:
            continue
        relationship_map.setdefault(relationship.source_member_id, []).append(
            MemberPromptRelationship(
                target_member_id=relationship.target_member_id,
                target_member_name=target_name,
                relation_type=relationship.relation_type,
                relation_label=RELATION_LABELS.get(relationship.relation_type, relationship.relation_type),
            )
        )

    profiles: list[MemberPromptProfile] = []
    for member in members:
        preference = preference_map.get(member.id)
        preferred_name = str(preference.preferred_name or "").strip() if preference is not None else ""
        aliases = _build_member_aliases(member=member, display_name=display_name_map.get(member.id, member.name))
        profiles.append(
            MemberPromptProfile(
                member_id=member.id,
                display_name=display_name_map.get(member.id, member.name),
                aliases=aliases,
                role=member.role,
                role_label=ROLE_LABELS.get(member.role, member.role),
                gender=member.gender,
                gender_label=GENDER_LABELS.get(member.gender or ""),
                age_group=member.age_group,
                age_group_label=AGE_GROUP_LABELS.get(member.age_group or ""),
                birthday=member.birthday,
                age_years=_calculate_age_years(member.birthday),
                preferred_name=preferred_name or None,
                guardian_member_id=member.guardian_member_id,
                guardian_name=display_name_map.get(member.guardian_member_id or ""),
                relationships=tuple(relationship_map.get(member.id, [])),
            )
        )
    return profiles


def build_member_prompt_context(
    db: Session,
    *,
    household_id: str,
    status_value: str = "active",
) -> str:
    profiles = list_member_prompt_profiles(
        db,
        household_id=household_id,
        status_value=status_value,
    )
    if not profiles:
        return "当前家庭还没有有效成员资料。"
    return "\n".join(_render_member_prompt_line(profile) for profile in profiles)


def _build_member_aliases(*, member: Member, display_name: str) -> tuple[str, ...]:
    aliases: list[str] = []
    for candidate in [display_name, member.nickname, member.name]:
        normalized = str(candidate or "").strip()
        if normalized and normalized not in aliases:
            aliases.append(normalized)
    return tuple(aliases)


def _calculate_age_years(birthday_value: str | None) -> int | None:
    if not birthday_value:
        return None
    try:
        birthday = date.fromisoformat(birthday_value)
    except ValueError:
        return None

    today = date.today()
    age_years = today.year - birthday.year
    if (today.month, today.day) < (birthday.month, birthday.day):
        age_years -= 1
    return max(age_years, 0)


def _render_member_prompt_line(profile: MemberPromptProfile) -> str:
    parts = [f"角色={profile.role_label}"]
    if profile.gender_label:
        parts.append(f"性别={profile.gender_label}")
    if profile.age_years is not None:
        parts.append(f"年龄={profile.age_years}岁")
    elif profile.age_group_label:
        parts.append(f"年龄段={profile.age_group_label}")
    if profile.birthday:
        parts.append(f"生日={profile.birthday}")
    if profile.preferred_name and profile.preferred_name != profile.display_name:
        parts.append(f"偏好称呼={profile.preferred_name}")
    if profile.guardian_name:
        parts.append(f"监护人={profile.guardian_name}")
    if profile.relationships:
        relationship_text = "；".join(
            f"对{relationship.target_member_name}是{relationship.relation_label}"
            for relationship in profile.relationships[:6]
        )
        parts.append(f"关系={relationship_text}")
    return f"- {profile.display_name}：{'；'.join(parts)}"
