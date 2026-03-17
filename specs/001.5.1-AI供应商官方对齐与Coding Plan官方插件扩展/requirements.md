# 需求文档 - AI供应商官方对齐与 Coding Plan 官方插件扩展

状态：Draft

## 简介

这次要解决的是已经落到代码里的两个硬伤。

第一，当前 14 家内置供应商并不是“都没接上”，真正的问题是“有些已经接上了，但接法不完整，或者默认配置和官方文档不一致”。这比空实现更恶心，因为它会让人误以为已经可用。

第二，业务要增加百炼、Kimi、GLM 三家 Coding Plan 供应商。项目现在明明已经有正式的 `ai-provider` 插件类型，再把这 3 家继续塞进 builtin 注册表，就是故意制造第二套体系。

这次要做的事很朴素：

- 修掉报告里已经确认的问题；
- 补齐该有的流式能力；
- 新增 3 家 Coding Plan，但必须走官方插件；
- 不打坏已经存在的 provider profile 和家庭配置。

## 术语表

- **System**：FamilyClaw 的 AI Gateway、插件系统和供应商配置链路。
- **内置供应商**：当前在 `provider_adapter_registry.py` 和虚拟 ai-provider manifest 里暴露出来的 14 家供应商。
- **官方插件供应商**：通过 `manifest.json`、`plugin_mounts`、`source_type=official` 接入的 `ai-provider` 插件。
- **Coding Plan 供应商**：提供面向编码/规划场景专用端点和专用鉴权的供应商，不等于普通通用模型供应商。
- **LLM 通讯逻辑**：包含协议族、请求端点、鉴权方式、默认 `base_url`、流式能力和请求 payload 约束。

## 范围说明

### In Scope

- 修正现有 14 家内置供应商里已经确认的官方对齐问题。
- 补齐 `claude` 和 `gemini` 的流式通讯逻辑。
- 新增百炼、Kimi、GLM 三家 Coding Plan 供应商。
- 这 3 家新增供应商必须按 `ai-provider` 官方插件方式实现。
- 新增插件的默认字段、文案和表单结构必须以官方文档与 OpenClaw 对照结果为准。
- 保证新增插件服从现有插件启用、禁用、挂载和家庭可见性规则。

### Out of Scope

- 把现有 14 家内置供应商全部迁成插件。
- 重做 AI Gateway 的模型路由、计费、日志和缓存架构。
- 新增这 3 家以外的其他供应商。
- 为了这次需求去破坏现有 provider profile 的读写兼容。

## 需求

### 需求 1：现有内置供应商必须按报告先修对

**用户故事：** 作为维护 AI 能力的开发者，我希望报告里已经确认的错误优先被修正，这样系统默认配置才不会继续误导后续接入和调试。

#### 验收标准

1. WHEN 开发者按本次 Spec 实施修复 THEN System SHALL 优先处理报告中标为 P0 和 P1 的内置供应商问题，而不是先去扩无关范围。
2. WHEN 修复 `minimax`、`doubao-coding`、`byteplus`、`byteplus-coding` THEN System SHALL 让默认 `base_url`、协议族、端点拼接方式和官方文档保持一致。
3. WHEN 某家内置供应商存在官方文档与当前接法不一致的情况 THEN System SHALL 在代码和文档里明确修正，不允许继续保留“看起来能跑”的错默认值。

### 需求 2：现有供应商的流式能力必须补齐

**用户故事：** 作为调用流式输出能力的用户，我希望被标记为支持的供应商真正能流式返回，而不是只有非流式勉强可用。

#### 验收标准

1. WHEN `claude` 被用于流式 LLM 调用 THEN System SHALL 走真实的 Anthropic 流式通讯逻辑，而不是缺实现或回退到非流式。
2. WHEN `gemini` 被用于流式 LLM 调用 THEN System SHALL 走真实的 Gemini 流式通讯逻辑，而不是缺实现或回退到非流式。
3. WHEN 流式调用失败 THEN System SHALL 给出和对应协议族一致的错误路径，不伪装成空实现成功。

### 需求 3：新增 3 家 Coding Plan 供应商时必须走官方插件

**用户故事：** 作为后续要继续扩供应商的人，我希望新增供应商沿着现有插件系统接入，而不是在 builtin provider 里再堆一套特殊逻辑。

#### 验收标准

