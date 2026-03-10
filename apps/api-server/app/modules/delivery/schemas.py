from pydantic import BaseModel, Field


class DeliveryTarget(BaseModel):
    member_id: str | None = None
    room_id: str | None = None
    channels: list[str] = Field(default_factory=list)


class DeliveryPlan(BaseModel):
    household_id: str
    task_id: str
    strategy: str
    targets: list[DeliveryTarget] = Field(default_factory=list)
