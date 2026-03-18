import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel

from app.modules.plugin.slot_service import invoke_slot_plugin, resolve_active_slot_plugin


class DemoSlotOutput(BaseModel):
    value: str


def _build_slot_plugin(slot_name: str, plugin_id: str = "demo-slot-plugin"):
    capability_map = {
        "memory_engine": None,
        "memory_provider": None,
        "context_engine": None,
    }
    capability_map[slot_name] = SimpleNamespace(slot_name=slot_name)
    return SimpleNamespace(
        id=plugin_id,
        enabled=True,
        types=[slot_name],
        capabilities=SimpleNamespace(**capability_map),
    )


class PluginSlotServiceTests(unittest.TestCase):
    def test_resolve_active_slot_plugin_returns_none_when_slot_unconfigured(self) -> None:
        with patch(
            "app.modules.plugin.slot_service.list_registered_plugins_for_household",
            return_value=SimpleNamespace(items=[]),
        ):
            resolved = resolve_active_slot_plugin(
                object(),
                household_id="household-demo",
                slot_name="context_engine",
            )

        self.assertIsNone(resolved)

    def test_invoke_slot_plugin_returns_validated_output_when_slot_plugin_succeeds(self) -> None:
        with patch(
            "app.modules.plugin.slot_service.list_registered_plugins_for_household",
            return_value=SimpleNamespace(items=[_build_slot_plugin("context_engine")]),
        ), patch(
            "app.modules.plugin.slot_service.execute_household_plugin",
            return_value=SimpleNamespace(success=True, output={"value": "from-slot"}),
        ):
            result = invoke_slot_plugin(
                object(),
                household_id="household-demo",
                slot_name="context_engine",
                operation="build_context_bundle",
                payload={"household_id": "household-demo"},
                output_model=DemoSlotOutput,
                fallback=lambda: DemoSlotOutput(value="from-fallback"),
            )

        self.assertIsInstance(result, DemoSlotOutput)
        assert isinstance(result, DemoSlotOutput)
        self.assertEqual("from-slot", result.value)

    def test_invoke_slot_plugin_falls_back_when_execution_fails(self) -> None:
        with patch(
            "app.modules.plugin.slot_service.list_registered_plugins_for_household",
            return_value=SimpleNamespace(items=[_build_slot_plugin("memory_provider")]),
        ), patch(
            "app.modules.plugin.slot_service.execute_household_plugin",
            return_value=SimpleNamespace(success=False, output=None),
        ):
            result = invoke_slot_plugin(
                object(),
                household_id="household-demo",
                slot_name="memory_provider",
                operation="query_memory",
                payload={"household_id": "household-demo"},
                output_model=DemoSlotOutput,
                fallback=lambda: DemoSlotOutput(value="from-fallback"),
            )

        self.assertIsInstance(result, DemoSlotOutput)
        assert isinstance(result, DemoSlotOutput)
        self.assertEqual("from-fallback", result.value)
