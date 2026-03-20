# 设计文档 - AI 供应商彻底插件化迁移

状态：In Progress

## 1. 这次设计到底解决什么

这次不是再补几个供应商特例，而是把协议执行层的边界掰正。

如果一个新供应商需要：

- 特殊请求体
- 特殊 messages 结构
- 特殊 header
- 特殊 stream/event
- 特殊响应提取

那这些都必须能在插件里独立完成。  
核心只保留宿主通用能力。

## 2. 当前问题

当前链路大致是这样：

1. 宿主根据 provider profile 找到 `ai-provider` 插件
2. 宿主通过 `provider_driver.py` 加载插件 driver
3. 插件 driver 目前只能在请求前“改一层参数”
4. 真正的请求拼装、流解析、响应提取仍主要落在 `provider_runtime.py`

这会带来三个问题：

1. 新增协议不标准的供应商时，还是容易回头改核心
2. 核心会继续积累 `api_family` 分支
3. 所谓“插件化”实际上只完成了配置和参数补丁，没有完成协议执行下沉

## 3. 目标结构

迁移完成后的结构固定为两层。

### 3.1 宿主层

位置：

- `apps/api-server/app/modules/ai_gateway/*`
- `apps/api-server/app/modules/plugin/*`

只负责：

- 统一调用入口
- provider profile 管理
- 路由、fallback、timeout、retry
- 权限、审计、密钥解析、插件状态校验
- 通用 HTTP/SSE/JSON 工具能力
- 统一错误语义与统一结果格式

不再负责：

- OpenAI 协议请求体
- Anthropic 协议请求体
- Gemini 协议请求体
- 供应商专属 stream 解析
- 供应商专属响应提取

### 3.2 插件层

位置：

- `apps/api-server/app/plugins/builtin/ai_provider_*/`
- 以及后续 `official` / `third_party` 的 `ai-provider` 插件

负责：

- 供应商声明
- branding / config_ui / model_discovery
- 请求编码
- 流式解析
- 响应提取
- 模型发现
- 供应商特例
- 模型级参数修正

## 4. 新的 driver 契约

### 4.1 设计原则

宿主和插件之间只保留统一契约，不保留供应商协议知识。

宿主传给插件的是“统一调用意图”，不是某个具体供应商请求体。  
插件返回给宿主的是“统一归一化结果”，不是原始供应商响应。

### 4.2 建议的输入输出

插件输入至少应包含：

- `capability`
- `provider_profile`
- `payload`
- `timeout_ms`
- `honor_timeout_override`
- 宿主统一注入的 trace / request context

插件输出至少应包含：

- `normalized_output`
- `finish_reason`
- `usage`
- `raw_response_ref`
- `error_code`
- `latency_ms`

流式调用时，插件自己负责把供应商原始事件流解析成宿主认可的 chunk 序列。

### 4.3 宿主通用 helper 的定位

可以保留共享 helper，但它们必须是“插件 SDK”，不是“核心协议实现”。

允许存在：

- `plugins/_sdk/http.py`
- `plugins/_sdk/sse.py`
- `plugins/_sdk/json_stream.py`
- `plugins/_sdk/openai_compat.py`
- `plugins/_sdk/anthropic_compat.py`
- `plugins/_sdk/gemini_compat.py`

这些 helper 只做复用，不做强绑定：

- 它们是插件可选工具箱
- 不是核心必须依赖的协议分支
- 不允许宿主根据 `api_family` 自动切到这些 helper

## 5. `provider_runtime.py` 的拆法

### 5.1 先拆出宿主通用能力

应该保留为通用能力的部分：

- 超时处理
- 通用 HTTP 请求封装
- 通用 SSE 读取器
- 通用 JSON 解析工具
- 通用错误包装
- 通用日志记录

### 5.2 迁出协议层实现

必须迁出的部分：

- `api_family == openai_chat_completions` 的请求拼装
- `api_family == anthropic_messages` 的请求拼装
- `api_family == gemini_generate_content` 的请求拼装
- 对应 stream parser
- 对应 response extractor

### 5.3 拆分后的形态

推荐形态：

1. 宿主层保留一个纯通用 runtime helper 包
2. 插件层通过 driver 或插件 SDK 调用这些 helper
3. 内置 OpenAI / Anthropic / Gemini 供应商插件各自实现协议适配

## 6. 前端边界补充

AI 设置页必须继续收口成一条数据源：

- 供应商品牌
- 供应商表单
- 模型发现

统一只消费 `/provider-adapters`。  
前端不允许再从 `PluginRegistryItem.capabilities.ai_provider` 重建 adapter。

`plugin registry` 在 AI 设置页里最多只允许承担通用插件信息展示，比如：

- 插件版本
- 更新状态
- 启停状态

它不能再承载供应商契约本身。

## 7. 完成标准

满足下面三个条件时，才算真的完成：

1. 新增一个非标准供应商时，只需要新增或修改插件，不需要改核心协议代码。
2. 核心目录中不再出现 `api_family -> request builder / stream parser / response extractor`。
3. 插件开发文档能明确告诉开发者：哪些能力属于宿主，哪些协议逻辑必须留在插件。
