from pydantic import BaseModel, ConfigDict, Field


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    account_type: str
    status: str
    household_id: str | None
    must_change_password: bool
    created_at: str
    updated_at: str


class AccountMemberBindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: str
    member_id: str
    household_id: str
    binding_status: str
    created_at: str
    updated_at: str


class AuthLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class AuthActorSummary(BaseModel):
    account_id: str
    username: str
    account_type: str
    account_status: str
    household_id: str | None = None
    member_id: str | None = None
    member_role: str | None = None
    role: str
    actor_type: str
    actor_id: str | None = None
    must_change_password: bool = False
    authenticated: bool = True


class AuthLoginResponse(BaseModel):
    actor: AuthActorSummary


class AuthLogoutResponse(BaseModel):
    ok: bool = True


class HouseholdAccountCreateRequest(BaseModel):
    household_id: str = Field(min_length=1)
    member_id: str = Field(min_length=1)
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)
    must_change_password: bool = False


class HouseholdAccountCreateResponse(BaseModel):
    account: AccountRead
    binding: AccountMemberBindingRead


class BootstrapAccountCompleteRequest(BaseModel):
    household_id: str = Field(min_length=1)
    member_id: str = Field(min_length=1)
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)
