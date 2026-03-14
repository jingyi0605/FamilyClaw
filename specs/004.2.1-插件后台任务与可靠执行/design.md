# 设计文档 - 插件后台任务与可靠执行

状态：Draft

## 1. 概述

### 1.1 目标

- 把插件执行从“请求内同步处理”改成“任务入队 + 后台执行”
- 给任务补齐状态、通知、响应、重试、恢复这几件必须品
- 在不推翻现有插件执行代码的前提下，先做一版项目内可落地的可靠任务系统

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4
- `requirements.md` 需求 5

### 1.3 技术约束

- 后端：FastAPI + SQLAlchemy
- 数据存储：现有主数据库 + Alembic migration
- 通知通道：优先复用现有 WebSocket 推送能力
- 执行模式：先在 API 服务内引入后台 worker，不依赖外部消息队列
- 兼容要求：现有插件执行逻辑尽量复用，先在外面包一层任务调度，不直接重写插件协议

## 2. 架构

### 2.1 系统结构

这套方案分五层：

1. **任务入口层**：HTTP / WebSocket / Agent 调用插件时，不直接执行插件，而是先创建任务。
2. **任务持久化层**：把任务主记录、执行尝试、通知记录、响应记录写进数据库。
3. **任务调度层**：从待执行任务里取任务，分发给后台 worker。
4. **执行器层**：真正调用现有插件执行器或 runner。
5. **通知与响应层**：任务状态变化后推送给前端；用户后续的重试、确认、取消也走统一入口。

数据主流向如下：

`调用入口 -> 创建任务 -> 后台 worker 执行 -> 更新任务状态 -> 发送通知 -> 等待用户响应或进入终态`

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `plugin_job_service` | 创建任务、查任务、响应任务 | 插件请求、用户响应 | 任务记录、状态变化 |
| `plugin_job_worker` | 后台轮询并执行任务 | 待执行任务 | 执行结果、重试安排 |
| `plugin.service` | 复用现有插件执行能力 | 插件执行请求 | 插件输出 |
| `plugin_notification_service` | 发送任务状态通知 | 任务状态事件 | WebSocket 事件、通知记录 |
| `plugin_recovery_service` | 启动恢复、超时收口 | 异常任务 | 恢复后的新状态 |

### 2.3 关键流程

#### 2.3.1 创建插件任务

1. 入口接口校验请求和权限。
2. 系统生成幂等键和任务记录，状态写成 `queued` 或 `waiting_confirmation`。
3. 接口立即返回任务编号、当前状态和建议的轮询/订阅方式。
4. 后台 worker 异步接手执行。

#### 2.3.2 后台执行和重试

1. worker 取到 `queued` 任务后抢占执行权，状态改成 `running`。
2. worker 调用现有插件执行器。
3. 成功则写 `succeeded`，失败则根据错误类型进入 `retry_waiting`、`failed` 或 `waiting_response`。
4. 每次状态变化都写通知事件。

#### 2.3.3 用户响应失败或待确认任务

1. 用户查看任务详情，看到失败原因和可执行动作。
2. 用户选择重试、取消、确认执行、补充参数等动作。
3. 系统写响应记录，并把任务推进到下一状态。
4. 若需要再次执行，则重新入队。

#### 2.3.4 服务重启后的恢复

1. 服务启动时扫描长时间停留在 `running` 的任务。
2. 根据最后心跳、尝试记录和任务类型判断是恢复、重排还是标记失败。
3. 统一补一条恢复通知，避免任务悄悄消失。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5

- `plugin_job_service`：统一任务创建、查询、响应入口
- `plugin_job_worker`：后台执行和状态推进
- `plugin_notification_service`：负责通知事件落库和推送
- `plugin_recovery_service`：负责超时收口和重启恢复

### 3.2 数据结构

覆盖需求：1、2、3、4、5

#### 3.2.1 `plugin_jobs`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | 任务主键 | UUID |
| `household_id` | string | 是 | 家庭 ID | 必须存在 |
| `plugin_id` | string | 是 | 插件 ID | 非空 |
| `plugin_type` | string | 是 | 插件类型 | connector / action / agent-skill / memory-ingestor |
| `trigger` | string | 是 | 触发来源 | 非空 |
| `status` | string | 是 | 当前任务状态 | 见 §4.2 |
| `request_payload_json` | json string | 是 | 原始请求载荷 | 可脱敏 |
| `payload_summary_json` | json string | 否 | 前端展示用摘要 | 不放敏感原文 |
| `idempotency_key` | string | 否 | 幂等键 | 同作用域唯一 |
| `current_attempt` | int | 是 | 当前第几次尝试 | 默认 0 |
| `max_attempts` | int | 是 | 最大尝试次数 | 默认按任务类型配置 |
| `last_error_code` | string | 否 | 最近一次错误码 | 可空 |
| `last_error_message` | text | 否 | 最近一次错误说明 | 可空 |
| `response_deadline_at` | string | 否 | 等待用户响应截止时间 | 可空 |
| `started_at` | string | 否 | 首次开始执行时间 | 可空 |
| `finished_at` | string | 否 | 终态完成时间 | 可空 |
| `updated_at` | string | 是 | 最近更新时间 | 必填 |
| `created_at` | string | 是 | 创建时间 | 必填 |

