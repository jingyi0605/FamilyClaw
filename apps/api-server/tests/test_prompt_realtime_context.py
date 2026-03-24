import unittest
from datetime import datetime, timezone

from app.modules.conversation.prompt_realtime_context_service import render_realtime_prompt_context


class PromptRealtimeContextTests(unittest.TestCase):
    def test_render_realtime_prompt_context_includes_local_time_weekday_and_quiet_hours(self) -> None:
        text = render_realtime_prompt_context(
            timezone_name="Asia/Shanghai",
            city="Hangzhou",
            generated_at="2026-03-19T14:00:00Z",
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
            now_utc=datetime(2026, 3, 19, 14, 30, tzinfo=timezone.utc),
        )

        self.assertIn("当前实时信息", text)
        self.assertIn("今天日期：2026-03-19", text)
        self.assertIn("当前本地时间：2026-03-19 22:30", text)
        self.assertIn("星期：星期四", text)
        self.assertIn("今天类型：工作日", text)
        self.assertIn("明天日期：2026-03-20", text)
        self.assertIn("明天星期：星期五", text)
        self.assertIn("明天类型：工作日", text)
        self.assertIn("当前时区：Asia/Shanghai", text)
        self.assertIn("当前时段：晚上", text)
        self.assertIn("家庭所在城市：Hangzhou", text)
        self.assertIn("静默时段：当前在静默时段内（22:00-07:00）", text)
        self.assertIn("上下文快照时间：2026-03-19 22:00", text)

    def test_render_realtime_prompt_context_handles_disabled_quiet_hours(self) -> None:
        text = render_realtime_prompt_context(
            timezone_name="Asia/Shanghai",
            quiet_hours_enabled=False,
            now_utc=datetime(2026, 3, 19, 1, 0, tzinfo=timezone.utc),
        )

        self.assertIn("静默时段：未启用", text)


if __name__ == "__main__":
    unittest.main()
