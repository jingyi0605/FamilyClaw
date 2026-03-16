from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.household.service import get_household_or_404
from app.modules.plugin.service import list_registered_plugins_for_household

from . import repository
from .models import ChannelPluginAccount
from .schemas import ChannelAccountCreate, ChannelAccountRead, ChannelAccountUpdate


class ChannelAccountServiceError(ValueError):
    pass


def list_channel_accounts(db: Session, *, household_id: str) -> list[ChannelAccountRead]:
    get_household_or_404(db, household_id)
    return [_to_channel_account_read(item) for item in repository.list_channel_plugin_accounts(db, household_id=household_id)]


def get_channel_account_or_404(db: Session, *, household_id: str, account_id: str) -> ChannelPluginAccount:
    get_household_or_404(db, household_id)
    row = repository.get_channel_plugin_account(db, account_id)
    if row is None or row.household_id != household_id:
        raise ChannelAccountServiceError("channel account not found")
    return row


def create_channel_account(
    db: Session,
    *,
    household_id: str,
    payload: ChannelAccountCreate,
) -> ChannelAccountRead:
    get_household_or_404(db, household_id)
    plugin = _resolve_channel_plugin(db, household_id=household_id, plugin_id=payload.plugin_id)
    spec = plugin.capabilities.channel
    assert spec is not None
    if payload.connection_mode not in spec.inbound_modes:
        raise ChannelAccountServiceError("channel connection_mode is not supported by plugin manifest")

    now = utc_now_iso()
    account_code = _resolve_account_code(
        db,
        household_id=household_id,
        platform_code=spec.platform_code,
        requested_account_code=payload.account_code,
    )
    row = ChannelPluginAccount(
        id=new_uuid(),
        household_id=household_id,
        plugin_id=plugin.id,
        platform_code=spec.platform_code,
        account_code=account_code,
        display_name=payload.display_name.strip(),
        connection_mode=payload.connection_mode,
        config_json=dump_json(payload.config) or "{}",
        status=payload.status,
        created_at=now,
        updated_at=now,
    )
    repository.add_channel_plugin_account(db, row)
    db.flush()
    return _to_channel_account_read(row)


def update_channel_account(
    db: Session,
    *,
    household_id: str,
    account_id: str,
    payload: ChannelAccountUpdate,
) -> ChannelAccountRead:
    row = get_channel_account_or_404(db, household_id=household_id, account_id=account_id)
    plugin = _resolve_channel_plugin(db, household_id=household_id, plugin_id=row.plugin_id)
    spec = plugin.capabilities.channel
    assert spec is not None

    if payload.display_name is not None:
        row.display_name = payload.display_name.strip()
    if payload.connection_mode is not None:
        if payload.connection_mode not in spec.inbound_modes:
            raise ChannelAccountServiceError("channel connection_mode is not supported by plugin manifest")
        row.connection_mode = payload.connection_mode
    if payload.config is not None:
        row.config_json = dump_json(payload.config) or "{}"
    if payload.status is not None:
        row.status = payload.status
    if payload.last_probe_status is not None:
        row.last_probe_status = payload.last_probe_status
    if payload.last_error_code is not None:
        row.last_error_code = payload.last_error_code
    if payload.last_error_message is not None:
        row.last_error_message = payload.last_error_message
    if payload.last_inbound_at is not None:
        row.last_inbound_at = payload.last_inbound_at
    if payload.last_outbound_at is not None:
        row.last_outbound_at = payload.last_outbound_at
    row.updated_at = utc_now_iso()
    db.flush()
    return _to_channel_account_read(row)


def _resolve_channel_plugin(db: Session, *, household_id: str, plugin_id: str):
    snapshot = list_registered_plugins_for_household(db, household_id=household_id)
    plugin = next((item for item in snapshot.items if item.id == plugin_id), None)
    if plugin is None:
        raise ChannelAccountServiceError("channel plugin not found")
    if not plugin.enabled:
        raise ChannelAccountServiceError("channel plugin is disabled for current household")
    if "channel" not in plugin.types:
        raise ChannelAccountServiceError("plugin is not a channel plugin")
    spec = plugin.capabilities.channel
    if spec is None or spec.reserved or spec.platform_code is None:
        raise ChannelAccountServiceError("channel plugin manifest is incomplete")
    return plugin


def _resolve_account_code(
    db: Session,
    *,
    household_id: str,
    platform_code: str,
    requested_account_code: str | None,
) -> str:
    normalized = (requested_account_code or "").strip()
    if normalized:
        return normalized

    base_code = f"{platform_code}-account"
    for _ in range(10):
        candidate = f"{base_code}-{new_uuid().replace('-', '')[:8]}"
        exists = repository.get_channel_plugin_account_by_account_code(
            db,
            household_id=household_id,
            account_code=candidate,
        )
        if exists is None:
            return candidate
    raise ChannelAccountServiceError("failed to generate unique channel account code")


def _to_channel_account_read(row: ChannelPluginAccount) -> ChannelAccountRead:
    config = load_json(row.config_json)
    return ChannelAccountRead(
        id=row.id,
        household_id=row.household_id,
        plugin_id=row.plugin_id,
        platform_code=row.platform_code,
        account_code=row.account_code,
        display_name=row.display_name,
        connection_mode=row.connection_mode,
        config=config if isinstance(config, dict) else {},
        status=row.status,
        last_probe_status=row.last_probe_status,
        last_error_code=row.last_error_code,
        last_error_message=row.last_error_message,
        last_inbound_at=row.last_inbound_at,
        last_outbound_at=row.last_outbound_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
