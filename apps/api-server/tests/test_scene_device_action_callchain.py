import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.scene.schemas import SceneTemplateRead
from app.modules.scene.service import _execute_action_step


class SceneDeviceActionCallchainTests(unittest.TestCase):
    @patch("app.modules.scene.service.create_execution_step")
    @patch("app.modules.scene.service.execute_device_action")
    def test_scene_device_action_step_still_uses_device_action_entry(
        self,
        execute_device_action_mock,
        create_execution_step_mock,
    ) -> None:
        execute_device_action_mock.return_value = (
            SimpleNamespace(model_dump=lambda mode="json": {"result": "success"}),
            SimpleNamespace(details={}),
        )
        create_execution_step_mock.side_effect = lambda db, payload: payload

        template = SceneTemplateRead(
            id="scene-1",
            household_id="household-1",
            template_code="smart_homecoming",
            name="回家模式",
            description=None,
            enabled=True,
            priority=1,
            cooldown_seconds=60,
            trigger={},
            conditions=[],
            guards=[],
            actions=[],
            rollout_policy={},
            version=1,
            updated_by=None,
            updated_at="2026-03-15T00:00:00Z",
        )

        result = _execute_action_step(
            object(),
            household_id="household-1",
            template=template,
            execution_id="execution-1",
            action={
                "type": "device_action",
                "device_id": "device-1",
                "action": "turn_on",
                "params": {},
            },
            step_index=0,
            confirm_high_risk=False,
        )

        execute_device_action_mock.assert_called_once()
        payload = execute_device_action_mock.call_args.kwargs["payload"]
        self.assertEqual("household-1", payload.household_id)
        self.assertEqual("device-1", payload.device_id)
        self.assertEqual("turn_on", payload.action)
        self.assertEqual("scene.smart_homecoming", payload.reason)
        self.assertEqual("success", result.status)


if __name__ == "__main__":
    unittest.main()
