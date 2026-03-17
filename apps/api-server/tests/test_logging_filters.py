import logging
import unittest

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
    def test_setup_logging_lowers_http_client_noise(self) -> None:
        setup_logging("INFO")

        for logger_name, logger_level in NOISY_THIRD_PARTY_LOGGER_LEVELS.items():
            self.assertEqual(logger_level, logging.getLogger(logger_name).level)


if __name__ == "__main__":
    unittest.main()
