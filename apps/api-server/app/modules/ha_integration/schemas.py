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
    created_rooms: int
    assigned_rooms: int
    skipped_entities: int
    failed_entities: int
    devices: list[DeviceRead]
    failures: list[HomeAssistantSyncFailure]


class HomeAssistantConfigRead(BaseModel):
    household_id: str
    base_url: str | None
    token_configured: bool
    sync_rooms_enabled: bool
    last_device_sync_at: str | None
    updated_at: str | None


class HomeAssistantConfigUpsert(BaseModel):
    base_url: str | None = Field(default=None, max_length=255)
    access_token: str | None = None
    clear_access_token: bool = False
    sync_rooms_enabled: bool = False


class HomeAssistantRoomSyncRequest(BaseModel):
    household_id: str = Field(min_length=1)
    room_names: list[str] = Field(default_factory=list)


class HomeAssistantRoomCandidate(BaseModel):
    name: str
    entity_count: int
    exists_locally: bool
    can_sync: bool


class HomeAssistantRoomSyncResponse(BaseModel):
    household_id: str
    created_rooms: int
    matched_entities: int
    skipped_entities: int
    rooms: list[dict[str, str]]


class HomeAssistantRoomCandidatesResponse(BaseModel):
    household_id: str
    items: list[HomeAssistantRoomCandidate]

