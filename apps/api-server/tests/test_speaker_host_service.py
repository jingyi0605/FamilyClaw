import json
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.utils import new_uuid, utc_now_iso
from app.modules.conversation.schemas import ConversationMessageRead
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.integration.models import IntegrationInstance
from app.modules.plugin.schemas import PluginStateUpdateRequest
from app.modules.plugin.service import set_household_plugin_enabled
from app.modules.voice.speaker_host_service import speaker_host_service
from app.modules.voice.speaker_schemas import SpeakerRuntimeHeartbeat
from tests.test_db_support import PostgresTestDatabase


PLUGIN_ID = "speaker-host-service-test"


class SpeakerHostServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.SessionLocal = self._db_helper.SessionLocal
        self.db: Session = self.SessionLocal()
        self.household = create_household(
            self.db,
            HouseholdCreate(name="Speaker Host Test Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()
        self._install_text_turn_plugin()
        self.instance = self._create_integration_instance()
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def test_report_runtime_heartbeat_marks_error_before_degraded_threshold(self) -> None:
        result = speaker_host_service.report_runtime_heartbeat(
            self.db,
            heartbeat=SpeakerRuntimeHeartbeat(
                plugin_id=PLUGIN_ID,
                integration_instance_id=self.instance.id,
                state="error",
                consecutive_failures=1,
                last_failed_at="2026-03-23T12:00:00Z",
                last_error_summary="小米登录失效",
            ),
        )
        self.db.flush()

        instance = self.db.get(IntegrationInstance, self.instance.id)
        assert instance is not None
        self.assertTrue(result.accepted)
        self.assertEqual("error", result.state)
        self.assertEqual("degraded", instance.status)
        self.assertEqual("speaker_runtime_error", instance.last_error_code)
        self.assertEqual("小米登录失效", instance.last_error_message)

    def test_report_runtime_heartbeat_uses_disabled_plugin_status(self) -> None:
        set_household_plugin_enabled(
            self.db,
            household_id=self.household.id,
            plugin_id=PLUGIN_ID,
            payload=PluginStateUpdateRequest(enabled=False),
            updated_by="test",
        )
        self.db.flush()

        result = speaker_host_service.report_runtime_heartbeat(
            self.db,
            heartbeat=SpeakerRuntimeHeartbeat(
                plugin_id=PLUGIN_ID,
                integration_instance_id=self.instance.id,
                state="running",
                consecutive_failures=0,
                last_succeeded_at="2026-03-23T12:05:00Z",
            ),
        )
        self.db.flush()

        instance = self.db.get(IntegrationInstance, self.instance.id)
        assert instance is not None
        self.assertTrue(result.accepted)
        self.assertEqual("disabled", instance.status)
        self.assertEqual("plugin_disabled", instance.last_error_code)
        self.assertIn("停用", instance.last_error_message or "")

    def test_build_turn_result_prefers_audio_url_fact(self) -> None:
        result = speaker_host_service._build_turn_result(
            session_id="session-audio",
            turn_id="turn-audio",
            messages=[
                ConversationMessageRead(
                    id="assistant-audio",
                    session_id="session-audio",
                    request_id="turn-audio",
                    seq=2,
                    role="assistant",
                    message_type="text",
                    content="这是一条给不支持音频 URL 时用的回退文本",
                    status="completed",
                    degraded=False,
                    error_code=None,
                    facts=[
                        {
                            "type": "speaker_audio_reply",
                            "audio_url": "https://media.example.com/reply.mp3",
                            "content_type": "audio/mpeg",
                            "fallback_text": "请播放音频 URL",
                        }
                    ],
                    suggestions=[],
                    created_at="2026-03-23T12:00:00Z",
                    updated_at="2026-03-23T12:00:00Z",
                )
            ],
        )

        self.assertTrue(result.accepted)
        self.assertEqual("audio_url", result.result_type)
        self.assertEqual("https://media.example.com/reply.mp3", result.audio_url)
        self.assertEqual("audio/mpeg", result.audio_content_type)
        self.assertEqual("请播放音频 URL", result.reply_text)

    def test_build_turn_result_ignores_invalid_audio_url_fact(self) -> None:
        result = speaker_host_service._build_turn_result(
            session_id="session-text",
            turn_id="turn-text",
            messages=[
                ConversationMessageRead(
                    id="assistant-text",
                    session_id="session-text",
                    request_id="turn-text",
                    seq=2,
                    role="assistant",
                    message_type="text",
                    content="只返回文本，不接受无效 URL",
                    status="completed",
                    degraded=False,
                    error_code=None,
                    facts=[
                        {
                            "type": "speaker_audio_reply",
                            "audio_url": "/relative/audio.mp3",
                        }
                    ],
                    suggestions=[],
                    created_at="2026-03-23T12:00:00Z",
                    updated_at="2026-03-23T12:00:00Z",
                )
            ],
        )

        self.assertEqual("text", result.result_type)
        self.assertEqual("只返回文本，不接受无效 URL", result.reply_text)
        self.assertIsNone(result.audio_url)

    def _install_text_turn_plugin(self) -> None:
        plugin_root = Path(settings.plugin_dev_root).resolve() / "speaker_host_service_test"
        plugin_root.mkdir(parents=True, exist_ok=True)
        manifest = {
            "id": PLUGIN_ID,
            "name": "Speaker Host Service Test",
            "version": "0.1.0",
            "types": ["integration"],
            "permissions": ["device.read"],
            "risk_level": "low",
            "triggers": ["manual"],
            "entrypoints": {
                "integration": "plugin.integration.sync",
                "speaker_adapter": "plugin.speaker_adapter.create_adapter",
            },
            "capabilities": {
                "integration": {
                    "domains": ["speaker"],
                    "instance_model": "multi_instance",
                    "refresh_mode": "manual",
                    "supports_discovery": False,
                    "supports_actions": False,
                    "supports_cards": False,
                    "entity_types": ["speaker.device"],
                },
                "speaker_adapter": {
                    "adapter_code": "speaker-host-service-test",
                    "supported_modes": ["text_turn"],
                    "supported_domains": ["speaker"],
                    "requires_runtime_worker": True,
                    "supports_discovery": False,
                    "supports_commands": False,
                },
            },
        }
        (plugin_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _create_integration_instance(self) -> IntegrationInstance:
        now = utc_now_iso()
        instance = IntegrationInstance(
            id=new_uuid(),
            household_id=self.household.id,
            plugin_id=PLUGIN_ID,
            display_name="测试音箱桥接",
            status="inactive",
            last_synced_at=None,
            last_error_code=None,
            last_error_message=None,
            created_at=now,
            updated_at=now,
        )
        self.db.add(instance)
        self.db.flush()
        return instance


if __name__ == "__main__":
    unittest.main()
