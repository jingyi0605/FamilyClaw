import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.db.utils import new_uuid, utc_now_iso
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.orchestrator import ConversationIntent, ConversationOrchestratorResult
from app.modules.device.models import Device, DeviceBinding
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.integration import repository as integration_repository
from app.modules.integration.models import IntegrationInstance
from app.modules.plugin.service import PluginServiceError
from app.modules.voice import repository as voice_repository
from app.modules.voice.speaker_host_service import (
    SpeakerHostServiceError,
    ensure_speaker_runtime_execution_allowed,
    get_speaker_runtime_state,
    open_speaker_audio_session,
    report_speaker_runtime_heartbeat,
    submit_speaker_text_turn,
)
from app.modules.voice.speaker_schemas import SpeakerAudioSessionEnvelope, SpeakerRuntimeHeartbeat, SpeakerTextTurnRequest


class SpeakerHostServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()

        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()

        self.household = create_household(
            self.db,
            HouseholdCreate(
                name="Speaker Host Home",
                city="Hangzhou",
                timezone="Asia/Shanghai",
                locale="zh-CN",
            ),
        )
        self.agent = create_agent(
            self.db,
            household_id=self.household.id,
            payload=AgentCreate(
                display_name="Speaker Agent",
                agent_type="butler",
                self_identity="我是 speaker 对话助手",
                role_summary="负责 speaker 插件桥接测试",
                intro_message="你好",
                speaking_style="直接",
                personality_traits=["冷静"],
                service_focus=["对话"],
                default_entry=True,
                conversation_enabled=True,
                created_by="test",
            ),
        )
        self.instance = IntegrationInstance(
            id=new_uuid(),
            household_id=self.household.id,
            plugin_id="speaker-plugin",
            display_name="Speaker Instance",
            status="active",
            last_synced_at=None,
            last_error_code=None,
            last_error_message=None,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        self.device = Device(
            id=new_uuid(),
            household_id=self.household.id,
            room_id=None,
            name="客厅音箱",
            device_type="speaker",
            vendor="demo",
            status="active",
            controllable=1,
            voice_auto_takeover_enabled=0,
            voiceprint_identity_enabled=0,
        )
        self.binding = DeviceBinding(
            id=new_uuid(),
            device_id=self.device.id,
            integration_instance_id=self.instance.id,
            platform="speaker-demo",
            external_entity_id="media_player.speaker_demo",
            external_device_id="speaker-ext-001",
            plugin_id="speaker-plugin",
            binding_version=1,
        )
        self.db.add(self.instance)
        self.db.add(self.device)
        self.db.flush()
        self.db.add(self.binding)
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_submit_text_turn_creates_and_reuses_same_session(self) -> None:
        with patch(
            "app.modules.voice.speaker_host_service.require_available_household_plugin",
            return_value=_build_plugin_stub(supported_modes=["text_turn"]),
        ), patch(
            "app.modules.conversation.service._run_orchestrated_turn",
            return_value=_build_orchestrator_result(text="好的，今天有家庭会议。"),
        ):
            first = submit_speaker_text_turn(
                self.db,
                payload=self._build_text_turn_payload(turn_id="turn-001"),
            )
            second = submit_speaker_text_turn(
                self.db,
                payload=self._build_text_turn_payload(turn_id="turn-002"),
            )

        self.assertTrue(first.accepted)
        self.assertEqual("text", first.result_type)
        self.assertEqual("好的，今天有家庭会议。", first.reply_text)
        self.assertFalse(first.duplicated)
        self.assertTrue(second.accepted)
        self.assertEqual("text", second.result_type)
        self.assertEqual(first.conversation_session_id, second.conversation_session_id)
        turn_sources = conversation_repository.list_turn_sources(
            self.db,
            session_id=first.conversation_session_id,
        )
        self.assertEqual(2, len(turn_sources))
        self.assertTrue(all(item.source_kind == "speaker_adapter" for item in turn_sources))
        self.assertTrue(all(item.platform_code == "speaker-plugin" for item in turn_sources))
        self.assertTrue(
            all(
                item.external_conversation_key
                == f"speaker:speaker-plugin:{self.instance.id}:speaker-ext-001:conversation-001"
                for item in turn_sources
            )
        )
        self.assertEqual(
            [],
            voice_repository.list_voice_terminal_conversation_bindings(
                self.db,
                household_id=self.household.id,
            ),
        )

    def test_submit_text_turn_is_idempotent_for_same_turn_id(self) -> None:
        with patch(
            "app.modules.voice.speaker_host_service.require_available_household_plugin",
            return_value=_build_plugin_stub(supported_modes=["text_turn"]),
        ), patch(
            "app.modules.conversation.service._run_orchestrated_turn",
            return_value=_build_orchestrator_result(text="这是一条可复用回复。"),
        ):
            first = submit_speaker_text_turn(
                self.db,
                payload=self._build_text_turn_payload(turn_id="turn-dup"),
            )
            second = submit_speaker_text_turn(
                self.db,
                payload=self._build_text_turn_payload(turn_id="turn-dup"),
            )

        self.assertTrue(first.accepted)
        self.assertTrue(second.accepted)
        self.assertTrue(second.duplicated)
        self.assertEqual("text", second.result_type)
        self.assertEqual("这是一条可复用回复。", second.reply_text)
        self.assertEqual(first.conversation_session_id, second.conversation_session_id)
        turn_sources = conversation_repository.list_turn_sources(
            self.db,
            session_id=first.conversation_session_id,
        )
        self.assertEqual(1, len(turn_sources))
        messages = conversation_repository.list_messages(
            self.db,
            session_id=first.conversation_session_id,
        )
        self.assertEqual(2, len(messages))

    def test_submit_text_turn_returns_plugin_disabled_error_result(self) -> None:
        with patch(
            "app.modules.voice.speaker_host_service.require_available_household_plugin",
            side_effect=PluginServiceError(
                "当前 speaker 插件已禁用，不能继续执行。",
                error_code="plugin_disabled",
                field="plugin_id",
                status_code=409,
            ),
        ):
            result = submit_speaker_text_turn(
                self.db,
                payload=self._build_text_turn_payload(turn_id="turn-disabled"),
            )

        self.assertFalse(result.accepted)
        self.assertEqual("error", result.result_type)
        self.assertEqual("plugin_disabled", result.error_code)

    def test_submit_text_turn_rejects_invalid_instance_and_binding(self) -> None:
        with patch(
            "app.modules.voice.speaker_host_service.require_available_household_plugin",
            return_value=_build_plugin_stub(supported_modes=["text_turn"]),
        ):
            invalid_instance = submit_speaker_text_turn(
                self.db,
                payload=self._build_text_turn_payload(
                    turn_id="turn-invalid-instance",
                    integration_instance_id="missing-instance",
                ),
            )
            invalid_binding = submit_speaker_text_turn(
                self.db,
                payload=self._build_text_turn_payload(
                    turn_id="turn-invalid-binding",
                    external_device_id="another-device",
                ),
            )

        self.assertFalse(invalid_instance.accepted)
        self.assertEqual("speaker_text_turn_invalid", invalid_instance.error_code)
        self.assertFalse(invalid_binding.accepted)
        self.assertEqual("speaker_binding_missing", invalid_binding.error_code)

    def test_report_runtime_heartbeat_updates_instance_status(self) -> None:
        with patch(
            "app.modules.voice.speaker_host_service.require_available_household_plugin",
            return_value=_build_plugin_stub(supported_modes=["text_turn"]),
        ):
            degraded_ack = report_speaker_runtime_heartbeat(
                self.db,
                payload=SpeakerRuntimeHeartbeat(
                    household_id=self.household.id,
                    plugin_id="speaker-plugin",
                    integration_instance_id=self.instance.id,
                    state="degraded",
                    consecutive_failures=2,
                    reported_at="2026-03-22T10:00:00Z",
                    last_succeeded_at="2026-03-22T09:55:00Z",
                    last_failed_at="2026-03-22T10:00:00Z",
                    last_error_summary="speaker token expired",
                ),
            )
            running_ack = report_speaker_runtime_heartbeat(
                self.db,
                payload=SpeakerRuntimeHeartbeat(
                    household_id=self.household.id,
                    plugin_id="speaker-plugin",
                    integration_instance_id=self.instance.id,
                    state="running",
                    consecutive_failures=0,
                    reported_at="2026-03-22T10:05:00Z",
                ),
            )

        self.assertTrue(degraded_ack.accepted)
        self.assertEqual("degraded", degraded_ack.runtime_state)
        self.assertTrue(running_ack.accepted)
        self.assertEqual("running", running_ack.runtime_state)

        refreshed = integration_repository.get_integration_instance(self.db, self.instance.id)
        assert refreshed is not None
        self.assertEqual("active", refreshed.status)
        self.assertEqual("2026-03-22T10:05:00Z", refreshed.last_synced_at)
        self.assertIsNone(refreshed.last_error_code)
        self.assertIsNone(refreshed.last_error_message)

        runtime_state = voice_repository.get_speaker_runtime_state_by_integration_instance(
            self.db,
            integration_instance_id=self.instance.id,
        )
        assert runtime_state is not None
        self.assertEqual("running", runtime_state.runtime_state)
        self.assertEqual(0, runtime_state.consecutive_failures)
        self.assertEqual("2026-03-22T10:05:00Z", runtime_state.last_heartbeat_at)
        self.assertIsNone(runtime_state.last_error_summary)

        runtime_state_read = get_speaker_runtime_state(
            self.db,
            integration_instance_id=self.instance.id,
        )
        assert runtime_state_read is not None
        self.assertEqual(runtime_state.id, runtime_state_read.id)
        self.assertEqual("running", runtime_state_read.runtime_state)
        self.assertEqual("speaker-demo", runtime_state_read.adapter_code)
        self.assertEqual("2026-03-22T10:05:00Z", runtime_state_read.last_heartbeat_at)

    def test_runtime_execution_guard_blocks_disabled_plugin(self) -> None:
        with patch(
            "app.modules.voice.speaker_host_service.require_available_household_plugin",
            side_effect=PluginServiceError(
                "当前 speaker 插件已禁用，不能继续执行。",
                error_code="plugin_disabled",
                field="plugin_id",
                status_code=409,
            ),
        ):
            with self.assertRaises(SpeakerHostServiceError) as context:
                ensure_speaker_runtime_execution_allowed(
                    self.db,
                    household_id=self.household.id,
                    plugin_id="speaker-plugin",
                    integration_instance_id=self.instance.id,
                )

        self.assertEqual("plugin_disabled", context.exception.error_code)

    def test_runtime_execution_guard_rejects_plugin_without_runtime_worker(self) -> None:
        with patch(
            "app.modules.voice.speaker_host_service.require_available_household_plugin",
            return_value=_build_plugin_stub(
                supported_modes=["audio_session"],
                requires_runtime_worker=False,
            ),
        ):
            with self.assertRaises(SpeakerHostServiceError) as context:
                ensure_speaker_runtime_execution_allowed(
                    self.db,
                    household_id=self.household.id,
                    plugin_id="speaker-plugin",
                    integration_instance_id=self.instance.id,
                )

        self.assertEqual("speaker_runtime_invalid", context.exception.error_code)

    def test_open_audio_session_rejects_text_only_plugin(self) -> None:
        with patch(
            "app.modules.voice.speaker_host_service.require_available_household_plugin",
            return_value=_build_plugin_stub(supported_modes=["text_turn"]),
        ):
            with self.assertRaises(SpeakerHostServiceError) as context:
                open_speaker_audio_session(
                    self.db,
                    payload=SpeakerAudioSessionEnvelope(
                        household_id=self.household.id,
                        plugin_id="speaker-plugin",
                        integration_instance_id=self.instance.id,
                        binding_id=self.binding.id,
                        device_id=self.device.id,
                        external_device_id=self.binding.external_device_id or "",
                        conversation_id="conversation-001",
                        session_id="audio-session-001",
                        stage="open",
                        occurred_at="2026-03-22T10:00:00Z",
                    ),
                )

        self.assertEqual("speaker_audio_session_unsupported", context.exception.error_code)

    def _build_text_turn_payload(
        self,
        *,
        turn_id: str,
        integration_instance_id: str | None = None,
        external_device_id: str | None = None,
    ) -> SpeakerTextTurnRequest:
        return SpeakerTextTurnRequest(
            household_id=self.household.id,
            plugin_id="speaker-plugin",
            integration_instance_id=integration_instance_id or self.instance.id,
            binding_id=self.binding.id,
            device_id=self.device.id,
            external_device_id=external_device_id or (self.binding.external_device_id or ""),
            conversation_id="conversation-001",
            turn_id=turn_id,
            input_text="今天有什么安排？",
            occurred_at="2026-03-22T09:00:00Z",
            context={},
        )


def _build_plugin_stub(*, supported_modes: list[str], requires_runtime_worker: bool = True):
    return SimpleNamespace(
        id="speaker-plugin",
        name="Speaker Plugin",
        entrypoints=SimpleNamespace(speaker_adapter="plugin.runtime.run"),
        capabilities=SimpleNamespace(
            speaker_adapter=SimpleNamespace(
                adapter_code="speaker-demo",
                supported_modes=supported_modes,
                supported_domains=["speaker"],
                requires_runtime_worker=requires_runtime_worker,
                supports_discovery=True,
                supports_commands=False,
            )
        ),
    )


def _build_orchestrator_result(*, text: str) -> ConversationOrchestratorResult:
    return ConversationOrchestratorResult(
        intent=ConversationIntent.FREE_CHAT,
        text=text,
        degraded=False,
        facts=[],
        suggestions=[],
        memory_candidate_payloads=[],
        config_suggestion=None,
        action_payloads=[],
        ai_trace_id=None,
        ai_provider_code="mock-provider",
        effective_agent_id=None,
        effective_agent_name=None,
    )


if __name__ == "__main__":
    unittest.main()
