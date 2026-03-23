import base64
import hashlib
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from xml.etree import ElementTree

from cryptography.hazmat.primitives import padding, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import httpx

from app.modules.channel.schemas import ChannelInboundMessage
from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.service import execute_plugin, list_registered_plugins
from app.plugins.builtin.channel_feishu import event_parser as feishu_event_parser
from app.plugins.builtin.channel_feishu import plugin_binding as feishu_plugin_binding


class _MockHttpResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class BuiltinChannelPluginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builtin_root = Path(__file__).resolve().parents[1] / "app" / "plugins" / "builtin"

    def test_builtin_channel_plugins_are_registered(self) -> None:
        snapshot = list_registered_plugins(self.builtin_root)
        plugin_ids = {item.id for item in snapshot.items}

        self.assertIn("channel-telegram", plugin_ids)
        self.assertIn("channel-discord", plugin_ids)
        self.assertIn("channel-feishu", plugin_ids)
        self.assertIn("channel-dingtalk", plugin_ids)

    def _legacy_test_telegram_plugin_normalizes_webhook_and_sends_text(self) -> None:
        webhook_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="channel-telegram",
                plugin_type="channel",
                payload={
                    "action": "webhook",
                    "account": {
                        "config": json.dumps(
                            {
                                "bot_token": "telegram-token",
                                "webhook_secret": "tg-secret",
                            }
                        )
                    },
                    "request": {
                        "headers": {"X-Telegram-Bot-Api-Secret-Token": "tg-secret"},
                        "body_text": json.dumps(
                            {
                                "update_id": 1001,
                                "message": {
                                    "message_id": 2002,
                                    "message_thread_id": 9,
                                    "text": "你好，Telegram",
                                    "chat": {"id": 3003, "type": "private"},
                                    "from": {"id": 4004, "username": "alice"},
                                },
                            }
                        ),
                    },
                },
            ),
            root_dir=self.builtin_root,
        )

        self.assertTrue(webhook_result.success)
        event = webhook_result.output["event"]
        self.assertEqual("1001", event["external_event_id"])
        self.assertEqual("4004", event["external_user_id"])
        self.assertEqual("chat:3003", event["external_conversation_key"])
        self.assertEqual("direct", event["normalized_payload"]["chat_type"])
        self.assertEqual("9", event["normalized_payload"]["thread_key"])
        self.assertEqual("alice", event["normalized_payload"]["sender_display_name"])
        self.assertEqual("3003", event["normalized_payload"]["metadata"]["chat_id"])
        self.assertEqual("2002", event["normalized_payload"]["metadata"]["message_id"])
        self.assertEqual("alice", event["normalized_payload"]["metadata"]["username"])

        with patch("app.plugins.builtin.channel_telegram.channel.httpx.post") as http_post:
            http_post.return_value = _MockHttpResponse({"ok": True, "result": {"message_id": 5555}})
            send_result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="channel-telegram",
                    plugin_type="channel",
                    payload={
                        "action": "send",
                        "account": {"config": json.dumps({"bot_token": "telegram-token"})},
                        "delivery": {
                            "external_conversation_key": "chat:3003#thread:9",
                            "text": "回复 Telegram",
                        },
                    },
                ),
                root_dir=self.builtin_root,
            )

        self.assertTrue(send_result.success)
        self.assertEqual("5555", send_result.output["provider_message_ref"])
        self.assertIn("/sendMessage", http_post.call_args.args[0])
        self.assertEqual(9, http_post.call_args.kwargs["json"]["message_thread_id"])

    def _legacy_test_telegram_plugin_handles_missing_display_name_and_username(self) -> None:
        webhook_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="channel-telegram",
                plugin_type="channel",
                payload={
                    "action": "webhook",
                    "account": {"config": json.dumps({"bot_token": "telegram-token"})},
                    "request": {
                        "body_text": json.dumps(
                            {
                                "update_id": 1002,
                                "message": {
                                    "message_id": 2003,
                                    "text": "hello",
                                    "chat": {"id": 3004, "type": "private"},
                                    "from": {"id": 4005},
                                },
                            }
                        )
                    },
                },
            ),
            root_dir=self.builtin_root,
        )

        self.assertTrue(webhook_result.success)
        event = webhook_result.output["event"]
        self.assertIsNone(event["normalized_payload"]["sender_display_name"])
        self.assertIsNone(event["normalized_payload"]["metadata"]["username"])
        self.assertEqual("3004", event["normalized_payload"]["metadata"]["chat_id"])

    def test_telegram_plugin_normalizes_polling_updates_and_sends_text(self) -> None:
        with patch("app.plugins.builtin.channel_telegram.channel.httpx.post") as http_post:
            http_post.side_effect = [
                _MockHttpResponse(
                    {
                        "ok": True,
                        "result": [
                            {
                                "update_id": 1001,
                                "message": {
                                    "message_id": 2002,
                                    "message_thread_id": 9,
                                    "text": "你好，Telegram",
                                    "chat": {"id": 3003, "type": "private"},
                                    "from": {"id": 4004, "username": "alice"},
                                },
                            }
                        ],
                    }
                ),
                _MockHttpResponse({"ok": True, "result": {"message_id": 5555}}),
            ]
            poll_result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="channel-telegram",
                    plugin_type="channel",
                    payload={
                        "action": "poll",
                        "account": {"config": json.dumps({"bot_token": "telegram-token"})},
                        "poll_state": {"cursor": "1001"},
                    },
                ),
                root_dir=self.builtin_root,
            )
            send_result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="channel-telegram",
                    plugin_type="channel",
                    payload={
                        "action": "send",
                        "account": {"config": json.dumps({"bot_token": "telegram-token"})},
                        "delivery": {
                            "external_conversation_key": "chat:3003#thread:9",
                            "text": "回复 Telegram",
                        },
                    },
                ),
                root_dir=self.builtin_root,
            )

        self.assertTrue(poll_result.success)
        self.assertEqual("1002", poll_result.output["next_cursor"])
        self.assertEqual(1, len(poll_result.output["events"]))
        event = poll_result.output["events"][0]
        self.assertEqual("1001", event["external_event_id"])
        self.assertEqual("4004", event["external_user_id"])
        self.assertEqual("chat:3003", event["external_conversation_key"])
        self.assertEqual("direct", event["normalized_payload"]["chat_type"])
        self.assertEqual("9", event["normalized_payload"]["thread_key"])
        self.assertEqual("alice", event["normalized_payload"]["sender_display_name"])
        self.assertEqual("3003", event["normalized_payload"]["metadata"]["chat_id"])
        self.assertEqual("2002", event["normalized_payload"]["metadata"]["message_id"])
        self.assertEqual("alice", event["normalized_payload"]["metadata"]["username"])

        self.assertTrue(send_result.success)
        self.assertEqual("5555", send_result.output["provider_message_ref"])
        self.assertIn("/sendMessage", http_post.call_args.args[0])
        self.assertEqual(9, http_post.call_args.kwargs["json"]["message_thread_id"])

    def test_telegram_plugin_handles_missing_display_name_and_username(self) -> None:
        with patch("app.plugins.builtin.channel_telegram.channel.httpx.post") as http_post:
            http_post.return_value = _MockHttpResponse(
                {
                    "ok": True,
                    "result": [
                        {
                            "update_id": 1002,
                            "message": {
                                "message_id": 2003,
                                "text": "hello",
                                "chat": {"id": 3004, "type": "private"},
                                "from": {"id": 4005},
                            },
                        }
                    ],
                }
            )
            poll_result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="channel-telegram",
                    plugin_type="channel",
                    payload={
                        "action": "poll",
                        "account": {"config": json.dumps({"bot_token": "telegram-token"})},
                    },
                ),
                root_dir=self.builtin_root,
            )

        self.assertTrue(poll_result.success)
        event = poll_result.output["events"][0]
        self.assertIsNone(event["normalized_payload"]["sender_display_name"])
        self.assertIsNone(event["normalized_payload"]["metadata"]["username"])
        self.assertEqual("3004", event["normalized_payload"]["metadata"]["chat_id"])

    def test_telegram_plugin_retries_polling_after_transport_error(self) -> None:
        request = httpx.Request("POST", "https://api.telegram.org/bottelegram-token/getUpdates")
        with patch("app.plugins.builtin.channel_telegram.channel.httpx.post") as http_post:
            http_post.side_effect = [
                httpx.ReadError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol", request=request),
                _MockHttpResponse(
                    {
                        "ok": True,
                        "result": [
                            {
                                "update_id": 1005,
                                "message": {
                                    "message_id": 2005,
                                    "text": "retry ok",
                                    "chat": {"id": 3005, "type": "private"},
                                    "from": {"id": 4005, "username": "retry_user"},
                                },
                            }
                        ],
                    }
                ),
            ]
            poll_result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="channel-telegram",
                    plugin_type="channel",
                    payload={
                        "action": "poll",
                        "account": {"config": json.dumps({"bot_token": "telegram-token"})},
                    },
                ),
                root_dir=self.builtin_root,
            )

        self.assertTrue(poll_result.success)
        self.assertEqual(2, http_post.call_count)
        self.assertEqual("1006", poll_result.output["next_cursor"])
        self.assertEqual("1005", poll_result.output["events"][0]["external_event_id"])

    def test_discord_plugin_handles_ping_and_command_delivery(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()

        ping_body = json.dumps({"type": 1})
        ping_headers = self._build_discord_headers(private_key, ping_body)
        ping_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="channel-discord",
                plugin_type="channel",
                payload={
                    "action": "webhook",
                    "account": {"config": json.dumps({"application_public_key": public_key})},
                    "request": {
                        "headers": ping_headers,
                        "body_text": ping_body,
                    },
                },
            ),
            root_dir=self.builtin_root,
        )

        self.assertTrue(ping_result.success)
        self.assertEqual({"type": 1}, ping_result.output["http_response"]["body_json"])

        command_body = json.dumps(
            {
                "type": 2,
                "id": "99001",
                "application_id": "app-001",
                "token": "interaction-token",
                "channel_id": "channel-009",
                "guild_id": "guild-001",
                "member": {
                    "user": {
                        "id": "discord-user-001",
                        "username": "discord-alice",
                    }
                },
                "data": {
                    "name": "familyclaw",
                    "options": [
                        {"name": "text", "type": 3, "value": "你好，Discord"}
                    ],
                },
            }
        )
        command_headers = self._build_discord_headers(private_key, command_body)
        command_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="channel-discord",
                plugin_type="channel",
                payload={
                    "action": "webhook",
                    "account": {"config": json.dumps({"application_public_key": public_key})},
                    "request": {
                        "headers": command_headers,
                        "body_text": command_body,
                    },
                },
            ),
            root_dir=self.builtin_root,
        )

        self.assertTrue(command_result.success)
        self.assertEqual({"type": 5}, command_result.output["http_response"]["body_json"])
        self.assertTrue(command_result.output["http_response"]["defer_processing"])
        event = command_result.output["event"]
        self.assertEqual("99001", event["external_event_id"])
        self.assertEqual("discord-user-001", event["external_user_id"])
        self.assertEqual("channel:channel-009", event["external_conversation_key"])

        with patch("app.plugins.builtin.channel_discord.channel.httpx.post") as http_post:
            http_post.return_value = _MockHttpResponse({"id": "discord-msg-001"})
            send_result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="channel-discord",
                    plugin_type="channel",
                    payload={
                        "action": "send",
                        "account": {"config": json.dumps({"bot_token": "discord-bot-token"})},
                        "delivery": {
                            "external_conversation_key": "channel:channel-009",
                            "text": "回复 Discord",
                            "metadata": {
                                "application_id": "app-001",
                                "interaction_token": "interaction-token",
                                "channel_id": "channel-009",
                            },
                        },
                    },
                ),
                root_dir=self.builtin_root,
            )

        self.assertTrue(send_result.success)
        self.assertEqual("discord-msg-001", send_result.output["provider_message_ref"])
        self.assertIn("/webhooks/app-001/interaction-token", http_post.call_args.args[0])

    def test_feishu_plugin_handles_challenge_message_and_send(self) -> None:
        challenge_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="channel-feishu",
                plugin_type="channel",
                payload={
                    "action": "webhook",
                    "account": {"config": json.dumps({"verification_token": "vt-001"})},
                    "request": {
                        "body_text": json.dumps(
                            {
                                "type": "url_verification",
                                "token": "vt-001",
                                "challenge": "challenge-xyz",
                            }
                        )
                    },
                },
            ),
            root_dir=self.builtin_root,
        )

        self.assertTrue(challenge_result.success)
        self.assertEqual(
            {"challenge": "challenge-xyz"},
            challenge_result.output["http_response"]["body_json"],
        )

        with patch(
            "app.plugins.builtin.channel_feishu.channel.route_inbound_event_for_core",
            side_effect=lambda _account, event: event,
        ):
            message_result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="channel-feishu",
                    plugin_type="channel",
                    payload={
                        "action": "webhook",
                        "account": {"config": json.dumps({"verification_token": "vt-001"})},
                        "request": {
                            "body_text": json.dumps(
                                {
                                    "schema": "2.0",
                                    "header": {
                                        "event_id": "evt-feishu-001",
                                        "event_type": "im.message.receive_v1",
                                    },
                                    "event_id": "evt-feishu-001",
                                    "token": "vt-001",
                                    "event": {
                                        "sender": {
                                            "sender_id": {"open_id": "ou_user_001"},
                                            "tenant_key": "张三",
                                        },
                                        "message": {
                                            "message_id": "om_001",
                                            "chat_id": "oc_123",
                                            "chat_type": "p2p",
                                            "message_type": "text",
                                            "thread_id": "th_001",
                                            "content": json.dumps({"text": "你好，飞书"}, ensure_ascii=False),
                                        },
                                    },
                                },
                                ensure_ascii=False,
                            )
                        },
                    },
                ),
                root_dir=self.builtin_root,
            )

        self.assertTrue(message_result.success)
        event = message_result.output["event"]
        self.assertEqual("evt-feishu-001", event["external_event_id"])
        self.assertEqual("ou_user_001", event["external_user_id"])
        self.assertEqual("chat:oc_123", event["external_conversation_key"])
        self.assertEqual("direct", event["normalized_payload"]["chat_type"])
        self.assertEqual("th_001", event["normalized_payload"]["thread_key"])

        with patch("app.plugins.builtin.channel_feishu.channel.httpx.post") as http_post:
            http_post.side_effect = [
                _MockHttpResponse({"tenant_access_token": "tenant-token-001"}),
                _MockHttpResponse({"data": {"message_id": "om_reply_001"}}),
            ]
            send_result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="channel-feishu",
                    plugin_type="channel",
                    payload={
                        "action": "send",
                        "account": {
                            "config": json.dumps(
                                {
                                    "app_id": "cli_xxx",
                                    "app_secret": "secret-yyy",
                                }
                            )
                        },
                        "delivery": {
                            "external_conversation_key": "chat:oc_123",
                            "text": "回复 飞书",
                        },
                    },
                ),
                root_dir=self.builtin_root,
            )

        self.assertTrue(send_result.success)
        self.assertEqual("om_reply_001", send_result.output["provider_message_ref"])
        self.assertIn("/tenant_access_token/internal", http_post.call_args_list[0].args[0])
        self.assertIn("/im/v1/messages", http_post.call_args_list[1].args[0])

    def test_feishu_plugin_accepts_encrypted_callback_payload(self) -> None:
        inner_payload = {
            "schema": "2.0",
            "event_id": "evt-feishu-encrypted-001",
            "token": "vt-enc-001",
            "event": {
                "sender": {
                    "sender_id": {"open_id": "ou_user_encrypt_001"},
                    "tenant_key": "李四",
                },
                "message": {
                    "message_id": "om_encrypt_001",
                    "chat_id": "oc_encrypt_123",
                    "chat_type": "p2p",
                    "message_type": "text",
                    "thread_id": "th_encrypt_001",
                    "content": json.dumps({"text": "你好，加密飞书"}, ensure_ascii=False),
                },
            },
        }
        encrypt_key = "feishu-encrypt-demo-key"
        encrypted_text = self._encrypt_feishu_payload(inner_payload, encrypt_key)

        with patch(
            "app.plugins.builtin.channel_feishu.channel.route_inbound_event_for_core",
            side_effect=lambda _account, event: event,
        ):
            result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="channel-feishu",
                    plugin_type="channel",
                    payload={
                        "action": "webhook",
                        "account": {
                            "config": json.dumps(
                                {
                                    "verification_token": "vt-enc-001",
                                    "encrypt_key": encrypt_key,
                                }
                            )
                        },
                        "request": {
                            "body_text": json.dumps({"encrypt": encrypted_text}),
                        },
                    },
                ),
                root_dir=self.builtin_root,
            )

        self.assertTrue(result.success)
        event = result.output["event"]
        self.assertEqual("evt-feishu-encrypted-001", event["external_event_id"])
        self.assertEqual("ou_user_encrypt_001", event["external_user_id"])
        self.assertEqual("chat:oc_encrypt_123", event["external_conversation_key"])
        self.assertEqual("th_encrypt_001", event["normalized_payload"]["thread_key"])

    def test_feishu_plugin_treats_private_chat_as_direct_message(self) -> None:
        event = feishu_event_parser.normalize_feishu_message_event(
            {
                "schema": "2.0",
                "header": {
                    "event_id": "evt-feishu-private-001",
                    "event_type": "im.message.receive_v1",
                },
                "event": {
                    "sender": {
                        "sender_id": {"open_id": "ou_user_private_001"},
                        "tenant_key": "王五",
                    },
                    "message": {
                        "message_id": "om_private_001",
                        "chat_id": "oc_private_001",
                        "chat_type": "private",
                        "message_type": "text",
                        "content": json.dumps({"text": "你好，私聊飞书"}, ensure_ascii=False),
                    },
                },
            }
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual("direct", event["normalized_payload"]["chat_type"])
        self.assertEqual("private", event["normalized_payload"]["metadata"]["chat_type"])

    def test_feishu_plugin_handles_unbound_direct_message_inside_plugin(self) -> None:
        class _FakeSession:
            def __init__(self) -> None:
                self.commit_count = 0
                self.account_row = SimpleNamespace(last_inbound_at=None, last_outbound_at=None, updated_at=None)

            def commit(self) -> None:
                self.commit_count += 1

        class _FakeSessionLocal:
            def __init__(self, db: _FakeSession) -> None:
                self._db = db

            def __call__(self):
                return self

            def __enter__(self):
                return self._db

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        fake_db = _FakeSession()
        fake_event_row = SimpleNamespace(received_at="2026-03-19T09:00:00Z")
        account_payload = {
            "id": "feishu-account-001",
            "household_id": "household-001",
            "config": json.dumps(
                {
                    "app_id": "cli_xxx",
                    "app_secret": "secret-yyy",
                }
            ),
        }
        inbound_event = {
            "external_event_id": "evt-feishu-unbound-001",
            "event_type": "message",
            "external_user_id": "ou_user_unbound_001",
            "external_conversation_key": "chat:oc_unbound_001",
            "received_at": "2026-03-19T09:00:00Z",
            "normalized_payload": {
                "text": "你好，未绑定飞书",
                "chat_type": "direct",
                "metadata": {
                    "chat_id": "oc_unbound_001",
                },
            },
        }

        with patch.object(feishu_plugin_binding, "SessionLocal", _FakeSessionLocal(fake_db)):
            with patch.object(feishu_plugin_binding, "_get_active_member_binding", return_value=None):
                with patch.object(
                    feishu_plugin_binding,
                    "record_channel_inbound_event",
                    return_value=(fake_event_row, True),
                ) as record_mock:
                    with patch.object(
                        feishu_plugin_binding.repository,
                        "get_channel_plugin_account",
                        return_value=fake_db.account_row,
                    ):
                        with patch.object(
                            feishu_plugin_binding,
                            "send_text_message",
                            return_value="om_reply_unbound_001",
                        ) as send_mock:
                            result = feishu_plugin_binding.route_inbound_event_for_core(account_payload, inbound_event)

        self.assertIsNone(result)
        record_mock.assert_called_once()
        send_mock.assert_called_once()
        self.assertEqual(feishu_plugin_binding.UNBOUND_DIRECT_REPLY_TEXT, send_mock.call_args.kwargs["text"])
        self.assertEqual(2, fake_db.commit_count)

    def test_channel_bridge_prefers_plugin_binding_metadata(self) -> None:
        normalized_message = ChannelInboundMessage.model_validate(
            {
                "text": "你好",
                "chat_type": "direct",
                "metadata": {
                    "plugin_binding": {
                        "managed_by_plugin": True,
                        "matched": True,
                        "strategy": "bound",
                        "member_id": "member-001",
                        "binding_id": "binding-001",
                    }
                },
            }
        )

        with patch("app.modules.channel.conversation_bridge.resolve_member_binding_for_inbound") as fallback_mock:
            from app.modules.channel import conversation_bridge

            result = conversation_bridge._resolve_inbound_binding(
                None,
                household_id="household-001",
                channel_account_id="channel-account-001",
                inbound_event=SimpleNamespace(external_user_id="ou_user_001"),
                normalized_message=normalized_message,
            )

        fallback_mock.assert_not_called()
        self.assertTrue(result.matched)
        self.assertEqual("bound", result.strategy)
        self.assertEqual("member-001", result.member_id)
        self.assertEqual("binding-001", result.binding_id)

    def test_dingtalk_plugin_polls_stream_queue_and_sends_group_message_via_openapi(self) -> None:
        class _FakePoller:
            def drain_events(self, *, limit: int) -> list[dict]:
                self.last_limit = limit
                return [
                    {
                        "external_event_id": "stream-msg-001",
                        "event_type": "message",
                        "external_user_id": "staff-001",
                        "external_conversation_key": "group:cid-001",
                        "normalized_payload": {
                            "text": "你好，钉钉",
                            "chat_type": "group",
                            "sender_display_name": "钉钉用户",
                            "metadata": {
                                "conversation_id": "cid-001",
                                "stream_message_id": "stream-msg-001",
                            },
                        },
                        "status": "received",
                    }
                ]

        fake_poller = _FakePoller()
        with patch(
            "app.plugins.builtin.channel_dingtalk.channel._ensure_stream_poller",
            return_value=fake_poller,
        ) as ensure_poller:
            poll_result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="channel-dingtalk",
                    plugin_type="channel",
                    payload={
                        "action": "poll",
                        "account": {
                            "id": "ding-account-001",
                            "config": json.dumps(
                                {
                                    "app_key": "ding-app-key-poll",
                                    "app_secret": "ding-app-secret-poll",
                                }
                            ),
                        },
                    },
                ),
                root_dir=self.builtin_root,
            )

        self.assertTrue(poll_result.success)
        ensure_poller.assert_called_once()
        self.assertEqual("stream-msg-001", poll_result.output["next_cursor"])
        self.assertEqual(1, len(poll_result.output["events"]))
        event = poll_result.output["events"][0]
        self.assertEqual("stream-msg-001", event["external_event_id"])
        self.assertEqual("staff-001", event["external_user_id"])
        self.assertEqual("group:cid-001", event["external_conversation_key"])
        self.assertEqual("group", event["normalized_payload"]["chat_type"])

        with patch("app.plugins.builtin.channel_dingtalk.channel.httpx.post") as http_post:
            http_post.side_effect = [
                _MockHttpResponse({"accessToken": "ding-access-token", "expireIn": 7200}),
                _MockHttpResponse({"processQueryKey": "ding-send-001"}),
            ]
            send_result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="channel-dingtalk",
                    plugin_type="channel",
                    payload={
                        "action": "send",
                        "account": {
                            "config": json.dumps(
                                {
                                    "app_key": "ding-app-key-send",
                                    "app_secret": "ding-app-secret-send",
                                }
                            )
                        },
                        "delivery": {
                            "external_conversation_key": "group:cid-001",
                            "text": "回复 钉钉",
                        },
                    },
                ),
                root_dir=self.builtin_root,
            )

        self.assertTrue(send_result.success)
        self.assertEqual("ding-send-001", send_result.output["provider_message_ref"])
        self.assertEqual(
            "https://api.dingtalk.com/v1.0/oauth2/accessToken",
            http_post.call_args_list[0].args[0],
        )
        self.assertEqual(
            "https://api.dingtalk.com/v1.0/robot/groupMessages/send",
            http_post.call_args_list[1].args[0],
        )
        self.assertEqual(
            "ding-access-token",
            http_post.call_args_list[1].kwargs["headers"]["x-acs-dingtalk-access-token"],
        )
        self.assertEqual(
            "cid-001",
            http_post.call_args_list[1].kwargs["json"]["openConversationId"],
        )

    def test_dingtalk_plugin_keeps_legacy_webhook_parse_and_session_webhook_fallback(self) -> None:
        webhook_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="channel-dingtalk",
                plugin_type="channel",
                payload={
                    "action": "webhook",
                    "request": {
                        "body_text": json.dumps(
                            {
                                "type": "CALLBACK",
                                "data": json.dumps(
                                    {
                                        "conversationId": "cid-001",
                                        "msgId": "msg-001",
                                        "senderStaffId": "staff-001",
                                        "senderNick": "钉钉用户",
                                        "conversationType": "2",
                                        "sessionWebhook": "https://example.test/dingtalk/session",
                                        "text": {"content": "你好，钉钉"},
                                    },
                                    ensure_ascii=False,
                                ),
                            },
                            ensure_ascii=False,
                        )
                    },
                },
            ),
            root_dir=self.builtin_root,
        )

        self.assertTrue(webhook_result.success)
        event = webhook_result.output["event"]
        self.assertEqual("msg-001", event["external_event_id"])
        self.assertEqual("staff-001", event["external_user_id"])
        self.assertEqual("conversation:cid-001", event["external_conversation_key"])
        self.assertEqual("group", event["normalized_payload"]["chat_type"])
        self.assertEqual(
            "https://example.test/dingtalk/session",
            event["normalized_payload"]["metadata"]["session_webhook"],
        )

        with patch("app.plugins.builtin.channel_dingtalk.channel.httpx.post") as http_post:
            http_post.return_value = _MockHttpResponse({"processQueryKey": "ding-send-001"})
            send_result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="channel-dingtalk",
                    plugin_type="channel",
                    payload={
                        "action": "send",
                        "delivery": {
                            "text": "回复 钉钉",
                            "metadata": {
                                "session_webhook": "https://example.test/dingtalk/session",
                            },
                        },
                    },
                ),
                root_dir=self.builtin_root,
            )

        self.assertTrue(send_result.success)
        self.assertEqual("ding-send-001", send_result.output["provider_message_ref"])
        self.assertEqual("https://example.test/dingtalk/session", http_post.call_args.args[0])

    def test_dingtalk_plugin_probe_accepts_app_key_only_or_full_credentials(self) -> None:
        session_webhook_mode_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="channel-dingtalk",
                plugin_type="channel",
                payload={
                    "action": "probe",
                    "account": {
                        "config": json.dumps(
                            {
                                "app_key": "ding-app-key-only",
                            }
                        )
                    },
                },
            ),
            root_dir=self.builtin_root,
        )

        self.assertTrue(session_webhook_mode_result.success)
        self.assertEqual("ok", session_webhook_mode_result.output["probe_status"])
        self.assertEqual(
            "dingtalk legacy webhook mode does not require active probe",
            session_webhook_mode_result.output["message"],
        )

        with patch("app.plugins.builtin.channel_dingtalk.channel.httpx.post") as http_post:
            http_post.return_value = _MockHttpResponse(
                {
                    "endpoint": "wss://example.test/gateway",
                    "ticket": "ticket-001",
                }
            )
            credential_mode_result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="channel-dingtalk",
                    plugin_type="channel",
                    payload={
                        "action": "probe",
                        "account": {
                            "connection_mode": "polling",
                            "config": json.dumps(
                                {
                                    "app_key": "ding-app-key",
                                    "app_secret": "ding-app-secret",
                                }
                            ),
                        },
                    },
                ),
                root_dir=self.builtin_root,
            )

        self.assertTrue(credential_mode_result.success)
        self.assertEqual("ok", credential_mode_result.output["probe_status"])
        self.assertEqual(
            "dingtalk stream credentials validated",
            credential_mode_result.output["message"],
        )

    def _build_discord_headers(self, private_key: Ed25519PrivateKey, body_text: str) -> dict[str, str]:
        timestamp = "1710400000"
        signature = private_key.sign((timestamp + body_text).encode("utf-8")).hex()
        return {
            "X-Signature-Ed25519": signature,
            "X-Signature-Timestamp": timestamp,
        }

    def _encrypt_feishu_payload(self, payload: dict, encrypt_key: str) -> str:
        plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        key_bytes = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        padded = padder.update(plaintext) + padder.finalize()
        cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(key_bytes[:16]))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(ciphertext).decode("ascii")

if __name__ == "__main__":
    unittest.main()
