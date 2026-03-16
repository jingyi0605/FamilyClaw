import unittest
from unittest.mock import AsyncMock, patch

from app.modules.channel import polling_worker
from app.modules.channel.polling_service import ChannelPollingServiceError
from app.modules.plugin.service import PluginExecutionError


class ChannelPollingWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_plugin_execution_error_is_logged_as_info_without_traceback(self) -> None:
        with patch.object(
            polling_worker,
            "run_blocking_db",
            new=AsyncMock(
                side_effect=[
                    [("household-1", "account-1")],
                    object(),
                ]
            ),
        ) as run_blocking_db_mock, patch.object(
            polling_worker,
            "run_blocking",
            new=AsyncMock(side_effect=[PluginExecutionError("plugin execution failed")]),
        ) as run_blocking_mock, patch.object(polling_worker.logger, "info") as info_mock, patch.object(
            polling_worker.logger,
            "warning",
        ) as warning_mock, patch.object(polling_worker.logger, "exception") as exception_mock:
            result = await polling_worker.run_channel_polling_worker_cycle()

        self.assertFalse(result)
        self.assertEqual(2, run_blocking_db_mock.await_count)
        self.assertEqual(1, run_blocking_mock.await_count)
        info_mock.assert_called_once()
        warning_mock.assert_not_called()
        exception_mock.assert_not_called()

    async def test_business_failure_is_logged_as_warning_without_traceback(self) -> None:
        with patch.object(
            polling_worker,
            "run_blocking_db",
            new=AsyncMock(
                side_effect=[
                    [("household-1", "account-1")],
                    ChannelPollingServiceError("connection mode mismatch"),
                    None,
                ]
            ),
        ) as run_blocking_db_mock, patch.object(
            polling_worker,
            "run_blocking",
            new=AsyncMock(),
        ) as run_blocking_mock, patch.object(polling_worker.logger, "warning") as warning_mock, patch.object(
            polling_worker.logger,
            "exception",
        ) as exception_mock:
            result = await polling_worker.run_channel_polling_worker_cycle()

        self.assertFalse(result)
        self.assertEqual(3, run_blocking_db_mock.await_count)
        self.assertEqual(0, run_blocking_mock.await_count)
        warning_mock.assert_called_once()
        exception_mock.assert_not_called()

    async def test_unexpected_failure_still_logs_exception(self) -> None:
        with patch.object(
            polling_worker,
            "run_blocking_db",
            new=AsyncMock(
                side_effect=[
                    [("household-1", "account-1")],
                    object(),
                    None,
                ]
            ),
        ) as run_blocking_db_mock, patch.object(
            polling_worker,
            "run_blocking",
            new=AsyncMock(side_effect=[RuntimeError("boom")]),
        ) as run_blocking_mock, patch.object(polling_worker.logger, "exception") as exception_mock:
            result = await polling_worker.run_channel_polling_worker_cycle()

        self.assertFalse(result)
        self.assertEqual(3, run_blocking_db_mock.await_count)
        self.assertEqual(1, run_blocking_mock.await_count)
        exception_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
