# 设计文档 - 事件循环与后台任务阻塞治理

状态：IN_REVIEW

## 1. 概述

### 1.1 目标

- 把“主事件循环能做什么、不能做什么”说清楚，不再靠个人感觉。
- 把 Telegram 轮询、插件任务、调度任务这些后台循环收口成统一执行模型。
- 把同步数据库、同步网络调用、插件执行这类高风险阻塞点隔离出去。
- 让故障处理、测试验证和后续排障有统一入口。

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4

### 1.3 技术约束

- 后端目前以 FastAPI + `asyncio` 为主，但项目里仍存在同步 ORM、同步网络调用和同步插件执行。
- 这次治理优先收口执行边界，不追求一次性把所有依赖替换成纯异步实现。
- 不能为了治理阻塞问题引入一套过重的新框架，优先用现有应用结构能承受的简单方案。
- 任何治理都不能破坏现有 API、WebSocket 和后台任务对外行为。

## 2. 架构

### 2.1 系统结构

这次治理围着四类执行面展开：

1. 请求入口
   - `async` HTTP endpoint
   - WebSocket handler
   - 应用启动/关闭生命周期协程
2. 常驻后台任务
   - Telegram 等通道轮询 worker
   - 插件 job worker
   - scheduler worker
3. 外部依赖调用
   - 同步 ORM
   - 同步 HTTP / SDK
   - 插件自定义代码
4. 统一治理层
   - 阻塞调用包装 helper
   - worker 运行模板
   - 超时 / 取消 / 重试 / 降级规则
   - 日志、健康检查和测试入口

核心原则很简单：

- 主事件循环只做快速协调，不做长时间阻塞。
- 会卡线程的逻辑必须显式下沉，不能假装它是异步的。
- worker 的生命周期、节拍、失败处理必须统一。

#### 2.1.1 哪些逻辑允许留在主事件循环

只允许下面这些轻量动作直接跑在主事件循环里：

- 请求参数解析、鉴权、权限判断、路由分发。
- WebSocket 收发消息、协议校验、连接注册和状态机切换。
- 把已经准备好的普通 Python 数据组装成响应体。
- 调用已经确认不会阻塞的 async API。

判断标准只有一条：这段逻辑必须能很快把控制权还给事件循环，不能偷偷做同步 I/O、长时间 CPU 计算，不能依赖 `time.sleep()` 这种硬阻塞。

#### 2.1.2 哪些逻辑必须下沉

下面这些逻辑一律不允许直接留在主事件循环里：

- 同步 ORM 查询、写入、事务提交、批量扫描。
- 同步 HTTP / SDK 调用，包括插件里包着的 `httpx.get/post`、轮询和重试。
- 插件执行、规则评估、上下文聚合这类已经确认可能走长链路的同步正文。
- 明显超过一次事件循环调度粒度的 CPU 计算。

这不是风格问题，是执行边界问题。只要代码会卡线程，就必须显式下沉。

#### 2.1.3 这轮采用的最小做法

这轮不做“大平台”，只收口两个公共入口：

- `run_blocking(...)`
  - 用来下沉同步网络调用、插件执行和其他普通阻塞函数。
- `run_blocking_db(...)`
  - 用来下沉需要同步 `Session` 的数据库逻辑，并且在线程里自己创建、提交、回滚和关闭 `Session`。

这两个入口解决的是一个真问题：别再让 async 入口和 worker 自己决定怎么切线程、怎么带 `Session`、怎么处理超时。更简单的方法没有了，再继续各写各的，只会继续复制坏味道。

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| async 入口守卫层 | 标记请求链路里的阻塞调用风险，决定是否下沉执行 | endpoint / WebSocket / 生命周期协程中的调用 | 直接执行或下沉后的 awaitable |
| 阻塞调用 helper | 统一包装同步 ORM、同步 HTTP、插件执行等慢操作 | 阻塞函数、超时、日志标签、取消上下文 | 可 await 的执行结果或受控异常 |
| worker 运行模板 | 统一后台循环的节拍、停止、超时、失败和健康状态 | 轮询函数、间隔、重试策略、依赖上下文 | 稳定的 worker 生命周期 |
| 通道适配层 | 处理 Telegram 等外部通道的拉取、发送和状态刷新 | 通道配置、网络请求、消息结果 | 通道任务结果和健康状态 |
| 观测与排障层 | 统一记录超时、重试、队列积压、连续失败等信号 | worker 运行信息、异常、耗时 | 日志、指标、健康快照、排障记录 |

