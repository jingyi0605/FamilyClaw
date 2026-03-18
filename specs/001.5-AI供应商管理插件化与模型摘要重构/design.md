# 设计文档 - AI供应商管理插件化与模型摘要重构

状态：Historical

## 2026-03-18 历史说明

这份设计文档只记录第一轮页面插件化和动态表单改造的历史设计。

如果你现在要设计：

- 宿主与 `ai-provider` 插件的最终边界
- `provider driver contract`
- `provider_adapter_registry.py` / `provider_runtime.py` 的迁移路径

请改看：

- `specs/004.8.1-AI供应商彻底插件化迁移/design.md`

## 1. 概述

### 1.1 目标

- 把 AI 供应商管理页从“平铺配置中心”改成“列表 + 摘要 + 编辑弹窗”。
- 用统一的供应商插件描述驱动前后端，而不是继续堆供应商特例。
- 明确供应商支持的模型类型和 `llm_workflow`，减少“这个模型到底能干什么”的猜测。
- 在不破坏旧 provider profile 数据的前提下完成改造。

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4

### 1.3 技术约束

- 后端继续使用现有 `AiProviderProfile`、`AiCapabilityRoute` 存储，不新增数据库结构。
- 前端改造落在 `apps/user-app`，不改 `user-web`。
- 页面文案必须走 i18n，不在组件里直接硬编码用户可见文字。
- 不启动新的插件市场或通用插件生命周期，只做 AI provider 专用插件化。

## 2. 架构

### 2.1 系统结构

这次改造围着一条简单数据链路：

1. 后端 provider adapter 注册表负责产出统一的供应商插件描述。
2. `provider_config_service` 把这些描述转换成 API 返回结构。
3. 前端设置页加载 adapter 列表、provider profile 列表、route 列表。
4. 主页面只展示列表和摘要。
5. 编辑弹窗根据选中的 adapter 动态渲染表单，并复用现有 create/update provider API。

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `provider_adapter_registry.py` | 维护内置供应商并加载外部 JSON 插件 | 内置条目、`provider_plugins/*.json` | 统一 adapter 元数据列表 |
| `provider_config_service.py` | 把 adapter 元数据转成 schema 响应 | registry 返回值 | `AiProviderAdapterRead[]` |
| `schemas.py` | 定义插件元数据字段和前端可见能力 | adapter 原始字典 | 稳定 API 契约 |
| `AiProviderConfigPanel.tsx` | 渲染列表、摘要、加载状态和删除流程 | adapters、providers、routes | 设置页主视图 |
| `AiProviderEditorDialog.tsx` | 负责供应商选择和动态表单 | 当前 adapter、form state | create/update 提交 |
| `aiProviderCatalog.ts` | 负责字段、本地化标签、模型类型和 workflow 文案映射 | adapter schema | 前端展示文案 |

### 2.3 关键流程

#### 2.3.1 页面加载流程

1. 前端并行请求 adapter 列表、household provider 列表、capability route 列表。
2. 前端把 adapter 数据补齐默认值，例如 `plugin_id`、`plugin_name`、`supported_model_types`、`llm_workflow`。
3. 页面渲染顶部统计、供应商列表和当前选中供应商的摘要卡片。

#### 2.3.2 新增模型流程

1. 用户点击新增按钮。
2. 弹窗先展示供应商插件选择区。
3. 用户选中某个 adapter 后，前端基于其 `field_schema` 初始化表单状态。
4. 弹窗展示该 adapter 的 `llm_workflow`、支持类型和动态字段。
5. 用户提交后，前端用现有 `buildCreateProviderPayload` 生成 payload 并调用创建接口。
6. 创建成功后刷新 provider 列表和 route 摘要。

#### 2.3.3 编辑模型流程

1. 用户在列表中选择已有供应商后点击编辑。
2. 前端读取该 provider 对应的 adapter 元数据，把旧配置转换成动态表单状态。
3. 编辑时保留 provider 与 adapter 的绑定关系，不允许随意切换 adapter，避免把旧数据改坏。
4. 提交后刷新列表和摘要。

## 3. 组件和接口

### 3.1 核心组件

- `AiProviderConfigPanel`
  - 负责页面主布局、统计、卡片列表、摘要展示和删除入口。
- `AiProviderEditorDialog`
  - 负责新增/编辑弹窗、供应商插件选择和动态字段渲染。
- `aiProviderCatalog`
  - 负责模型类型、workflow、字段标签、帮助文案的本地化映射。

### 3.2 数据结构

#### 3.2.1 `AiProviderAdapterRead`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `plugin_id` | `string` | 是 | 插件唯一标识 | 适配器级唯一 |
| `plugin_name` | `string` | 是 | 插件名称 | 前端直接展示 |
| `adapter_code` | `string` | 是 | 供应商适配器编码 | 创建/编辑时绑定 |
| `display_name` | `string` | 是 | 默认显示名称 | 可用于默认文案 |
| `description` | `string` | 是 | 供应商说明 | 摘要和选择器使用 |
| `transport_type` | `string` | 是 | 调用传输类型 | 复用旧值 |
| `api_family` | `string` | 是 | 调用家族 | 复用旧值 |
| `default_privacy_level` | `string` | 是 | 默认隐私级别 | 复用旧值 |
| `default_supported_capabilities` | `string[]` | 是 | 默认能力路由 | 可为空 |
| `supported_model_types` | `string[]` | 是 | 支持类型 | 仅允许 `llm/embedding/vision/speech/image` |
| `llm_workflow` | `string` | 是 | LLM 工作流标识 | 默认回退到 `api_family` |
| `field_schema` | `AiProviderFieldRead[]` | 是 | 动态表单字段定义 | 至少支持显示基础字段 |

