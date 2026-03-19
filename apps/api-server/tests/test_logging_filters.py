import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app.core.logging as app_logging
from app.core.logging import NOISY_THIRD_PARTY_LOGGER_LEVELS, UvicornAccessNoiseFilter, setup_logging


class UvicornAccessNoiseFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.filter = UvicornAccessNoiseFilter()

    def test_filters_voice_discovery_report_success_log(self) -> None:
        record = self._build_access_record(
            method="POST",
            path="/api/v1/integrations/discoveries/report",
            status_code=200,
        )

        self.assertFalse(self.filter.filter(record))

    def test_keeps_voice_discovery_error_log(self) -> None:
        record = self._build_access_record(
            method="POST",
            path="/api/v1/integrations/discoveries/report",
            status_code=404,
        )

        self.assertTrue(self.filter.filter(record))

    def test_keeps_non_target_access_log(self) -> None:
        record = self._build_access_record(
            method="GET",
            path="/api/v1/devices",
            status_code=200,
        )

        self.assertTrue(self.filter.filter(record))

    @staticmethod
    def _build_access_record(*, method: str, path: str, status_code: int) -> logging.LogRecord:
        return logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg='%s - "%s %s HTTP/%s" %d',
            args=("127.0.0.1:12345", method, path, "1.1", status_code),
            exc_info=None,
        )


class LoggingSetupTests(unittest.TestCase):
    def tearDown(self) -> None:
        app_logging._clear_logger_handlers(logging.getLogger())
        app_logging._clear_logger_handlers(logging.getLogger(app_logging.CONVERSATION_DEBUG_LOGGER_NAME))

    def test_setup_logging_lowers_http_client_noise(self) -> None:
        setup_logging("INFO")

        for logger_name, logger_level in NOISY_THIRD_PARTY_LOGGER_LEVELS.items():
            self.assertEqual(logger_level, logging.getLogger(logger_name).level)

    def test_channel_logger_name_filter_matches_expected_namespaces(self) -> None:
        self.assertTrue(app_logging.is_channel_logger_name("app.modules.channel.polling_worker"))
        self.assertTrue(app_logging.is_channel_logger_name("app.plugins.builtin.channel_dingtalk.channel"))
        self.assertTrue(app_logging.is_channel_logger_name("app.plugins.builtin.channel_feishu.ws_runtime"))
        self.assertFalse(app_logging.is_channel_logger_name("app.modules.conversation.service"))

    def test_channel_logs_only_write_to_channel_file_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            app_log_file = temp_root / "logs" / "api-server.log"
            channel_log_file = temp_root / "log" / "channel-debug.log"

            with (
                patch.object(app_logging, "LOG_DIR", temp_root / "logs"),
                patch.object(app_logging, "APP_LOG_FILE", app_log_file),
                patch.object(app_logging, "CHANNEL_LOG_DIR", temp_root / "log"),
                patch.object(app_logging, "CHANNEL_DEBUG_LOG_FILE", channel_log_file),
            ):
                try:
                    setup_logging("INFO", channel_debug_enabled=True)
                    logging.getLogger("app.modules.channel.polling_worker").info("channel-message-enabled")
                    logging.getLogger("app.main").info("app-message-enabled")
                    self._flush_root_handlers()

                    self.assertTrue(channel_log_file.exists())
                    self.assertIn("channel-message-enabled", channel_log_file.read_text(encoding="utf-8"))
                    self.assertTrue(app_log_file.exists())
                    app_log_content = app_log_file.read_text(encoding="utf-8")
                    self.assertIn("app-message-enabled", app_log_content)
                    self.assertNotIn("channel-message-enabled", app_log_content)
                finally:
                    self._reset_logging_state()

    def test_channel_logs_are_dropped_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            app_log_file = temp_root / "logs" / "api-server.log"
            channel_log_file = temp_root / "log" / "channel-debug.log"

            with (
                patch.object(app_logging, "LOG_DIR", temp_root / "logs"),
                patch.object(app_logging, "APP_LOG_FILE", app_log_file),
                patch.object(app_logging, "CHANNEL_LOG_DIR", temp_root / "log"),
                patch.object(app_logging, "CHANNEL_DEBUG_LOG_FILE", channel_log_file),
            ):
                try:
                    setup_logging("INFO", channel_debug_enabled=False)
                    logging.getLogger("app.modules.channel.polling_worker").info("channel-message-disabled")
                    logging.getLogger("app.main").info("app-message-disabled")
                    self._flush_root_handlers()

                    self.assertFalse(channel_log_file.exists())
                    self.assertTrue(app_log_file.exists())
                    app_log_content = app_log_file.read_text(encoding="utf-8")
                    self.assertIn("app-message-disabled", app_log_content)
                    self.assertNotIn("channel-message-disabled", app_log_content)
                finally:
                    self._reset_logging_state()

    @staticmethod
    def _flush_root_handlers() -> None:
        for handler in logging.getLogger().handlers:
            handler.flush()

    @staticmethod
    def _reset_logging_state() -> None:
        app_logging._clear_logger_handlers(logging.getLogger())
        app_logging._clear_logger_handlers(logging.getLogger(app_logging.CONVERSATION_DEBUG_LOGGER_NAME))


if __name__ == "__main__":
    unittest.main()
