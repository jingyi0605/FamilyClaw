# 设计文档 - WebSocket 实时通道与 AI 管家初始化迁移

状态：Draft

## 1. 概述

### 1.1 目标

- 用统一的 WebSocket 实时通道替换当前 AI 管家初始化对话的 SSE 链路
- 把会话、请求轮次、消息记录和草稿状态统一收回服务端管理
- 让刷新恢复、断线重连和多轮连续对话有稳定行为，而不是靠前端补丁硬撑

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4
- `requirements.md` 需求 5

### 1.3 技术约束

- 后端：FastAPI + SQLAlchemy
- 前端：React + Vite
- 数据存储：SQLite / Alembic 迁移体系
- 认证授权：沿用现有基于 session cookie 的身份体系
- 外部依赖：现有 AI Gateway 和供应商流式能力不重写，只重写项目内部实时通道和状态管理

## 2. 架构

### 2.1 系统结构

重写后分成四层：

1. **WebSocket 连接层**：只负责鉴权、连接保活、事件收发
2. **实时业务层**：负责 AI 管家初始化对话的请求调度、轮次管理、事件广播
3. **会话持久化层**：负责保存消息、会话状态、当前轮次和恢复快照
4. **LLM 运行层**：继续负责与 AI Gateway / 供应商交互，但输出先被规范化，再变成业务事件

核心变化只有一句话：

**WebSocket 只搬运事件，真正的状态和业务逻辑留在服务端。**

### 2.1.1 去标签协议原则

这次重写里有一条不能退让的硬规则：

- 展示文本就是展示文本，只能走 `agent.chunk`
- 结构化状态就是结构化状态，只能走 `agent.state_patch`
- 服务端 reducer 是唯一的状态合并入口
- 严禁再把 `<config>...</config>`、`<json>...</json>`、`---` 分隔块或任何等价标签协议塞回展示文本

原因很简单：

1. 这类协议会把控制信息污染到用户可见文本里
2. 前端不得不写脆弱的正则去清洗和反解析
3. 一旦模型输出格式抖动，展示和状态都会一起坏

所以这次设计明确要求：

- **优先方案**：供应商支持 JSON schema / tool calling / 等价结构化输出时，直接产出结构化状态
- **降级方案**：供应商不支持时，单独做一次结构化提取调用
- **禁止方案**：把控制协议和展示文本混在同一条回复里

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `realtime/ws_endpoint` | 建立 WebSocket、鉴权、收发统一事件 | cookie、事件包 | 连接上下文、事件发送 |
| `realtime/connection_manager` | 管理会话订阅、广播、连接关闭 | session_id、socket | 广播结果、连接状态 |
| `agent_bootstrap/realtime_service` | 处理用户消息、启动 LLM、发事件 | 用户事件、session_id | chunk/state_patch/done/error |
| `agent_bootstrap/repository` | 持久化会话、消息、轮次 | 会话对象、消息对象 | 数据库记录、快照 |
| `llm_task/stream executor` | 读取供应商流并规范化 | provider stream | 文本块、结构化结果、结束信号 |

### 2.3 关键流程

#### 2.3.1 首次连接并恢复当前会话

1. 前端进入 AI 管家初始化页面，先通过 HTTP 获取当前会话快照或创建新会话。
2. 前端用 `session_id` 建立 WebSocket 连接。
3. 后端鉴权成功后返回 `session.ready`。
4. 后端立刻发送 `session.snapshot`，内容包含历史消息、当前草稿、当前状态、是否存在进行中的轮次。
5. 前端用快照直接恢复页面，不再依赖本地缓存作为真相来源。

#### 2.3.2 用户发起一轮初始化对话

1. 前端生成 `request_id`，发送 `user.message` 事件。
2. 后端校验当前会话是否允许继续对话。
3. 后端先落库用户消息和本轮请求，再回 `user.message.accepted`。
4. 后端启动 LLM 流式执行。
5. 每收到新的文本块，就发 `agent.chunk`。
6. 每拿到新的结构化提取结果，就通过 reducer 更新草稿并发 `agent.state_patch`。
7. 一轮结束时，后端保存 assistant 最终消息、更新会话状态，发送 `agent.done`。

这里额外强调一条实现约束：

