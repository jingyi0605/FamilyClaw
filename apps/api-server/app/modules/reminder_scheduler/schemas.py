from pydantic import BaseModel, Field


class ReminderScheduleSlot(BaseModel):
    task_id: str
    household_id: str
    planned_at: str
    trigger_reason: str
    schedule_slot_key: str = Field(min_length=1, max_length=100)


class ReminderRunDraft(BaseModel):
    can_create_run: bool
    slot: ReminderScheduleSlot
    skip_reason: str | None = None
