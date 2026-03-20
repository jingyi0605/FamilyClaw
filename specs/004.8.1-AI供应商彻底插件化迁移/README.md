# Spec 004.8.1 - AI 供应商彻底插件化迁移

状态：In Progress

## 这份 Spec 现在负责什么

这份 Spec 负责定义 AI 供应商插件化的最终边界。

从现在开始，凡是涉及下面这些问题，都以 `004.8.1` 为准：

- 宿主和 `ai-provider` 插件的职责边界
- `ai-provider manifest` 的正式契约
- AI 设置页可以依赖哪些接口，不能依赖哪些核心结构
- LLM 请求执行逻辑到底应该留在宿主还是下沉到插件
- 后续新增供应商时，什么情况下算“只改插件”，什么情况下算“架构违规”

## 当前判断

第一阶段迁移已经完成了这些事情：

- builtin AI 供应商已经落成真实插件目录
- 核心不再维护 AI 供应商注册表真相源
- 前端品牌资源、配置表单、模型发现已经开始按插件契约渲染
- 现有一部分厂商特例已经迁入插件 driver

但这还不算彻底完成。

现在最关键的剩余问题是：  
核心 `ai_gateway` 里仍然保留了按 `api_family` 驱动的请求拼装、流式解析和响应提取逻辑。  
这会导致新增一个“协议不标准”的供应商时，还是得回头改核心。

## 从这一版开始写死的三条红线

1. 核心不得再出现任何供应商协议枚举驱动的请求拼装分支。
2. 任一 provider 的请求编码、流解析、响应提取必须可在插件内独立实现。
3. 新增 provider 如需改核心，只允许改“宿主通用能力”，不允许改“供应商协议逻辑”。

这三条不是建议，是本 spec 的正式边界。

## 当前正式边界

宿主保留：

- 统一 AI Gateway 入口
- provider profile 管理
- 路由、fallback、timeout、retry、状态收口
- 权限、审计、密钥解析、插件启停校验
- 通用 HTTP/SSE/JSON 调用能力
- 统一错误语义、统一调用结果

`ai-provider` 插件负责：

- 供应商声明
- 品牌资源和说明文案
- 配置字段 schema
- `config_ui`
- `model_discovery`
- provider driver entrypoint
- 请求编码
- 流式解析
- 响应提取
- 供应商特例
- 模型级参数修正

一句话说明：

宿主负责平台规则。  
供应商怎么发请求、怎么编码、怎么解析、有哪些奇怪参数，全部由插件负责。

## 当前明确不允许什么

- 不允许核心继续维护 `api_family -> request builder`
- 不允许核心继续维护 `api_family -> stream parser`
- 不允许核心继续维护 `api_family -> response extractor`
- 不允许在核心前端继续拼装 `PluginRegistryItem.capabilities.ai_provider` 来重建 adapter
- 不允许新增供应商时去改核心里的 messages 结构、请求体字段名、供应商专属 header 或 SSE 事件格式
- 不允许把供应商 Logo、说明文案、模型发现行为、表单动作塞回核心目录

## 下一阶段的真正目标

下一阶段不是“再补几个特例”，而是把协议层边界彻底掰正：

- 把 `provider_runtime.py` 从“供应商协议执行层”拆成“宿主通用能力层”
- 设计新的插件 driver 契约，让插件自己接管请求编码、流解析、响应提取
- 把当前 OpenAI / Anthropic / Gemini 这三类协议实现迁成插件 SDK 或插件内实现
- 让新增一个非标准供应商时，只改插件，不改核心

## 阅读顺序

1. `requirements.md`
2. `design.md`
3. `tasks.md`
4. `docs/开发者文档/插件开发/zh-CN/05-插件对接方式说明.md`

## 本轮落地结果（2026-03-20）

这一轮已经把协议边界真正落成代码：

- 核心 `provider_runtime.py` 不再保留 OpenAI / Anthropic / Gemini 协议分支。
- 新增 `app/plugins/_sdk/ai_provider_messages.py` 与 `app/plugins/_sdk/ai_provider_drivers.py`，协议编码、流解析、响应提取统一下沉到插件层 SDK。
- builtin provider 的 manifest 全部改为指向各自插件目录内的 `driver.build_driver`。
- `family_qa` 与 `llm_task` 的流式调用改为先解 provider driver，再调用 `driver.stream(...)`。
- 新增后端回归测试，明确禁止核心重新出现协议 builder、协议分支和 manifest 回指核心。