- `agent.chunk` 只能承载用户可见文本
- `agent.state_patch` 只能承载结构化状态变化
- 两者来源可以来自同一次模型调用或二次提取调用，但协议上绝不能混用

#### 2.3.3 页面刷新或断线后恢复

1. 页面刷新后重新走 HTTP 快照读取。
2. 若存在未完成会话，则返回最近会话及完整消息记录。
3. 前端重连 WebSocket 后请求 `session.snapshot` 或直接接收服务器推送快照。
4. 若上一轮已经完成，则快照里显示完整结果；若上一轮仍在执行，则服务端继续按当前轮次推事件。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5

- `RealtimeBootstrapWsEndpoint`：AI 管家初始化的 WebSocket 入口
- `RealtimeConnectionManager`：按 `household_id + session_id` 管理连接集合
- `BootstrapRealtimeService`：按请求轮次驱动 AI 对话执行
- `BootstrapStateReducer`：把结构化提取结果并到当前会话草稿里
- `BootstrapSnapshotService`：统一返回当前会话快照
- `BootstrapStructuredExtractionService`：负责供应商结构化输出或二次提取调用

### 3.2 数据结构

覆盖需求：2、3、4

#### 3.2.1 `BootstrapRealtimeEvent`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `type` | string | 是 | 事件类型 | 只能是约定集合 |
| `session_id` | string | 是 | 当前会话 ID | 必须存在 |
| `request_id` | string | 否 | 当前轮次 ID | 用户消息和 AI 回复事件必须有 |
| `seq` | int | 是 | 会话内递增序号 | 单调递增 |
| `payload` | object | 是 | 事件内容 | 结构依赖事件类型 |
| `ts` | string | 是 | 事件时间 | ISO-8601 |

#### 3.2.1.1 `agent.chunk` payload

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `text` | string | 是 | 用户可见文本块 | 纯文本，禁止控制标签 |

#### 3.2.1.2 `agent.state_patch` payload

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `display_name` | string | 否 | 当前提取到的名字 | 可空 |
| `speaking_style` | string | 否 | 当前提取到的说话风格 | 可空 |
| `personality_traits` | list[string] | 否 | 当前提取到的性格标签 | 可空 |

说明：

- `agent.chunk` 和 `agent.state_patch` 是两种不同事件，不能在同一个文本字段里塞双重语义
- 前端不得再从文本里反向提取状态

#### 3.2.2 `family_agent_bootstrap_sessions`（调整）

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | text | 是 | 会话 ID | 主键 |
| `household_id` | text | 是 | 家庭 ID | 外键 |
| `status` | string | 是 | `collecting/reviewing/completed/cancelled` | 有限集合 |
| `pending_field` | string | 否 | 当前待收集字段 | 为空表示可确认或已完成 |
| `draft_json` | text | 是 | 当前草稿 | UTF-8 JSON |
| `current_request_id` | text | 否 | 正在执行的轮次 | 同一时刻最多一个 |
| `last_event_seq` | int | 是 | 最新事件序号 | 默认 0 |
| `created_at` | text | 是 | 创建时间 | ISO-8601 |
| `updated_at` | text | 是 | 更新时间 | ISO-8601 |
| `completed_at` | text | 否 | 完成时间 | 可空 |

#### 3.2.3 `family_agent_bootstrap_messages`（新增）

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | text | 是 | 消息 ID | 主键 |
| `session_id` | text | 是 | 所属会话 | 外键 |
| `request_id` | text | 否 | 所属轮次 | 可为空 |
| `role` | string | 是 | `user/assistant/system` | 有限集合 |
| `content` | text | 是 | 消息正文 | UTF-8 文本 |
| `seq` | int | 是 | 消息顺序 | 会话内递增 |
| `created_at` | text | 是 | 创建时间 | ISO-8601 |

#### 3.2.4 `family_agent_bootstrap_requests`（新增）

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | text | 是 | 轮次 ID | 主键 |
| `session_id` | text | 是 | 所属会话 | 外键 |
| `status` | string | 是 | `running/succeeded/failed/cancelled` | 有限集合 |
| `user_message_id` | text | 是 | 用户消息 ID | 外键 |
| `assistant_message_id` | text | 否 | 最终回复消息 ID | 可空 |
| `error_code` | text | 否 | 失败代码 | 可空 |
| `started_at` | text | 是 | 开始时间 | ISO-8601 |
| `finished_at` | text | 否 | 结束时间 | 可空 |

