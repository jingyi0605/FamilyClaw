from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    household_id: str
    actor_type: str
    actor_id: str | None
    action: str
    target_type: str
    target_id: str | None
    result: str
    details: str | None
    created_at: str


class AuditLogListResponse(BaseModel):
    items: list[AuditLogRead]
    page: int
    page_size: int
    total: int

