"""LLM 输出解析"""

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

TAG_NAMES = ("config", "json", "output", "memories")


def extract_tagged_json(text: str) -> tuple[str, str] | None:
    """提取标签包裹的 JSON 文本。"""
    if not text:
        return None

    for tag in TAG_NAMES:
        match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL | re.IGNORECASE)
        if match:
            return tag, match.group(1).strip()
    return None


def strip_structured_output(text: str) -> str:
    """移除给系统解析的结构化块，只保留用户可见文本。"""
    if not text:
        return ""

    cleaned = text
    for tag in TAG_NAMES:
        cleaned = re.sub(
            rf"\n*---\s*\n*<{tag}>[\s\S]*?</{tag}>",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"<{tag}>[\s\S]*?</{tag}>",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"\n*---\s*\n*<{tag}>[\s\S]*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"<{tag}>[\s\S]*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

    separator_match = re.search(r"\n*---\s*$", cleaned)
    if separator_match:
        cleaned = cleaned[:separator_match.start()]

    partial_match = _find_partial_structured_start(cleaned)
    if partial_match is not None:
        cleaned = cleaned[:partial_match]

    return cleaned.strip()


def _find_partial_structured_start(text: str) -> int | None:
    patterns = [
        r"\n\s*---\s*(?:\n\s*)?<(?:config|json|output|memories)?[^>]*$",
        r"<(?:config|json|output|memories)\b[^>]*$",
        r"\n\s*---\s*$",
    ]
    positions: list[int] = []
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            positions.append(match.start())
    if not positions:
        return None
    return min(positions)


def extract_json(text: str) -> dict[str, Any] | list[Any] | None:
    """从文本中提取 JSON

    支持以下格式：
    1. <config>...</config> 或 <json>...</json> 等标签
    2. ```json ... ``` 代码块
    3. 直接的 JSON 文本
    """
    if not text:
        return None

    # 1. 尝试提取标签内容 <config>/<json>/<memories>/<output>
    tagged = extract_tagged_json(text)
    if tagged:
        _, json_text = tagged
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            pass

    # 2. 尝试提取 ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. 尝试直接解析整个文本
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 4. 尝试从脏文本里提取第一个合法 JSON 片段
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[index:])
            return parsed
        except json.JSONDecodeError:
            continue
    return None


def parse_to_model(text: str, model_class: type[T]) -> T | None:
    """解析为 Pydantic 模型

    Args:
        text: LLM 返回的文本
        model_class: 目标 Pydantic 模型类

    Returns:
        解析成功返回模型实例，失败返回 None
    """
    data = extract_json(text)
    if data is None:
        return None

    try:
        # 处理列表数据：如果模型期望 items 字段
        if isinstance(data, list):
            if hasattr(model_class, "model_fields") and "items" in model_class.model_fields:
                return model_class(items=data)
            # 如果模型有 mempries 字段
            if hasattr(model_class, "model_fields") and "memories" in model_class.model_fields:
                return model_class(memories=data)
            return None

        # 处理字典数据
        return model_class(**data)
    except Exception:
        return None