### 3.3 接口契约

覆盖需求：1、2、4、5

#### 3.3.1 WebSocket 连接：AI 管家初始化实时通道

- 类型：WebSocket
- 路径或标识：`/api/v1/realtime/agent-bootstrap`
- 输入：cookie 鉴权、查询参数 `household_id`、`session_id`
- 输出：统一事件包
- 校验：
  - 只能访问当前用户可操作的家庭
  - `session_id` 必须属于该家庭
  - 已完成会话允许读取快照，不允许继续发起新轮次
- 错误：
  - 鉴权失败：连接拒绝
  - 会话不存在：发送 `agent.error` 后关闭
  - 会话和家庭不匹配：发送 `agent.error` 后关闭

#### 3.3.2 HTTP：读取最近初始化会话快照

- 类型：HTTP
- 路径或标识：`GET /api/v1/ai-config/{household_id}/butler-bootstrap/sessions/latest`
- 输入：`household_id`
- 输出：当前最近会话的完整快照，包括消息记录、当前状态、草稿、最近活动时间
- 校验：必须有权限访问当前家庭
- 错误：无会话时返回 `null`

#### 3.3.3 HTTP：重新开始初始化会话

- 类型：HTTP
- 路径或标识：`POST /api/v1/ai-config/{household_id}/butler-bootstrap/sessions/restart`
- 输入：`household_id`
- 输出：新会话快照
- 校验：当前家庭还没有已启用管家
- 错误：已有启用管家时返回业务错误

#### 3.3.4 WebSocket 事件类型

- `session.ready`：连接建立成功
- `session.snapshot`：当前会话全量快照
- `user.message.accepted`：当前轮次已落库并开始执行
- `agent.chunk`：增量文本
- `agent.state_patch`：草稿增量更新
- `agent.done`：本轮结束
- `agent.error`：本轮失败或连接级业务错误
- `ping` / `pong`：保活

#### 3.3.5 结构化输出策略

- 类型：内部策略
- 路径或标识：`BootstrapStructuredExtractionService`
- 输入：
  - LLM 原始文本流或最终文本
  - 当前会话草稿
  - 当前供应商能力信息
- 输出：结构化状态补丁
- 校验：
  - 若供应商支持 JSON schema / tool calling，则直接走结构化输出
  - 若不支持，则发起单独二次提取调用
  - 不允许把结构化状态塞进展示文本
- 错误：
  - 结构化提取失败只影响 `agent.state_patch`，不污染 `agent.chunk`

## 4. 数据与状态模型

### 4.1 数据关系

- 一个 `bootstrap_session` 对应多条 `bootstrap_message`
- 一个 `bootstrap_session` 对应多条 `bootstrap_request`
- 一条 `bootstrap_request` 必须属于一条 `bootstrap_session`
- 一轮请求通常有 1 条用户消息和 0 或 1 条最终 assistant 消息
- 会话草稿只在服务端权威保存，前端只是渲染副本

### 4.2 状态流转

#### 会话状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `collecting` | 还在收集名字、说话风格、性格等 | 创建会话或信息未收齐 | 信息补齐进入 `reviewing` |
| `reviewing` | 信息已收齐，等用户确认 | reducer 判断必填项已齐 | 用户确认后进入 `completed`；用户重开后创建新会话 |
| `completed` | 已完成并创建管家 | 确认创建成功 | 不再接受新消息 |
| `cancelled` | 用户重开导致旧会话废弃 | 用户点击重新开始 | 不再接受新消息 |

#### 请求轮次状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `running` | 正在生成回复 | 收到 `user.message` 并开始执行 | 正常结束、失败或取消 |
| `succeeded` | 本轮完成 | 已发 `agent.done` | 无 |
| `failed` | 本轮失败 | 已发 `agent.error` | 无 |
| `cancelled` | 被重连清理或用户重开打断 | 明确取消 | 无 |

## 5. 错误处理

### 5.1 错误类型

- `ws_auth_failed`：WebSocket 握手成功前后鉴权失败
- `session_not_found`：会话不存在或不属于当前家庭
- `session_closed`：已完成或已取消的会话仍尝试继续发消息
- `request_conflict`：上一轮未结束时又发起新一轮
- `provider_stream_failed`：上游模型流式调用失败
- `structured_extraction_failed`：结构化提取失败
- `snapshot_restore_failed`：快照读取或解码失败
- `invalid_event_payload`：前端发来的事件结构不合法

