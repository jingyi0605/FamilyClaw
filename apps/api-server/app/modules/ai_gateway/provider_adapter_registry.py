from __future__ import annotations

from typing import Any


def list_provider_adapters() -> list[dict[str, Any]]:
    return [
        _build_openai_compatible_provider(
            adapter_code="chatgpt",
            display_name="ChatGPT",
            description="适合直接对接 OpenAI 官方接口，也适合兼容 OpenAI Chat Completions 的网关。",
            base_url="https://api.openai.com/v1",
            secret_placeholder="例如：OPENAI_API_KEY",
            model_placeholder="例如：gpt-4o-mini",
            model_default="gpt-4o-mini",
            privacy_options=_public_privacy_options(include_local=True),
        ),
        _build_openai_compatible_provider(
            adapter_code="deepseek",
            display_name="DeepSeek",
            description="DeepSeek 官方兼容接口，适合通用问答，也能承接轻量代码解释。",
            base_url="https://api.deepseek.com/v1",
            secret_placeholder="例如：DEEPSEEK_API_KEY",
            model_placeholder="例如：deepseek-chat",
            model_default="deepseek-chat",
        ),
        _build_openai_compatible_provider(
            adapter_code="qwen",
            display_name="通义千问",
            description="阿里云百炼兼容接口，走 OpenAI 兼容协议，国内接入通常更直接。",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            secret_placeholder="例如：DASHSCOPE_API_KEY",
            model_placeholder="例如：qwen-plus",
            model_default="qwen-plus",
        ),
        _build_openai_compatible_provider(
            adapter_code="glm",
            display_name="GLM",
            description="智谱 GLM 的兼容配置模板，仍然走统一网关模型。",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            secret_placeholder="例如：GLM_API_KEY",
            model_placeholder="例如：glm-4-flash",
            model_default="glm-4-flash",
        ),
        _build_openai_compatible_provider(
            adapter_code="siliconflow",
            display_name="硅基流动",
            description="硅基流动的兼容配置模板，适合托管多家模型，也方便切推理模型。",
            base_url="https://api.siliconflow.cn/v1",
            secret_placeholder="例如：SILICONFLOW_API_KEY",
            model_placeholder="例如：Qwen/Qwen2.5-72B-Instruct",
            model_default="Qwen/Qwen2.5-72B-Instruct",
        ),
        _build_openai_compatible_provider(
            adapter_code="kimi",
            display_name="KIMI",
            description="Moonshot 官方兼容接口，适合长上下文问答。",
            base_url="https://api.moonshot.cn/v1",
            secret_placeholder="例如：KIMI_API_KEY",
            model_placeholder="例如：moonshot-v1-8k",
            model_default="moonshot-v1-8k",
        ),
        _build_openai_compatible_provider(
            adapter_code="minimax",
            display_name="MINIMAX",
            description="MINIMAX 的兼容配置模板，保留最小接入字段，不替你暴露一堆高级参数。",
            base_url="https://api.minimax.chat/v1",
            secret_placeholder="例如：MINIMAX_API_KEY",
            model_placeholder="例如：MiniMax-Text-01",
            model_default="MiniMax-Text-01",
        ),
        _build_native_provider(
            adapter_code="claude",
            display_name="Claude",
            description="Anthropic 官方 Messages API。这个不是 OpenAI 兼容接口，按原生协议发请求。",
            base_url="https://api.anthropic.com/v1",
            secret_placeholder="例如：ANTHROPIC_API_KEY",
            model_placeholder="例如：claude-3-7-sonnet-latest",
            model_default="claude-3-7-sonnet-latest",
            extra_fields=[
                _field("anthropic_version", "Anthropic 版本", "text", required=False, placeholder="例如：2023-06-01", default_value="2023-06-01"),
            ],
        ),
        _build_native_provider(
            adapter_code="gemini",
            display_name="Gemini",
            description="Google Gemini 官方 GenerateContent API。也是原生协议，不走 OpenAI 兼容层。",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            secret_placeholder="例如：GEMINI_API_KEY",
            model_placeholder="例如：gemini-2.0-flash",
            model_default="gemini-2.0-flash",
        ),
        _build_openai_compatible_provider(
            adapter_code="openrouter",
            display_name="OpenRouter",
            description="聚合多家模型的平台。借鉴 OpenClaw 的做法，保留少量 provider 专用字段，由运行时统一补请求头。",
            base_url="https://openrouter.ai/api/v1",
            secret_placeholder="例如：OPENROUTER_API_KEY",
            model_placeholder="例如：openai/gpt-4o-mini",
            model_default="openai/gpt-4o-mini",
            extra_fields=[
                _field("site_url", "站点地址", "text", required=False, placeholder="例如：https://familyclaw.local", help_text="如果填写，运行时会作为 HTTP-Referer 发给 OpenRouter。"),
                _field("app_name", "应用名称", "text", required=False, placeholder="例如：FamilyClaw", help_text="如果填写，运行时会作为 X-Title 发给 OpenRouter。"),
            ],
        ),
        _build_openai_compatible_provider(
            adapter_code="doubao",
            display_name="豆包 Ark",
            description="火山引擎 Ark 官方兼容接口，适合国内主模型接入。",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            secret_placeholder="例如：ARK_API_KEY",
            model_placeholder="例如：doubao-seed-1-6-flash-250615",
            model_default="doubao-seed-1-6-flash-250615",
        ),
        _build_openai_compatible_provider(
            adapter_code="doubao-coding",
            display_name="豆包 Coding",
            description="借鉴 OpenClaw 的成对 provider 思路，把代码/计划型模型单独做成一类提供商，避免和普通问答模型搅在一起。",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            secret_placeholder="例如：ARK_API_KEY",
            model_placeholder="例如：doubao-seed-code-250615",
            model_default="doubao-seed-code-250615",
        ),
        _build_openai_compatible_provider(
            adapter_code="byteplus",
            display_name="BytePlus ModelArk",
            description="BytePlus 国际版兼容接口，适合海外环境统一接入。",
            base_url="https://ark.byteintl.com/api/v3",
            secret_placeholder="例如：BYTEPLUS_API_KEY",
            model_placeholder="例如：doubao-1.5-pro-32k",
            model_default="doubao-1.5-pro-32k",
        ),
        _build_openai_compatible_provider(
            adapter_code="byteplus-coding",
            display_name="BytePlus Coding",
            description="对应 OpenClaw 里的 byteplus-plan 思路，给代码解释、生成、计划类能力留独立模型入口。",
            base_url="https://ark.byteintl.com/api/v3",
            secret_placeholder="例如：BYTEPLUS_API_KEY",
            model_placeholder="例如：doubao-seed-code",
            model_default="doubao-seed-code",
        ),
    ]


