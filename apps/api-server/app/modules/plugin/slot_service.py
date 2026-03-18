from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.modules.plugin.schemas import PluginExecutionRequest, PluginRegistryItem
from app.modules.plugin.service import execute_household_plugin, list_registered_plugins_for_household

SlotName = Literal["memory_engine", "memory_provider", "context_engine"]
T = TypeVar("T")


class SlotServiceError(RuntimeError):
    pass


@dataclass(slots=True)
class ResolvedSlotPlugin:
    slot_name: SlotName
    plugin_id: str
    plugin: PluginRegistryItem


def resolve_active_slot_plugin(
    db: Session,
    *,
    household_id: str,
    slot_name: SlotName,
) -> ResolvedSlotPlugin | None:
    snapshot = list_registered_plugins_for_household(db, household_id=household_id)
    matched_plugins: list[PluginRegistryItem] = []

    for plugin in snapshot.items:
        if not plugin.enabled or slot_name not in plugin.types:
            continue
        slot_capability = getattr(plugin.capabilities, slot_name, None)
        if slot_capability is None or slot_capability.slot_name != slot_name:
            continue
        matched_plugins.append(plugin)

    if not matched_plugins:
        return None
    if len(matched_plugins) > 1:
        plugin_ids = ", ".join(sorted(plugin.id for plugin in matched_plugins))
        raise SlotServiceError(f"槽位 {slot_name} 存在多个已启用插件: {plugin_ids}")

    plugin = matched_plugins[0]
    return ResolvedSlotPlugin(slot_name=slot_name, plugin_id=plugin.id, plugin=plugin)


def invoke_slot_plugin(
    db: Session,
    *,
    household_id: str,
    slot_name: SlotName,
    operation: str,
    payload: dict[str, Any],
    fallback: Callable[[], T],
    output_model: type[BaseModel] | None = None,
) -> T | BaseModel | Any:
    try:
        resolved = resolve_active_slot_plugin(
            db,
            household_id=household_id,
            slot_name=slot_name,
        )
    except SlotServiceError:
        return fallback()

    if resolved is None:
        return fallback()

    execution = execute_household_plugin(
        db,
        household_id=household_id,
        request=PluginExecutionRequest(
            plugin_id=resolved.plugin_id,
            plugin_type=slot_name,
            trigger=f"slot:{slot_name}",
            payload={
                "slot_name": slot_name,
                "operation": operation,
                "input_contract_version": 1,
                "payload": payload,
            },
        ),
    )
    if not execution.success:
        return fallback()

    raw_output = execution.output
    if output_model is None:
        return raw_output

    try:
        return output_model.model_validate(raw_output or {})
    except ValidationError:
        return fallback()