1. WHEN 新增百炼 Coding Plan、Kimi Coding Plan、GLM Coding Plan THEN System SHALL 为它们分别提供独立的 `manifest.json`，并声明 `types=["ai-provider"]`。
2. WHEN 这 3 家供应商接入系统 THEN System SHALL 通过官方插件挂载和家庭可见性链路暴露出来，而不是新增到 `provider_adapter_registry.py` 的 builtin 列表里。
3. WHEN 家庭未安装或未启用对应官方插件 THEN System SHALL 阻止创建或使用对应 provider profile。

### 需求 4：新增 Coding Plan 插件的默认配置必须贴合官方文档

**用户故事：** 作为配置供应商的人，我希望表单里给出的默认地址、说明和字段就是官方要求的，不用再猜这是哪家兼容哪家。

#### 验收标准

1. WHEN 创建百炼 Coding Plan 插件配置 THEN System SHALL 提供符合官方文档的中国站和国际站 `base_url` 选项。
2. WHEN 创建 Kimi Coding Plan 插件配置 THEN System SHALL 使用独立端点和独立 API Key 的配置说明，并按 Anthropic Messages 协议接入。
3. WHEN 创建 GLM Coding Plan 插件配置 THEN System SHALL 提供符合官方文档的中国站和国际站 `base_url` 选项，并按 OpenAI 兼容协议接入。

### 需求 5：插件启停和执行校验必须统一

**用户故事：** 作为维护插件系统的人，我希望 AI 供应商插件也服从统一启停规则，这样不会在供应商这块再绕开系统边界。

#### 验收标准

1. WHEN 系统列出某个家庭可用的 AI 供应商插件 THEN System SHALL 只返回该家庭已挂载且当前可用的 `ai-provider` 官方插件。
2. WHEN 创建、更新或执行某个官方插件供应商配置 THEN System SHALL 通过现有 `require_available_household_plugin(..., plugin_type=\"ai-provider\")` 一类校验收口。
3. WHEN 插件被禁用、卸载或挂载失效 THEN System SHALL 阻止继续使用对应供应商，而不是让旧配置悄悄绕过插件状态。

### 需求 6：旧配置不能被打坏

**用户故事：** 作为已经有 AI 配置的家庭管理员，我希望这次改造不会让我现有的 provider profile 全部失效。

#### 验收标准

1. WHEN 系统加载历史内置供应商的 provider profile THEN System SHALL 继续允许读取、展示和更新这些配置。
2. WHEN 本次新增 3 家官方插件供应商上线 THEN System SHALL 不要求用户迁移现有内置供应商配置才能继续使用系统。
3. WHEN 某个旧 provider profile 不属于本次新增官方插件 THEN System SHALL 保持原有兼容逻辑，不因为插件化改造被误判为非法。

## 非功能需求

### 非功能需求 1：可维护性

1. WHEN 后续继续新增 Coding Plan 类供应商 THEN System SHALL 允许沿用同一套 `ai-provider` 官方插件模式，而不是继续扩大 builtin provider 特判。
2. WHEN 开发者阅读这次实现 THEN System SHALL 能从 Spec、插件 manifest 和 OpenClaw/官方文档对照里直接看懂为什么这样配。

### 非功能需求 2：可靠性

1. WHEN 某个官方 `ai-provider` 插件 manifest 写错 THEN System SHALL 按统一插件规则处理，不能把整个查询链路炸成 500。
2. WHEN 外部供应商接口异常 THEN System SHALL 返回真实错误，不伪装成“已成功接入”。

### 非功能需求 3：可验证性

1. WHEN 本次改造完成 THEN System SHALL 至少具备覆盖 builtin 修复、流式能力和 3 家官方插件的后端测试。
2. WHEN 需要人工验收 THEN System SHALL 提供清楚的插件安装、启用、创建配置和实际调用验证步骤。

## 成功定义

- 报告里的 P0 / P1 问题被落到明确代码修复，不再只是文档发现。
- `claude` 和 `gemini` 的流式调用具备真实实现。
- 百炼、Kimi、GLM 三家 Coding Plan 以 `ai-provider` 官方插件形式接入。
- 这 3 家不再写进 builtin provider 注册表。
- 新插件遵守统一插件启停和家庭可见性规则。
- 旧的 provider profile 仍然可读可用。
