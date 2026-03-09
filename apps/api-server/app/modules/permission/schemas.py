from typing import Literal

from pydantic import BaseModel, ConfigDict

ResourceType = Literal["memory", "health", "device", "photo", "scenario"]
ResourceScope = Literal["self", "children", "family", "public"]
PermissionAction = Literal["read", "write", "execute", "manage"]
PermissionEffect = Literal["allow", "deny"]


class MemberPermissionRule(BaseModel):
    resource_type: ResourceType
    resource_scope: ResourceScope
    action: PermissionAction
    effect: PermissionEffect


class MemberPermissionReplaceRequest(BaseModel):
    rules: list[MemberPermissionRule]


class MemberPermissionRead(MemberPermissionRule):
    model_config = ConfigDict(from_attributes=True)

    id: str
    household_id: str
    member_id: str
    created_at: str


class MemberPermissionListResponse(BaseModel):
    member_id: str
    household_id: str
    items: list[MemberPermissionRead]
