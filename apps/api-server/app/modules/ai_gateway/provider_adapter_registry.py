from __future__ import annotations

from typing import Any


def list_provider_adapters() -> list[dict[str, Any]]:
    return [
        {
            "adapter_code": "chatgpt",
            "display_name": "ChatGPT",
            "description": "适合直接对接 OpenAI 或兼容 OpenAI Chat Completions 的网关。",
            "transport_type": "openai_compatible",
            "default_privacy_level": "public_cloud",
            "default_supported_capabilities": ["qa_generation", "qa_structured_answer"],
            "field_schema": [
                _field("display_name", "显示名称", "text", required=True, placeholder="例如：家庭主对话模型"),
                _field("provider_code", "供应商编码", "text", required=True, placeholder="例如：family-chatgpt-main"),
                _field(
                    "base_url",
                    "Base URL",
                    "text",
                    required=False,
                    placeholder="https://api.openai.com/v1",
                    default_value="https://api.openai.com/v1",
                    help_text="默认就是 OpenAI 官方兼容地址，通常不用改。",
                ),
                _field("secret_ref", "密钥引用", "secret", required=True, placeholder="例如：OPENAI_API_KEY"),
                _field("model_name", "模型名", "text", required=True, placeholder="例如：gpt-4o-mini"),
                _field(
                    "privacy_level",
                    "隐私等级",
                    "select",
                    required=True,
                    options=[
                        {"label": "公有云", "value": "public_cloud"},
                        {"label": "私有云", "value": "private_cloud"},
                        {"label": "仅本地", "value": "local_only"},
                    ],
                    default_value="public_cloud",
                ),
                _field(
                    "latency_budget_ms",
                    "延迟预算",
                    "number",
                    required=False,
                    placeholder="15000",
                    help_text="单位毫秒，用来约束网关调用超时预算。",
                ),
            ],
        },
        {
            "adapter_code": "glm",
            "display_name": "GLM",
            "description": "智谱 GLM 的兼容配置模板，仍然走统一网关模型。",
            "transport_type": "openai_compatible",
            "default_privacy_level": "public_cloud",
            "default_supported_capabilities": ["qa_generation", "qa_structured_answer"],
            "field_schema": [
                _field("display_name", "显示名称", "text", required=True, placeholder="例如：GLM 家庭问答"),
                _field("provider_code", "供应商编码", "text", required=True, placeholder="例如：family-glm-main"),
                _field("base_url", "Base URL", "text", required=False, placeholder="填写 GLM 官方兼容接口地址", default_value="https://open.bigmodel.cn/api/paas/v4"),
                _field("secret_ref", "密钥引用", "secret", required=True, placeholder="例如：GLM_API_KEY"),
                _field("model_name", "模型名", "text", required=True, placeholder="例如：glm-4-flash"),
                _field(
                    "privacy_level",
                    "隐私等级",
                    "select",
                    required=True,
                    options=[
                        {"label": "公有云", "value": "public_cloud"},
                        {"label": "私有云", "value": "private_cloud"},
                    ],
                    default_value="public_cloud",
                ),
            ],
        },
        {
            "adapter_code": "siliconflow",
            "display_name": "硅基流动",
            "description": "硅基流动的兼容配置模板，主要用于模型托管接口接入。",
            "transport_type": "openai_compatible",
            "default_privacy_level": "public_cloud",
            "default_supported_capabilities": ["qa_generation", "qa_structured_answer"],
            "field_schema": [
                _field("display_name", "显示名称", "text", required=True, placeholder="例如：硅基流动主模型"),
                _field("provider_code", "供应商编码", "text", required=True, placeholder="例如：family-siliconflow-main"),
                _field("base_url", "Base URL", "text", required=False, placeholder="填写硅基流动兼容接口地址", default_value="https://api.siliconflow.cn/v1"),
                _field("secret_ref", "密钥引用", "secret", required=True, placeholder="例如：SILICONFLOW_API_KEY"),
                _field("model_name", "模型名", "text", required=True, placeholder="例如：Qwen/Qwen2.5-72B-Instruct"),
                _field(
                    "privacy_level",
                    "隐私等级",
                    "select",
                    required=True,
                    options=[
                        {"label": "公有云", "value": "public_cloud"},
                        {"label": "私有云", "value": "private_cloud"},
                    ],
                    default_value="public_cloud",
                ),
            ],
        },
        {
            "adapter_code": "kimi",
            "display_name": "KIMI",
            "description": "KIMI 的兼容配置模板，用来接入 Moonshot 系列模型。",
            "transport_type": "openai_compatible",
            "default_privacy_level": "public_cloud",
            "default_supported_capabilities": ["qa_generation", "qa_structured_answer"],
            "field_schema": [
                _field("display_name", "显示名称", "text", required=True, placeholder="例如：KIMI 家庭助手"),
                _field("provider_code", "供应商编码", "text", required=True, placeholder="例如：family-kimi-main"),
                _field("base_url", "Base URL", "text", required=False, placeholder="填写 KIMI 官方兼容接口地址", default_value="https://api.moonshot.cn/v1"),
                _field("secret_ref", "密钥引用", "secret", required=True, placeholder="例如：KIMI_API_KEY"),
                _field("model_name", "模型名", "text", required=True, placeholder="例如：moonshot-v1-8k"),
                _field(
                    "privacy_level",
                    "隐私等级",
                    "select",
                    required=True,
                    options=[
                        {"label": "公有云", "value": "public_cloud"},
                        {"label": "私有云", "value": "private_cloud"},
                    ],
                    default_value="public_cloud",
                ),
            ],
        },
        {
            "adapter_code": "minimax",
            "display_name": "MINIMAX",
            "description": "MINIMAX 的兼容配置模板，保留最小接入字段，不替你暴露一堆高级参数。",
            "transport_type": "openai_compatible",
            "default_privacy_level": "public_cloud",
            "default_supported_capabilities": ["qa_generation", "qa_structured_answer"],
            "field_schema": [
                _field("display_name", "显示名称", "text", required=True, placeholder="例如：MiniMax 主模型"),
                _field("provider_code", "供应商编码", "text", required=True, placeholder="例如：family-minimax-main"),
                _field("base_url", "Base URL", "text", required=False, placeholder="填写 MINIMAX 兼容接口地址", default_value="https://api.minimax.chat/v1"),
                _field("secret_ref", "密钥引用", "secret", required=True, placeholder="例如：MINIMAX_API_KEY"),
                _field("model_name", "模型名", "text", required=True, placeholder="例如：MiniMax-Text-01"),
                _field(
                    "privacy_level",
                    "隐私等级",
                    "select",
                    required=True,
                    options=[
                        {"label": "公有云", "value": "public_cloud"},
                        {"label": "私有云", "value": "private_cloud"},
                    ],
                    default_value="public_cloud",
                ),
            ],
        },
    ]


def _field(
    key: str,
    label: str,
    field_type: str,
    *,
    required: bool,
    placeholder: str | None = None,
    help_text: str | None = None,
    default_value: str | int | bool | None = None,
    options: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "field_type": field_type,
        "required": required,
        "placeholder": placeholder,
        "help_text": help_text,
        "default_value": default_value,
        "options": options or [],
    }
