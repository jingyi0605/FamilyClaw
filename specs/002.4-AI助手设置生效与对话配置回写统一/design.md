# 设计文档 - AI助手设置生效与对话配置回写统一

状态：Draft

## 1. 概述

### 1.1 目标

- 把 AI 助手设置页收口成真正的配置入口，不再展示假字段。
- 让设置页保存、对话回写、会话选择、Prompt 组装都读写同一份 Agent 配置。
- 修正运行策略在前端和后端行为不一致的问题。
- 用最少的新概念解决问题，优先复用现有 `ai-config`、`agent service`、`conversation service`。

### 1.2 覆盖需求

- `requirements.md` 需求 1：设置页展示字段必须都是真字段
- `requirements.md` 需求 2：运行策略语义统一
- `requirements.md` 需求 3：助手资料编辑契约统一
- `requirements.md` 需求 4：成员互动设置真实生效或下线
- `requirements.md` 需求 5：对话改配置后设置页能读到最新值
- `requirements.md` 需求 6：链路可验证、可追踪

### 1.3 技术约束

- 后端继续使用现有 `app/modules/agent/`、`app/modules/conversation/`、`app/modules/ai_gateway/`。
- 前端继续在 `apps/user-app` 中实现，不新增第二套设置页。
- 优先复用现有数据库表，不为了“看着整齐”新建重复表。
- 不允许继续在“设置保存链路”和“对话配置回写链路”里各维护一套字段解释。

## 2. 架构

### 2.1 系统结构

这次不加新层，重点是把现有三条链路收成一条：

1. **设置写入链路**
   - `user-app` 设置页表单
   - `ai_config` 相关接口
   - `agent.service` 统一更新方法

2. **运行时读取链路**
   - 会话创建与默认 Agent 选择
   - `build_agent_runtime_context`
   - `provider_runtime` Prompt 组装
   - 动作/提案策略判定

3. **对话配置回写链路**
   - `proposal_analyzers`
   - `conversation.service` 中的 `config.apply` / `config_apply`
   - 统一落到 Agent 更新服务

目标不是“多一套抽象层”，而是让这三条链路使用同一套字段契约。

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `AgentDetailDialog` | 展示和编辑用户可见 Agent 设置 | Agent 详情读模型 | 结构化设置 payload |
| `AgentConfigPanel` | 管理 Agent 列表和详情刷新 | 家庭下 Agent 列表、详情 | 最新 Agent 读模型 |
| `ai_config` 接口 | 暴露 Agent 配置读写入口 | 前端请求 | 标准 Agent 读模型 |
| `agent.service` | 维护 Agent 配置真值源 | 写入 payload | 数据库存储、运行时读模型 |
| `conversation.service` | 执行动作策略和配置回写 | 对话提案、动作记录 | Agent 更新、动作结果 |
| `proposal_analyzers` | 从对话中抽取可回写配置字段 | 用户消息证据 | 结构化配置建议 |
| `build_agent_runtime_context` | 组装对话和问答运行时上下文 | Agent、成员、策略数据 | 统一运行时 context |
| `provider_runtime` | 将运行时 context 组装进 Prompt | 统一运行时 context | 供模型消费的 Prompt 文本 |

### 2.3 关键流程

#### 2.3.1 设置页保存 Agent 资料

1. 前端只提交本期定义为真实可编辑的字段。
2. 后端通过统一的 Agent 更新服务写入。
3. 返回最新 Agent 详情读模型。
4. 前端刷新列表和当前详情弹窗。

#### 2.3.2 创建会话并选择默认 Agent

1. 前端发送显式 `active_agent_id` 时，后端先校验该 Agent 是否 `status=active && conversation_enabled=true`。
2. 没有显式 Agent 时，后端按“`default_entry` 优先，其次主 Agent，再其次第一个可对话 Agent”的顺序解析。
3. 前端和后端使用同一套“可对话 Agent”定义。

#### 2.3.3 对话中应用配置建议

1. 提案抽取器只产出本期允许回写的资料字段。
2. `conversation.service` 收到 `config.apply` 或 `config_apply` 后，不直接散写数据库。
3. 所有回写都转成统一的 Agent 更新 payload，走 Agent 更新服务。
4. 回写成功后返回变更字段和 Agent 更新时间，供前端失效缓存并刷新表单。

#### 2.3.4 成员互动设置进入 Prompt

1. `build_agent_runtime_context` 读取当前请求成员的互动设置。
2. `provider_runtime` 只消费本期保留的稳定字段：
   - `display_address`
   - `communication_style`
   - `prompt_notes`
3. 没有稳定消费者的字段不再显示给普通用户。

## 3. 组件和接口

### 3.1 核心设计决定

#### 3.1.1 不再让“展示字段”和“运行时字段”分叉

所有用户可见字段必须登记在一份字段契约里，至少要回答：

- 它存在哪里
- 谁读取它
- 对话能不能改它
- 如何测试它

这份契约不一定做成新表，可以先落在代码常量和文档里，但不能继续靠隐性约定。

#### 3.1.2 对话回写和设置保存必须复用同一条更新服务

