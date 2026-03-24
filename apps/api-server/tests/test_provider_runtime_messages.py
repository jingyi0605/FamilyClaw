import unittest

from app.plugins._sdk.ai_provider_messages import build_messages


class ProviderRuntimeMessagesTests(unittest.TestCase):
    def test_qa_generation_prompt_forbids_claiming_execution_from_history(self) -> None:
        messages = build_messages(
            capability="text",
            payload={
                "question": "帮我关掉",
                "answer_draft": "当前没有执行结果，需要先确认设备目标。",
                "device_context_summary_text": "最近设备上下文摘要：\n- 最近一次设备查询：设备=书房灯；device_id=device-1；来源=device_state",
                "conversation_history": [
                    {"role": "user", "content": "打开书房灯"},
                    {"role": "assistant", "content": "已为你打开书房灯。"},
                ],
            },
        )

        self.assertIn("不能说“已为你打开/关闭/执行”", messages[0]["content"])
        self.assertIn("不能说“我这就帮你打开/关闭/执行”", messages[0]["content"])
        self.assertIn("最近设备上下文只用于理解用户这轮可能在指哪个设备", messages[0]["content"])
        self.assertIn("书房灯", messages[0]["content"])

    def test_qa_generation_prompt_includes_realtime_context(self) -> None:
        messages = build_messages(
            capability="text",
            payload={
                "question": "今天要不要早点休息",
                "answer_draft": "可以提醒用户今天已经比较晚了。",
                "realtime_context_text": (
                    "当前实时信息：\n"
                    "- 今天日期：2026-03-19\n"
                    "- 当前本地时间：2026-03-19 22:30\n"
                    "- 星期：星期四\n"
                    "- 今天类型：工作日\n"
                    "- 明天日期：2026-03-20\n"
                    "- 明天星期：星期五\n"
                    "- 明天类型：工作日\n"
                    "- 当前时区：Asia/Shanghai"
                ),
            },
        )

        self.assertIn("下面这段实时上下文只用于理解“今天”“明天”“现在”“今晚”“工作日”“周末”这类相对时间或周期表达", messages[0]["content"])
        self.assertIn("今天日期：2026-03-19", messages[0]["content"])
        self.assertIn("当前本地时间：2026-03-19 22:30", messages[0]["content"])
        self.assertIn("明天星期：星期五", messages[0]["content"])
        self.assertIn("明天类型：工作日", messages[0]["content"])
        self.assertIn("当前时区：Asia/Shanghai", messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
