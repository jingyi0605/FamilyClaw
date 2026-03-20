# 需求文档 - AI 供应商彻底插件化迁移

状态：In Progress

## 背景

第一阶段迁移已经把 AI 供应商的品牌资源、配置表单、模型发现和一部分厂商特例迁到了插件侧。

但现在还残留一个大问题：  
核心 `ai_gateway` 仍然掌握协议级执行逻辑。  
只要遇到下面这些情况，开发者还是会下意识去改核心：

- 这个供应商不是标准 `chat/completions`
- 这个模型需要特殊 messages 结构
- 这个供应商的 stream/event 格式不一样
- 这个参数必须按 provider 专属协议编码
- 这个供应商需要独立响应提取逻辑

这些情况不是边缘情况，而是普遍情况。  
所以这次要把边界写死，不再允许核心继续承担供应商协议知识。

## 范围

### In Scope

- 明确宿主与 `ai-provider` 插件在协议执行层的最终边界
- 明确禁止核心继续维护 `api_family -> request builder`
- 设计新的插件 driver 契约
- 拆分 `provider_runtime.py`
- 把 OpenAI / Anthropic / Gemini 的现有协议执行迁成插件 SDK 或插件内实现
- 更新 `004.8.1` 与插件开发文档
- 增加防回归校验，防止以后又把协议逻辑写回核心

### Out of Scope

- 改写 AI Gateway 的业务路由策略
- 改写计费、审计或权限模型
- 重做插件市场
- 继续往核心里加“过渡性兼容分支”

## 核心规则

### 规则 1：核心不得再出现供应商协议枚举驱动的请求拼装分支

验收标准：

1. WHEN 审查核心 `ai_gateway` 代码 THEN System SHALL 不再出现 `api_family -> request builder` 这类协议分支。
2. WHEN 新增一个协议不标准的供应商 THEN System SHALL 不需要修改核心请求拼装逻辑。
3. WHEN 审查 `provider_runtime.py` THEN System SHALL 只能看到宿主通用能力，不能看到供应商协议知识。

### 规则 2：任一 provider 的请求编码、流解析、响应提取必须可在插件内独立实现

验收标准：

1. WHEN 某个供应商需要特殊 messages 结构 THEN System SHALL 允许在插件内独立实现。
2. WHEN 某个供应商需要特殊 stream/event 解析 THEN System SHALL 允许在插件内独立实现。
3. WHEN 某个供应商需要独立响应提取逻辑 THEN System SHALL 允许在插件内独立实现。
4. WHEN 某个模型需要独立参数修正 THEN System SHALL 允许仅修改插件完成。

### 规则 3：新增 provider 如需改核心，只允许改宿主通用能力

验收标准：

1. WHEN 新增 provider 需要修改核心 THEN 修改内容 SHALL 只属于通用 HTTP、SSE、错误收口、超时控制、审计或插件加载能力。
2. WHEN 新增 provider 需要修改核心里的请求体字段、header 规则、messages 结构、stream parser 或 response extractor THEN System SHALL 将其视为违规实现。
3. WHEN 代码评审一个新 provider 接入 THEN 审查者 SHALL 能清楚判断改动是“插件实现”还是“核心越界”。

## 角色与边界

### 宿主必须保留

- 统一调用入口
- provider profile 管理
- 路由、fallback、timeout、retry
- 插件启停和 household 可见性校验
- 密钥解析、权限、审计
- 统一错误语义和统一结果格式
- 通用 HTTP/SSE/JSON 能力

### `ai-provider` 插件必须负责

- 供应商声明
- branding / config_ui / model_discovery
- 协议映射
- 请求编码
- 流式解析
- 响应提取
- 供应商特例
- 模型级参数黑白名单和默认值修正

## 需求

### 需求 1：AI 设置页只能消费插件投影接口

验收标准：

1. WHEN 设置页列出 AI 供应商 THEN System SHALL 只消费 `/provider-adapters` 返回的数据。
2. WHEN 前端需要品牌、表单、模型发现信息 THEN System SHALL 不再直接读取 `PluginRegistryItem.capabilities.ai_provider`。
3. WHEN 前端仍然通过 registry 重建 adapter THEN System SHALL 视为违规实现。

### 需求 2：`ai-provider manifest` 必须继续作为前端契约真相源

验收标准：

1. WHEN 宿主加载 `ai-provider` 插件 THEN System SHALL 从 manifest 解析 `branding`、`config_ui`、`model_discovery`。
2. WHEN 新增供应商品牌资源或配置动作 THEN System SHALL 通过插件 manifest 和插件资源接入，而不是通过核心前端硬编码映射接入。

### 需求 3：新的 provider driver 契约必须允许插件独立处理协议执行

验收标准：

1. WHEN 宿主调用 provider driver THEN System SHALL 只依赖统一 driver 契约。
2. WHEN 插件需要自己构造请求体 THEN 契约 SHALL 允许插件接管请求编码。
3. WHEN 插件需要自己处理 stream/event THEN 契约 SHALL 允许插件接管流解析。
4. WHEN 插件需要自己做响应归一化 THEN 契约 SHALL 允许插件返回统一格式结果。

### 需求 4：核心 `provider_runtime.py` 必须拆分

验收标准：

1. WHEN 拆分完成 THEN 宿主核心 SHALL 不再承担 OpenAI / Anthropic / Gemini 这种供应商协议层逻辑。
2. WHEN 宿主保留运行时能力 THEN 这些能力 SHALL 是无供应商知识的通用 helper。
3. WHEN 新增 provider THEN 开发者 SHALL 优先复用插件 SDK，而不是修改核心 runtime。

### 需求 5：OpenAI / Anthropic / Gemini 现有协议实现必须迁移

验收标准：

1. WHEN 回扫核心目录 THEN System SHALL 不再把这三类协议实现作为核心规则保留。
2. WHEN 插件需要这些协议 THEN System SHALL 通过插件 SDK 或插件内实现复用。
3. WHEN 接入同类新供应商 THEN 开发者 SHALL 能在插件内完成接入，不必修改核心协议代码。

### 需求 6：必须补文档与防回归

验收标准：

1. WHEN 开发者阅读 `004.8.1` THEN 能清楚看懂协议执行边界已经收紧到什么程度。
2. WHEN 开发者阅读插件开发文档 THEN 能知道“哪些 helper 可以复用，哪些协议逻辑绝不能回到核心”。
3. WHEN CI 或本地检查回扫核心目录 THEN 能阻止 `api_family -> request builder`、`registry -> adapter rebuild` 之类回退实现。

## 非功能需求

### 可维护性

1. WHEN 后续接入新供应商 THEN 优先修改插件，不修改核心。
2. WHEN 排查供应商协议问题 THEN 能快速定位是插件实现问题还是宿主通用能力问题。

### 一致性

1. WHEN 任意文档提到 AI 供应商插件化 THEN 都应使用同一套边界说明。
2. WHEN 审查新增 provider 改动 THEN 团队对“核心越界”的判断标准一致。

### 可验证性

1. WHEN 声称边界已经收紧 THEN 必须给出代码回扫、单测或 typecheck 证据。
2. WHEN 回扫核心目录 THEN 能证明核心中没有新的供应商协议拼装逻辑。

## 成功定义

- 核心不再维护 `api_family -> request builder`
- 插件 driver 契约允许插件独立完成请求编码、流解析和响应提取
- `provider_runtime.py` 被拆成宿主通用能力层
- OpenAI / Anthropic / Gemini 现有协议实现迁到插件 SDK 或插件内
- 新增一个协议不标准的供应商时，不需要修改核心供应商协议逻辑