现在最大的问题之一，就是设置页改一套、对话里改一套，支持字段还不一样。  
这次必须改成：

- 设置页保存资料：走统一资料更新服务
- 对话回写资料：也走统一资料更新服务
- 任何一侧新增字段，都必须在同一处登记支持范围

#### 3.1.3 没有稳定语义的字段，优先下线

这次不继续纵容“先放个字段，后面再说”。  
如果字段当前没有稳定消费者，本期优先从用户表单移除，而不是继续摆着骗人。

### 3.2 字段真值矩阵

#### 3.2.1 助手资料字段

| 字段 | 当前存储 | 运行时消费者 | 对话回写 | 本期动作 |
| --- | --- | --- | --- | --- |
| `display_name` | `family_agents.display_name` | 会话标题、Agent 选择、Prompt 名称 | 支持 | 保留 |
| `role_summary` | `family_agent_soul_profiles.role_summary` | Prompt 角色定位 | 支持 | 保留 |
| `intro_message` | `family_agent_soul_profiles.intro_message` | 对话欢迎语和 Prompt | 支持 | 保留 |
| `speaking_style` | `family_agent_soul_profiles.speaking_style` | Prompt 说话风格 | 支持 | 保留 |
| `personality_traits` | `personality_traits_json` | Prompt 性格标签 | 支持 | 保留 |
| `service_focus` | `service_focus_json` | Prompt 服务重点 | 设置页支持；对话回写可选 | 保留 |
| `self_identity` | `family_agent_soul_profiles.self_identity` | Prompt 自我认知 | 不直接回写 | 改为派生字段或高级字段，不再和普通资料并列展示 |

#### 3.2.2 运行策略字段

| 字段 | 当前存储 | 运行时消费者 | 本期动作 |
| --- | --- | --- | --- |
| `conversation_enabled` | `family_agent_runtime_policies.conversation_enabled` | 前端 Agent 列表、后端会话创建、Agent 切换 | 保留并统一强校验 |
| `default_entry` | `family_agent_runtime_policies.default_entry` | 前端默认 Agent、后端默认会话解析 | 保留并统一解析顺序 |
| `autonomous_action_policy.memory` | `autonomous_action_policy_json` | 动作记录、提案执行 | 保留并统一语义 |
| `autonomous_action_policy.config` | 同上 | 动作记录、提案执行 | 保留并统一语义 |
| `autonomous_action_policy.action` | 同上 | 动作记录、提案执行 | 保留并统一语义 |
| `routing_tags` | `routing_tags_json` | 当前没有稳定消费者 | 从普通用户表单移除，保留存储兼容 |

#### 3.2.3 成员互动字段

| 字段 | 当前存储 | 运行时消费者 | 本期动作 |
| --- | --- | --- | --- |
| `display_address` | `family_agent_member_cognitions.display_address` | Prompt 中的称呼建议 | 保留 |
| `communication_style` | `communication_style` | Prompt 中的沟通方式建议 | 保留 |
| `prompt_notes` | `prompt_notes` | Prompt 中的补充注意事项 | 保留 |
| `closeness_level` | `closeness_level` | 当前没有稳定消费者 | 从普通用户表单移除，保留存储兼容 |
| `service_priority` | `service_priority` | 当前没有稳定消费者 | 从普通用户表单移除，保留存储兼容 |

### 3.3 接口契约

#### 3.3.1 Agent 详情接口

- 类型：HTTP
- 路径：`GET /api/v1/ai-config/{household_id}/agents/{agent_id}`
- 输入：`household_id`、`agent_id`
- 输出：
  - 只返回本期仍然可见和可消费的字段
  - 可包含派生字段标记，例如 `self_identity_mode = derived | explicit`
- 校验：
  - Agent 必须属于当前家庭
- 错误：
  - `404`：Agent 不存在

#### 3.3.2 Agent 运行策略更新接口

- 类型：HTTP
- 路径：`PUT /api/v1/ai-config/{household_id}/agents/{agent_id}/runtime-policy`
- 输入：
  - `conversation_enabled`
  - `default_entry`
  - `autonomous_action_policy`
  - 其余本期保留的运行策略字段
- 输出：最新运行策略读模型
- 校验：
  - `default_entry=true` 时，目标 Agent 必须可对话
  - 同一家庭同一时刻最多一个 `default_entry=true`
- 错误：
  - `400`：策略字段非法
  - `409`：目标 Agent 不可对话

#### 3.3.3 对话配置回写结果

- 类型：函数 / 内部结果模型
- 触发点：
  - `config.apply`
  - `config_apply`
- 输出至少包含：
  - `agent_id`
  - `applied_fields`
  - `agent_updated_at`
  - `source = conversation`
- 用途：
  - 前端刷新 Agent 列表和详情
  - 审计与排查

#### 3.3.4 前端刷新通知

- 类型：前端事件或共享失效信号
- 触发点：
  - 设置页保存成功
  - 对话配置回写成功
- 输出：
  - `household_id`
  - `agent_id`
  - `updated_at`
