from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RelationType = Literal["spouse", "parent", "child", "guardian", "caregiver"]
VisibilityScope = Literal["public", "family", "private"]
DelegationScope = Literal["none", "reminder", "health", "device"]


class MemberRelationshipCreate(BaseModel):
    household_id: str = Field(min_length=1)
    source_member_id: str = Field(min_length=1)
    target_member_id: str = Field(min_length=1)
    relation_type: RelationType
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

