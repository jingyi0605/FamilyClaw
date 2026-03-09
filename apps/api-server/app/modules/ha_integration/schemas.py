from pydantic import BaseModel, Field

from app.modules.device.schemas import DeviceRead


class HomeAssistantSyncRequest(BaseModel):
    household_id: str = Field(min_length=1)


class HomeAssistantSyncFailure(BaseModel):
    entity_id: str | None = None
    reason: str


class HomeAssistantSyncResponse(BaseModel):
    household_id: str
    created_devices: int
    updated_devices: int
    created_bindings: int
    skipped_entities: int
    failed_entities: int
    devices: list[DeviceRead]
    failures: list[HomeAssistantSyncFailure]

