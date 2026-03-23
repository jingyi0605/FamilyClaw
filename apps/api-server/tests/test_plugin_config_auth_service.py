import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, inspect as sa_inspect
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.plugin.config_auth_service import (
    cleanup_unused_plugin_config_auth_session,
    resolve_plugin_config_callback_base_url,
)
from app.modules.plugin.models import PluginConfigAuthSession


class PluginConfigAuthServiceTests(unittest.TestCase):
    def test_prefers_configured_base_url(self) -> None:
        previous = settings.base_url
        try:
            settings.base_url = " https://public.example.com/app/ "
            result = resolve_plugin_config_callback_base_url("http://127.0.0.1:8000/")
        finally:
            settings.base_url = previous

        self.assertEqual("https://public.example.com/app", result)

    def test_falls_back_to_request_base_url(self) -> None:
        previous = settings.base_url
        try:
            settings.base_url = None
            result = resolve_plugin_config_callback_base_url("http://127.0.0.1:8000/")
        finally:
            settings.base_url = previous

        self.assertEqual("http://127.0.0.1:8000", result)

    def test_cleanup_unused_pending_session_expunge_without_delete(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        db = Session(engine)
        row = PluginConfigAuthSession(
            id="session-1",
            household_id="household-1",
            plugin_id="plugin-1",
            scope_type="channel_account",
            scope_key="draft",
            action_key="start_login",
            status="pending",
            callback_token="callback-token",
            state_token="state-token",
            session_payload_json="{}",
            callback_payload_json=None,
            error_code=None,
            error_message=None,
            expires_at="2026-03-23T00:10:00Z",
            callback_received_at=None,
            finished_at=None,
            created_at="2026-03-23T00:00:00Z",
            updated_at="2026-03-23T00:00:00Z",
        )
        db.add(row)

        with patch("app.modules.plugin.config_auth_service.repository.delete_plugin_config_auth_session") as delete_mock:
            cleanup_unused_plugin_config_auth_session(db, row)

        self.assertTrue(sa_inspect(row).transient)
        delete_mock.assert_not_called()
        db.close()


if __name__ == "__main__":
    unittest.main()
