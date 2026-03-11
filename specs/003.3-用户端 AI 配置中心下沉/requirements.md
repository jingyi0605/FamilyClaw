# 需求文档 - 用户端 AI 配置中心下沉

状态：Draft

## 简介

现在 `user-web` 里的 AI 配置是假的，真正的配置能力还留在 `admin-web`。  
这不符合正式产品定位。

这份需求文档定义的是：

- 用户端必须具备哪些正式 AI 配置能力
- AI 供应商配置要如何进入正式产品
- Agent 配置要如何进入正式产品
- 首个管家 Agent 如何通过对话方式创建

## 需求 1：用户端必须具备正式 AI 供应商配置入口

**用户故事：** 作为真实用户，我希望在正式产品里完成 AI 供应商配置，而不是被赶去开发调试后台。

### 验收标准

1. WHEN 用户进入 `user-web` 的 AI 配置中心 THEN System SHALL 提供正式的 AI 供应商配置入口。
2. WHEN 用户还没有任何供应商配置 THEN System SHALL 能在用户端新增第一个供应商。
3. WHEN 用户已经有供应商配置 THEN System SHALL 能查看、编辑、启用、停用和删除供应商配置。

## 需求 2：供应商配置必须通过适配器层统一抽象

**用户故事：** 作为产品团队成员，我希望不同 AI 供应商虽然字段不同，但产品层不要为每一家写一套散装逻辑。

### 验收标准

1. WHEN 系统支持 `ChatGPT`、`GLM`、`硅基流动`、`KIMI`、`MINIMAX` 等供应商 THEN System SHALL 通过统一的供应商适配器层暴露差异化字段。
2. WHEN 用户选择某个供应商适配器 THEN System SHALL 展示该适配器需要的配置项和说明。
3. WHEN 后续新增新的供应商 THEN System SHALL 主要通过新增适配器扩展，而不是重写整套页面逻辑。

## 需求 3：用户端必须具备正式 Agent 配置入口

**用户故事：** 作为用户，我希望在正式产品里管理管家、营养师等 Agent，而不是只能看一个只读页面。

### 验收标准

1. WHEN 用户进入 AI 配置中心 THEN System SHALL 能看到当前家庭下的 Agent 列表。
2. WHEN 用户选择某个 Agent THEN System SHALL 能查看和编辑其基础资料、人格摘要、运行时策略和成员认知。
3. WHEN 用户需要新增 Agent THEN System SHALL 能在 `user-web` 中完成新增，不依赖 `admin-web`。

## 需求 4：首个管家 Agent 必须支持对话式创建

**用户故事：** 作为第一次使用产品的用户，我希望系统通过一段引导式对话帮我创建第一个管家，而不是先让我填一大堆表。

### 验收标准

1. WHEN 当前家庭还没有默认管家 Agent THEN System SHALL 提供对话式创建流程。
2. WHEN 用户在对话中给出名字、风格、性格偏好 THEN System SHALL 将这些结果转成首个管家 Agent 的结构化资料。
3. WHEN 对话式创建结束 THEN System SHALL 创建可用的默认管家 Agent。
4. WHEN 对话过程未完成 THEN System SHALL 允许继续，不强制从头开始。

## 需求 5：用户端 AI 配置中心必须成为正式入口

**用户故事：** 作为产品使用者，我希望 `AI配置` 就是正式入口，而不是一个“去后台配置”的中转页。

### 验收标准

1. WHEN 用户进入设置中的 `AI配置` THEN System SHALL 直接提供正式配置能力，而不是提示去 `admin-web`。
2. WHEN 用户完成供应商配置和 Agent 配置 THEN System SHALL 在 `user-web` 内完成闭环。
3. WHEN `admin-web` 存在同类配置页面 THEN System SHALL 只把它视为开发调试用途，不再作为正式用户流程依赖。

## 需求 6：配置结果必须直接影响对话主链路

**用户故事：** 作为用户，我希望在 AI 配置中心里改过的供应商和 Agent，不是摆设，而是真的影响对话结果。

### 验收标准

1. WHEN 用户启用或停用供应商 THEN System SHALL 影响后续对话使用的可选模型供应能力。
2. WHEN 用户修改 Agent 的默认入口或可对话状态 THEN System SHALL 直接影响对话页的默认 Agent 和可切换列表。
3. WHEN 用户修改 Agent 的人格或运行时策略 THEN System SHALL 在后续对话中生效。

## 非功能需求

### 非功能需求 1：可扩展性

1. WHEN 后续继续增加供应商或 Agent 类型 THEN System SHALL 允许在现有结构下继续扩展，而不是推翻重来。

### 非功能需求 2：可理解性

1. WHEN 用户配置供应商或 Agent THEN System SHALL 用用户能看懂的话说明每项配置在干什么。

### 非功能需求 3：可靠性

1. WHEN 某个供应商校验失败 THEN System SHALL 只阻塞该配置，不破坏其他已可用配置。
2. WHEN Agent 配置保存失败 THEN System SHALL 保留用户当前输入并允许重试。

## 成功定义

- `user-web` 中已具备正式 AI 供应商配置能力
- `user-web` 中已具备正式 Agent 配置能力
- 首个管家 Agent 能通过对话式流程创建
- `admin-web` 不再是正式用户必须依赖的 AI 配置入口
- 配置结果会直接进入对话主链路
