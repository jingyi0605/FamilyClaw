# 设计文档 - 对话触发计划任务操作

状态：Draft

## 1. 概述

### 1.1 目标

- 把计划任务接进现有对话 proposal 主链，而不是再外挂一套私有入口
- 复用已有计划任务草稿解析和正式创建 service
- 让用户在聊天里能确认创建计划任务，同时不绕过现有权限和风险边界

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4

### 1.3 技术约束

- 后端：现有 `FastAPI` + `SQLAlchemy`
- 现有可复用模块：`conversation.proposal_pipeline`、`conversation.proposal_analyzers`、`scheduler.draft_service`、`scheduler.service`
- 兼容要求：不能破坏现有 `memory_write`、`config_apply`、`reminder_create` 提案流程

## 2. 架构

### 2.1 系统结构

这次不新建聊天子系统，只是在现有 proposal 主链上多加一种提案：`scheduled_task_create`。

整体流程：

1. 用户发送聊天消息
2. 提案分析器识别出计划任务意图
3. 调用计划任务草稿解析逻辑，生成结构化草稿
4. 把草稿包装成 proposal item 持久化
5. 前端展示确认卡片
6. 用户确认后，执行器复用正式计划任务创建 service 落库

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `conversation.proposal_analyzers` | 识别计划任务意图并产出 proposal draft | 对话消息、LLM 提取结果 | `scheduled_task_create` 提案 |
| `scheduler.draft_service` | 解析聊天文本，生成任务草稿，校验缺失字段 | 文本、当前成员、家庭 | `ScheduledTaskDraftRead` |
| `conversation.proposal_pipeline` | 持久化提案并统一确认/取消 | proposal draft | proposal batch / item |
| `conversation.service` | 确认计划任务提案后执行正式创建 | proposal item | 正式任务 id / 执行结果 |

### 2.3 关键流程

#### 2.3.1 聊天识别计划任务意图

1. 现有提案分析器继续跑。
2. 新增 `ScheduledTaskProposalAnalyzer`。
3. 该分析器先判断本轮消息是否明显是计划任务意图。
4. 如果是，就调用 `scheduler.draft_service.create_draft_from_conversation(...)` 的解析能力，但不直接落正式任务。
5. 解析结果被包装成 `ProposalDraft(proposal_kind="scheduled_task_create")`。

#### 2.3.2 提案确认创建正式任务

1. 用户点击确认。
2. `confirm_conversation_proposal(...)` 识别 proposal kind 为 `scheduled_task_create`。
3. 从 proposal payload 里拿到草稿 id 或草稿 payload。
4. 调用 `scheduler.draft_service.confirm_draft_from_conversation(...)` 或统一确认入口。
5. 创建成功后回写 `affected_target_id = scheduled_task_definition.id`。

#### 2.3.3 缺字段和失败处理

1. 如果草稿缺时间、名字、目标 Agent 等关键字段，proposal 仍可生成，但状态标记为“还不能确认”。
2. 前端看到缺失字段后，可以提示用户继续补充。
3. 确认时如果仍缺字段，返回明确错误，不创建正式任务。
4. 如果目标依赖失效、权限不足或目标不支持计划触发，也返回明确错误并保留 proposal 记录。

## 3. 组件和接口

### 3.1 核心组件

- `ScheduledTaskProposalAnalyzer`：把聊天意图转成计划任务提案
- `ScheduledTaskProposalExecutor`：确认时创建正式任务
- `scheduler.draft_service`：继续做草稿解析和确认，但不再只给独立接口用

### 3.2 数据结构

#### 3.2.1 计划任务 proposal payload

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `draft_id` | `string` | 是 | 对应草稿 id | 必须存在 |
| `intent_summary` | `string` | 是 | 给前端展示的人话摘要 | 不能是空串 |
| `missing_fields` | `string[]` | 是 | 当前还缺什么字段 | 可为空 |
| `draft_payload` | `object` | 是 | 解析出的结构化草稿 | 只存可序列化数据 |
| `can_confirm` | `boolean` | 是 | 当前是否允许直接确认 | 由缺失字段决定 |