### 2.3 关键流程

#### 2.3.1 `async` 请求主链路

1. HTTP endpoint、WebSocket handler 或生命周期协程进入主事件循环。
2. 代码先判断当前调用是否只做轻量协调。
3. 如果要访问同步 ORM、同步网络、插件执行或明显慢操作，就走统一阻塞调用 helper。
4. helper 负责在线程池中执行、绑定超时、写日志并把结果送回事件循环。
5. 主事件循环只等待受控结果，不直接承担阻塞细节。

#### 2.3.2 worker 单次 tick 流程

1. worker 按统一模板启动，注册名称、节拍、超时和停止信号。
2. 每次 tick 先读取运行上下文和健康状态。
3. tick 内的阻塞操作统一走 helper，下沉执行并受超时控制。
4. 如果 tick 成功，更新最近成功时间和耗时。
5. 如果 tick 失败，按策略记录日志、累计失败次数，并决定重试、跳过或短暂停用。
6. worker 进入下一轮前等待统一节拍，而不是自己乱睡眠。

这里有个不能破坏的现有行为：如果单次 tick 明确返回“刚处理了任务”，模板允许立刻进入下一轮，不强行插入额外等待。这样才不会把现有轮询和 job claim 吞吐量无端砍掉。

#### 2.3.3 外部通道故障隔离流程

1. Telegram 轮询或插件任务遇到网络超时、接口 5xx、SDK 卡住或插件逻辑长时间不返回。
2. worker 在受控超时内终止本次执行，记录依赖名称、耗时和失败原因。
3. 连续失败达到阈值后，worker 进入降级状态，例如跳过本轮、延长间隔或临时停用。
4. API / WebSocket 主链路继续运行，不因为该依赖故障一起被拖住。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4

- `BlockingCallPolicy`
  - 作用：描述某段逻辑是否允许直接跑在事件循环里，还是必须下沉执行。
- `run_blocking(...)`
  - 作用：统一包装同步调用，处理线程池下沉、超时、取消和日志。
- `WorkerRuntime`
  - 作用：统一后台 worker 的启动、停止、节拍、失败计数和健康状态。
- `WorkerHealthSnapshot`
  - 作用：记录 worker 最近成功时间、最近失败时间、失败次数、当前状态和最近耗时。
- `DegradationPolicy`
  - 作用：定义超时、连续失败和外部依赖异常时的跳过、重试或停用策略。

### 3.2 数据结构

覆盖需求：1、2、3

#### 3.2.1 `BlockingCallPolicy`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `label` | `str` | 是 | 调用标签，便于日志和排障 | 全局可读 |
| `kind` | `str` | 是 | 调用类型 | 仅允许 `sync_db`、`sync_network`、`plugin_code`、`cpu_bound` |
| `timeout_seconds` | `float` | 是 | 单次执行超时 | 必须大于 0 |
| `allow_retry` | `bool` | 是 | 是否允许自动重试 | 与重试策略联动 |
| `fallback_mode` | `str` | 否 | 超时后的降级方式 | 可为空 |

#### 3.2.2 `WorkerRuntimeConfig`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `worker_name` | `str` | 是 | worker 名称 | 进程内唯一 |
| `interval_seconds` | `float` | 是 | tick 间隔 | 必须大于 0 |
| `tick_timeout_seconds` | `float` | 是 | 单次 tick 最长执行时间 | 必须大于 0 |
| `max_consecutive_failures` | `int` | 是 | 连续失败阈值 | 必须大于等于 1 |
| `degrade_interval_seconds` | `float` | 否 | 降级后间隔 | 可为空 |
| `supports_pause` | `bool` | 是 | 是否允许临时停用 | 默认 `true` |

