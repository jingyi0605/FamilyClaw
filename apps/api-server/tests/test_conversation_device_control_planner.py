import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext
from app.db.utils import dump_json, new_uuid
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.conversation.device_context_summary import ConversationDeviceContextSummary, ConversationDeviceContextTarget
from app.modules.conversation.device_control_planner import (
    ConversationDevicePlannerError,
    ConversationDevicePlannerResult,
    plan_device_control,
)
from app.modules.conversation.device_shortcut_service import normalize_device_shortcut_text
from app.modules.conversation.device_control_toolkit import (
    ConversationDeviceExecutionPlan,
    DeviceControlToolResult,
)
from app.modules.conversation.orchestrator import (
    ConversationIntent,
    ConversationIntentDetection,
    ConversationIntentLabel,
    ConversationLane,
    ConversationLaneSelection,
    run_orchestrated_turn,
)
from app.modules.conversation.repository import list_device_control_shortcuts_by_phrase
from app.modules.conversation.schemas import ConversationSessionCreate
from app.modules.conversation.service import create_conversation_session
from app.modules.device.models import Device, DeviceBinding
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.llm_task.output_models import (
    ConversationDevicePlannerPlanOutput,
    ConversationDevicePlannerStepOutput,
    ConversationDevicePlannerToolCallOutput,
)
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from tests.homeassistant_test_support import seed_homeassistant_integration_instance


class _FakeLlmResult:
    def __init__(self, *, data, text: str = "", raw_text: str | None = None, provider: str = "mock-provider") -> None:
        self.data = data
        self.text = text
        self.raw_text = raw_text if raw_text is not None else text
        self.provider = provider


class ConversationDeviceControlPlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.SessionLocal = self._db_helper.SessionLocal
        self.db = self.SessionLocal()

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Planner Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="Owner", role="admin"),
        )
        self.agent = create_agent(
            self.db,
            household_id=self.household.id,
            payload=AgentCreate(
                display_name="管家",
                agent_type="butler",
                self_identity="我是家庭管家",
                role_summary="负责家庭设备控制和日常对话",
                personality_traits=["直接", "稳重"],
                service_focus=["设备控制"],
                default_entry=True,
            ),
        )
        instance = seed_homeassistant_integration_instance(
            self.db,
            household_id=self.household.id,
            sync_rooms_enabled=False,
        )
        self.integration_instance_id = instance.id
        self.study_light_id = self._add_device_with_binding(
            name="书房主灯",
            device_type="light",
            entity_payloads=[
                {
                    "entity_id": "light.study_main",
                    "name": "书房主灯",
                    "domain": "light",
                    "state": "off",
                    "state_display": "关闭",
                    "control": {
                        "kind": "toggle",
                        "value": False,
                        "action_on": "turn_on",
                        "action_off": "turn_off",
                    },
                },
                {
                    "entity_id": "sensor.study_power",
                    "name": "书房功率",
                    "domain": "sensor",
                    "state": "15",
                    "state_display": "15W",
                    "control": {"kind": "none", "value": None},
                },
            ],
            primary_entity_id="light.study_main",
        )
        self.bedroom_light_id = self._add_device_with_binding(
            name="卧室壁灯",
            device_type="light",
            entity_payloads=[
                {
                    "entity_id": "light.bedroom_lamp",
                    "name": "卧室壁灯",
                    "domain": "light",
                    "state": "on",
                    "state_display": "开启",
                    "control": {
                        "kind": "toggle",
                        "value": True,
                        "action_on": "turn_on",
                        "action_off": "turn_off",
                    },
                }
            ],
            primary_entity_id="light.bedroom_lamp",
        )
        self.lock_device_id = self._add_device_with_binding(
            name="入户门锁",
            device_type="lock",
            entity_payloads=[
                {
                    "entity_id": "lock.front_door",
                    "name": "入户门锁",
                    "domain": "lock",
                    "state": "locked",
                    "state_display": "已上锁",
                }
            ],
            primary_entity_id="lock.front_door",
        )
        self.session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(household_id=self.household.id, active_agent_id=self.agent.id),
            actor=self._build_actor(),
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def test_plan_device_control_uses_tools_to_resolve_multi_entity_device(self) -> None:
        with patch(
            "app.modules.conversation.device_control_planner.invoke_llm",
            side_effect=[
                _FakeLlmResult(
                    data=ConversationDevicePlannerStepOutput(
                        outcome="tool_call",
                        reason="先搜索设备候选。",
                        tool_call=ConversationDevicePlannerToolCallOutput(
                            tool_name="search_controllable_entities",
                            arguments={"query": "书房灯", "limit": 5},
                        ),
                    )
                ),
                _FakeLlmResult(
                    data=ConversationDevicePlannerStepOutput(
                        outcome="tool_call",
                        reason="已经定位到设备，继续读取实体画像。",
                        tool_call=ConversationDevicePlannerToolCallOutput(
                            tool_name="get_device_entity_profile",
                            arguments={"device_id": self.study_light_id},
                        ),
                    )
                ),
                _FakeLlmResult(
                    data=ConversationDevicePlannerStepOutput(
                        outcome="final_plan",
                        reason="书房主灯下只有 light.study_main 能执行开灯。",
                        final_plan=ConversationDevicePlannerPlanOutput(
                            device_id=self.study_light_id,
                            entity_id="light.study_main",
                            action="turn_on",
                            params={},
                            confidence=0.92,
                            reason="书房主灯实体唯一可控。",
                            requires_high_risk_confirmation=False,
                        ),
                    )
                ),
            ],
        ), patch(
            "app.modules.conversation.device_control_planner.list_device_entities",
            return_value=self._build_validation_entity_list("light.study_main", "turn_on", "turn_off"),
        ):
            result = plan_device_control(
                self.db,
                household_id=self.household.id,
                message="打开书房灯",
            )

        self.assertIsNotNone(result.plan)
        assert result.plan is not None
        self.assertEqual(self.study_light_id, result.plan.device_id)
        self.assertEqual("light.study_main", result.plan.entity_id)
        self.assertEqual("tool_planner", result.resolution_trace["source"])
        self.assertEqual(2, len(result.resolution_trace["tool_steps"]))

    def test_plan_device_control_returns_clarification_for_ambiguous_candidates(self) -> None:
        with patch(
            "app.modules.conversation.device_control_planner.invoke_llm",
            side_effect=[
                _FakeLlmResult(
                    data=ConversationDevicePlannerStepOutput(
                        outcome="tool_call",
                        reason="先查有哪些灯。",
                        tool_call=ConversationDevicePlannerToolCallOutput(
                            tool_name="search_controllable_entities",
                            arguments={"query": "灯", "limit": 5},
                        ),
                    )
                ),
                _FakeLlmResult(
                    data=ConversationDevicePlannerStepOutput(
                        outcome="clarification",
                        reason="同样像目标的灯有两个。",
                        clarification_question="你要打开书房主灯，还是卧室壁灯？",
                        suggestions=["书房主灯", "卧室壁灯"],
                    )
                ),
            ],
        ):
            result = plan_device_control(
                self.db,
                household_id=self.household.id,
                message="打开灯",
            )

        self.assertIsNone(result.plan)
        self.assertIsNotNone(result.clarification)
        assert result.clarification is not None
        self.assertEqual("device_resolution_ambiguous", result.clarification.code)
        self.assertEqual(["书房主灯", "卧室壁灯"], result.clarification.suggestions)

    def test_plan_device_control_raises_parse_failed_with_debug_payload(self) -> None:
        with patch(
            "app.modules.conversation.device_control_planner.invoke_llm",
            return_value=_FakeLlmResult(
                data=None,
                text="模型直接回了人话，不是 JSON。",
                raw_text="我觉得你要关书房灯，所以直接执行吧。",
                provider="mock-provider",
            ),
        ):
            with self.assertRaises(ConversationDevicePlannerError) as exc_context:
                plan_device_control(
                    self.db,
                    household_id=self.household.id,
                    message="关闭书房灯",
                )

        exc = exc_context.exception
        self.assertEqual("planner_parse_failed", exc.code)
        self.assertEqual(1, exc.debug_payload["planner_step"])
        self.assertEqual("mock-provider", exc.debug_payload["provider"])
        self.assertIn("直接执行吧", exc.debug_payload["raw_text_preview"])
        self.assertIn("不是 JSON", exc.debug_payload["display_text_preview"])

    def test_planner_output_accepts_name_and_input_aliases(self) -> None:
        parsed = ConversationDevicePlannerStepOutput.model_validate(
            {
                "outcome": "tool_call",
                "reason": "先搜索设备候选。",
                "tool_call": {
                    "name": "search_controllable_entities",
                    "input": {"query": "书房灯", "limit": 1},
                },
            }
        )

        self.assertIsNotNone(parsed.tool_call)
        assert parsed.tool_call is not None
        self.assertEqual("search_controllable_entities", parsed.tool_call.tool_name)
        self.assertEqual({"query": "书房灯", "limit": 1}, parsed.tool_call.arguments)

    def test_planner_output_accepts_null_suggestions_and_params(self) -> None:
        parsed = ConversationDevicePlannerStepOutput.model_validate(
            {
                "outcome": "final_plan",
                "reason": None,
                "final_plan": {
                    "device_id": self.study_light_id,
                    "entity_id": "light.study_main",
                    "action": "turn_off",
                    "params": None,
                    "reason": None,
                    "requires_high_risk_confirmation": False,
                },
                "clarification_question": None,
                "suggestions": None,
            }
        )

        self.assertEqual("", parsed.reason)
        self.assertEqual([], parsed.suggestions)
        assert parsed.final_plan is not None
        self.assertEqual({}, parsed.final_plan.params)
        self.assertEqual("", parsed.final_plan.reason)

    def test_plan_device_control_injects_device_context_summary_into_prompt(self) -> None:
        device_context_summary = ConversationDeviceContextSummary(
            latest_target=ConversationDeviceContextTarget(
                source_type="device_state",
                message_id=new_uuid(),
                request_id=new_uuid(),
                created_at="2026-03-17T00:00:00Z",
                device_id=self.study_light_id,
                device_name="书房主灯",
                device_type="light",
                status="off",
            ),
            recent_targets=[
                ConversationDeviceContextTarget(
                    source_type="device_state",
                    message_id=new_uuid(),
                    request_id=new_uuid(),
                    created_at="2026-03-17T00:00:00Z",
                    device_id=self.study_light_id,
                    device_name="书房主灯",
                    device_type="light",
                    status="off",
                )
            ],
            unique_device_ids=[self.study_light_id],
            can_resume_control=True,
            resume_reason="最近对话上下文只指向一个设备，可以承接省略式设备控制。",
        )
        with patch(
            "app.modules.conversation.device_control_planner.invoke_llm",
            return_value=_FakeLlmResult(
                data=ConversationDevicePlannerStepOutput(
                    outcome="not_found",
                    reason="先验证提示词入参。",
                )
            ),
        ) as mocked_invoke:
            plan_device_control(
                self.db,
                household_id=self.household.id,
                message="帮我关掉",
                device_context_summary=device_context_summary,
            )

        variables = mocked_invoke.call_args.kwargs["variables"]
        self.assertIn("书房主灯", variables["device_context_summary"])
        self.assertIn("省略式设备控制可承接：是", variables["device_context_summary"])

    def test_plan_device_control_allows_temporarily_unavailable_but_identified_entity(self) -> None:
        with patch(
            "app.modules.conversation.device_control_planner.invoke_llm",
            return_value=_FakeLlmResult(
                data=ConversationDevicePlannerStepOutput(
                    outcome="final_plan",
                    reason="已经定位到书房主灯，继续走统一执行链判断是否可执行。",
                    final_plan=ConversationDevicePlannerPlanOutput(
                        device_id=self.study_light_id,
                        entity_id="light.study_main",
                        action="turn_off",
                        params={},
                        confidence=0.88,
                        reason="书房主灯是唯一匹配目标。",
                        requires_high_risk_confirmation=False,
                    ),
                )
            ),
        ), patch(
            "app.modules.conversation.device_control_planner.list_device_entities",
            return_value=self._build_validation_entity_list(
                "light.study_main",
                "turn_on",
                "turn_off",
                disabled=True,
            ),
        ):
            result = plan_device_control(
                self.db,
                household_id=self.household.id,
                message="帮我把书房灯关掉",
            )

        self.assertIsNotNone(result.plan)
        assert result.plan is not None
        self.assertEqual(self.study_light_id, result.plan.device_id)
        self.assertEqual("light.study_main", result.plan.entity_id)
        self.assertEqual("turn_off", result.plan.action)

    def test_plan_device_control_recovers_invalid_final_plan_from_unique_tool_candidate(self) -> None:
        with patch(
            "app.modules.conversation.device_control_planner.invoke_llm",
            side_effect=[
                _FakeLlmResult(
                    data=ConversationDevicePlannerStepOutput(
                        outcome="tool_call",
                        reason="先搜索书房灯候选。",
                        tool_call=ConversationDevicePlannerToolCallOutput(
                            tool_name="search_controllable_entities",
                            arguments={"query": "书房灯", "limit": 5},
                        ),
                    )
                ),
                _FakeLlmResult(
                    data=ConversationDevicePlannerStepOutput(
                        outcome="final_plan",
                        reason="模型直接产出了计划，但实体写错了。",
                        final_plan=ConversationDevicePlannerPlanOutput(
                            device_id=self.study_light_id,
                            entity_id="light.wrong_entity",
                            action="close",
                            params={},
                            confidence=0.61,
                            reason="书房灯应该关闭。",
                            requires_high_risk_confirmation=False,
                        ),
                    )
                ),
            ],
        ), patch(
            "app.modules.conversation.device_control_planner.device_control_tool_registry.execute",
            return_value=DeviceControlToolResult(
                tool_name="search_controllable_entities",
                items=[
                    {
                        "device_id": self.study_light_id,
                        "device_name": "书房主灯",
                        "device_type": "light",
                        "entity_id": "light.study_main",
                        "entity_name": "书房主灯",
                        "action_candidates": [
                            {"action": "turn_on", "params": {}, "label": "打开"},
                            {"action": "turn_off", "params": {}, "label": "关闭"},
                        ],
                    }
                ],
                summary="找到 1 个候选实体",
            ),
        ), patch(
            "app.modules.conversation.device_control_planner.list_device_entities",
            return_value=self._build_validation_entity_list("light.study_main", "turn_on", "turn_off"),
        ):
            result = plan_device_control(
                self.db,
                household_id=self.household.id,
                message="帮我关闭书房灯",
            )

        self.assertIsNotNone(result.plan)
        assert result.plan is not None
        self.assertEqual(self.study_light_id, result.plan.device_id)
        self.assertEqual("light.study_main", result.plan.entity_id)
        self.assertEqual("turn_off", result.plan.action)
        self.assertEqual("recovered_plan", result.resolution_trace["planner_outcome"])

    def test_run_orchestrated_turn_uses_planner_after_shortcut_miss(self) -> None:
        with patch(
            "app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service",
            return_value={"status": "ok"},
        ) as mocked_call:
            with patch(
                "app.modules.conversation.orchestrator.detect_conversation_intent",
                return_value=self._build_detection(),
            ), patch(
                "app.modules.conversation.orchestrator.select_conversation_lane",
                return_value=self._build_fast_action_lane(),
            ), patch(
                "app.modules.conversation.device_control_planner.invoke_llm",
                side_effect=[
                    _FakeLlmResult(
                        data=ConversationDevicePlannerStepOutput(
                            outcome="tool_call",
                            reason="先搜索设备候选。",
                            tool_call=ConversationDevicePlannerToolCallOutput(
                                tool_name="search_controllable_entities",
                                arguments={"query": "书房灯", "limit": 5},
                            ),
                        )
                    ),
                    _FakeLlmResult(
                        data=ConversationDevicePlannerStepOutput(
                            outcome="tool_call",
                            reason="继续看实体画像。",
                            tool_call=ConversationDevicePlannerToolCallOutput(
                                tool_name="get_device_entity_profile",
                                arguments={"device_id": self.study_light_id},
                            ),
                        )
                    ),
                    _FakeLlmResult(
                        data=ConversationDevicePlannerStepOutput(
                            outcome="final_plan",
                            reason="唯一可控实体已经明确。",
                            final_plan=ConversationDevicePlannerPlanOutput(
                                device_id=self.study_light_id,
                                entity_id="light.study_main",
                                action="turn_on",
                                params={},
                                confidence=0.95,
                                reason="书房主灯是唯一匹配。",
                                requires_high_risk_confirmation=False,
                            ),
                        )
                    ),
                ],
            ), patch(
                "app.modules.conversation.device_control_planner.list_device_entities",
                return_value=self._build_validation_entity_list("light.study_main", "turn_on", "turn_off"),
            ), patch(
                "app.modules.conversation.orchestrator.settings.conversation_lane_takeover_enabled",
                True,
            ):
                result = run_orchestrated_turn(
                    self.db,
                    session=self.session,
                    message="打开书房灯",
                    actor=self._build_actor(),
                    conversation_history=[],
                )

        self.assertEqual(ConversationIntent.FAST_ACTION, result.intent)
        self.assertEqual("tool_planner", result.facts[0]["extra"]["resolution_trace"]["source"])
        shortcuts = list_device_control_shortcuts_by_phrase(
            self.db,
            household_id=self.household.id,
            member_id=self.member.id,
            normalized_text=normalize_device_shortcut_text("打开书房灯"),
        )
        self.assertEqual(1, len(shortcuts))
        self.assertEqual("tool_planner", shortcuts[0].resolution_source)
        self.assertEqual("light.study_main", shortcuts[0].entity_id)
        mocked_call.assert_called_once_with(
            domain="light",
            service="turn_on",
            data={"entity_id": "light.study_main"},
        )

    def test_run_orchestrated_turn_requires_confirmation_for_planner_high_risk_action(self) -> None:
        with patch(
            "app.modules.conversation.orchestrator.detect_conversation_intent",
            return_value=self._build_detection(),
        ), patch(
            "app.modules.conversation.orchestrator.select_conversation_lane",
            return_value=self._build_fast_action_lane(),
        ), patch(
            "app.modules.conversation.orchestrator.plan_device_control",
            return_value=ConversationDevicePlannerResult(
                plan=ConversationDeviceExecutionPlan(
                    device_id=self.lock_device_id,
                    entity_id="lock.front_door",
                    action="unlock",
                    params={},
                    reason="conversation.fast_action.tool_planner",
                    resolution_trace={"source": "tool_planner"},
                ),
                resolution_trace={"source": "tool_planner"},
            ),
        ), patch(
            "app.modules.conversation.orchestrator.settings.conversation_lane_takeover_enabled",
            True,
        ), patch(
            "app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service",
            return_value={"status": "ok"},
        ) as mocked_call:
            result = run_orchestrated_turn(
                self.db,
                session=self.session,
                message="解锁入户门锁",
                actor=self._build_actor(),
                conversation_history=[],
            )

        self.assertEqual(ConversationIntent.FAST_ACTION, result.intent)
        self.assertIn("确认解锁", result.text)
        self.assertEqual([], result.facts)
        mocked_call.assert_not_called()

    def test_run_orchestrated_turn_logs_structured_debug_event_for_planner_shortcut_writeback(self) -> None:
        logger_mock = Mock()
        with patch(
            "app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service",
            return_value={"status": "ok"},
        ), patch(
            "app.modules.conversation.orchestrator.detect_conversation_intent",
            return_value=self._build_detection(),
        ), patch(
            "app.modules.conversation.orchestrator.select_conversation_lane",
            return_value=self._build_fast_action_lane(),
        ), patch(
            "app.modules.conversation.device_control_planner.invoke_llm",
            side_effect=[
                _FakeLlmResult(
                    data=ConversationDevicePlannerStepOutput(
                        outcome="tool_call",
                        reason="先搜索设备候选。",
                        tool_call=ConversationDevicePlannerToolCallOutput(
                            tool_name="search_controllable_entities",
                            arguments={"query": "书房灯", "limit": 5},
                        ),
                    )
                ),
                _FakeLlmResult(
                    data=ConversationDevicePlannerStepOutput(
                        outcome="tool_call",
                        reason="继续读取实体画像。",
                        tool_call=ConversationDevicePlannerToolCallOutput(
                            tool_name="get_device_entity_profile",
                            arguments={"device_id": self.study_light_id},
                        ),
                    )
                ),
                _FakeLlmResult(
                    data=ConversationDevicePlannerStepOutput(
                        outcome="final_plan",
                        reason="唯一可控实体已经明确。",
                        final_plan=ConversationDevicePlannerPlanOutput(
                            device_id=self.study_light_id,
                            entity_id="light.study_main",
                            action="turn_on",
                            params={},
                            confidence=0.95,
                            reason="书房主灯是唯一匹配。",
                            requires_high_risk_confirmation=False,
                        ),
                    )
                ),
            ],
        ), patch(
            "app.modules.conversation.device_control_planner.list_device_entities",
            return_value=self._build_validation_entity_list("light.study_main", "turn_on", "turn_off"),
        ), patch(
            "app.modules.conversation.orchestrator.settings.conversation_lane_takeover_enabled",
            True,
        ), patch(
            "app.modules.conversation.orchestrator.get_conversation_debug_logger",
            return_value=logger_mock,
        ):
            run_orchestrated_turn(
                self.db,
                session=self.session,
                message="打开书房灯",
                actor=self._build_actor(),
                conversation_history=[],
                request_context={"request_id": "req-planner-1", "session_id": self.session.id},
            )

        logged_events = [json.loads(call.args[0]) for call in logger_mock.info.call_args_list]
        logged_stages = [event["stage"] for event in logged_events]
        expected_stages = [
            "fast_action.plan.resolve.started",
            "fast_action.shortcut.miss",
            "fast_action.tool_planner.started",
            "fast_action.tool_planner.completed",
            "fast_action.plan.selected",
            "fast_action.execution.started",
            "fast_action.shortcut.upserted",
            "fast_action.execution.completed",
        ]
        for stage in expected_stages:
            self.assertIn(stage, logged_stages)
        stage_indexes = [logged_stages.index(stage) for stage in expected_stages]
        self.assertEqual(stage_indexes, sorted(stage_indexes))
        self.assertTrue(
            any(
                event["stage"] == "fast_action.shortcut.upserted"
                and event["payload"].get("resolution_source") == "tool_planner"
                and event["request_id"] == "req-planner-1"
                and event["session_id"] == self.session.id
                for event in logged_events
            )
        )

    def test_run_orchestrated_turn_falls_back_to_legacy_when_planner_fails(self) -> None:
        with patch(
            "app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service",
            return_value={"status": "ok"},
        ) as mocked_call:
            with patch(
                "app.modules.conversation.orchestrator.detect_conversation_intent",
                return_value=self._build_detection(),
            ), patch(
                "app.modules.conversation.orchestrator.select_conversation_lane",
                return_value=self._build_fast_action_lane(),
            ), patch(
                "app.modules.conversation.orchestrator.plan_device_control",
                side_effect=ConversationDevicePlannerError("planner_parse_failed"),
            ), patch(
                "app.modules.conversation.orchestrator._infer_fast_action",
                return_value="turn_on",
            ), patch(
                "app.modules.conversation.orchestrator._match_fast_action_devices",
                return_value=[self.db.get(Device, self.study_light_id)],
            ), patch(
                "app.modules.conversation.orchestrator._resolve_fast_action_entity_for_device",
                return_value=("light.study_main", None),
            ), patch(
                "app.modules.conversation.orchestrator.settings.conversation_lane_takeover_enabled",
                True,
            ):
                result = run_orchestrated_turn(
                    self.db,
                    session=self.session,
                    message="打开书房灯",
                    actor=self._build_actor(),
                    conversation_history=[],
                )

        self.assertEqual(ConversationIntent.FAST_ACTION, result.intent)
        self.assertEqual("legacy_rule", result.facts[0]["extra"]["resolution_trace"]["source"])
        mocked_call.assert_called_once_with(
            domain="light",
            service="turn_on",
            data={"entity_id": "light.study_main"},
        )

    def test_run_orchestrated_turn_logs_planner_failure_debug_payload(self) -> None:
        logger_mock = Mock()
        with patch(
            "app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service",
            return_value={"status": "ok"},
        ), patch(
            "app.modules.conversation.orchestrator.detect_conversation_intent",
            return_value=self._build_detection(),
        ), patch(
            "app.modules.conversation.orchestrator.select_conversation_lane",
            return_value=self._build_fast_action_lane(),
        ), patch(
            "app.modules.conversation.orchestrator.plan_device_control",
            side_effect=ConversationDevicePlannerError(
                "planner_parse_failed",
                debug_payload={
                    "planner_step": 1,
                    "provider": "mock-provider",
                    "raw_text_preview": "我觉得就是书房小爱音箱。",
                    "display_text_preview": "不是合法 JSON。",
                },
            ),
        ), patch(
            "app.modules.conversation.orchestrator._infer_fast_action",
            return_value="turn_on",
        ), patch(
            "app.modules.conversation.orchestrator._match_fast_action_devices",
            return_value=[self.db.get(Device, self.study_light_id)],
        ), patch(
            "app.modules.conversation.orchestrator._resolve_fast_action_entity_for_device",
            return_value=("light.study_main", None),
        ), patch(
            "app.modules.conversation.orchestrator.settings.conversation_lane_takeover_enabled",
            True,
        ), patch(
            "app.modules.conversation.orchestrator.get_conversation_debug_logger",
            return_value=logger_mock,
        ):
            run_orchestrated_turn(
                self.db,
                session=self.session,
                message="打开书房灯",
                actor=self._build_actor(),
                conversation_history=[],
                request_context={"request_id": "req-planner-fail", "session_id": self.session.id},
            )

        logged_events = [json.loads(call.args[0]) for call in logger_mock.info.call_args_list]
        planner_failed_events = [event for event in logged_events if event["stage"] == "fast_action.tool_planner.failed"]
        self.assertEqual(1, len(planner_failed_events))
        payload = planner_failed_events[0]["payload"]
        self.assertEqual("planner_parse_failed", payload["error"])
        self.assertEqual("mock-provider", payload["provider"])
        self.assertIn("书房小爱音箱", payload["raw_text_preview"])
        self.assertIn("不是合法 JSON", payload["display_text_preview"])

    def _build_actor(self) -> ActorContext:
        return ActorContext(
            role="admin",
            actor_type="member",
            actor_id=self.member.id,
            account_id="account-1",
            account_type="household",
            account_status="active",
            username="owner",
            household_id=self.household.id,
            member_id=self.member.id,
            member_role="admin",
            is_authenticated=True,
        )

    def _build_detection(self) -> ConversationIntentDetection:
        return ConversationIntentDetection(
            primary_intent=ConversationIntentLabel.FREE_CHAT,
            confidence=0.8,
            reason="test",
        )

    def _build_fast_action_lane(self) -> ConversationLaneSelection:
        return ConversationLaneSelection(
            lane=ConversationLane.FAST_ACTION,
            confidence=0.9,
            reason="test-fast-action",
            target_kind="device_action",
            requires_clarification=False,
            source="test",
        )

    def _add_device_with_binding(
        self,
        *,
        name: str,
        device_type: str,
        entity_payloads: list[dict],
        primary_entity_id: str,
    ) -> str:
        device = Device(
            id=new_uuid(),
            household_id=self.household.id,
            room_id=None,
            name=name,
            device_type=device_type,
            vendor="ha",
            status="active",
            controllable=1,
        )
        self.db.add(device)
        self.db.flush()
        self.db.add(
            DeviceBinding(
                id=new_uuid(),
                device_id=device.id,
                integration_instance_id=self.integration_instance_id,
                platform="home_assistant",
                plugin_id="homeassistant",
                binding_version=1,
                external_entity_id=primary_entity_id,
                external_device_id=f"ext-{device.id}",
                capabilities=dump_json(
                    {
                        "primary_entity_id": primary_entity_id,
                        "entity_ids": [item["entity_id"] for item in entity_payloads],
                        "entities": entity_payloads,
                    }
                ),
            )
        )
        self.db.flush()
        return device.id

    def _build_validation_entity_list(
        self,
        entity_id: str,
        action_on: str,
        action_off: str,
        *,
        disabled: bool = False,
    ):
        return SimpleNamespace(
            items=[
                SimpleNamespace(
                    entity_id=entity_id,
                    read_only=False,
                    control=SimpleNamespace(
                        kind="toggle",
                        action_on=action_on,
                        action_off=action_off,
                        action=None,
                        options=[],
                        disabled=disabled,
                    ),
                )
            ]
        )


if __name__ == "__main__":
    unittest.main()