#### 3.2.2 proposal kind 扩展

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `proposal_kind` | `string` | 是 | 新值为 `scheduled_task_create` | 进入现有 proposal item |
| `policy_category` | `string` | 是 | 第一版继续走 `ask` | 不自动执行 |

### 3.3 接口契约

#### 3.3.1 对话创建消息

- 类型：HTTP
- 路径：`POST /api/v1/conversations/sessions/{session_id}/turns`
- 输入：用户聊天消息
- 输出：现有 `ConversationTurnRead`，其中 proposal 列表里可能出现 `scheduled_task_create`
- 校验：只在识别到明确计划任务意图时生成对应提案
- 错误：不因为计划任务提案生成失败而拖垮整轮对话

#### 3.3.2 确认计划任务提案

- 类型：HTTP
- 路径：`POST /api/v1/conversations/proposal-items/{proposal_item_id}/confirm`
- 输入：proposal item id
- 输出：执行结果，带正式创建的任务 id
- 校验：
  - proposal kind 必须是 `scheduled_task_create`
  - 草稿必须完整
  - 权限必须通过
- 错误：
  - 草稿缺字段
  - 权限不足
  - 目标依赖失效

## 4. 数据与状态模型

### 4.1 数据关系

- conversation proposal item 持有一份计划任务草稿摘要
- 草稿本身仍由 `scheduler.draft_service` 管理
- proposal confirm 成功后，产生正式 `ScheduledTaskDefinition`

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `drafting` | 草稿还不完整 | 缺字段 | 用户补齐字段 |
| `awaiting_confirm` | 草稿完整，等确认 | 字段齐全 | 用户确认或取消 |
| `confirmed` | 已创建正式任务 | confirm 成功 | 结束 |
| `cancelled` | 用户取消 | dismiss | 结束 |

## 5. 错误处理

### 5.1 错误类型

- `scheduled_task_draft_incomplete`：草稿缺关键字段
- `scheduled_task_permission_denied`：越权创建
- `scheduled_task_dependency_invalid`：目标 Agent / 插件无效
- `scheduled_task_confirm_failed`：确认时正式创建失败

### 5.2 处理策略

1. 草稿缺字段：保留提案，提示还缺什么
2. 权限不足：拒绝确认，不创建任务
3. 目标依赖失效：拒绝确认，并在提案结果里写明原因
4. 提案分析异常：记录失败，但不拖垮整轮对话

## 6. 正确性属性

### 6.1 属性 1：聊天入口不绕过正式创建逻辑

*对于任何* 聊天确认创建请求，系统都应该满足：最终正式落库仍然通过统一计划任务 service 完成。

**验证需求：** 需求 2、需求 3

### 6.2 属性 2：计划任务提案和其他提案共存时不互相破坏

*对于任何* 同一轮对话里的多种提案，系统都应该满足：计划任务提案不会破坏记忆提案、配置提案和提醒提案的现有行为。

**验证需求：** 需求 1、需求 4

## 7. 测试策略

### 7.1 单元测试

- 计划任务意图识别
- 草稿 payload 包装
- 缺字段和权限失败分支

### 7.2 集成测试

- 聊天输入 -> 生成 `scheduled_task_create` proposal
- confirm -> 创建正式任务
- dismiss -> 不创建正式任务

### 7.3 端到端测试

- 用户在聊天里说“每天晚上九点提醒我吃药”
- 前端拿到确认提案
- 用户确认后在计划任务列表里看到新任务

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.3.1、§3.2 | 提案生成测试 |
| `requirements.md` 需求 2 | `design.md` §2.3.2、§3.3.2 | confirm 创建测试 |
| `requirements.md` 需求 3 | `design.md` §2.3.3、§5.2 | 权限和依赖失败测试 |
| `requirements.md` 需求 4 | `design.md` §3.2、§4.2 | 前端展示字段检查 |

## 8. 风险与待确认项

### 8.1 风险

- 现在独立草稿接口和 conversation proposal payload 可能出现双份结构，处理不好会分叉
- 计划任务意图和普通提醒意图边界如果写得太模糊，会互相抢提案

### 8.2 待确认项

- 计划任务提案是否要单独前端卡片样式，还是先复用通用 proposal 卡片
- 缺字段时，是继续依赖前端补充，还是直接回到聊天里做追问回合
