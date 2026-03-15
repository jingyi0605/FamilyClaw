import logging
import unittest

from app.core.logging import UvicornAccessNoiseFilter


class UvicornAccessNoiseFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.filter = UvicornAccessNoiseFilter()

    def test_filters_voice_discovery_report_success_log(self) -> None:
        record = self._build_access_record(
            method="POST",
            path="/api/v1/devices/voice-terminals/discoveries/report",
            status_code=200,
        )

        self.assertFalse(self.filter.filter(record))

    def test_filters_voice_discovery_binding_success_log(self) -> None:
        record = self._build_access_record(
            method="GET",
            path="/api/v1/devices/voice-terminals/discoveries/open_xiaoai%3ALX06%3A23948/C4QX00829/binding",
            status_code=200,
        )

        self.assertFalse(self.filter.filter(record))

    def test_keeps_voice_discovery_error_log(self) -> None:
        record = self._build_access_record(
            method="GET",
            path="/api/v1/devices/voice-terminals/discoveries/open_xiaoai%3ALX06%3AUNKNOWN/binding",
            status_code=404,
        )

        self.assertTrue(self.filter.filter(record))

    def test_filters_voice_discovery_list_success_log(self) -> None:
        record = self._build_access_record(
            method="GET",
            path="/api/v1/devices/voice-terminals/discoveries",
            status_code=200,
        )

        self.assertFalse(self.filter.filter(record))

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


if __name__ == "__main__":
    unittest.main()