#### 3.2.2 `plugin_job_attempts`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | 尝试记录主键 | UUID |
| `job_id` | string | 是 | 对应任务 | 外键 |
| `attempt_no` | int | 是 | 第几次尝试 | 从 1 开始 |
| `status` | string | 是 | 尝试结果 | running / succeeded / failed / timed_out |
| `worker_id` | string | 否 | 执行该尝试的 worker | 可空 |
| `started_at` | string | 是 | 尝试开始时间 | 必填 |
| `finished_at` | string | 否 | 尝试结束时间 | 可空 |
| `error_code` | string | 否 | 错误码 | 可空 |
| `error_message` | text | 否 | 错误说明 | 可空 |
| `output_summary_json` | json string | 否 | 结果摘要 | 可空 |

#### 3.2.3 `plugin_job_notifications`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | 通知记录主键 | UUID |
| `job_id` | string | 是 | 对应任务 | 外键 |
| `notification_type` | string | 是 | 通知类型 | state_changed / failed / waiting_response / recovered |
| `channel` | string | 是 | 通知通道 | websocket / in_app |
| `payload_json` | json string | 是 | 通知内容 | 非空 |
| `delivered_at` | string | 否 | 实际发送时间 | 可空 |
| `created_at` | string | 是 | 创建时间 | 必填 |

#### 3.2.4 `plugin_job_responses`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | 响应记录主键 | UUID |
| `job_id` | string | 是 | 对应任务 | 外键 |
| `action` | string | 是 | 响应动作 | retry / confirm / cancel / provide_input |
| `actor_type` | string | 是 | 响应者类型 | member / admin / system |
| `actor_id` | string | 否 | 响应者 ID | 可空 |
| `payload_json` | json string | 否 | 补充参数 | 可空 |
| `created_at` | string | 是 | 响应时间 | 必填 |

### 3.3 接口契约

覆盖需求：1、2、3、4

#### 3.3.1 创建插件任务

- 类型：HTTP
- 路径或标识：`POST /api/v1/plugin-jobs`
- 输入：插件 ID、插件类型、触发来源、请求载荷、可选幂等键
- 输出：任务 ID、当前状态、是否已复用旧任务、轮询地址、订阅主题
- 校验：插件存在、权限合法、幂等键格式合法
- 错误：400、403、404、409

#### 3.3.2 查询任务详情

- 类型：HTTP
- 路径或标识：`GET /api/v1/plugin-jobs/{job_id}`
- 输入：任务 ID
- 输出：任务详情、最近尝试、可执行响应动作、最近通知摘要
- 校验：只能看自己家庭内任务
- 错误：403、404

#### 3.3.3 查询任务列表

- 类型：HTTP
- 路径或标识：`GET /api/v1/plugin-jobs`
- 输入：`household_id`、状态、插件 ID、时间范围、分页参数
- 输出：任务列表
- 校验：列表过滤参数合法
- 错误：400、403

#### 3.3.4 响应任务

- 类型：HTTP
- 路径或标识：`POST /api/v1/plugin-jobs/{job_id}/responses`
- 输入：动作类型、可选补充参数
- 输出：更新后的任务状态
- 校验：只有处于 `waiting_response` 或可重试失败的任务才能响应
- 错误：400、403、404、409

#### 3.3.5 订阅任务状态

- 类型：WebSocket Event
- 路径或标识：现有实时连接下新增 `plugin.job.updated`
- 输入：登录态 + household 作用域
- 输出：任务状态变化事件
- 校验：只推送当前家庭可见任务
- 错误：鉴权失败时拒绝订阅

## 4. 数据与状态模型

### 4.1 数据关系

