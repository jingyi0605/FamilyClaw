from pydantic import BaseModel, ConfigDict, Field


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    timezone: str = Field(min_length=1, max_length=64)
    locale: str = Field(min_length=1, max_length=32)


class HouseholdRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    timezone: str
    locale: str
    status: str
    created_at: str
    updated_at: str