### 5.2 错误响应格式

```json
{
  "type": "agent.error",
  "session_id": "session-id",
  "request_id": "request-id",
  "seq": 12,
  "payload": {
    "detail": "这轮对话失败了，请重试",
    "error_code": "provider_stream_failed"
  },
  "ts": "2026-03-12T00:00:00Z"
}
```

### 5.3 处理策略

1. 输入验证错误：直接返回 `agent.error`，不启动 LLM。
2. 业务规则错误：比如已完成会话继续发消息，直接返回 `agent.error`。
3. 结构化提取失败：保留本轮展示文本，记录提取失败日志，不允许回退到标签协议。
4. 外部依赖错误：记录 request 失败状态，保留已落库消息，允许用户重新发起下一轮。
5. 重试、降级或补偿：WebSocket 失败后先用 HTTP 快照恢复会话，不再让前端靠本地假状态续聊。

## 6. 正确性属性

### 6.1 属性 1：一轮请求必须有明确结束

*对于任何* 已接受的 `request_id`，系统都应该满足：最终一定落到 `succeeded`、`failed` 或 `cancelled` 三者之一，不能出现悬空轮次。

**验证需求：** 需求 2、需求 4

### 6.2 属性 2：服务端快照是真相来源

*对于任何* 页面刷新、重连或重新进入初始化页面的场景，系统都应该满足：恢复出来的消息历史和会话状态以服务端持久化快照为准。

**验证需求：** 需求 3、需求 4

### 6.3 属性 3：文本落库必须可读

*对于任何* 从上游模型返回并保存到数据库的消息文本，系统都应该满足：最终数据库里保存的是可正常读取的 UTF-8 文本，而不是乱码字节残片。

**验证需求：** 非功能需求 3

### 6.4 属性 4：展示文本与状态提取必须分离

*对于任何* AI 管家初始化回复，系统都应该满足：用户看到的文本输出和服务端保存的结构化状态是两条分离链路，系统不会依赖标签协议从展示文本里反解析状态。

**验证需求：** 需求 2.1

## 7. 测试策略

### 7.1 单元测试

- 事件协议编码与解码
- reducer 的草稿合并逻辑
- request 状态流转和结束语义
- 结构化提取策略选择：JSON schema / tool calling / 二次提取调用

### 7.2 集成测试

- WebSocket 鉴权和会话校验
- 一轮对话的 `accepted -> chunk -> state_patch -> done`
- 消息与会话快照落库
- 重连后快照恢复
- 展示文本中不再出现 `<config>`、`<json>` 或等价标签协议

### 7.3 端到端测试

- 新家庭初始化页面通过 WebSocket 完成多轮对话
- 刷新页面恢复历史消息
- 点击重新开始后生成新会话并废弃旧会话
- 连续多轮对话不再出现挂起和串轮次

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2、§3.3 | WebSocket 建连与事件协议测试 |
| `requirements.md` 需求 2 | `design.md` §2.3、§4.2、§6.1 | 多轮实时对话集成测试 |
| `requirements.md` 需求 3 | `design.md` §3.2、§4.1、§6.2 | 刷新恢复和快照接口测试 |
| `requirements.md` 需求 4 | `design.md` §2.3.3、§5.3、§6.2 | 断线重连恢复测试 |
| `requirements.md` 需求 5 | `design.md` §3.3.2、§3.3.3 | HTTP 兼容接口测试 |
| `requirements.md` 需求 2.1 | `design.md` §2.1.1、§2.3.2、§3.3.5、§6.4 | 结构化输出与去标签协议测试 |

## 8. 风险与待确认项

### 8.1 风险

- 现有 `llm_task` 流读取层本身还有编码和结束语义问题，迁移时必须顺手收口
- WebSocket 加入后，如果连接管理和 session 归属没收紧，容易引入新的并发问题
- 前端如果继续保留过多本地状态推断，会再次和服务端快照打架

### 8.2 待确认项

- 后续实时能力是否直接共用这条通道，还是先按模块拆子命名空间
- 是否需要为后台执行中的长任务增加事件重放接口，而不只靠快照
