import base64
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

from cryptography.hazmat.primitives import padding, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import httpx

from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.service import execute_plugin, list_registered_plugins


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
        self.assertIn("channel-wecom-app", plugin_ids)
        self.assertIn("channel-wecom-bot", plugin_ids)

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

    def test_dingtalk_plugin_normalizes_stream_event_and_sends_via_session_webhook(self) -> None:
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

    def test_wecom_app_plugin_handles_handshake_message_and_send(self) -> None:
        aes_key = self._build_wecom_aes_key()
        timestamp = "1710500000"
        nonce = "nonce-001"
        token = "token-001"
        corp_id = "wxcorp001"

        echostr = self._encrypt_wecom_payload("hello-wecom", aes_key, corp_id)
        handshake_signature = self._build_wecom_signature(token, timestamp, nonce, echostr)
        handshake_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="channel-wecom-app",
                plugin_type="channel",
                payload={
                    "action": "webhook",
                    "account": {
                        "config": json.dumps(
                            {
                                "callback_token": token,
                                "encoding_aes_key": aes_key,
                                "corp_id": corp_id,
                            }
                        )
                    },
                    "request": {
                        "method": "GET",
                        "query_params": {
                            "msg_signature": handshake_signature,
                            "timestamp": timestamp,
                            "nonce": nonce,
                            "echostr": echostr,
                        },
                    },
                },
            ),
            root_dir=self.builtin_root,
        )

        self.assertTrue(handshake_result.success)
        self.assertEqual("hello-wecom", handshake_result.output["http_response"]["body_text"])

        message_xml = (
            "<xml>"
            "<ToUserName><![CDATA[wxcorp001]]></ToUserName>"
            "<FromUserName><![CDATA[user_wecom_001]]></FromUserName>"
            "<CreateTime>1710500000</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<Content><![CDATA[你好，企微]]></Content>"
            "<MsgId>987654321</MsgId>"
            "<AgentID>1000002</AgentID>"
            "</xml>"
        )
        encrypted = self._encrypt_wecom_payload(message_xml, aes_key, corp_id)
        message_signature = self._build_wecom_signature(token, timestamp, nonce, encrypted)
        body_xml = (
            "<xml>"
            f"<Encrypt><![CDATA[{encrypted}]]></Encrypt>"
            f"<MsgSignature><![CDATA[{message_signature}]]></MsgSignature>"
            f"<TimeStamp>{timestamp}</TimeStamp>"
            f"<Nonce><![CDATA[{nonce}]]></Nonce>"
            "</xml>"
        )
        message_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="channel-wecom-app",
                plugin_type="channel",
                payload={
                    "action": "webhook",
                    "account": {
                        "config": json.dumps(
                            {
                                "callback_token": token,
                                "encoding_aes_key": aes_key,
                                "corp_id": corp_id,
                            }
                        )
                    },
                    "request": {
                        "method": "POST",
                        "query_params": {
                            "msg_signature": message_signature,
                            "timestamp": timestamp,
                            "nonce": nonce,
                        },
                        "body_text": body_xml,
                    },
                },
            ),
            root_dir=self.builtin_root,
        )

        self.assertTrue(message_result.success)
        self.assertEqual("success", message_result.output["http_response"]["body_text"])
        event = message_result.output["event"]
        self.assertEqual("987654321", event["external_event_id"])
        self.assertEqual("user_wecom_001", event["external_user_id"])
        self.assertEqual("direct:user_wecom_001", event["external_conversation_key"])

        with patch("app.plugins.builtin.channel_wecom_app.channel.httpx.get") as http_get:
            with patch("app.plugins.builtin.channel_wecom_app.channel.httpx.post") as http_post:
                http_get.return_value = _MockHttpResponse({"access_token": "wecom-token-001"})
                http_post.return_value = _MockHttpResponse({"msgid": "wecom-msg-001"})
                send_result = execute_plugin(
                    PluginExecutionRequest(
                        plugin_id="channel-wecom-app",
                        plugin_type="channel",
                        payload={
                            "action": "send",
                            "account": {
                                "config": json.dumps(
                                    {
                                        "corp_id": corp_id,
                                        "corp_secret": "secret-001",
                                        "agent_id": "1000002",
                                    }
                                )
                            },
                            "delivery": {
                                "external_conversation_key": "direct:user_wecom_001",
                                "text": "回复 企微",
                            },
                        },
                    ),
                    root_dir=self.builtin_root,
                )

        self.assertTrue(send_result.success)
        self.assertEqual("wecom-msg-001", send_result.output["provider_message_ref"])
        self.assertIn("gettoken", http_get.call_args.args[0])
        self.assertIn("message/send", http_post.call_args.args[0])

    def test_wecom_bot_plugin_exposes_send_only_boundary(self) -> None:
        webhook_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="channel-wecom-bot",
                plugin_type="channel",
                payload={"action": "webhook"},
            ),
            root_dir=self.builtin_root,
        )

        self.assertTrue(webhook_result.success)
        self.assertEqual("success", webhook_result.output["http_response"]["body_text"])
        self.assertIn("只支持出站推送", webhook_result.output["message"])

        with patch("app.plugins.builtin.channel_wecom_bot.channel.httpx.post") as http_post:
            http_post.return_value = _MockHttpResponse({"errmsg": "ok"})
            send_result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="channel-wecom-bot",
                    plugin_type="channel",
                    payload={
                        "action": "send",
                        "account": {"config": json.dumps({"key": "bot-key-001"})},
                        "delivery": {"text": "回复 企微机器人"},
                    },
                ),
                root_dir=self.builtin_root,
            )

        self.assertTrue(send_result.success)
        self.assertEqual("ok", send_result.output["provider_message_ref"])
        self.assertIn("webhook/send?key=bot-key-001", http_post.call_args.args[0])

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

    def _build_wecom_aes_key(self) -> str:
        return base64.b64encode(b"0123456789abcdef0123456789abcdef").decode("ascii").rstrip("=")

    def _encrypt_wecom_payload(self, plaintext: str, aes_key: str, corp_id: str) -> str:
        key = base64.b64decode(aes_key + "=")
        random_prefix = b"abcdefghijklmnop"
        xml_bytes = plaintext.encode("utf-8")
        msg_len = len(xml_bytes).to_bytes(4, byteorder="big")
        raw = random_prefix + msg_len + xml_bytes + corp_id.encode("utf-8")
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        padded = padder.update(raw) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(key[:16]))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(ciphertext).decode("ascii")

    def _build_wecom_signature(self, token: str, timestamp: str, nonce: str, encrypted: str) -> str:
        return hashlib.sha1("".join(sorted([token, timestamp, nonce, encrypted])).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    unittest.main()