- 一条 `plugin_jobs` 对应多条 `plugin_job_attempts`
- 一条 `plugin_jobs` 对应多条 `plugin_job_notifications`
- 一条 `plugin_jobs` 对应多条 `plugin_job_responses`
- 任务主表负责“当前状态”，尝试表负责“历史细节”
- 通知和响应都不能直接覆盖任务历史，必须单独留痕

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `queued` | 已创建，等待 worker 执行 | 新建任务或重新入队 | 被 worker 抢占执行 |
| `running` | 正在执行 | worker 开始执行 | 成功、失败、超时、待响应 |
| `retry_waiting` | 等待下一次自动重试 | 可重试失败 | 到达重试时间后重新入队 |
| `waiting_response` | 等待人工确认或补充参数 | 需要人工确认、补参、人工选择 | 用户响应后重新入队或取消 |
| `succeeded` | 执行成功终态 | 插件执行成功 | 不再退出 |
| `failed` | 失败终态 | 不可重试失败或重试耗尽 | 用户手动重试时重新创建新尝试或新任务 |
| `cancelled` | 主动取消终态 | 用户取消或系统取消 | 不再退出 |

状态不变量：

- 终态任务不能再被 worker 自动执行
- `running` 任务必须有正在进行中的尝试记录
- `waiting_response` 任务必须能给出允许的响应动作列表

## 5. 错误处理

### 5.1 错误类型

- `job_validation_error`：请求参数、权限或插件配置不合法
- `job_execution_failed`：插件运行失败
- `job_timeout`：插件超时
- `job_response_required`：需要人工确认或补参
- `job_recovery_failed`：恢复阶段无法判断安全状态

### 5.2 错误响应格式

```json
{
  "detail": "任务当前不能执行这个响应动作",
  "error_code": "job_invalid_response_action",
  "field": "action",
  "timestamp": "2026-03-14T00:00:00Z"
}
```

### 5.3 处理策略

1. 输入验证错误：直接拒绝创建任务，不入队。
2. 插件运行错误：记录尝试失败，按错误类型决定自动重试还是进入终态失败。
3. 需要人工确认：转成 `waiting_response`，推送通知，不继续自动执行。
4. 超时：尝试记录标记超时；高风险动作不自动重试。
5. 恢复异常：如果无法安全恢复，宁可标记失败并通知，也不默默继续执行。

## 6. 正确性属性

### 6.1 属性 1：一条任务在同一时刻只能被一个 worker 执行

*对于任何* 处于 `running` 的任务，系统都应该满足：同时最多只有一个活动尝试记录持有执行权。

**验证需求：** `requirements.md` 需求 1、需求 4

### 6.2 属性 2：失败任务不会静默丢失

*对于任何* 执行失败、超时或需要人工确认的任务，系统都应该满足：任务状态、错误信息和通知记录至少保留一份可查证据。

**验证需求：** `requirements.md` 需求 2、需求 3、需求 5

### 6.3 属性 3：终态任务不会被自动重复执行

*对于任何* 已处于 `succeeded`、`failed`、`cancelled` 的任务，系统都应该满足：除非收到明确响应动作，否则不会再次进入执行。

**验证需求：** `requirements.md` 需求 4

## 7. 测试策略

### 7.1 单元测试

- 任务状态流转
- 自动重试判定
- 幂等键去重
- 响应动作校验

### 7.2 集成测试

- 创建任务后接口立即返回，后台异步完成执行
- 失败任务生成通知并可查询
- 待确认任务收到响应后重新入队
- 服务重启后恢复中断任务

### 7.3 端到端测试

- 前端创建插件任务 -> 轮询/订阅看到成功
- 前端创建高风险动作任务 -> 收到待确认通知 -> 人工确认 -> 任务完成
- 插件失败 -> 前端收到失败通知 -> 手动重试 -> 任务成功或终态失败

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.3.1、§3.3.1、§4.2 | 接口测试、并发回归测试 |
| `requirements.md` 需求 2 | `design.md` §3.3.2、§3.3.3、§3.3.5、§4.1 | 查询接口测试、推送事件测试 |
| `requirements.md` 需求 3 | `design.md` §2.3.3、§3.3.4、§5.3 | 失败通知测试、人工响应测试 |
| `requirements.md` 需求 4 | `design.md` §2.3.2、§4.2、§6.1、§6.3 | 重试测试、幂等测试 |
| `requirements.md` 需求 5 | `design.md` §2.3.4、§5.3、§6.2 | 恢复测试、超时测试 |

## 8. 风险与待确认项

### 8.1 风险

- 单进程 worker 版本先能解决阻塞问题，但还不是最终的多实例调度方案
- 如果任务类型很多，状态机会膨胀，必须坚持统一状态模型，不能每类任务私自加状态
- 通知如果只做 WebSocket，不做离线补偿，用户不在线时可能错过即时提醒

### 8.2 待确认项

- 第一版失败通知默认进哪条通知中心：仅站内通知，还是同步进入会话消息
- 人工响应动作是否需要区分普通成员和管理员的不同权限范围
- 是否需要给部分高风险动作单独配置更严格的超时和重试策略
