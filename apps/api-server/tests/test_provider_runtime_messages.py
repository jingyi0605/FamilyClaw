import unittest

from app.modules.ai_gateway.provider_runtime import _build_messages


class ProviderRuntimeMessagesTests(unittest.TestCase):
    def test_qa_generation_prompt_forbids_claiming_execution_from_history(self) -> None:
        messages = _build_messages(
            capability="qa_generation",
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


if __name__ == "__main__":
    unittest.main()