#### 3.2.3 `WorkerHealthSnapshot`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `worker_name` | `str` | 是 | worker 名称 | 与配置一致 |
| `state` | `str` | 是 | 当前状态 | `starting/running/degraded/paused/stopped` |
| `last_started_at` | `datetime` | 否 | 最近一次 tick 开始时间 | 可为空 |
| `last_succeeded_at` | `datetime` | 否 | 最近一次成功时间 | 可为空 |
| `last_failed_at` | `datetime` | 否 | 最近一次失败时间 | 可为空 |
| `consecutive_failures` | `int` | 是 | 连续失败次数 | 大于等于 0 |
| `last_duration_ms` | `float` | 否 | 最近一次耗时 | 可为空 |
| `last_error_summary` | `str` | 否 | 最近一次错误摘要 | 可为空 |

### 3.3 接口契约

覆盖需求：1、2、3

#### 3.3.1 阻塞调用包装接口

- 类型：Function
- 路径或标识：`run_blocking(callable, policy, *, cancellable=False, context=None)`
- 输入：
  - 一个同步 callable
  - `BlockingCallPolicy`
  - 可选取消上下文和日志上下文
- 输出：
  - callable 返回值
  - 或受控超时 / 下沉执行异常
- 校验：
  - 没有 `policy` 不允许直接调用
  - `timeout_seconds` 必须显式给出
  - 线程池下沉必须由统一入口处理
- 错误：
  - 超时
  - 线程池拥塞或执行失败
  - 调用被取消

##### 主事件循环边界规则

- 调用方必须先判断这段逻辑是不是同步阻塞；是的话，不能直接调，必须走 `run_blocking(...)` 或 `run_blocking_db(...)`。
- `policy.label` 必须写清楚链路位置，至少能让日志看出是哪个 endpoint、worker 或插件调用超时。
- 不允许把“只是先试试能不能直接跑”当方案。没有例外白名单，就默认下沉。

##### 线程池 Session 边界规则

- 请求作用域 `Session`、WebSocket 循环里的 `Session`、生命周期协程里的 `Session` 都不允许直接传进线程池。
- 线程池里的数据库逻辑只能接收线程内新建的 `Session`。
- 如果调用方需要把数据库结果带进线程池，必须先在主线程把它序列化成普通数据，或者先提交事务再下沉，不允许把半成品 ORM 对象和未提交事务一起带过去。
- 线程池任务内的事务提交、回滚和 `Session.close()` 由 `run_blocking_db(...)` 接管，不能再让调用方自己散着写。

#### 3.3.2 worker 运行模板接口

- 类型：Function / Class
- 路径或标识：`WorkerRuntime.run_forever(tick_fn, config, *, stop_event)`
- 输入：
  - 单次 tick 函数
  - `WorkerRuntimeConfig`
  - 停止信号
- 输出：
  - 循环执行结果和健康状态更新
- 校验：
  - tick 必须在统一超时内执行
  - 失败处理必须由模板接管
  - 自己写 `while True + sleep` 的 worker 需要迁移到统一模板
- 错误：
  - tick 超时
  - 未捕获依赖异常
  - 停止过程取消异常

##### 模板落地规则

- `tick_fn` 返回 `bool`，表示这一轮是否实际处理了任务。
- 返回 `True` 时，模板允许直接开始下一轮；返回 `False` 时，按 `interval_seconds` 等待。
- 达到连续失败阈值后，模板把状态切到 `degraded`，并使用 `degrade_interval_seconds`；没有显式降级间隔时，就退回普通轮询间隔。
- 健康状态先用进程内快照维护，这一轮不强行补管理接口。

#### 3.3.3 健康状态查询接口

- 类型：Function / HTTP（按项目现状择一）
- 路径或标识：worker 健康快照读取入口
- 输入：
  - worker 名称或全部 worker
- 输出：
  - `WorkerHealthSnapshot` 或快照列表
- 校验：
  - 至少包含状态、连续失败次数、最近成功时间
- 错误：
  - worker 未注册
  - 健康状态不可读

## 4. 数据与状态模型

### 4.1 数据关系

这里真正的关系只有三层：

1. 主事件循环
   - 负责调度和协调
2. 下沉执行层
   - 负责承接同步阻塞调用
3. 常驻 worker
   - 负责周期性任务，但每次 tick 仍然必须遵守下沉边界

关系重点：

