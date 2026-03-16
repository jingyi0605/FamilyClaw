# 需求文档 - AI供应商管理插件化与模型摘要重构

状态：Blocked

## 简介

这次改造要解决两个真实问题：

1. AI 供应商页把所有配置平铺开，用户很难快速看清“现在有哪些模型正在工作”。
2. 新增供应商和模型时，页面和后端都在堆特殊情况，导致每加一个供应商都像补丁。

目标很直接：页面主视图只保留列表和配置摘要；供应商能力改成插件描述；新增模型时先选供应商，再走供应商自己的动态表单；同时把该供应商支持的模型类型和 LLM 工作流说清楚。

## 术语表

- **System**：FamilyClaw 的 AI 配置中心，包括 `user-app` 设置页和 `api-server` AI provider adapter 注册表。
- **供应商插件**：描述一个 AI 供应商的元数据对象，至少包含适配器编码、字段 schema、支持类型、LLM workflow 等信息。
- **模型类型**：供应商支持的能力类别，包含 `llm`、`embedding`、`vision`、`speech`、`image`。
- **动态表单**：根据供应商插件提供的 `field_schema` 渲染出的新增/编辑表单，而不是写死字段。
- **配置摘要**：主页面展示的供应商关键信息，包括插件、模型名称、支持类型、路由能力和主要配置字段。

## 范围说明

### In Scope

- 重构 `user-app` AI 供应商页主视图，只保留列表和配置摘要。
- 新增模型流程改成“先选供应商插件，再展示该插件的动态表单”。
- 后端暴露供应商插件元数据，支持内置供应商和外部 JSON 插件文件。
- 前端展示供应商支持的模型类型和 `llm_workflow`。
- 保持现有 AI provider profile 存量数据可读、可编辑。

### Out of Scope

- 把 AI 供应商接入统一插件市场、安装中心或插件生命周期治理。
- 重做 AI route、调用日志、成本策略等整套 AI 网关架构。
- 完成依赖真实线上账号或真实第三方 key 的全自动联调。

## 需求

### 需求 1：主页面只展示列表和摘要

**用户故事：** 作为正在配置家庭 AI 的管理员，我希望一进页面就看到“有哪些供应商模型”和“它们当前怎么工作”，而不是被一整页配置项淹没，这样我才能快速判断配置是否正常。

#### 验收标准

1. WHEN 用户打开 AI 供应商管理页 THEN System SHALL 只展示供应商列表、汇总统计和当前选中供应商的配置摘要，不再在主页面平铺完整编辑表单。
2. WHEN 用户选择某个供应商 THEN System SHALL 在摘要区展示该供应商的插件名、模型名、支持类型、路由能力、LLM workflow 和关键配置字段。
3. WHEN 当前没有任何供应商 THEN System SHALL 展示空状态，而不是渲染一堆不可用表单。

### 需求 2：供应商配置要插件化

**用户故事：** 作为要接更多模型来源的开发者，我希望供应商元数据来自插件描述，而不是散落在多处硬编码里，这样新增供应商时只需要补插件描述，而不是把前后端都撕开。

#### 验收标准

1. WHEN 后端列出 AI provider adapters THEN System SHALL 返回 `plugin_id`、`plugin_name`、`supported_model_types`、`llm_workflow` 和 `field_schema`。
2. WHEN 系统启动并扫描 AI provider 插件目录 THEN System SHALL 同时加载内置供应商和外部 JSON 插件文件，并按 `adapter_code` 输出统一结构。
3. WHEN 读取旧的 provider profile 数据 THEN System SHALL 继续兼容现有配置，不要求用户重建已有模型。

### 需求 3：新增模型必须先选供应商，再走动态表单

**用户故事：** 作为管理员，我希望新增模型时先选供应商，再填写该供应商真正需要的字段，而不是先看到一张混杂所有供应商字段的大表单。

#### 验收标准

1. WHEN 用户点击“添加模型/添加供应商” THEN System SHALL 先展示供应商插件选择区。
2. WHEN 用户选中某个供应商插件 THEN System SHALL 根据该插件的 `field_schema` 渲染动态表单，并显示该插件的支持类型和 `llm_workflow`。
3. WHEN 用户提交表单 THEN System SHALL 生成与当前插件匹配的 provider payload，并创建或更新对应的 provider profile。

### 需求 4：支持类型和 LLM workflow 必须可见

**用户故事：** 作为管理员，我希望知道一个供应商到底支持聊天、嵌入、视觉、语音还是生图，以及它走哪类 LLM 流程，这样我才能判断它能不能承担当前路由。

#### 验收标准

1. WHEN 前端展示供应商卡片或摘要 THEN System SHALL 用明确标签显示 `llm`、`embedding`、`vision`、`speech`、`image` 的支持情况。
2. WHEN 前端展示供应商详情或编辑弹窗 THEN System SHALL 显示该供应商的 `llm_workflow`。
3. WHEN 某个供应商没有声明某类支持类型 THEN System SHALL 不伪造能力标签。

## 非功能需求

### 非功能需求 1：可维护性

1. WHEN 新增一个供应商 THEN System SHALL 允许通过内置注册表条目或外部 JSON 插件文件扩展，而不是要求同时改多处表单逻辑。
2. WHEN 前端本地化显示插件字段 THEN System SHALL 统一走 i18n 或字段元数据映射，不在页面里堆硬编码文案。

### 非功能需求 2：向后兼容

1. WHEN 用户已经有旧版 provider profile 数据 THEN System SHALL 继续展示并允许编辑，不破坏现有 household 的 AI 配置。
2. WHEN 旧接口继续被现有页面调用 THEN System SHALL 保持原有创建、更新、删除 provider profile 的基本行为不变。

### 非功能需求 3：可验证性

1. WHEN 开发完成 THEN System SHALL 至少能通过前端类型检查和后端 provider registry 定向测试。
2. WHEN 需要做端到端验收 THEN System SHALL 提供清晰的人工验证路径，覆盖列表摘要、插件选择、动态表单和摘要回显。

## 成功定义

- `user-app` AI 供应商主页面不再平铺全部设置，而是列表加摘要。
- 新增模型时能先选供应商插件，再加载对应动态表单。
- 页面能看到支持类型和 `llm_workflow`。
- 后端 provider adapter 支持内置注册表加外部 JSON 插件扩展。
- 前端类型检查通过，后端 provider registry 定向测试通过。
