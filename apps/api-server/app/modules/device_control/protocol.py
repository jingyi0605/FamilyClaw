from __future__ import annotations

from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

DeviceActionName = Literal[
    "turn_on",
    "turn_off",
    "set_brightness",
    "set_temperature",
    "set_hvac_mode",
    "open",
    "close",
    "stop",
    "play_pause",
    "set_volume",
    "lock",
    "unlock",
]
RiskLevel = Literal["low", "medium", "high"]


class DeviceActionDefinition(BaseModel):
    action: DeviceActionName
    supported_device_types: tuple[str, ...]
    risk_level: RiskLevel
    params_schema: dict[str, Any] = Field(default_factory=dict)
    required_permissions: tuple[str, ...] = ("device.control",)
    idempotent_scope: str = "device_action"


class DeviceControlProtocolError(ValueError):
    def __init__(self, message: str, *, error_code: str, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.field = field


def _ensure_object(params: dict[str, Any] | None) -> dict[str, Any]:
    if params is None:
        return {}
    if not isinstance(params, dict):
        raise DeviceControlProtocolError(
            "动作参数必须是对象",
            error_code="invalid_action_params",
            field="params",
        )
    return params


def _normalize_no_params(params: dict[str, Any]) -> dict[str, Any]:
    _ensure_object(params)
    return {}


def _normalize_percent(
    *,
    params: dict[str, Any],
    canonical_key: str,
    legacy_key: str,
    minimum: int,
    maximum: int,
) -> dict[str, Any]:
    normalized_params = _ensure_object(params)
    raw_value = normalized_params.get(canonical_key)
    if raw_value is None:
        raw_value = normalized_params.get(legacy_key)
        if legacy_key == "volume" and isinstance(raw_value, (int, float)) and 0 <= float(raw_value) <= 1:
            raw_value = float(raw_value) * 100

    if not isinstance(raw_value, (int, float)):
        raise DeviceControlProtocolError(
            f"{canonical_key} 必须是数字",
            error_code="invalid_action_params",
            field=f"params.{canonical_key}",
        )

    value = int(round(float(raw_value)))
    if value < minimum or value > maximum:
        raise DeviceControlProtocolError(
            f"{canonical_key} 必须在 {minimum}~{maximum} 之间",
            error_code="invalid_action_params",
            field=f"params.{canonical_key}",
        )
    return {canonical_key: value}


def _normalize_temperature(params: dict[str, Any]) -> dict[str, Any]:
    normalized_params = _ensure_object(params)
    raw_value = normalized_params.get("temperature_c")
    if raw_value is None:
        raw_value = normalized_params.get("temperature")
    if not isinstance(raw_value, (int, float)):
        raise DeviceControlProtocolError(
            "temperature_c 必须是数字",
            error_code="invalid_action_params",
            field="params.temperature_c",
        )
    value = float(raw_value)
    if value < 16 or value > 30:
        raise DeviceControlProtocolError(
            "temperature_c 必须在 16~30 之间",
            error_code="invalid_action_params",
            field="params.temperature_c",
        )
    return {"temperature_c": value}


def _normalize_hvac_mode(params: dict[str, Any]) -> dict[str, Any]:
    normalized_params = _ensure_object(params)
    raw_value = normalized_params.get("hvac_mode")
    allowed = {"cool", "heat", "auto", "dry", "fan_only", "off"}
    if not isinstance(raw_value, str) or raw_value.strip() not in allowed:
        raise DeviceControlProtocolError(
            "hvac_mode 不合法",
            error_code="invalid_action_params",
            field="params.hvac_mode",
        )
    return {"hvac_mode": raw_value.strip()}


Normalizer = Callable[[dict[str, Any]], dict[str, Any]]


_ACTION_NORMALIZERS: dict[DeviceActionName, Normalizer] = {
    "turn_on": _normalize_no_params,
    "turn_off": _normalize_no_params,
    "set_brightness": lambda params: _normalize_percent(
        params=params,
        canonical_key="brightness_pct",
        legacy_key="brightness",
        minimum=1,
        maximum=100,
    ),
    "set_temperature": _normalize_temperature,
    "set_hvac_mode": _normalize_hvac_mode,
    "open": _normalize_no_params,
    "close": _normalize_no_params,
    "stop": _normalize_no_params,
    "play_pause": _normalize_no_params,
    "set_volume": lambda params: _normalize_percent(
        params=params,
        canonical_key="volume_pct",
        legacy_key="volume",
        minimum=0,
        maximum=100,
    ),
    "lock": _normalize_no_params,
    "unlock": _normalize_no_params,
}


class DeviceControlProtocolRegistry:
    def __init__(self) -> None:
        self._definitions: dict[DeviceActionName, DeviceActionDefinition] = {
            "turn_on": DeviceActionDefinition(
                action="turn_on",
                supported_device_types=("light", "ac", "speaker"),
                risk_level="low",
            ),
            "turn_off": DeviceActionDefinition(
                action="turn_off",
                supported_device_types=("light", "ac", "speaker"),
                risk_level="low",
            ),
            "set_brightness": DeviceActionDefinition(
                action="set_brightness",
                supported_device_types=("light",),
                risk_level="low",
                params_schema={"brightness_pct": {"type": "integer", "minimum": 1, "maximum": 100}},
            ),
            "set_temperature": DeviceActionDefinition(
                action="set_temperature",
                supported_device_types=("ac",),
                risk_level="medium",
                params_schema={"temperature_c": {"type": "number", "minimum": 16, "maximum": 30}},
            ),
            "set_hvac_mode": DeviceActionDefinition(
                action="set_hvac_mode",
                supported_device_types=("ac",),
                risk_level="medium",
                params_schema={
                    "hvac_mode": {
                        "type": "string",
                        "enum": ["cool", "heat", "auto", "dry", "fan_only", "off"],
                    }
                },
            ),
            "open": DeviceActionDefinition(
                action="open",
                supported_device_types=("curtain",),
                risk_level="low",
            ),
            "close": DeviceActionDefinition(
                action="close",
                supported_device_types=("curtain",),
                risk_level="low",
            ),
            "stop": DeviceActionDefinition(
                action="stop",
                supported_device_types=("curtain",),
                risk_level="low",
            ),
            "play_pause": DeviceActionDefinition(
                action="play_pause",
                supported_device_types=("speaker",),
                risk_level="low",
            ),
            "set_volume": DeviceActionDefinition(
                action="set_volume",
                supported_device_types=("speaker",),
                risk_level="low",
                params_schema={"volume_pct": {"type": "integer", "minimum": 0, "maximum": 100}},
            ),
            "lock": DeviceActionDefinition(
                action="lock",
                supported_device_types=("lock",),
                risk_level="medium",
            ),
            "unlock": DeviceActionDefinition(
                action="unlock",
                supported_device_types=("lock",),
                risk_level="high",
            ),
        }

    def list_definitions(self) -> list[DeviceActionDefinition]:
        return list(self._definitions.values())

    def get_definition(self, action: str) -> DeviceActionDefinition:
        definition = self._definitions.get(action)
        if definition is None:
            raise DeviceControlProtocolError(
                "动作不存在",
                error_code="action_not_supported",
                field="action",
            )
        return definition

    def validate_action_for_device(
        self,
        *,
        device_type: str,
        action: str,
        params: dict[str, Any] | None,
    ) -> tuple[DeviceActionDefinition, dict[str, Any]]:
        definition = self.get_definition(action)
        if device_type not in definition.supported_device_types:
            raise DeviceControlProtocolError(
                "当前设备类型不支持该动作",
                error_code="action_not_supported",
                field="action",
            )
        normalizer = _ACTION_NORMALIZERS[definition.action]
        normalized_params = normalizer(_ensure_object(params))
        return definition, normalized_params

    def is_high_risk(self, action: str) -> bool:
        return self.get_definition(action).risk_level == "high"


device_control_protocol_registry = DeviceControlProtocolRegistry()
