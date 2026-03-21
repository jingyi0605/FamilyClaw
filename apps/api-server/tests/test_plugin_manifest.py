import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.service import (
    _REPORTED_PLUGIN_REGISTRY_ISSUES,
    PluginManifestValidationError,
    disable_plugin,
    discover_plugin_manifests,
    enable_plugin,
    execute_plugin,
    list_registered_plugins_for_household,
    list_registered_plugins,
    load_plugin_manifest,
    set_household_plugin_enabled,
)
from app.modules.plugin.schemas import PluginExecutionRequest, PluginStateUpdateRequest
from app.modules.plugin.schemas import PluginRunnerConfig


class PluginManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builtin_root = Path(__file__).resolve().parents[1] / "app" / "plugins" / "builtin"

    def _write_ai_provider_resources(
        self,
        root: Path,
        *,
        description_payload: object | None = None,
    ) -> None:
        resources_dir = root / "resources"
        resources_dir.mkdir(parents=True, exist_ok=True)
        (resources_dir / "logo.svg").write_text(
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'></svg>",
            encoding="utf-8",
        )
        payload = description_payload if description_payload is not None else {"zh-CN": "provider description"}
        (resources_dir / "description.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_load_valid_manifest(self) -> None:
        manifest = load_plugin_manifest(
            self.builtin_root / "health_basic" / "manifest.json"
        )

        self.assertEqual("health-basic-reader", manifest.id)
        self.assertEqual(["integration"], manifest.types)
        self.assertEqual("app.plugins.builtin.health_basic.integration.sync", manifest.entrypoints.integration)

    def test_manifest_accepts_integration_instance_name_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "placeholder-demo",
                        "name": "Placeholder Demo",
                        "version": "0.1.0",
                        "types": ["integration"],
                        "permissions": ["device.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"integration": "plugin.integration.sync"},
                        "capabilities": {
                            "integration": {
                                "domains": ["demo"],
                                "instance_model": "multi_instance",
                                "refresh_mode": "manual",
                                "supports_discovery": False,
                                "supports_actions": False,
                                "supports_cards": False,
                                "instance_display_name_placeholder": "例如：客厅 Demo / 书房 Demo",
                                "instance_display_name_placeholder_key": "plugin.demo.instance_name_placeholder",
                                "entity_types": ["demo.entity"],
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manifest = load_plugin_manifest(manifest_path)

        assert manifest.capabilities.integration is not None
        self.assertEqual(
            "例如：客厅 Demo / 书房 Demo",
            manifest.capabilities.integration.instance_display_name_placeholder,
        )
        self.assertEqual(
            "plugin.demo.instance_name_placeholder",
            manifest.capabilities.integration.instance_display_name_placeholder_key,
        )

    def test_load_locale_pack_manifest_without_entrypoints(self) -> None:
        manifest = load_plugin_manifest(
            self.builtin_root / "locale_zh_tw_pack" / "manifest.json"
        )

        self.assertEqual("locale-zh-tw", manifest.id)
        self.assertEqual(["locale-pack"], manifest.types)
        self.assertEqual(1, len(manifest.locales))
        self.assertEqual("zh-TW", manifest.locales[0].id)
        self.assertIsNone(manifest.entrypoints.integration)

    def test_manifest_accepts_ai_provider_driver_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            self._write_ai_provider_resources(Path(tempdir))
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "driver-ai-provider",
                        "name": "Driver AI Provider",
                        "version": "0.1.0",
                        "types": ["ai-provider"],
                        "permissions": [],
                        "risk_level": "low",
                        "triggers": [],
                        "entrypoints": {"ai_provider": "plugin.driver.build_driver"},
                        "capabilities": {
                            "ai_provider": {
                                "adapter_code": "driver-ai-provider",
                                "display_name": "Driver AI Provider",
                                "branding": {
                                    "logo_resource": "resources/logo.svg",
                                    "description_resource": "resources/description.json",
                                },
                                "field_schema": [
                                    {
                                        "key": "secret_ref",
                                        "label": "API Key",
                                        "field_type": "secret",
                                        "required": True,
                                        "options": [],
                                    }
                                ],
                                "config_ui": {
                                    "field_order": ["secret_ref"],
                                    "sections": [
                                        {
                                            "key": "connection",
                                            "title": "Connection",
                                            "fields": ["secret_ref"],
                                        }
                                    ],
                                    "actions": [],
                                },
                                "model_discovery": {
                                    "enabled": False,
                                    "depends_on_fields": [],
                                },
                                "supported_model_types": ["llm"],
                                "llm_workflow": "openai_chat_completions",
                                "runtime_capability": {
                                    "transport_type": "openai_compatible",
                                    "api_family": "openai_chat_completions",
                                    "default_privacy_level": "public_cloud",
                                    "default_supported_capabilities": ["text"],
                                },
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manifest = load_plugin_manifest(manifest_path)

        self.assertEqual(["ai-provider"], manifest.types)
        self.assertEqual("plugin.driver.build_driver", manifest.entrypoints.ai_provider)
        assert manifest.capabilities.ai_provider is not None
        self.assertEqual("resources/logo.svg", manifest.capabilities.ai_provider.branding.logo_resource)

    def test_manifest_rejects_ai_provider_without_branding_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-ai-provider-branding",
                        "name": "Broken AI Provider Branding",
                        "version": "0.1.0",
                        "types": ["ai-provider"],
                        "permissions": [],
                        "risk_level": "low",
                        "triggers": [],
                        "entrypoints": {"ai_provider": "plugin.driver.build_driver"},
                        "capabilities": {
                            "ai_provider": {
                                "adapter_code": "broken-ai-provider-branding",
                                "display_name": "Broken AI Provider Branding",
                                "field_schema": [
                                    {
                                        "key": "secret_ref",
                                        "label": "API Key",
                                        "field_type": "secret",
                                        "required": True,
                                        "options": [],
                                    }
                                ],
                                "config_ui": {
                                    "field_order": ["secret_ref"],
                                    "sections": [
                                        {
                                            "key": "connection",
                                            "title": "Connection",
                                            "fields": ["secret_ref"],
                                        }
                                    ],
                                    "actions": [],
                                },
                                "model_discovery": {
                                    "enabled": False,
                                    "depends_on_fields": [],
                                },
                                "supported_model_types": ["llm"],
                                "llm_workflow": "openai_chat_completions",
                                "runtime_capability": {
                                    "transport_type": "openai_compatible",
                                    "api_family": "openai_chat_completions",
                                    "default_privacy_level": "public_cloud",
                                    "default_supported_capabilities": ["text"],
                                },
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("branding", str(context.exception))

    def test_manifest_rejects_ai_provider_without_config_ui_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            self._write_ai_provider_resources(Path(tempdir))
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-ai-provider-config-ui",
                        "name": "Broken AI Provider Config UI",
                        "version": "0.1.0",
                        "types": ["ai-provider"],
                        "permissions": [],
                        "risk_level": "low",
                        "triggers": [],
                        "entrypoints": {"ai_provider": "plugin.driver.build_driver"},
                        "capabilities": {
                            "ai_provider": {
                                "adapter_code": "broken-ai-provider-config-ui",
                                "display_name": "Broken AI Provider Config UI",
                                "branding": {
                                    "logo_resource": "resources/logo.svg",
                                    "description_resource": "resources/description.json",
                                },
                                "field_schema": [
                                    {
                                        "key": "secret_ref",
                                        "label": "API Key",
                                        "field_type": "secret",
                                        "required": True,
                                        "options": [],
                                    }
                                ],
                                "model_discovery": {
                                    "enabled": False,
                                    "depends_on_fields": [],
                                },
                                "supported_model_types": ["llm"],
                                "llm_workflow": "openai_chat_completions",
                                "runtime_capability": {
                                    "transport_type": "openai_compatible",
                                    "api_family": "openai_chat_completions",
                                    "default_privacy_level": "public_cloud",
                                    "default_supported_capabilities": ["text"],
                                },
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("config_ui", str(context.exception))

    def test_manifest_rejects_ai_provider_without_model_discovery_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            self._write_ai_provider_resources(Path(tempdir))
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-ai-provider-model-discovery",
                        "name": "Broken AI Provider Model Discovery",
                        "version": "0.1.0",
                        "types": ["ai-provider"],
                        "permissions": [],
                        "risk_level": "low",
                        "triggers": [],
                        "entrypoints": {"ai_provider": "plugin.driver.build_driver"},
                        "capabilities": {
                            "ai_provider": {
                                "adapter_code": "broken-ai-provider-model-discovery",
                                "display_name": "Broken AI Provider Model Discovery",
                                "branding": {
                                    "logo_resource": "resources/logo.svg",
                                    "description_resource": "resources/description.json",
                                },
                                "field_schema": [
                                    {
                                        "key": "secret_ref",
                                        "label": "API Key",
                                        "field_type": "secret",
                                        "required": True,
                                        "options": [],
                                    }
                                ],
                                "config_ui": {
                                    "field_order": ["secret_ref"],
                                    "sections": [
                                        {
                                            "key": "connection",
                                            "title": "Connection",
                                            "fields": ["secret_ref"],
                                        }
                                    ],
                                    "actions": [],
                                },
                                "supported_model_types": ["llm"],
                                "llm_workflow": "openai_chat_completions",
                                "runtime_capability": {
                                    "transport_type": "openai_compatible",
                                    "api_family": "openai_chat_completions",
                                    "default_privacy_level": "public_cloud",
                                    "default_supported_capabilities": ["text"],
                                },
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("model_discovery", str(context.exception))

    def test_manifest_rejects_ai_provider_when_branding_resource_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            resources_dir = Path(tempdir) / "resources"
            resources_dir.mkdir(parents=True, exist_ok=True)
            (resources_dir / "description.json").write_text(
                json.dumps({"zh-CN": "provider description"}, ensure_ascii=False),
                encoding="utf-8",
            )
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-ai-provider-missing-logo",
                        "name": "Broken AI Provider Missing Logo",
                        "version": "0.1.0",
                        "types": ["ai-provider"],
                        "permissions": [],
                        "risk_level": "low",
                        "triggers": [],
                        "entrypoints": {"ai_provider": "plugin.driver.build_driver"},
                        "capabilities": {
                            "ai_provider": {
                                "adapter_code": "broken-ai-provider-missing-logo",
                                "display_name": "Broken AI Provider Missing Logo",
                                "branding": {
                                    "logo_resource": "resources/logo.svg",
                                    "description_resource": "resources/description.json",
                                },
                                "field_schema": [
                                    {
                                        "key": "secret_ref",
                                        "label": "API Key",
                                        "field_type": "secret",
                                        "required": True,
                                        "options": [],
                                    }
                                ],
                                "config_ui": {
                                    "field_order": ["secret_ref"],
                                    "sections": [
                                        {
                                            "key": "connection",
                                            "title": "Connection",
                                            "fields": ["secret_ref"],
                                        }
                                    ],
                                    "actions": [],
                                },
                                "model_discovery": {
                                    "enabled": False,
                                    "depends_on_fields": [],
                                },
                                "supported_model_types": ["llm"],
                                "llm_workflow": "openai_chat_completions",
                                "runtime_capability": {
                                    "transport_type": "openai_compatible",
                                    "api_family": "openai_chat_completions",
                                    "default_privacy_level": "public_cloud",
                                    "default_supported_capabilities": ["text"],
                                },
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("资源文件不存在", str(context.exception))

    def test_builtin_ai_provider_manifests_expose_required_plugin_contract_and_resources(self) -> None:
        ai_provider_manifests = sorted(self.builtin_root.glob("ai_provider_*/manifest.json"))
        self.assertGreaterEqual(len(ai_provider_manifests), 3)

        for manifest_path in ai_provider_manifests:
            manifest = load_plugin_manifest(manifest_path)
            capability = manifest.capabilities.ai_provider
            self.assertIsNotNone(capability, msg=str(manifest_path))
            assert capability is not None
            self.assertIsNotNone(capability.branding, msg=str(manifest_path))
            self.assertIsNotNone(capability.config_ui, msg=str(manifest_path))
            self.assertIsNotNone(capability.model_discovery, msg=str(manifest_path))
            self.assertGreater(len(capability.config_ui.field_order), 0, msg=str(manifest_path))
            self.assertGreater(len(capability.config_ui.sections), 0, msg=str(manifest_path))

            manifest_dir = manifest_path.parent
            self.assertTrue((manifest_dir / capability.branding.logo_resource).is_file(), msg=str(manifest_path))
            self.assertTrue((manifest_dir / capability.branding.description_resource).is_file(), msg=str(manifest_path))

    def test_manifest_rejects_ai_provider_model_discovery_binding_with_missing_action(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-ai-provider-discovery",
                        "name": "Broken AI Provider Discovery",
                        "version": "0.1.0",
                        "types": ["ai-provider"],
                        "permissions": [],
                        "risk_level": "low",
                        "triggers": [],
                        "entrypoints": {"ai_provider": "plugin.driver.build_driver"},
                        "capabilities": {
                            "ai_provider": {
                                "adapter_code": "broken-ai-provider-discovery",
                                "display_name": "Broken AI Provider Discovery",
                                "branding": {
                                    "logo_resource": "resources/logo.svg",
                                    "description_resource": "resources/description.json",
                                },
                                "field_schema": [
                                    {
                                        "key": "base_url",
                                        "label": "Base URL",
                                        "field_type": "text",
                                        "required": True,
                                        "options": [],
                                    },
                                    {
                                        "key": "model_name",
                                        "label": "Model Name",
                                        "field_type": "text",
                                        "required": True,
                                        "options": [],
                                    },
                                ],
                                "config_ui": {
                                    "field_order": ["base_url", "model_name"],
                                    "sections": [
                                        {
                                            "key": "default",
                                            "title": "Default",
                                            "fields": ["base_url", "model_name"],
                                        }
                                    ],
                                    "actions": [],
                                },
                                "model_discovery": {
                                    "enabled": True,
                                    "action_key": "discover_models",
                                    "depends_on_fields": ["base_url"],
                                    "target_field": "model_name",
                                },
                                "supported_model_types": ["llm"],
                                "llm_workflow": "openai_chat_completions",
                                "runtime_capability": {
                                    "transport_type": "openai_compatible",
                                    "api_family": "openai_chat_completions",
                                    "default_privacy_level": "public_cloud",
                                    "default_supported_capabilities": ["text"],
                                    "supports_model_discovery": True,
                                },
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("model_discovery.action_key", str(context.exception))

    def test_manifest_rejects_ai_provider_without_driver_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-ai-provider",
                        "name": "Broken AI Provider",
                        "version": "0.1.0",
                        "types": ["ai-provider"],
                        "permissions": [],
                        "risk_level": "low",
                        "triggers": [],
                        "entrypoints": {},
                        "capabilities": {
                            "ai_provider": {
                                "adapter_code": "broken-ai-provider",
                                "display_name": "Broken AI Provider",
                                "field_schema": [
                                    {
                                        "key": "secret_ref",
                                        "label": "API Key",
                                        "field_type": "secret",
                                        "required": True,
                                        "options": [],
                                    }
                                ],
                                "supported_model_types": ["llm"],
                                "llm_workflow": "openai_chat_completions",
                                "runtime_capability": {
                                    "transport_type": "openai_compatible",
                                    "api_family": "openai_chat_completions",
                                    "default_privacy_level": "public_cloud",
                                    "default_supported_capabilities": ["text"],
                                },
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("ai_provider", str(context.exception))

    def test_reject_manifest_missing_required_field(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-plugin",
                        "name": "Broken Plugin",
                        "types": ["integration"],
                        "permissions": ["device.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"integration": "app.plugins.demo.connector.sync"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("version", str(context.exception))

    def test_manifest_accepts_region_context_capability_and_reserved_region_provider_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "region-context-plugin",
                        "name": "Region Context Plugin",
                        "version": "0.1.0",
                        "types": ["integration"],
                        "permissions": ["region.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"integration": "plugin.integration.sync"},
                        "capabilities": {
                            "context_reads": {"household_region_context": True},
                            "region_provider": {
                                "provider_code": "plugin.future-region-provider",
                                "country_codes": ["JP", "US"],
                                "entrypoint": "plugin.region_provider.build",
                                "reserved": True,
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manifest = load_plugin_manifest(manifest_path)

        self.assertTrue(manifest.capabilities.context_reads.household_region_context)
        assert manifest.capabilities.region_provider is not None
        self.assertEqual("plugin.future-region-provider", manifest.capabilities.region_provider.provider_code)
        self.assertEqual(["JP", "US"], manifest.capabilities.region_provider.country_codes)

    def test_manifest_accepts_runtime_region_provider_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "jp-region-provider",
                        "name": "Japan Region Provider",
                        "version": "0.1.0",
                        "types": ["region-provider"],
                        "permissions": ["region.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"region_provider": "plugin.region_provider.handle"},
                        "capabilities": {
                            "region_provider": {
                                "provider_code": "plugin.jp-sample",
                                "country_codes": ["JP"],
                                "entrypoint": "plugin.region_provider.handle",
                                "reserved": False,
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manifest = load_plugin_manifest(manifest_path)

        self.assertEqual(["region-provider"], manifest.types)
        self.assertEqual("plugin.region_provider.handle", manifest.entrypoints.region_provider)

    def test_manifest_accepts_channel_plugin_with_channel_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "telegram-channel-plugin",
                        "name": "Telegram 閫氳閫氶亾鎻掍欢",
                        "version": "0.1.0",
                        "types": ["channel"],
                        "permissions": ["channel.receive", "channel.send"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"channel": "plugin.channel.handle"},
                        "config_specs": [
                            {
                                "scope_type": "channel_account",
                                "title": "Telegram 閰嶇疆",
                                "schema_version": 1,
                                "config_schema": {
                                    "fields": [
                                        {
                                            "key": "bot_token",
                                            "label": "Bot Token",
                                            "type": "secret",
                                            "required": True,
                                        }
                                    ]
                                },
                                "ui_schema": {
                                    "sections": [
                                        {
                                            "id": "basic",
                                            "title": "杩炴帴鍙傛暟",
                                            "fields": ["bot_token"],
                                        }
                                    ],
                                    "widgets": {
                                        "bot_token": {
                                            "widget": "password",
                                            "placeholder": "123456:ABC",
                                            "help_text": "Bot token",
                                        }
                                    },
                                },
                            }
                        ],
                        "capabilities": {
                            "channel": {
                                "platform_code": "telegram",
                                "inbound_modes": ["polling"],
                                "delivery_modes": ["reply", "push"],
                                "supports_member_binding": True,
                                "supports_group_chat": True,
                                "supports_threading": True,
                                "ui": {
                                    "binding": {
                                        "identity_label": "TG-ID",
                                    },
                                },
                                "reserved": False,
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manifest = load_plugin_manifest(manifest_path)

        self.assertEqual(["channel"], manifest.types)
        self.assertEqual("plugin.channel.handle", manifest.entrypoints.channel)
        assert manifest.capabilities.channel is not None
        self.assertEqual("telegram", manifest.capabilities.channel.platform_code)
        self.assertEqual(["polling"], manifest.capabilities.channel.inbound_modes)
        self.assertEqual(["reply", "push"], manifest.capabilities.channel.delivery_modes)
        self.assertEqual("channel_account", manifest.config_specs[0].scope_type)
        self.assertEqual("bot_token", manifest.config_specs[0].config_schema.fields[0].key)
        self.assertEqual("password", manifest.config_specs[0].ui_schema.widgets["bot_token"].widget)
        self.assertEqual("TG-ID", manifest.capabilities.channel.ui.binding.identity_label)

    def test_manifest_rejects_invalid_config_widget_for_secret_field(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-config-widget-plugin",
                        "name": "Broken Config Plugin",
                        "version": "0.1.0",
                        "types": ["integration"],
                        "permissions": ["device.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"integration": "plugin.integration.sync"},
                        "config_specs": [
                            {
                                "scope_type": "plugin",
                                "title": "鎻掍欢閰嶇疆",
                                "schema_version": 1,
                                "config_schema": {
                                    "fields": [
                                        {
                                            "key": "api_key",
                                            "label": "API Key",
                                            "type": "secret",
                                            "required": True,
                                        }
                                    ]
                                },
                                "ui_schema": {
                                    "sections": [
                                        {
                                            "id": "basic",
                                            "title": "杩炴帴鍙傛暟",
                                            "fields": ["api_key"],
                                        }
                                    ],
                                    "widgets": {
                                        "api_key": {
                                            "widget": "input",
                                        }
                                    },
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("widget", str(context.exception))
        self.assertIn("api_key", str(context.exception))

    def test_manifest_accepts_config_i18n_key_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "config-i18n-plugin",
                        "name": "Config I18n Plugin",
                        "version": "0.1.0",
                        "types": ["integration"],
                        "permissions": ["device.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"integration": "plugin.integration.sync"},
                        "config_specs": [
                            {
                                "scope_type": "plugin",
                                "title": "插件配置",
                                "title_key": "plugin.config.title",
                                "description": "插件配置说明",
                                "description_key": "plugin.config.description",
                                "schema_version": 1,
                                "config_schema": {
                                    "fields": [
                                        {
                                            "key": "mode",
                                            "label": "模式",
                                            "label_key": "plugin.config.fields.mode.label",
                                            "description": "模式说明",
                                            "description_key": "plugin.config.fields.mode.description",
                                            "type": "enum",
                                            "required": True,
                                            "enum_options": [
                                                {
                                                    "value": "strict",
                                                    "label": "严格",
                                                    "label_key": "plugin.config.fields.mode.options.strict",
                                                }
                                            ],
                                        }
                                    ]
                                },
                                "ui_schema": {
                                    "sections": [
                                        {
                                            "id": "basic",
                                            "title": "基础设置",
                                            "title_key": "plugin.config.sections.basic.title",
                                            "description": "基础设置说明",
                                            "description_key": "plugin.config.sections.basic.description",
                                            "fields": ["mode"],
                                        }
                                    ],
                                    "submit_text": "保存配置",
                                    "submit_text_key": "plugin.config.submit",
                                    "widgets": {
                                        "mode": {
                                            "widget": "select",
                                            "placeholder": "请选择模式",
                                            "placeholder_key": "plugin.config.fields.mode.placeholder",
                                            "help_text": "这里选择模式",
                                            "help_text_key": "plugin.config.fields.mode.help_text",
                                        }
                                    },
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manifest = load_plugin_manifest(manifest_path)

        self.assertEqual("plugin.config.title", manifest.config_specs[0].title_key)
        self.assertEqual(
            "plugin.config.fields.mode.label",
            manifest.config_specs[0].config_schema.fields[0].label_key,
        )
        self.assertEqual(
            "plugin.config.fields.mode.options.strict",
            manifest.config_specs[0].config_schema.fields[0].enum_options[0].label_key,
        )
        self.assertEqual(
            "plugin.config.fields.mode.help_text",
            manifest.config_specs[0].ui_schema.widgets["mode"].help_text_key,
        )
        self.assertEqual(
            "plugin.config.submit",
            manifest.config_specs[0].ui_schema.submit_text_key,
        )

    def test_manifest_rejects_blank_config_i18n_key(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-config-i18n-plugin",
                        "name": "Broken Config I18n Plugin",
                        "version": "0.1.0",
                        "types": ["integration"],
                        "permissions": ["device.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"integration": "plugin.integration.sync"},
                        "config_specs": [
                            {
                                "scope_type": "plugin",
                                "title": "插件配置",
                                "title_key": "   ",
                                "schema_version": 1,
                                "config_schema": {
                                    "fields": [
                                        {"key": "name", "label": "名称", "type": "string", "required": True}
                                    ]
                                },
                                "ui_schema": {
                                    "sections": [
                                        {"id": "basic", "title": "基础", "fields": ["name"]}
                                    ]
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("i18n key", str(context.exception))

    def test_manifest_rejects_duplicate_config_scope_type(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-config-scope-plugin",
                        "name": "鍧忎綔鐢ㄥ煙鎻掍欢",
                        "version": "0.1.0",
                        "types": ["integration"],
                        "permissions": ["device.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"integration": "plugin.integration.sync"},
                        "config_specs": [
                            {
                                "scope_type": "plugin",
                                "title": "閰嶇疆涓€",
                                "schema_version": 1,
                                "config_schema": {
                                    "fields": [
                                        {"key": "name", "label": "Name", "type": "string", "required": True}
                                    ]
                                },
                                "ui_schema": {
                                    "sections": [{"id": "basic", "title": "鍩虹", "fields": ["name"]}]
                                },
                            },
                            {
                                "scope_type": "plugin",
                                "title": "Config Two",
                                "schema_version": 1,
                                "config_schema": {
                                    "fields": [
                                        {"key": "other", "label": "Other", "type": "string", "required": True}
                                    ]
                                },
                                "ui_schema": {
                                    "sections": [{"id": "basic", "title": "鍩虹", "fields": ["other"]}]
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("scope_type", str(context.exception))

    def test_reject_channel_plugin_missing_channel_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-channel-plugin",
                        "name": "鍧忛€氶亾鎻掍欢",
                        "version": "0.1.0",
                        "types": ["channel"],
                        "permissions": ["channel.receive"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "capabilities": {
                            "channel": {
                                "platform_code": "telegram",
                                "inbound_modes": ["webhook"],
                                "delivery_modes": ["reply"],
                                "reserved": False,
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("entrypoints", str(context.exception))
        self.assertIn("channel", str(context.exception))

    def test_reject_channel_plugin_with_invalid_inbound_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "invalid-channel-plugin",
                        "name": "闈炴硶閫氶亾鎻掍欢",
                        "version": "0.1.0",
                        "types": ["channel"],
                        "permissions": ["channel.receive"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"channel": "plugin.channel.handle"},
                        "capabilities": {
                            "channel": {
                                "platform_code": "telegram",
                                "inbound_modes": ["smtp"],
                                "delivery_modes": ["reply"],
                                "reserved": False,
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("inbound_modes", str(context.exception))
        self.assertIn("smtp", str(context.exception))

    def test_manifest_accepts_schedule_templates_when_schedule_trigger_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "schedule-template-plugin",
                        "name": "璁″垝妯℃澘鎻掍欢",
                        "version": "0.1.0",
                        "types": ["integration"],
                        "permissions": ["health.read"],
                        "risk_level": "low",
                        "triggers": ["manual", "schedule"],
                        "entrypoints": {"integration": "plugin.integration.sync"},
                        "schedule_templates": [
                            {
                                "code": "daily-check",
                                "name": "姣忔棩宸℃",
                                "description": "Check once per day",
                                "default_definition": {
                                    "trigger_type": "schedule",
                                    "schedule_type": "daily",
                                    "schedule_expr": "09:00"
                                },
                                "enabled_by_default": False,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manifest = load_plugin_manifest(manifest_path)

        self.assertEqual(1, len(manifest.schedule_templates))
        self.assertEqual("daily-check", manifest.schedule_templates[0].code)

    def test_manifest_rejects_schedule_templates_without_schedule_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-schedule-template-plugin",
                        "name": "Broken Template Plugin",
                        "version": "0.1.0",
                        "types": ["integration"],
                        "permissions": ["health.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"integration": "plugin.integration.sync"},
                        "schedule_templates": [
                            {
                                "code": "daily-check",
                                "name": "姣忔棩宸℃",
                                "default_definition": {"trigger_type": "schedule"},
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("声明计划任务模板前，triggers 必须包含 schedule", str(context.exception))

    def test_reject_runtime_region_provider_without_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-jp-region-provider",
                        "name": "鍧忓湴鍖烘彁渚涙柟",
                        "version": "0.1.0",
                        "types": ["region-provider"],
                        "permissions": ["region.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"region_provider": "plugin.region_provider.handle"},
                        "capabilities": {
                            "region_provider": {
                                "provider_code": "plugin.jp-sample",
                                "country_codes": [],
                                "entrypoint": "plugin.region_provider.handle",
                                "reserved": False,
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("地区 provider 运行时至少要声明一个 country_code", str(context.exception))

    def test_discover_builtin_manifests(self) -> None:
        manifests = discover_plugin_manifests(self.builtin_root)

        manifest_ids = {item.id for item in manifests}
        self.assertGreaterEqual(len(manifests), 2)
        self.assertIn("homeassistant", manifest_ids)
        self.assertIn("health-basic-reader", manifest_ids)
        self.assertIn("locale-zh-tw", manifest_ids)
        self.assertIn("channel-telegram", manifest_ids)
        self.assertIn("channel-discord", manifest_ids)
        self.assertIn("channel-feishu", manifest_ids)
        self.assertIn("channel-dingtalk", manifest_ids)
        self.assertIn("channel-wecom-app", manifest_ids)
        self.assertIn("channel-wecom-bot", manifest_ids)

    def test_list_registered_plugins_defaults_to_enabled(self) -> None:
        snapshot = list_registered_plugins(self.builtin_root)

        self.assertGreaterEqual(len(snapshot.items), 2)
        self.assertTrue(all(item.enabled for item in snapshot.items))
        locale_pack = next(item for item in snapshot.items if item.id == "locale-zh-tw")
        self.assertEqual(["locale-pack"], locale_pack.types)
        self.assertEqual("zh-TW", locale_pack.locales[0].id)

    def test_list_registered_plugins_skips_invalid_manifest_and_logs_error(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            valid_dir = root / "valid_plugin"
            valid_dir.mkdir(parents=True)
            (valid_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "id": "valid-plugin",
                        "name": "有效插件",
                        "version": "0.1.0",
                        "types": ["integration"],
                        "permissions": ["health.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"integration": "plugin.integration.sync"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            invalid_dir = root / "invalid_plugin"
            invalid_dir.mkdir(parents=True)
            (invalid_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "id": "broken-plugin",
                        "name": "坏插件",
                        "types": ["integration"],
                        "permissions": ["health.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"integration": "plugin.integration.sync"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            _REPORTED_PLUGIN_REGISTRY_ISSUES.clear()
            with patch("app.modules.plugin.service.logger.error") as mock_logger_error:
                snapshot = list_registered_plugins(root)

        self.assertEqual(["valid-plugin"], [item.id for item in snapshot.items])
        mock_logger_error.assert_called_once()
        logged_message = mock_logger_error.call_args.args[0]
        self.assertIn("插件 manifest 无效，已从注册表发现结果中跳过", logged_message)
        self.assertIn("invalid_plugin", logged_message)

    def test_disable_and_enable_plugin_persists_state(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            state_file = Path(tempdir) / "plugin_registry_state.json"

            disabled = disable_plugin(
                "health-basic-reader",
                root_dir=self.builtin_root,
                state_file=state_file,
            )
            self.assertFalse(disabled.enabled)

            disabled_snapshot = list_registered_plugins(self.builtin_root, state_file=state_file)
            disabled_item = next(item for item in disabled_snapshot.items if item.id == "health-basic-reader")
            self.assertFalse(disabled_item.enabled)

            enabled = enable_plugin(
                "health-basic-reader",
                root_dir=self.builtin_root,
                state_file=state_file,
            )
            self.assertTrue(enabled.enabled)

            enabled_snapshot = list_registered_plugins(self.builtin_root, state_file=state_file)
            enabled_item = next(item for item in enabled_snapshot.items if item.id == "health-basic-reader")
            self.assertTrue(enabled_item.enabled)

    def test_execute_plugin_returns_success_result(self) -> None:
        result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="integration",
                payload={"member_id": "mom"},
            ),
            root_dir=self.builtin_root,
        )

        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)
        self.assertIsInstance(result.output, dict)
        assert isinstance(result.output, dict)
        self.assertEqual("health-basic-reader", result.output["source"])
        self.assertEqual("mom", result.output["member_id"])

    def test_execute_plugin_marks_builtin_backend_as_in_process(self) -> None:
        result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="integration",
                payload={"member_id": "mom"},
            ),
            root_dir=self.builtin_root,
        )

        self.assertTrue(result.success)
        self.assertEqual("in_process", result.execution_backend)

    def test_execute_plugin_supports_channel_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            plugin_dir = root / "channel_runtime_plugin"
            package_dir = plugin_dir / "plugin"
            package_dir.mkdir(parents=True)

            (plugin_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "id": "channel-runtime-plugin",
                        "name": "Channel Runtime Plugin",
                        "version": "0.1.0",
                        "types": ["channel"],
                        "permissions": ["channel.receive", "channel.send"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {
                            "channel": "plugin.channel.handle"
                        },
                        "capabilities": {
                            "channel": {
                                "platform_code": "telegram",
                                "inbound_modes": ["webhook"],
                                "delivery_modes": ["reply"],
                                "reserved": False,
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (package_dir / "__init__.py").write_text("", encoding="utf-8")
            (package_dir / "channel.py").write_text(
                "def handle(payload=None):\n"
                "    data = payload or {}\n"
                "    return {\n"
                "        'source': 'channel-runtime-plugin',\n"
                "        'mode': 'channel',\n"
                "        'echo': data,\n"
                "    }\n",
                encoding="utf-8",
            )

            result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="channel-runtime-plugin",
                    plugin_type="channel",
                    payload={"platform_code": "telegram", "event_id": "evt-001"},
                ),
                root_dir=root,
                source_type="third_party",
                runner_config=PluginRunnerConfig(
                    plugin_root=str(plugin_dir),
                    python_path=sys.executable,
                    working_dir=str(plugin_dir),
                    timeout_seconds=10,
                ),
            )

        self.assertTrue(result.success)
        self.assertEqual("subprocess_runner", result.execution_backend)
        self.assertIsInstance(result.output, dict)
        assert isinstance(result.output, dict)
        self.assertEqual("channel", result.output["mode"])
        self.assertEqual("evt-001", result.output["echo"]["event_id"])

    def test_execute_plugin_dispatches_to_subprocess_runner_for_third_party_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            plugin_root = root / "demo_plugin"
            package_dir = plugin_root / "plugin"
            package_dir.mkdir(parents=True)

            (plugin_root / "manifest.json").write_text(
                json.dumps(
                    {
                        "id": "demo-third-party-plugin",
                        "name": "Third Party Demo Plugin",
                        "version": "0.1.0",
                        "types": ["integration"],
                        "permissions": ["health.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {
                            "integration": "plugin.integration.sync"
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (package_dir / "__init__.py").write_text("", encoding="utf-8")
            (package_dir / "integration.py").write_text(
                "def sync(payload=None):\n"
                "    data = payload or {}\n"
                "    return {\n"
                "        'source': 'demo-third-party-plugin',\n"
                "        'mode': 'integration',\n"
                "        'echo': data,\n"
                "        'records': []\n"
                "    }\n",
                encoding="utf-8",
            )

            result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="demo-third-party-plugin",
                    plugin_type="integration",
                    payload={"member_id": "member-001"},
                ),
                root_dir=plugin_root,
                source_type="third_party",
                runner_config=PluginRunnerConfig(
                    plugin_root=str(plugin_root),
                    python_path=sys.executable,
                    working_dir=str(plugin_root),
                    timeout_seconds=10,
                ),
            )

        self.assertTrue(result.success)
        self.assertEqual("subprocess_runner", result.execution_backend)
        self.assertIsInstance(result.output, dict)
        assert isinstance(result.output, dict)
        self.assertEqual("demo-third-party-plugin", result.output["source"])
        self.assertEqual("member-001", result.output["echo"]["member_id"])

    def test_execute_plugin_returns_timeout_error_for_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_third_party_integration_plugin(Path(tempdir), plugin_id="runner-timeout-plugin")

            with patch("app.modules.plugin.executors.subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired(cmd=[sys.executable], timeout=1)

                result = execute_plugin(
                    PluginExecutionRequest(
                        plugin_id="runner-timeout-plugin",
                        plugin_type="integration",
                        payload={},
                    ),
                    root_dir=plugin_root,
                    source_type="third_party",
                    runner_config=PluginRunnerConfig(
                        plugin_root=str(plugin_root),
                        python_path=sys.executable,
                        working_dir=str(plugin_root),
                        timeout_seconds=1,
                    ),
                )

        self.assertFalse(result.success)
        self.assertEqual("subprocess_runner", result.execution_backend)
        self.assertEqual("plugin_runner_timeout", result.error_code)

    def test_execute_plugin_returns_invalid_output_error_for_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_third_party_integration_plugin(Path(tempdir), plugin_id="runner-invalid-json-plugin")

            with patch("app.modules.plugin.executors.subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=[sys.executable, "-m", "app.modules.plugin.runner_protocol"],
                    returncode=0,
                    stdout="not-json",
                    stderr="",
                )

                result = execute_plugin(
                    PluginExecutionRequest(
                        plugin_id="runner-invalid-json-plugin",
                        plugin_type="integration",
                        payload={},
                    ),
                    root_dir=plugin_root,
                    source_type="third_party",
                    runner_config=PluginRunnerConfig(
                        plugin_root=str(plugin_root),
                        python_path=sys.executable,
                        working_dir=str(plugin_root),
                        timeout_seconds=1,
                    ),
                )

        self.assertFalse(result.success)
        self.assertEqual("plugin_runner_invalid_output", result.error_code)

    def test_execute_plugin_returns_dependency_missing_error_for_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_third_party_integration_plugin(Path(tempdir), plugin_id="runner-missing-dependency-plugin")

            with patch("app.modules.plugin.executors.subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=[sys.executable, "-m", "app.modules.plugin.runner_protocol"],
                    returncode=1,
                    stdout="",
                    stderr="ModuleNotFoundError: No module named 'missing_dependency'",
                )

                result = execute_plugin(
                    PluginExecutionRequest(
                        plugin_id="runner-missing-dependency-plugin",
                        plugin_type="integration",
                        payload={},
                    ),
                    root_dir=plugin_root,
                    source_type="third_party",
                    runner_config=PluginRunnerConfig(
                        plugin_root=str(plugin_root),
                        python_path=sys.executable,
                        working_dir=str(plugin_root),
                        timeout_seconds=1,
                    ),
                )

        self.assertFalse(result.success)
        self.assertEqual("plugin_runner_dependency_missing", result.error_code)

    def test_ingest_plugin_raw_records_to_memory_uses_subprocess_runner_for_third_party_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_third_party_sync_plugin(Path(tempdir), plugin_id="third-party-sync-plugin")

            integration_result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="third-party-sync-plugin",
                    plugin_type="integration",
                    payload={"member_id": "member-001"},
                ),
                root_dir=plugin_root,
                source_type="third_party",
                runner_config=PluginRunnerConfig(
                    plugin_root=str(plugin_root),
                    python_path=sys.executable,
                    working_dir=str(plugin_root),
                    timeout_seconds=10,
                ),
            )

            self.assertTrue(integration_result.success)

    def _create_third_party_integration_plugin(self, root: Path, *, plugin_id: str) -> Path:
        return self._create_third_party_plugin(
            root,
            plugin_id=plugin_id,
            integration_body=(
                "def sync(payload=None):\n"
                "    data = payload or {}\n"
                "    return {\n"
                "        'source': '" + plugin_id + "',\n"
                "        'mode': 'integration',\n"
                "        'echo': data,\n"
                "        'records': []\n"
                "    }\n"
            ),
        )

    def _create_third_party_sync_plugin(self, root: Path, *, plugin_id: str) -> Path:
        return self._create_third_party_plugin(
            root,
            plugin_id=plugin_id,
            plugin_types=["integration"],
            entrypoints={
                "integration": "plugin.integration.sync",
            },
            integration_body=(
                "def sync(payload=None):\n"
                "    data = payload or {}\n"
                "    member_id = data.get('member_id', 'member-001')\n"
                "    return {\n"
                "        'source': '" + plugin_id + "',\n"
                "        'records': [\n"
                "            {\n"
                "                'record_type': 'steps',\n"
                "                'member_id': member_id,\n"
                "                'value': 42,\n"
                "                'unit': 'count',\n"
                "                'captured_at': '2026-03-13T07:30:00Z'\n"
                "            }\n"
                "        ]\n"
                "    }\n"
            ),
            ingestor_body=(
                "def transform(payload=None):\n"
                "    data = payload or {}\n"
                "    records = data.get('records', [])\n"
                "    if not records:\n"
                "        return []\n"
                "    record = records[0]\n"
                "    source = record.get('payload', {})\n"
                "    return [\n"
                "        {\n"
                "            'type': 'Observation',\n"
                "            'subject_type': 'Person',\n"
                "            'subject_id': source.get('member_id'),\n"
                "            'category': 'daily_steps',\n"
                "            'value': source.get('value'),\n"
                "            'unit': source.get('unit'),\n"
                "            'observed_at': record.get('captured_at'),\n"
                "            'source_plugin_id': '" + plugin_id + "',\n"
                "            'source_record_ref': record.get('id')\n"
                "        }\n"
                "    ]\n"
            ),
        )

    def _create_third_party_plugin(
        self,
        root: Path,
        *,
        plugin_id: str,
        plugin_types: list[str] | None = None,
        entrypoints: dict[str, str] | None = None,
        integration_body: str | None = None,
        ingestor_body: str | None = None,
    ) -> Path:
        plugin_root = root / plugin_id
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True)

        manifest = {
            "id": plugin_id,
            "name": f"{plugin_id}-name",
            "version": "0.1.0",
            "types": plugin_types or ["integration"],
            "permissions": ["health.read"],
            "risk_level": "low",
            "triggers": ["manual"],
            "entrypoints": entrypoints or {"integration": "plugin.integration.sync"},
        }
        (plugin_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        if integration_body is not None:
            (package_dir / "integration.py").write_text(integration_body, encoding="utf-8")
        if ingestor_body is not None:
            (package_dir / "ingestor.py").write_text(ingestor_body, encoding="utf-8")
        return plugin_root

    def test_execute_plugin_returns_failure_when_plugin_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            state_file = Path(tempdir) / "plugin_registry_state.json"
            disable_plugin("health-basic-reader", root_dir=self.builtin_root, state_file=state_file)

            result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="health-basic-reader",
                    plugin_type="integration",
                    payload={},
                ),
                root_dir=self.builtin_root,
                state_file=state_file,
            )

        self.assertFalse(result.success)
        self.assertEqual("plugin_execution_failed", result.error_code)
        self.assertIn("已禁用", result.error_message or "")

    def test_reject_locale_pack_manifest_without_locales(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-locale-pack",
                        "name": "Broken Locale Pack",
                        "version": "0.1.0",
                        "types": ["locale-pack"],
                        "permissions": [],
                        "risk_level": "low",
                        "triggers": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("locale-pack 插件至少要声明一个 locale", str(context.exception))

    def test_execute_plugin_returns_failure_when_handler_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            plugin_dir = root / "broken"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "id": "broken-runtime-plugin",
                        "name": "杩愯澶辫触鎻掍欢",
                        "version": "0.1.0",
                        "types": ["integration"],
                        "permissions": ["health.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {
                            "integration": "app.plugins.builtin.health_basic.integration.fail_sync"
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="broken-runtime-plugin",
                    plugin_type="integration",
                    payload={},
                ),
                root_dir=root,
            )

        self.assertFalse(result.success)
        self.assertEqual("plugin_execution_failed", result.error_code)
        self.assertIn("demo plugin failure", result.error_message or "")

    def test_theme_pack_manifest_requires_resource_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "theme-pack-missing-resource-meta",
                        "name": "Theme Pack Missing Resource Meta",
                        "version": "1.0.0",
                        "types": ["theme-pack"],
                        "permissions": [],
                        "risk_level": "low",
                        "triggers": [],
                        "entrypoints": {},
                        "capabilities": {
                            "theme_pack": {
                                "theme_id": "chun-he-jing-ming",
                                "display_name": "春和景明",
                                "tokens_resource": "themes/chun-he-jing-ming.json",
                                "resource_source": "builtin_bundle",
                                "theme_schema_version": 1,
                                "platform_targets": ["h5", "rn"],
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("resource_version", str(context.exception))

    def test_registered_plugins_include_theme_and_real_ai_provider_entries(self) -> None:
        registry = list_registered_plugins(self.builtin_root)

        theme_plugin = next(item for item in registry.items if item.id == "builtin.theme.chun-he-jing-ming")
        self.assertEqual(["theme-pack"], theme_plugin.types)
        self.assertEqual("1.0.0", theme_plugin.installed_version)
        self.assertEqual("chun-he-jing-ming", theme_plugin.capabilities.theme_pack.theme_id)
        self.assertEqual(
            (self.builtin_root / "theme_chun_he_jing_ming_pack" / "manifest.json").resolve(),
            Path(theme_plugin.manifest_path).resolve(),
        )
        self.assertEqual("1.0.0", theme_plugin.capabilities.theme_pack.resource_version)
        self.assertEqual(1, theme_plugin.capabilities.theme_pack.theme_schema_version)
        self.assertEqual(["h5", "rn"], theme_plugin.capabilities.theme_pack.platform_targets)

        ai_provider_plugin = next(item for item in registry.items if item.id == "builtin.provider.chatgpt")
        self.assertEqual(["ai-provider"], ai_provider_plugin.types)
        self.assertEqual("1.0.0", ai_provider_plugin.installed_version)
        self.assertEqual(
            (self.builtin_root / "ai_provider_chatgpt" / "manifest.json").resolve(),
            Path(ai_provider_plugin.manifest_path).resolve(),
        )
        self.assertEqual("chatgpt", ai_provider_plugin.capabilities.ai_provider.adapter_code)
        self.assertEqual(
            "app.plugins.builtin.ai_provider_chatgpt.driver.build_driver",
            ai_provider_plugin.entrypoints.ai_provider,
        )
        self.assertEqual(
            "openai_chat_completions",
            ai_provider_plugin.compatibility["api_family"],
        )

    def test_stage1_framework_checkpoint_smoke(self) -> None:
        registry = list_registered_plugins(self.builtin_root)
        self.assertGreaterEqual(len(registry.items), 2)

        health_plugin = next(item for item in registry.items if item.id == "health-basic-reader")
        self.assertTrue(health_plugin.enabled)
        self.assertIn("integration", health_plugin.types)

        success_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="integration",
                payload={"member_id": "dad"},
            ),
            root_dir=self.builtin_root,
        )
        self.assertTrue(success_result.success)
        self.assertEqual("health-basic-reader", success_result.plugin_id)

        failure_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="not-exists-plugin",
                plugin_type="integration",
                payload={},
            ),
            root_dir=self.builtin_root,
        )
        self.assertFalse(failure_result.success)
        self.assertEqual("plugin_execution_failed", failure_result.error_code)
        self.assertIn("插件不存在", failure_result.error_message or "")


class PluginEffectiveStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        self.builtin_root = Path(__file__).resolve().parents[1] / "app" / "plugins" / "builtin"
        self.state_file = Path(self._tempdir.name) / "plugin_registry_state.json"

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
        self.db: Session = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_household_override_can_disable_builtin_plugin(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="State Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        updated = set_household_plugin_enabled(
            self.db,
            household_id=household.id,
            plugin_id="health-basic-reader",
            payload=PluginStateUpdateRequest(enabled=False),
            updated_by="tester",
            root_dir=self.builtin_root,
            state_file=self.state_file,
        )
        self.db.commit()

        self.assertTrue(updated.base_enabled)
        self.assertFalse(updated.enabled)
        self.assertEqual(False, updated.household_enabled)
        self.assertIn("当前家庭已停用该插件", updated.disabled_reason or "")

        snapshot = list_registered_plugins_for_household(
            self.db,
            household_id=household.id,
            root_dir=self.builtin_root,
            state_file=self.state_file,
        )
        plugin = next(item for item in snapshot.items if item.id == "health-basic-reader")
        self.assertFalse(plugin.enabled)
        self.assertEqual(False, plugin.household_enabled)

    def test_effective_enabled_uses_base_and_household_state(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Merged State Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()
        disable_plugin("health-basic-reader", root_dir=self.builtin_root, state_file=self.state_file)

        updated = set_household_plugin_enabled(
            self.db,
            household_id=household.id,
            plugin_id="health-basic-reader",
            payload=PluginStateUpdateRequest(enabled=True),
            updated_by="tester",
            root_dir=self.builtin_root,
            state_file=self.state_file,
        )

        self.assertFalse(updated.base_enabled)
        self.assertEqual(True, updated.household_enabled)
        self.assertFalse(updated.enabled)
        self.assertIn("基础状态", updated.disabled_reason or "")

    def test_household_override_can_disable_virtual_ai_provider_plugin(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="AI Provider Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        updated = set_household_plugin_enabled(
            self.db,
            household_id=household.id,
            plugin_id="builtin.provider.chatgpt",
            payload=PluginStateUpdateRequest(enabled=False),
            updated_by="tester",
            root_dir=self.builtin_root,
            state_file=self.state_file,
        )

        self.assertIn("ai-provider", updated.types)
        self.assertFalse(updated.enabled)
        self.assertEqual(False, updated.household_enabled)

        snapshot = list_registered_plugins_for_household(
            self.db,
            household_id=household.id,
            root_dir=self.builtin_root,
            state_file=self.state_file,
        )
        plugin = next(item for item in snapshot.items if item.id == "builtin.provider.chatgpt")
        self.assertFalse(plugin.enabled)
        self.assertEqual(False, plugin.household_enabled)