def _build_openai_compatible_provider(
    *,
    adapter_code: str,
    display_name: str,
    description: str,
    base_url: str,
    secret_placeholder: str,
    model_placeholder: str,
    model_default: str,
    privacy_options: list[dict[str, str]] | None = None,
    extra_fields: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fields = [
        _field("display_name", "显示名称", "text", required=True, placeholder=f"例如：{display_name} 主模型"),
        _field("provider_code", "供应商编码", "text", required=True, placeholder=f"例如：family-{adapter_code}-main"),
        _field(
            "base_url",
            "Base URL",
            "text",
            required=False,
            placeholder=base_url,
            default_value=base_url,
            help_text="默认给你填常用官方兼容地址；如果你走企业网关或代理，再自己改。",
        ),
        _field("secret_ref", "密钥引用", "secret", required=True, placeholder=secret_placeholder),
        _field("model_name", "模型名", "text", required=True, placeholder=model_placeholder, default_value=model_default),
        _field(
            "privacy_level",
            "隐私等级",
            "select",
            required=True,
            options=privacy_options or _public_privacy_options(),
            default_value="public_cloud",
        ),
    ]
    if extra_fields:
        fields.extend(extra_fields)
    return {
        "adapter_code": adapter_code,
        "display_name": display_name,
        "description": description,
        "transport_type": "openai_compatible",
        "api_family": "openai_chat_completions",
        "default_privacy_level": "public_cloud",
        "default_supported_capabilities": ["qa_generation", "qa_structured_answer"],
        "field_schema": fields,
    }


def _build_native_provider(
    *,
    adapter_code: str,
    display_name: str,
    description: str,
    base_url: str,
    secret_placeholder: str,
    model_placeholder: str,
    model_default: str,
    extra_fields: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fields = [
        _field("display_name", "显示名称", "text", required=True, placeholder=f"例如：{display_name} 主模型"),
        _field("provider_code", "供应商编码", "text", required=True, placeholder=f"例如：family-{adapter_code}-main"),
        _field(
            "base_url",
            "Base URL",
            "text",
            required=False,
            placeholder=base_url,
            default_value=base_url,
            help_text="默认填官方接口地址；如果你走企业代理，再自己改。",
        ),
        _field("secret_ref", "密钥引用", "secret", required=True, placeholder=secret_placeholder),
        _field("model_name", "模型名", "text", required=True, placeholder=model_placeholder, default_value=model_default),
        _field(
            "privacy_level",
            "隐私等级",
            "select",
            required=True,
            options=_public_privacy_options(),
            default_value="public_cloud",
        ),
    ]
    if extra_fields:
        fields.extend(extra_fields)
    return {
        "adapter_code": adapter_code,
        "display_name": display_name,
        "description": description,
        "transport_type": "native_sdk",
        "api_family": "anthropic_messages" if adapter_code == "claude" else "gemini_generate_content",
        "default_privacy_level": "public_cloud",
        "default_supported_capabilities": ["qa_generation", "qa_structured_answer"],
        "field_schema": fields,
    }


def _public_privacy_options(*, include_local: bool = False) -> list[dict[str, str]]:
    options = [
        {"label": "公有云", "value": "public_cloud"},
        {"label": "私有云", "value": "private_cloud"},
    ]
    if include_local:
        options.append({"label": "仅本地", "value": "local_only"})
    return options


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
