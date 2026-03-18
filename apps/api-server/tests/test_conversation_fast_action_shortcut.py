import unittest
from unittest.mock import Mock, patch

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext
from app.db.utils import dump_json, new_uuid
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.conversation.device_context_summary import (
    ConversationDeviceContextSummary,
    ConversationDeviceContextTarget,
)
from app.modules.conversation.device_control_planner import (
    ConversationDevicePlannerError,
    ConversationDevicePlannerResult,
)
from app.modules.conversation.device_control_toolkit import ConversationDeviceExecutionPlan
from app.modules.conversation.device_shortcut_service import (
    DeviceShortcutUpsertPayload,
    normalize_device_shortcut_text,
    upsert_device_shortcut,
)
from app.modules.conversation.orchestrator import (
    ConversationIntent,
    ConversationIntentDetection,
    ConversationIntentLabel,
    ConversationLane,
    ConversationLaneSelection,
    _match_fast_action_devices,
    run_orchestrated_turn,
    select_conversation_lane,
)
from app.modules.conversation.repository import list_device_control_shortcuts_by_phrase
from app.modules.conversation.schemas import ConversationSessionCreate
from app.modules.conversation.service import create_conversation_session
from app.modules.device.models import Device, DeviceBinding
from app.modules.family_qa.schemas import FamilyQaQueryResponse
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from tests.homeassistant_test_support import seed_homeassistant_integration_instance


class ConversationFastActionShortcutTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.SessionLocal = self._db_helper.SessionLocal
        self.db = self.SessionLocal()

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Shortcut Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
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
                role_summary="负责家庭设备和日常对话",
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
        self.light_device_id = self._add_device_with_binding(
            name="客厅灯",
            device_type="light",
            entity_payloads=[
                {
                    "entity_id": "light.living_room_main",
                    "name": "客厅主灯",
                    "domain": "light",
                    "state": "on",
                    "state_display": "开启",
                    "control": {
                        "kind": "toggle",
                        "value": True,
                        "action_on": "turn_on",
                        "action_off": "turn_off",
                    },
                },
                {
                    "entity_id": "sensor.living_room_power",
                    "name": "客厅灯功率",
                    "domain": "sensor",
                    "state": "18",
                    "state_display": "18W",
                    "control": {"kind": "none", "value": None},
                },
            ],
            primary_entity_id="light.living_room_main",
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

    def test_run_orchestrated_turn_prefers_shortcut_and_touches_hit_count(self) -> None:
        shortcut = upsert_device_shortcut(
            self.db,
            payload=DeviceShortcutUpsertPayload(
                household_id=self.household.id,
                member_id=self.member.id,
                source_text="把客厅灯关掉",
                device_id=self.light_device_id,
                entity_id="light.living_room_main",
                action="turn_off",
                params={},
                confidence=0.96,
            ),
        )
        self.db.commit()

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
                "app.modules.conversation.orchestrator._infer_fast_action",
                return_value="turn_off",
            ), patch(
                "app.modules.conversation.orchestrator._match_fast_action_devices",
                return_value=[self.db.get(Device, self.light_device_id)],
            ), patch(
                "app.modules.conversation.orchestrator._resolve_fast_action_entity_for_device",
                return_value=("light.living_room_main", None),
            ), patch(
                "app.modules.conversation.orchestrator.settings.conversation_lane_takeover_enabled",
                True,
            ):
                result = run_orchestrated_turn(
                    self.db,
                    session=self.session,
                    message="把客厅灯关掉",
                    actor=self._build_actor(),
                    conversation_history=[],
                )

        self.db.refresh(shortcut)
        self.assertEqual(ConversationIntent.FAST_ACTION, result.intent)
        self.assertEqual(2, shortcut.hit_count)
        self.assertEqual("turn_off", result.facts[0]["extra"]["action"])
        self.assertEqual("light.living_room_main", result.facts[0]["extra"]["entity_id"])
        mocked_call.assert_called_once_with(
            domain="light",
            service="turn_off",
            data={"entity_id": "light.living_room_main"},
        )

    def test_run_orchestrated_turn_reuses_shortcut_for_semantic_alias(self) -> None:
        shortcut = upsert_device_shortcut(
            self.db,
            payload=DeviceShortcutUpsertPayload(
                household_id=self.household.id,
                member_id=self.member.id,
                source_text="打开客厅灯",
                device_id=self.light_device_id,
                entity_id="light.living_room_main",
                action="turn_on",
                params={},
                confidence=0.94,
            ),
        )
        self.db.commit()

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
                "app.modules.conversation.orchestrator._infer_fast_action",
                return_value="turn_on",
            ), patch(
                "app.modules.conversation.orchestrator._match_fast_action_devices",
                return_value=[self.db.get(Device, self.light_device_id)],
            ), patch(
                "app.modules.conversation.orchestrator._resolve_fast_action_entity_for_device",
                return_value=("light.living_room_main", None),
            ), patch(
                "app.modules.conversation.orchestrator.settings.conversation_lane_takeover_enabled",
                True,
            ):
                result = run_orchestrated_turn(
                    self.db,
                    session=self.session,
                    message="开启客厅灯",
                    actor=self._build_actor(),
                    conversation_history=[],
                )

        self.db.refresh(shortcut)
        shortcuts = list_device_control_shortcuts_by_phrase(
            self.db,
            household_id=self.household.id,
            member_id=self.member.id,
            normalized_text=normalize_device_shortcut_text("打开客厅灯"),
        )
        self.assertEqual(ConversationIntent.FAST_ACTION, result.intent)
        self.assertEqual(2, shortcut.hit_count)
        self.assertEqual(1, len(shortcuts))
        self.assertEqual("turn_on", result.facts[0]["extra"]["action"])
        mocked_call.assert_called_once_with(
            domain="light",
            service="turn_on",
            data={"entity_id": "light.living_room_main"},
        )

    def test_stale_shortcut_falls_back_to_legacy_entity_resolution(self) -> None:
        _ = upsert_device_shortcut(
            self.db,
            payload=DeviceShortcutUpsertPayload(
                household_id=self.household.id,
                member_id=self.member.id,
                source_text="把客厅灯关掉",
                device_id=self.light_device_id,
                entity_id="light.deleted_entity",
                action="turn_off",
                params={},
                confidence=0.61,
            ),
        )
        self.db.commit()

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
                "app.modules.conversation.orchestrator._infer_fast_action",
                return_value="turn_off",
            ), patch(
                "app.modules.conversation.orchestrator._match_fast_action_devices",
                return_value=[self.db.get(Device, self.light_device_id)],
            ), patch(
                "app.modules.conversation.orchestrator._resolve_fast_action_entity_for_device",
                return_value=("light.living_room_main", None),
            ), patch(
                "app.modules.conversation.orchestrator.settings.conversation_lane_takeover_enabled",
                True,
            ):
                result = run_orchestrated_turn(
                    self.db,
                    session=self.session,
                    message="把客厅灯关掉",
                    actor=self._build_actor(),
                    conversation_history=[],
                )

        shortcuts = list_device_control_shortcuts_by_phrase(
            self.db,
            household_id=self.household.id,
            member_id=self.member.id,
            normalized_text=normalize_device_shortcut_text("把客厅灯关掉"),
        )
        self.assertEqual(ConversationIntent.FAST_ACTION, result.intent)
        self.assertEqual(2, len(shortcuts))
        stale_shortcut = next(item for item in shortcuts if item.entity_id == "light.deleted_entity")
        refreshed_shortcut = next(item for item in shortcuts if item.entity_id == "light.living_room_main")
        self.assertEqual("stale", stale_shortcut.status)
        self.assertEqual("active", refreshed_shortcut.status)
        self.assertEqual("legacy_rule", refreshed_shortcut.resolution_source)
        self.assertEqual("legacy_rule", result.facts[0]["extra"]["resolution_trace"]["source"])
        mocked_call.assert_called_once_with(
            domain="light",
            service="turn_off",
            data={"entity_id": "light.living_room_main"},
        )

    def test_match_fast_action_devices_prefers_light_when_message_explicitly_mentions_light(self) -> None:
        speaker = Device(
            id=new_uuid(),
            household_id=self.household.id,
            room_id=None,
            name="书房小爱音箱",
            device_type="speaker",
            vendor="ha",
            status="active",
            controllable=1,
        )
        study_light = Device(
            id=new_uuid(),
            household_id=self.household.id,
            room_id=None,
            name="书房灯",
            device_type="light",
            vendor="ha",
            status="active",
            controllable=1,
        )

        matched = _match_fast_action_devices(
            message="帮我关闭书房灯吧",
            devices=[speaker, study_light],
            action="turn_off",
        )

        self.assertEqual(["书房灯"], [item.name for item in matched])

    def test_run_orchestrated_turn_uses_recent_device_context_for_action_only_followup(self) -> None:
        device_context_summary = self._build_device_context_summary(device_id=self.light_device_id, device_name="客厅灯")

        with patch(
            "app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service",
            return_value={"status": "ok"},
        ) as mocked_call, patch(
            "app.modules.conversation.orchestrator.detect_conversation_intent",
            return_value=self._build_structured_qa_detection(),
        ), patch(
            "app.modules.conversation.orchestrator.plan_device_control",
            return_value=ConversationDevicePlannerResult(
                plan=ConversationDeviceExecutionPlan(
                    device_id=self.light_device_id,
                    entity_id="light.living_room_main",
                    action="turn_off",
                    params={},
                    reason="conversation.fast_action.tool_planner",
                    resolution_trace={"source": "tool_planner"},
                ),
                resolution_trace={"source": "tool_planner"},
            ),
        ), patch(
            "app.modules.conversation.orchestrator.settings.conversation_lane_takeover_enabled",
            True,
        ):
            result = run_orchestrated_turn(
                self.db,
                session=self.session,
                message="帮我关掉",
                actor=self._build_actor(),
                conversation_history=[],
                device_context_summary=device_context_summary,
            )

        self.assertEqual(ConversationIntent.FAST_ACTION, result.intent)
        self.assertEqual("device_context", result.lane_selection.source)
        mocked_call.assert_called_once_with(
            domain="light",
            service="turn_off",
            data={"entity_id": "light.living_room_main"},
        )

    def test_run_orchestrated_turn_reuses_context_target_when_planner_parse_fails(self) -> None:
        device_context_summary = self._build_device_context_summary(device_id=self.light_device_id, device_name="客厅灯")

        with patch(
            "app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service",
            return_value={"status": "ok"},
        ) as mocked_call, patch(
            "app.modules.conversation.orchestrator.detect_conversation_intent",
            return_value=self._build_structured_qa_detection(),
        ), patch(
            "app.modules.conversation.orchestrator.select_conversation_lane",
            return_value=ConversationLaneSelection(
                lane=ConversationLane.FAST_ACTION,
                confidence=0.84,
                reason="device-context-test",
                target_kind="device_action",
                requires_clarification=False,
                source="device_context",
            ),
        ), patch(
            "app.modules.conversation.orchestrator.plan_device_control",
            side_effect=ConversationDevicePlannerError("planner_parse_failed"),
        ), patch(
            "app.modules.conversation.orchestrator._resolve_fast_action_entity_for_device",
            return_value=("light.living_room_main", None),
        ), patch(
            "app.modules.conversation.orchestrator.settings.conversation_lane_takeover_enabled",
            True,
        ):
            result = run_orchestrated_turn(
                self.db,
                session=self.session,
                message="帮我关掉吧",
                actor=self._build_actor(),
                conversation_history=[],
                device_context_summary=device_context_summary,
            )

        self.assertEqual(ConversationIntent.FAST_ACTION, result.intent)
        self.assertEqual("device_context", result.lane_selection.source)
        mocked_call.assert_called_once_with(
            domain="light",
            service="turn_off",
            data={"entity_id": "light.living_room_main"},
        )

    def test_run_orchestrated_turn_executes_confirmation_reply_from_pending_context(self) -> None:
        target = ConversationDeviceContextTarget(
            source_type="fast_action_confirmation_request",
            message_id=new_uuid(),
            request_id=new_uuid(),
            created_at="2026-03-17T00:00:00Z",
            device_id=self.light_device_id,
            device_name="客厅灯",
            device_type="light",
            entity_id="light.living_room_main",
            action="turn_off",
        )
        device_context_summary = ConversationDeviceContextSummary(
            latest_target=target,
            latest_confirmation_target=target,
            resume_target=target,
            recent_targets=[target],
            unique_device_ids=[self.light_device_id],
            can_resume_control=True,
            can_resume_confirmation=True,
            resume_reason="最近对话上下文只指向一个设备，可以承接省略式设备控制。",
        )

        with patch(
            "app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service",
            return_value={"status": "ok"},
        ) as mocked_call, patch(
            "app.modules.conversation.orchestrator.detect_conversation_intent",
            return_value=self._build_structured_qa_detection(),
        ), patch(
            "app.modules.conversation.orchestrator.settings.conversation_lane_takeover_enabled",
            True,
        ):
            result = run_orchestrated_turn(
                self.db,
                session=self.session,
                message="是的",
                actor=self._build_actor(),
                conversation_history=[],
                device_context_summary=device_context_summary,
            )

        self.assertEqual(ConversationIntent.FAST_ACTION, result.intent)
        self.assertEqual("device_confirmation_context", result.lane_selection.source)
        mocked_call.assert_called_once_with(
            domain="light",
            service="turn_off",
            data={"entity_id": "light.living_room_main"},
        )

    def test_select_conversation_lane_does_not_resume_when_recent_device_context_is_ambiguous(self) -> None:
        detection = self._build_structured_qa_detection()
        lane = select_conversation_lane(
            session=self.session,
            message="帮我关掉",
            detection=detection,
            device_context_summary=ConversationDeviceContextSummary(
                recent_targets=[
                    ConversationDeviceContextTarget(
                        source_type="device_state",
                        message_id=new_uuid(),
                        request_id=new_uuid(),
                        created_at="2026-03-17T00:00:00Z",
                        device_id=new_uuid(),
                        device_name="书房灯",
                    ),
                    ConversationDeviceContextTarget(
                        source_type="device_state",
                        message_id=new_uuid(),
                        request_id=new_uuid(),
                        created_at="2026-03-17T00:00:01Z",
                        device_id=new_uuid(),
                        device_name="卧室灯",
                    ),
                ],
                unique_device_ids=["device-1", "device-2"],
                can_resume_control=False,
                resume_reason="最近对话里提到了 2 个设备，当前不能省略目标。",
            ),
        )

        self.assertEqual(ConversationLane.REALTIME_QUERY, lane.lane)

    def test_run_orchestrated_turn_passes_device_context_summary_to_structured_qa(self) -> None:
        device_context_summary = self._build_device_context_summary(device_id=self.light_device_id, device_name="客厅灯")

        with patch(
            "app.modules.conversation.orchestrator.detect_conversation_intent",
            return_value=self._build_structured_qa_detection(),
        ), patch(
            "app.modules.conversation.orchestrator.select_conversation_lane",
            return_value=self._build_realtime_query_lane(),
        ), patch(
            "app.modules.conversation.orchestrator.query_family_qa",
            return_value=FamilyQaQueryResponse(
                answer_type="device_status",
                answer="客厅灯当前状态是开启。",
                confidence=0.9,
                facts=[],
                degraded=False,
                suggestions=[],
                effective_agent_id=self.agent.id,
                effective_agent_name="管家",
            ),
        ) as mocked_query, patch(
            "app.modules.conversation.orchestrator.settings.conversation_lane_takeover_enabled",
            True,
        ):
            result = run_orchestrated_turn(
                self.db,
                session=self.session,
                message="它现在什么状态",
                actor=self._build_actor(),
                conversation_history=[],
                device_context_summary=device_context_summary,
            )

        payload = mocked_query.call_args.args[1]
        self.assertEqual("客厅灯", payload.context["device_context_summary"]["resume_target"]["device_name"])
        self.assertEqual(ConversationIntent.STRUCTURED_QA, result.intent)

    def test_run_orchestrated_turn_passes_device_context_summary_to_free_chat_prompt(self) -> None:
        device_context_summary = self._build_device_context_summary(device_id=self.light_device_id, device_name="客厅灯")

        with patch(
            "app.modules.conversation.orchestrator.detect_conversation_intent",
            return_value=self._build_detection(),
        ), patch(
            "app.modules.conversation.orchestrator.select_conversation_lane",
            return_value=self._build_free_chat_lane(),
        ), patch(
            "app.modules.conversation.orchestrator.invoke_llm",
            return_value=Mock(text="好的", provider="fake-provider"),
        ) as mocked_llm, patch(
            "app.modules.conversation.orchestrator.settings.conversation_lane_takeover_enabled",
            True,
        ):
            result = run_orchestrated_turn(
                self.db,
                session=self.session,
                message="继续说说刚才那个",
                actor=self._build_actor(),
                conversation_history=[],
                device_context_summary=device_context_summary,
            )

        variables = mocked_llm.call_args.kwargs["variables"]
        self.assertIn("客厅灯", variables["device_context"])
        self.assertEqual(ConversationIntent.FREE_CHAT, result.intent)

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

    def _build_structured_qa_detection(self) -> ConversationIntentDetection:
        return ConversationIntentDetection(
            primary_intent=ConversationIntentLabel.STRUCTURED_QA,
            confidence=0.8,
            reason="test-structured-qa",
            route_intent=ConversationIntent.STRUCTURED_QA,
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

    def _build_realtime_query_lane(self) -> ConversationLaneSelection:
        return ConversationLaneSelection(
            lane=ConversationLane.REALTIME_QUERY,
            confidence=0.9,
            reason="test-realtime-query",
            target_kind="state_query",
            requires_clarification=False,
            source="test",
        )

    def _build_free_chat_lane(self) -> ConversationLaneSelection:
        return ConversationLaneSelection(
            lane=ConversationLane.FREE_CHAT,
            confidence=0.9,
            reason="test-free-chat",
            target_kind="none",
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

    def _build_device_context_summary(
        self,
        *,
        device_id: str,
        device_name: str,
    ) -> ConversationDeviceContextSummary:
        target = ConversationDeviceContextTarget(
            source_type="device_state",
            message_id=new_uuid(),
            request_id=new_uuid(),
            created_at="2026-03-17T00:00:00Z",
            device_id=device_id,
            device_name=device_name,
            device_type="light",
            status="on",
        )
        return ConversationDeviceContextSummary(
            latest_target=target,
            latest_query_target=target,
            resume_target=target,
            recent_targets=[target],
            unique_device_ids=[device_id],
            can_resume_control=True,
            resume_reason="最近对话上下文只指向一个设备，可以承接省略式设备控制。",
        )


if __name__ == "__main__":
    unittest.main()
