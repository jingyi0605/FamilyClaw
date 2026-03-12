"""LLM 任务模块 - 一次定义，到处复用"""

from app.modules.llm_task.invoke import invoke_llm, stream_llm, LlmResult, LlmStreamEvent
from app.modules.llm_task.definitions import get_task, TASKS, LlmTaskDef, register
from app.modules.llm_task.parser import extract_json, parse_to_model

__all__ = [
    "invoke_llm",
    "stream_llm",
    "LlmResult",
    "LlmStreamEvent",
    "get_task",
    "TASKS",
    "LlmTaskDef",
    "register",
    "extract_json",
    "parse_to_model",
]