- 要求：
  - 已打开的详情弹窗在命中同一 Agent 时重新拉取详情
  - 助手页在当前家庭下刷新可对话 Agent 列表

## 4. 数据与状态模型

### 4.1 可对话 Agent 判定

系统统一使用下面的条件判定某个 Agent 是否可用于对话：

1. `status == active`
2. `conversation_enabled == true`

任何地方只要要做“默认 Agent 解析”“会话创建”“Agent 切换”，都必须复用这一定义。

### 4.2 默认 Agent 解析顺序

后端默认 Agent 解析改为：

1. 显式传入且可对话的 `active_agent_id`
2. `default_entry=true` 的可对话 Agent
3. `is_primary=true` 的可对话 Agent
4. `sort_order` 最靠前的可对话 Agent
5. 若没有任何可对话 Agent，返回明确错误，不偷偷选不可对话 Agent

### 4.3 运行策略状态语义

| 策略值 | 含义 | 动作记录状态 | 用户感知 |
| --- | --- | --- | --- |
| `ask` | 先问用户，再执行 | `pending_confirmation` | 用户需要点确认 |
| `notify` | 立即执行，但明确告诉用户已执行 | `completed` | 用户能看到执行结果和原因 |
| `auto` | 立即执行，不再额外弹确认卡 | `completed` | 用户只看到紧凑结果或回合摘要 |

这张表同时约束：

- `ConversationActionRecord`
- `ProposalDraft` / `ProposalItem`
- 前端展示文案

不能再出现“数据上有三种值，代码里其实只有两种行为”的垃圾设计。

## 5. 错误处理

### 5.1 错误类型

- 选择了不可对话的 Agent
- 试图把不可对话 Agent 设为默认助手
- 对话回写携带了不受支持的资料字段
- 设置页请求到了已经失效的 Agent 详情

### 5.2 处理策略

1. 选择不可对话 Agent：
   - 会话创建直接报错或回退到合法默认 Agent，并给出明确原因。
2. 默认助手非法：
   - 拒绝保存，返回可读错误。
3. 对话回写字段超出白名单：
   - 丢弃非法字段，记录日志，不允许旁路写库。
4. 前端详情过期：
   - 重新拉取最新 Agent 详情，不保留静态脏数据。

## 6. 正确性属性

### 6.1 单一真值源

对于任何用户可见的 Agent 设置字段，系统都必须满足：

- 设置页写入的结果，和对话回写的结果，最终落到同一份存储。
- 运行时读取只从这份存储衍生，不允许再维护一份“聊天专用配置”。

**验证需求：** `requirements.md` 需求 1、需求 3、需求 5

### 6.2 无假字段

对于任何展示给用户的设置字段，系统都必须满足：

- 要么存在明确运行时消费者。
- 要么在本期从用户表单移除。

**验证需求：** `requirements.md` 需求 1、需求 4

### 6.3 会话合法性

对于任何新建或切换的会话，系统都必须满足：

- `active_agent_id` 对应的 Agent 一定是可对话 Agent。

**验证需求：** `requirements.md` 需求 2

## 7. 测试策略

### 7.1 单元测试

- `resolve_effective_agent` 的默认解析顺序
- `ask/notify/auto` 的状态语义映射
- 对话配置回写的字段白名单和 payload 归一化
- `build_agent_runtime_context` 和 `provider_runtime` 的字段消费

### 7.2 集成测试

- 设置页保存运行策略后，会话创建与 Agent 列表行为一致
- 对话回写 Agent 名称、角色摘要、简介、说话风格、性格标签后，重新获取详情能看到最新值
- 成员互动设置中的保留字段会进入 Prompt

### 7.3 端到端测试

- 设置页关闭某个 Agent 的对话权限后，助手页不再把它当可对话 Agent
- 设置页设置默认助手后，新会话默认选中该 Agent
- 对话里修改 Agent 名称和角色设定后，打开设置页看到新值

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` 3.2、6.2 | 单元测试 + 页面检查 |
| `requirements.md` 需求 2 | `design.md` 4.1、4.2、4.3 | 单元测试 + 集成测试 |
| `requirements.md` 需求 3 | `design.md` 3.2.1、3.3.3、6.1 | 集成测试 |
| `requirements.md` 需求 4 | `design.md` 2.3.4、3.2.3、6.2 | 集成测试 |
| `requirements.md` 需求 5 | `design.md` 3.3.3、3.3.4 | 集成测试 + 端到端测试 |
| `requirements.md` 需求 6 | `design.md` 5、7 | 日志检查 + 自动化测试 |

## 8. 风险与待确认项

### 8.1 风险

- 对 `self_identity`、`routing_tags`、`closeness_level`、`service_priority` 的收口会改变现有表单，需要注意用户认知迁移。
- `notify` 和 `auto` 语义拆开后，前端展示文案和状态说明也要同步更新，否则又会出现“代码改了，页面没跟上”。
- 对话回写字段范围扩大后，如果没有白名单约束，很容易再次出现旁路更新。

### 8.2 待确认项

- 无。当前问题的本质已经足够明确，本期不需要再为假字段找借口。