- worker 不是“随便写个协程循环”。
- `async` 入口也不是“只要函数上写了 async 就安全”。
- 只要实际执行的是同步慢调用，就必须明确落到下沉执行层。

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `starting` | worker 刚启动 | 应用初始化或手动恢复 | 首次 tick 成功或失败 |
| `running` | worker 正常工作 | tick 连续成功或失败次数未超阈值 | 连续失败超阈值、暂停或停止 |
| `degraded` | worker 进入降级节拍或跳过模式 | 连续失败达到阈值 | 恢复成功、人工暂停或停止 |
| `paused` | worker 被临时停用 | 人工停用或自动保护 | 人工恢复或停止 |
| `stopped` | worker 已退出 | 应用关闭或显式停止 | 重新启动 |

## 5. 错误处理

### 5.1 错误类型

- 主循环阻塞风险：同步慢调用直接出现在 `async` 路径里。
- 下沉执行超时：线程池中的同步调用超过限制时间。
- 外部依赖错误：Telegram、插件依赖、第三方 API 返回错误或长时间无响应。
- worker 连续失败：同一个 worker 多次失败，已经从偶发抖动变成持续异常。
- 观测缺失：任务失败了，但日志和健康状态不足以判断原因。

### 5.2 错误响应格式

```json
{
  "worker": "telegram-polling",
  "state": "degraded",
  "error_code": "WORKER_TICK_TIMEOUT",
  "detail": "Telegram polling tick exceeded timeout and was skipped.",
  "timestamp": "2026-03-16T00:00:00Z"
}
```

### 5.3 处理策略

1. 主循环阻塞风险
   - 代码审查和测试一旦发现同步慢调用直接进入 `async` 路径，必须改成统一 helper 下沉执行。
2. 下沉执行超时
   - 超时后立即记录标签、耗时、依赖名称，并把本次 tick 记为失败。
3. 外部依赖错误
   - 用可控重试和退避，不允许无限等待或无限重试。
4. worker 连续失败
   - 达到阈值后切到降级状态，必要时允许暂停该 worker。
5. 观测缺失
   - 没有上下文日志和健康状态的实现视为不合格实现。

## 6. 正确性属性

### 6.1 主循环只做轻量协调

对于任何 `async` HTTP、WebSocket 或生命周期链路，系统都应该满足：只允许快速协调、状态转换和结果拼装直接运行在主事件循环里；同步慢调用必须显式下沉。

**验证需求：** `requirements.md` 需求 1

### 6.2 worker tick 必须有边界

对于任何后台 worker，系统都应该满足：每一轮 tick 都有明确的超时、失败计数和下一步策略，而不是无限挂住。

**验证需求：** `requirements.md` 需求 2、需求 3

### 6.3 局部故障不能扩散成全局阻塞

对于任何单个外部依赖故障，系统都应该满足：最多影响对应 worker 或对应能力的降级，不应拖垮 API 和 WebSocket 主链路。

**验证需求：** `requirements.md` 需求 1、需求 3

### 6.4 治理规则必须能被重复检查

对于任何未来新增的后台任务或 async 链路，系统都应该满足：可以通过公共 helper、测试和文档检查项判断它是否违反执行边界。

**验证需求：** `requirements.md` 需求 4

## 7. 测试策略

### 7.1 单元测试

- 验证阻塞调用 helper 会把同步函数下沉执行，并正确处理超时和取消。
- 验证 worker 运行模板对成功、失败、超时、降级状态的更新逻辑。
- 验证连续失败阈值和降级策略不会失控。

### 7.2 集成测试

- 验证 Telegram 轮询、插件 worker、scheduler worker 中的高风险调用已经接入统一 helper 或模板。
- 验证外部依赖超时后，worker 状态会进入受控降级，而 API / WebSocket 不会一起阻塞。
- 验证 async endpoint / WebSocket 链路中的同步 ORM 或同步网络调用已被显式隔离。

### 7.3 人工验收

