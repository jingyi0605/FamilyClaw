import asyncio
import logging
import unittest

from app.core.worker_runtime import WorkerRuntime, WorkerRuntimeConfig


class WorkerRuntimeTests(unittest.TestCase):
    def test_run_once_updates_health_snapshot(self) -> None:
        runtime = WorkerRuntime(
            config=WorkerRuntimeConfig(
                worker_name="worker-runtime-test",
                interval_seconds=1,
                tick_timeout_seconds=5,
            ),
            logger=logging.getLogger(__name__),
        )

        async def tick() -> bool:
            return True

        processed = asyncio.run(runtime.run_once(tick))

        snapshot = runtime.get_health_snapshot()
        self.assertTrue(processed)
        self.assertEqual("running", snapshot.state)
        self.assertEqual(0, snapshot.consecutive_failures)
        self.assertIsNotNone(snapshot.last_started_at)
        self.assertIsNotNone(snapshot.last_succeeded_at)
        self.assertFalse(runtime.is_running())

    def test_is_running_reflects_start_and_stop(self) -> None:
        runtime = WorkerRuntime(
            config=WorkerRuntimeConfig(
                worker_name="worker-runtime-lifecycle-test",
                interval_seconds=0.05,
                tick_timeout_seconds=1,
            ),
            logger=logging.getLogger(__name__),
        )

        async def scenario() -> tuple[bool, bool]:
            async def tick() -> bool:
                await asyncio.sleep(0.01)
                return False

            await runtime.start(tick)
            running_before_stop = runtime.is_running()
            await asyncio.sleep(0.02)
            await runtime.stop()
            return running_before_stop, runtime.is_running()

        running_before_stop, running_after_stop = asyncio.run(scenario())

        self.assertTrue(running_before_stop)
        self.assertFalse(running_after_stop)
        self.assertEqual("stopped", runtime.get_health_snapshot().state)


if __name__ == "__main__":
    unittest.main()