#### 3.2.2 `AiProviderFieldRead`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `key` | `string` | 是 | 字段键名 | 前后端约定 |
| `label` | `string` | 是 | 默认标签 | 可被前端本地化覆盖 |
| `field_type` | `string` | 是 | 字段类型 | `text/secret/number/select/boolean` |
| `required` | `boolean` | 是 | 是否必填 | 动态表单校验使用 |
| `placeholder` | `string?` | 否 | 占位提示 | 可为空 |
| `help_text` | `string?` | 否 | 辅助说明 | 可为空 |
| `default_value` | `string|number|boolean|null` | 否 | 默认值 | 初始化表单使用 |
| `options` | `AiProviderFieldOptionRead[]` | 是 | 选择项 | 仅 `select` 使用 |

### 3.3 接口契约

#### 3.3.1 列出供应商插件

- 类型：HTTP
- 路径或标识：现有 settings API 的 provider adapter 列表接口
- 输入：无业务新增参数
- 输出：`AiProviderAdapterRead[]`
- 校验：
  - 内置条目必须有完整字段
  - JSON 插件缺字段时直接报错，不输出半残数据
- 错误：
  - 插件 JSON 非法
  - 字段结构不合法

#### 3.3.2 创建/更新 provider profile

- 类型：HTTP
- 路径或标识：现有 household AI provider create/update 接口
- 输入：由前端动态表单生成的 payload
- 输出：provider profile
- 校验：
  - `provider_code`、`display_name`、`model_name` 等基础字段仍按原规则校验
  - 动态字段进入 `extra_config`
- 错误：
  - adapter 未选择
  - 必填字段缺失
  - 后端 schema 校验失败

## 4. 数据与状态模型

### 4.1 数据关系

- adapter 元数据描述“这个供应商长什么样”。
- provider profile 描述“这个家庭实际配了哪个模型”。
- capability route 描述“哪些能力当前路由到哪个 provider profile”。

三者关系很清楚：

1. adapter 是模板。
2. provider profile 是模板实例。
3. route 绑定具体实例，而不是绑定模板。

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `adapter_selected` | 已选定供应商插件 | 用户在新增弹窗选择 adapter | 用户关闭弹窗或提交成功 |
| `editing` | 正在填写动态表单 | 选中 adapter 或进入编辑模式 | 提交成功或取消 |
| `saved` | provider 已创建或更新 | 后端接口返回成功 | 页面重新加载后回到稳定展示态 |

## 5. 错误处理

### 5.1 错误类型

- 插件描述错误：JSON 文件缺字段或字段类型错误。
- 表单输入错误：未选 adapter、缺少必填项、字段格式不合法。
- 外部环境错误：真实登录不可用、真实 OpenAI key 无效，导致联调或依赖真实调用的测试失败。

### 5.2 处理策略

1. 插件描述错误
   - 后端在加载阶段直接抛错，避免把坏插件静默混进列表。
2. 表单输入错误
   - 前端在提交前禁用按钮或显示错误，不提交半成品。
3. 外部环境错误
   - 不把这类失败伪装成本次结构改造 bug，单独记录为联调阻塞项。

## 6. 正确性约束

### 6.1 旧配置必须可继续读取

对于任何已经存在的 provider profile，系统都必须还能在新页面中渲染列表、摘要和编辑弹窗，而不是要求用户删掉重建。

**验证需求：** `requirements.md` 需求 2

### 6.2 新增流程必须先选供应商再填表

对于任何新建 provider 的操作，系统都必须先明确 adapter，再按该 adapter 的字段 schema 渲染表单，不能重新退回“所有字段混在一起”的方案。

**验证需求：** `requirements.md` 需求 3

### 6.3 主页面不再承担完整编辑职责

对于任何主页面展示场景，系统都只负责列表和摘要，完整编辑必须进入弹窗或后续专门界面。

**验证需求：** `requirements.md` 需求 1

## 7. 测试策略

### 7.1 单元测试

- 后端验证 provider adapter registry 能输出核心内置供应商。
- 后端验证插件元数据字段能被 schema 正常序列化。

### 7.2 集成测试

- 前端类型检查覆盖 `AiProviderConfigPanel`、`AiProviderEditorDialog`、settings type 扩展和 i18n 接入。
- 后端定向测试覆盖 provider registry 到 service 的主链路。

### 7.3 人工验收

- 打开 AI 供应商管理页，确认主页面只剩列表和摘要。
- 点击新增，确认先出现供应商插件选择。
- 选择不同供应商，确认动态字段、支持类型和 `llm_workflow` 随插件变化。
- 保存后返回列表，确认摘要区能正确回显插件、模型名、支持类型和路由能力。

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` 2.3.1、3.1、6.3 | 页面人工验收 |
| `requirements.md` 需求 2 | `design.md` 2.2、3.2、3.3、6.1 | 后端定向测试 |
| `requirements.md` 需求 3 | `design.md` 2.3.2、2.3.3、6.2 | 页面人工验收 |
| `requirements.md` 需求 4 | `design.md` 3.1、3.2 | 类型检查 + 页面人工验收 |

## 8. 风险与待确认项

### 8.1 风险

- `pageMessages.zh-CN.ts` 和全局样式文件本来就很脏，后续补改时很容易把 diff 扩大。
- 如果后续真要把 AI provider 纳入通用插件系统，这一轮的 AI 专用插件注册表还需要再收口一次。
- 外部 JSON 插件当前只做加载和字段规范，不包含签名、远程拉取和安全沙箱。

### 8.2 待确认项

- 用户是否后续要把 AI provider 插件继续接入统一插件市场。
- 页面联调所需的有效测试账号和第三方 key 由谁提供。