- 断开或限速 Telegram 等外部通道依赖，观察 API 和 WebSocket 是否仍能正常响应。
- 人为制造单个 worker 超时，确认日志、健康状态和降级行为符合预期。
- 对照文档检查新增后台任务的实现是否还能一眼看清执行边界。

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` 2.1、2.3.1、6.1、6.3 | 集成测试 + 人工限速验证 |
| `requirements.md` 需求 2 | `design.md` 2.2、2.3.2、3.2、3.3、6.2 | 单元测试 + worker 代码审查 |
| `requirements.md` 需求 3 | `design.md` 2.3.3、5.3、6.3 | 集成测试 + 健康状态检查 |
| `requirements.md` 需求 4 | `design.md` 3.1、6.4、7.1、7.2、7.3 | 测试补齐 + 文档验收 |

## 8. 风险与待确认项

### 8.1 风险

- 项目里可能不止 Telegram 一条链路在偷偷做同步阻塞调用，盘点不全就会漏风险。
- 线程池下沉不是万能药，如果并发和连接池边界不控住，只是把阻塞从事件循环挪到别处。
- 插件代码如果完全不受控，哪怕下沉执行也可能长期占满资源，需要额外限流和停用策略。

### 8.2 待确认项

- 当前最容易拖慢主链路的路径到底是 Telegram 轮询、插件任务，还是某个 async endpoint 内的同步数据库访问。
- 现有项目是否已经有可复用的线程池或 worker 基类，还是需要最小化新增一层公共 helper。
- worker 健康状态是先落日志和内存快照，还是顺手补一个只读管理接口。

### 8.3 2026-03-16 盘点后补充结论

- `ChannelPollingWorker`、`ScheduledTaskWorker` 当前都是 async 外壳直接包同步 tick，阶段 2 不需要再争论“先盘点还是先抽象”，应直接为这类 worker 收口统一模板。
- `channel_gateway_webhook_endpoint`、`/realtime/agent-bootstrap`、`/realtime/conversation` 已经确认存在 async 入口直接混同步插件或同步 ORM，这些链路属于第一批治理对象，不再继续扩大到全部 endpoint。
- `aexecute_household_plugin` 和 `arun_plugin_sync_pipeline` 当前把调用方 `Session` 带进线程池，这是后续公共 helper 设计必须先解决的执行边界问题。
- scheduler 现状要分清：常驻 worker 目前负责“扫到期并创建 queued run”，`dispatch_task_run` 还没接成常驻执行链路，所以这轮先治理 tick 阻塞、超时、失败和健康状态，不重做整个调度系统。

### 8.4 2026-03-16 阶段 2 收口检查

- 现在已经有两类最小公共入口：
  - `run_blocking(...)`
  - `run_blocking_db(...)`
- 现在已经有统一 worker 骨架：
  - `WorkerRuntimeConfig`
  - `WorkerHealthSnapshot`
  - `WorkerRuntime`
- 现在已经完成的边界收口：
  - 插件异步包装不再把调用方 `Session` 直接带进线程池。
  - 通道轮询、scheduler、plugin job 三个常驻 worker 已经共用同一套启动、停止、节拍、tick 超时、失败计数和健康快照骨架。

结论很直接：阶段 2 需要的规则已经够支撑首批治理，不需要再发明新抽象。后面的 3.1、3.2、3.3 可以直接基于这套边界去改具体链路。

这也顺手回答三个问题：

- 这是真问题，不是假问题。前面的盘点已经把 P0/P1 链路钉死了。
- 有没有更简单的方法。有，就是现在这套最小 helper 加统一 runtime；再复杂就是过度设计。
- 会破坏什么吗。只要继续守住“主线程 `Session` 不进线程池、busy tick 不强插等待、不重写现有业务语义”这三条线，就不会破坏现有 API、WebSocket 和 webhook 行为。

### 8.5 2026-03-16 通道轮询 / 调度 / 插件 worker 落地补充

- `ChannelPollingWorker`
  - 当前已经把账户列表读取、单账户轮询、失败状态写回全部改成通过公共 helper 下沉。
  - 这样 Telegram 插件里的同步 HTTP 和 `time.sleep()` 重试不会再直接堵住主事件循环。
- `ScheduledTaskWorker`
  - 当前已经把整轮 `process_due_schedule_tick` / `process_due_heartbeat_tick` 下沉到线程内 `Session` 执行。
  - 这轮只治理 tick 阻塞，不碰 `dispatch_task_run` 的常驻执行链路。
- `PluginJobWorker`
  - 当前沿用已有 `to_thread` 执行插件本体，但循环骨架已经切到统一 runtime。
  - 这轮不重写 job 业务语义，只保证节拍、失败计数和健康状态不再各写各的。

结论：`3.1` 和 `3.2` 需要的“执行边界 + worker 模板”已经具备，下一步可以直接进入 async webhook / WebSocket 主链路治理。
