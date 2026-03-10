from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RelationType = Literal[
    # 配偶
    "husband", "wife", "spouse",
    # 父母 / 子女
    "father", "mother", "son", "daughter", "parent", "child",
    # 兄弟姐妹
    "older_brother", "older_sister", "younger_brother", "younger_sister",
    # 祖辈（父系）
    "grandfather_paternal", "grandmother_paternal",
    # 祖辈（母系）
    "grandfather_maternal", "grandmother_maternal",
    # 孙辈
    "grandson", "granddaughter",
    # 监护 / 照护
    "guardian", "ward",
    "caregiver",
]

VisibilityScope = Literal["public", "family", "private"]
DelegationScope = Literal["none", "reminder", "health", "device"]

# ---------- 反向关系映射 ----------
# 值为 callable(target_gender) -> str 或者固定 str
# target_gender 是被指向那一方的性别: "male" | "female" | None

_REVERSE_MAP_FIXED: dict[str, str] = {
    "husband": "wife",
    "wife": "husband",
    "spouse": "spouse",
    "guardian": "ward",
    "ward": "guardian",
}


def _reverse_parent(target_gender: str | None) -> str:
    """A 是 B 的 father/mother → B 是 A 的 son/daughter"""
    if target_gender == "male":
        return "son"
    if target_gender == "female":
        return "daughter"
    return "child"


def _reverse_child(target_gender: str | None) -> str:
    """A 是 B 的 son/daughter → B 是 A 的 father/mother"""
    if target_gender == "male":
        return "father"
    if target_gender == "female":
        return "mother"
    return "parent"


def _reverse_older_sibling(target_gender: str | None) -> str:
    if target_gender == "male":
        return "younger_brother"
    if target_gender == "female":
        return "younger_sister"
    return "younger_brother"


def _reverse_younger_sibling(target_gender: str | None) -> str:
    if target_gender == "male":
        return "older_brother"
    if target_gender == "female":
        return "older_sister"
    return "older_brother"


def _reverse_grandparent(target_gender: str | None) -> str:
    if target_gender == "male":
        return "grandson"
    if target_gender == "female":
        return "granddaughter"
    return "grandson"


def _reverse_grandchild_paternal(target_gender: str | None) -> str:
    if target_gender == "male":
        return "grandfather_paternal"
    if target_gender == "female":
        return "grandmother_paternal"
    return "grandfather_paternal"


def _reverse_grandchild_maternal(target_gender: str | None) -> str:
    if target_gender == "male":
        return "grandfather_maternal"
    if target_gender == "female":
        return "grandmother_maternal"
    return "grandfather_maternal"


_REVERSE_MAP_GENDERED: dict[str, callable] = {
    "father": _reverse_parent,
    "mother": _reverse_parent,
    "parent": _reverse_parent,
    "son": _reverse_child,
    "daughter": _reverse_child,
    "child": _reverse_child,
    "older_brother": _reverse_older_sibling,
    "older_sister": _reverse_older_sibling,
    "younger_brother": _reverse_younger_sibling,
    "younger_sister": _reverse_younger_sibling,
    "grandfather_paternal": _reverse_grandparent,
    "grandmother_paternal": _reverse_grandparent,
    "grandfather_maternal": _reverse_grandparent,
    "grandmother_maternal": _reverse_grandparent,
    "grandson": _reverse_grandchild_paternal,
    "granddaughter": _reverse_grandchild_paternal,
}


def get_reverse_relation(relation_type: str, target_gender: str | None) -> str | None:
    """根据关系类型和 target 的性别，返回反向关系类型。caregiver 无反向关系。"""
    if relation_type in _REVERSE_MAP_FIXED:
        return _REVERSE_MAP_FIXED[relation_type]
    fn = _REVERSE_MAP_GENDERED.get(relation_type)
    if fn is not None:
        return fn(target_gender)
    return None


class MemberRelationshipCreate(BaseModel):
    household_id: str = Field(min_length=1)
    source_member_id: str = Field(min_length=1)
    target_member_id: str = Field(min_length=1)
    relation_type: RelationType
    reverse_relation_type: RelationType | None = None  # 可选：前端可覆盖自动推断
    visibility_scope: VisibilityScope = "family"
    delegation_scope: DelegationScope = "none"


class MemberRelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    household_id: str
    source_member_id: str
    target_member_id: str
    relation_type: RelationType
    visibility_scope: VisibilityScope
    delegation_scope: DelegationScope
    created_at: str


class MemberRelationshipListResponse(BaseModel):
    items: list[MemberRelationshipRead]
    page: int
    page_size: int
    total: int
