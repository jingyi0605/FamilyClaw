# 设计文档 - 计划任务系统

状态：Draft

## 1. 概述

### 1.1 目标

- 建一套项目内统一的计划任务系统，覆盖固定时间调度和心跳巡检
- 复用现有 `plugin_job` 体系做插件执行，不重复发明后台执行模型
- 给 Agent 主动提醒提供正式入口，但把风险边界收死
- 让家庭状态成为正式规则输入，而不是散落在各模块里的临时判断
- 让计划任务同时支持家庭公共归属和成员私有归属
- 给用户前端和对话入口都留出正式创建路径，而不是只给后台接口
- 保持第一版结构简单，先支撑单服务部署和家庭级配置

### 1.2 覆盖需求

- `requirements.md` 需求 1：统一计划任务定义和运行记录
- `requirements.md` 需求 1A：区分家庭公共任务和成员私有任务
- `requirements.md` 需求 1B：同时记录账号操作人和归属成员
- `requirements.md` 需求 2：支持固定时间调度和心跳巡检
- `requirements.md` 需求 2A：支持用户前端正式管理计划任务
- `requirements.md` 需求 2B：支持通过对话创建计划任务草稿
- `requirements.md` 需求 3：对接现有插件后台任务体系
- `requirements.md` 需求 4：驱动 Agent 主动提醒并限制风险
- `requirements.md` 需求 5：接入家庭状态规则判断
- `requirements.md` 需求 6：提供停用、限流、审计和异常收口能力

### 1.3 技术约束

- 后端：现有 `FastAPI` + `SQLAlchemy`
- 数据存储：现阶段主库仍为 `SQLite`，表结构变更必须走 Alembic
- 现有可复用模块：`plugin.job_service`、`plugin.job_worker`、`agent.service`、`context.service`、`realtime`
- 账号 / 成员约束：现有系统同时有 `accounts`、`account_member_bindings`、`members` 三层对象，计划任务不能只挂账号，也不能只挂家庭
- 运行约束：第一版按当前单服务进程模型设计，不假设外部消息队列和分布式调度器
- 安全约束：高风险动作插件和高风险 Agent 行为不能默认被计划任务自动放开

## 2. 架构

### 2.1 系统结构

第一版只拆 5 层，别做成“宇宙调度平台”。

1. **计划任务定义层**：保存家庭公共规则和成员私有规则，说明什么时候触发、触发后做什么、归谁管理。
2. **调度与心跳层**：负责找出“到点任务”和“该巡检任务”。
3. **规则评估层**：对心跳类任务读取家庭状态并判断是否命中。
4. **执行分发层**：把运行记录分发给插件后台任务、Agent 提醒或系统通知。
5. **观测与控制层**：负责启停、异常标记、审计、运行查询和冷却抑制。

整体数据流如下：

1. 管理端、用户前端或对话确认入口创建 `ScheduledTaskDefinition`。
2. 调度器按 `next_run_at` 找到到期任务；心跳器按 `next_heartbeat_at` 找到要巡检的任务。
3. 如果是心跳任务，规则评估器通过家庭状态服务读取上下文并判断是否命中。
4. 命中后创建 `ScheduledTaskRun`，生成幂等键并进入 `queued`。
5. 执行分发器按目标类型分发：
   - 插件目标 -> 创建 `plugin_job`
   - Agent 提醒目标 -> 创建提醒投递记录 / 实时事件
   - 系统通知目标 -> 走统一通知出口
6. 运行结果回写 `ScheduledTaskRun`，并刷新 `ScheduledTaskDefinition` 的下一次时间、最近结果和失败计数。

还要补一条用户入口规则：

- 表单创建和对话创建都不直接绕开 `ScheduledTaskService`
- 对话入口只负责“把人话收成草稿”，正式创建仍走统一校验和落库逻辑

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `scheduler` 模块 | 管理任务定义、到期扫描、心跳扫描、执行分发 | 家庭级任务配置、当前时间 | 运行记录、执行结果 |
| `plugin` 适配器 | 把计划任务运行转成 `plugin_job` | 任务运行、插件目标参数 | `plugin_job` 记录 |
| `agent` 适配器 | 把计划任务运行转成 Agent 主动提醒 | 任务运行、Agent 提醒参数 | 提醒事件、投递记录 |
| `context` 规则输入 | 提供家庭状态概览和关键 insight | `household_id` | `ContextOverviewRead` |
| `conversation` 草稿解析入口 | 把自然语言计划任务请求转成结构化草稿 | 对话文本、当前账号、当前成员 | 任务草稿、缺失字段 |
| `user-web` 管理入口 | 展示我的任务、家庭任务、运行记录和创建表单 | 计划任务接口、当前登录态 | 管理页面、创建确认 |
| `realtime` / 通知出口 | 把运行结果发给前端或提醒中心 | 运行状态变化、提醒载荷 | WebSocket 事件、通知记录 |

### 2.3 关键流程

#### 2.3.1 固定时间任务触发

1. 调度器批量读取 `enabled=true` 且 `next_run_at <= now` 的任务定义。
2. 为每条任务定义生成稳定的运行窗口幂等键，例如 `task_id + scheduled_for`。
3. 如果该窗口已有运行记录，直接跳过，避免重复触发。
4. 创建 `ScheduledTaskRun(status=queued)`。
5. 分发器按目标类型执行。
6. 成功或失败后回写运行状态，并计算该定义下一次 `next_run_at`。

#### 2.3.2 心跳巡检任务触发

1. 心跳器批量读取 `trigger_type=heartbeat` 且 `next_heartbeat_at <= now` 的任务定义。
2. 规则评估器读取家庭状态输入，第一版统一通过 `context.service.build_context_overview` 的正式读模型。
3. 规则评估器生成 `RuleEvaluationResult`：`matched / skipped / suppressed / error`。
4. 如果命中且未处于冷却窗口，创建 `ScheduledTaskRun` 并进入分发。
5. 如果未命中，只更新最近巡检时间和下一次 `next_heartbeat_at`。
6. 如果命中但处于安静时段或访客模式抑制规则，则记录 `suppressed`，不创建提醒执行。

#### 2.3.3 插件型计划任务执行

1. 分发器识别目标类型为 `plugin_job`。
2. 校验对应插件已注册、已启用，且 manifest 允许 `schedule` 触发。
3. 生成 `PluginExecutionRequest(trigger="schedule")`。
4. 调用现有 `enqueue_household_plugin_job` 创建正式插件后台任务。
5. 将 `plugin_job_id` 回写到 `ScheduledTaskRun.target_run_id`。
6. 后续由现有插件 worker 继续执行，计划任务运行只跟踪其最终结果摘要。

#### 2.3.4 Agent 主动提醒执行

1. 分发器识别目标类型为 `agent_reminder`。
2. 通过 `agent.service.resolve_effective_agent` 或指定 `agent_id` 找到目标 Agent。
3. 结合模板参数、家庭状态摘要和任务上下文生成提醒载荷。
4. 写入提醒记录并走现有实时推送 / 会话入口的受控通知出口。
5. 回写投递状态、摘要和去重键。

第一版限制：

- 只允许“提醒”和“低风险建议”两类 Agent 主动输出
- 不允许计划任务直接驱动高风险动作型 Agent 自动执行

#### 2.3.5 插件声明与家庭级启用流程

1. 插件 manifest 继续使用现有 `triggers` 字段。
2. 如果插件要被计划任务触发，manifest 必须包含 `schedule`。
3. 插件可以额外声明推荐的计划任务模板，但模板只是建议，不等于自动启用。
4. 真正生效的计划任务定义仍然按家庭维度落库。
5. 插件被禁用、卸载或失效时，对应计划任务定义进入 `invalid_dependency` 或自动停用状态。

这里必须把边界说死：

- 插件声明“能被 schedule 触发”只是资格，不是自动开跑许可
- 家庭没有显式启用前，插件不能自己给系统塞定时任务

#### 2.3.6 对话创建计划任务

1. 用户在聊天或助手入口说出明确意图，比如“每天晚上九点提醒我吃药”。
2. 对话侧先把请求解析为 `ScheduledTaskDraft`，包括触发方式、目标类型、归属对象、提醒内容等字段。
3. 如果缺少关键字段，比如时区、归属成员、提醒对象、执行目标，对话侧继续追问。
4. 草稿完整后，系统给出结构化确认卡片或确认文本。
5. 用户确认后，调用正式 `ScheduledTaskService.create_task(...)` 落库。
6. 如果是跨成员创建、家庭公共任务创建或高风险执行目标，先走权限和风险校验，不通过就拒绝创建。

这一步必须收住边界：

- 对话创建不是直接执行器，它只是更自然的录入入口
- 没确认前只是一份草稿，不是正式任务

#### 2.3.7 用户前端管理计划任务

1. 计划任务管理入口挂到家庭记忆面板里，作为和“记忆”并列的标签页，不再单独塞进设置体系。
2. 前端进入家庭记忆面板后，先按当前账号拿“我的成员任务”和“家庭公共任务”。
3. 成员默认只能改自己的任务；管理员额外能切换查看其他成员任务。
4. 创建页先选任务归属：家庭公共 / 我的任务 / 代某成员创建（仅管理员）。
5. 编辑页展示下一次执行时间、最近一次运行结果、失败原因和启停状态。
6. 对话创建成功后，前端也能在同一面板里的“计划任务”标签页看到新任务，不另造第二套管理入口。

这么放的原因也很直接：

- 计划任务和家庭记忆、提醒、长期事实是同一类“家庭长期管理信息”
- 放进设置页太像系统配置，不像家庭运营面板
- 放进家庭记忆面板更符合用户心智：这里不只是看过去记住了什么，也能看未来要主动做什么

##### 2.3.7.1 标签页结构

家庭记忆面板第一版建议改成双主标签，不要一上来做太多层级。

主标签：

1. `记忆`
2. `计划任务`

其中 `计划任务` 标签页内再做轻量二级视图：

- `我的任务`
- `家庭任务`
- `成员切换`（仅管理员可见，不单独做成第三主标签）

这样设计的原因：

- 主标签只保留两项，切换成本低
- 普通成员最常用的是“我的任务”，不该被管理员视角污染
- 管理员的“看其他成员任务”属于增强操作，不该占掉普通用户主路径

##### 2.3.7.2 页面区块布局

`计划任务` 标签页内建议按“上方总览 + 中间列表 + 右侧详情”布局，尽量复用现有 `MemoriesPage` 的浏览习惯。

建议区块如下：

1. **面板头部**
   - 标题：`计划任务`
   - 副标题：说明这里管理家庭未来要主动执行和提醒的事项
   - 主按钮：`新建任务`
   - 次按钮：`从对话创建` 或 `去聊天创建`

2. **摘要条**
   - 我的任务数
   - 家庭任务数
   - 今日待执行数
   - 最近失败数

3. **视图切换条**
   - `我的任务`
   - `家庭任务`
   - 管理员可见成员选择器

4. **筛选和搜索条**
   - 关键词搜索
   - 状态筛选
   - 触发方式筛选
   - 目标类型筛选

5. **任务列表区**
   - 每行显示：名称、归属、触发方式、下一次执行、最近结果、启停状态
   - 支持快速启停
   - 支持点击进入详情

6. **详情抽屉或右侧详情区**
   - 基本信息
   - 执行配置
   - 运行记录
   - 最近失败原因
   - 编辑 / 停用 / 复制任务

7. **空态区**
   - 我的任务为空：引导创建个人提醒
   - 家庭任务为空：引导管理员创建公共计划

第一版不建议做的东西：

- 复杂日历视图
- 拖拽式时间轴
- 多列看板式编排

##### 2.3.7.3 与记忆页共用的头部和筛选规则

家庭记忆面板不要拆成两套完全不同的页面壳子，第一版建议复用这些共用区域：

- 共用家庭选择上下文
- 共用页面级标题区域
- 共用顶部搜索框位置
- 共用右侧详情抽屉交互模式

但不要强行共用这些东西：

- 不共用完全相同的筛选项
- 不共用同一个列表字段定义
- 不把记忆的可见性、修订状态硬套到计划任务上

更具体地说：

可共用的头部能力：

- 家庭切换
- 搜索输入框位置
- 新建按钮位置
- 空态样式

需要按标签页切换的筛选项：

- `记忆` 标签页：类型、可见性、状态、时间范围
- `计划任务` 标签页：归属范围、触发方式、任务状态、目标类型

共享规则建议：

1. 搜索框位置不变，但搜索语义跟随当前标签页变化。
2. 头部操作区位置不变，但按钮文案按标签页变化。
3. 详情面板交互保持一致，这样用户不用重新学习第二套操作方式。

##### 2.3.7.4 前端实现约束

前端实现时必须守住两个规则，不要做出一眼就像后台工具的页面。

1. **UI 风格必须和当前主题保持一致**
   - 沿用当前 `MemoriesPage` 已有的页面结构、卡片层次、间距节奏和交互习惯
   - 不要单独给计划任务标签页发明一套完全不同的色彩、按钮、面板或列表语言
   - 如果家庭记忆面板当前已经有固定标题区、列表区、详情抽屉样式，计划任务页优先复用

2. **文案必须完全站在用户视角**
   - 页面上不要出现“调度器”“worker”“cron 表达式”“任务分发器”“运行快照”这种工程实现词
   - 不要出现“开发中”“供调试”“内部状态”“系统链路”这种开发视角提示
   - 同一个字段如果后端叫 `heartbeat`，前端也要翻成用户看得懂的话，比如“定期检查”或“按状态检查”

3. **前端说明文字的基本原则**
   - 优先解释“这会为你做什么”，不要解释“系统内部怎么实现”
   - 优先写“下次什么时候提醒你”“最近一次结果怎样”，不要写“最近一次调度窗口”
   - 错误提示优先说用户要怎么处理，不要直接扔后端术语

示例对照：

- 不推荐：`任务调度失败，请检查 worker 日志`
- 推荐：`这条计划暂时没有执行成功，你可以稍后重试或调整设置`
- 不推荐：`heartbeat 规则未命中`
- 推荐：`这次定期检查没有触发提醒`

##### 2.3.7.5 计划任务标签页用户文案样例

下面这些不是最终 UI 定稿，但它们代表第一版该坚持的语言方向。

**页面标题与说明**

- 页面标题：`计划任务`
- 页面说明：`把你想定期提醒、定期检查和自动处理的事情放在这里。`
- 家庭任务说明：`家庭任务会影响全家可见或全家共用的安排。`
- 我的任务说明：`我的任务只管理和我有关的提醒与安排。`

**标签与视图文案**

- 主标签：`记忆` / `计划任务`
- 次级视图：`我的任务` / `家庭任务`
- 管理员成员切换占位：`查看成员任务`

**按钮文案**

- `新建任务`
- `从对话创建`
- `暂停任务`
- `恢复任务`
- `查看详情`
- `复制任务`
- `保存修改`

**列表字段文案**

- `下次时间`
- `最近结果`
- `提醒方式`
- `归属`
- `状态`

不要用这些文案：

- `调度窗口`
- `执行器`
- `心跳规则`
- `运行快照`

**空态文案**

- 我的任务为空：`你还没有计划任务。现在创建一个，按你想要的时间提醒自己。`
- 家庭任务为空：`这个家还没有公共计划任务。你可以先加一个每天都会用到的提醒。`
- 搜索无结果：`没有找到符合条件的计划任务，试试换个关键词。`

**状态文案**

- `进行中` 不用，改成 `已开启`
- `paused` 前端显示：`已暂停`
- `active` 前端显示：`已开启`
- `error` 前端显示：`需要处理`
- `invalid_dependency` 前端显示：`暂时无法执行`

**结果文案**

- 成功：`已按计划完成`
- 抑制：`这次没有发出提醒`
- 失败：`这次没有成功，你可以稍后再试`
- 等待下次：`下次会继续按计划执行`

**错误提示文案**

- 创建失败：`这条计划还没有保存成功，请检查时间和提醒对象后再试一次。`
- 权限不足：`这条计划不属于你，暂时不能修改。`
- 依赖失效：`这条计划现在用不到原来的服务了，请重新选择提醒方式或目标。`
- 对话草稿未确认：`这条计划还在确认中，确认后才会正式生效。`

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、1A、1B、2、2A、2B、3、4、5、6

- `ScheduledTaskService`：计划任务定义的增删改查、启停、下一次时间计算
- `ScheduledTaskOwnershipService`：处理账号、成员、家庭三者之间的归属校验和默认推导
- `ScheduledTaskHeartbeatService`：心跳任务批量巡检和规则评估
- `ScheduledTaskDispatcher`：根据目标类型执行分发
- `PluginScheduleAdapter`：把运行记录转成 `plugin_job`
- `AgentReminderAdapter`：把运行记录转成 Agent 主动提醒
- `TaskRuleEvaluator`：读取家庭状态并执行规则判断、冷却判断、抑制判断
- `ScheduledTaskDraftService`：处理对话入口的草稿解析、补字段和确认前校验

### 3.2 数据结构

覆盖需求：1、1A、1B、2、2A、2B、3、4、5、6

#### 3.2.1 `ScheduledTaskDefinition`

建议新建 `scheduled_task_definitions`。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 主键 | UUID |
| `household_id` | `text` | 是 | 所属家庭 | 非空 |
| `owner_scope` | `varchar(32)` | 是 | `household` / `member` | 非空 |
| `owner_member_id` | `text` | 否 | 归属成员 id | `owner_scope=member` 时必填 |
| `created_by_account_id` | `text` | 是 | 创建账号 | 非空 |
| `last_modified_by_account_id` | `text` | 是 | 最后修改账号 | 非空 |
| `code` | `varchar(64)` | 是 | 家庭内稳定编码 | `(household_id, code)` 唯一 |
| `name` | `varchar(100)` | 是 | 任务名称 | 非空 |
| `description` | `varchar(255)` | 否 | 人话说明 | 可空 |
| `trigger_type` | `varchar(32)` | 是 | `schedule` / `heartbeat` | 非空 |
| `schedule_type` | `varchar(32)` | 否 | `cron` / `interval` / `daily` | 仅 `schedule` 使用 |
| `schedule_expr` | `varchar(128)` | 否 | cron 或间隔表达式 | 仅 `schedule` 使用 |
| `heartbeat_interval_seconds` | `int` | 否 | 心跳频率 | 仅 `heartbeat` 使用 |
| `timezone` | `varchar(64)` | 是 | 计算时区 | 默认家庭时区 |
| `target_type` | `varchar(32)` | 是 | `plugin_job` / `agent_reminder` / `system_notice` | 非空 |
| `target_ref_id` | `varchar(100)` | 否 | 插件 id / agent id / 通知模板 id | 按目标类型解释 |
| `rule_type` | `varchar(32)` | 否 | `none` / `context_insight` / `presence` / `device_summary` | 心跳任务使用 |
| `rule_config_json` | `text` | 否 | 规则参数 | JSON |
| `payload_template_json` | `text` | 否 | 执行参数模板 | JSON |
| `cooldown_seconds` | `int` | 是 | 冷却窗口 | 默认 0 |
| `quiet_hours_policy` | `varchar(32)` | 是 | `allow` / `suppress` / `delay` | 默认 `suppress` |
| `enabled` | `bool` | 是 | 是否启用 | 默认 `true` |
| `status` | `varchar(32)` | 是 | `active` / `paused` / `error` / `invalid_dependency` | 非空 |
| `last_run_at` | `text` | 否 | 最近一次运行时间 | ISO 时间 |
| `last_result` | `varchar(32)` | 否 | 最近一次结果摘要 | 可空 |
| `consecutive_failures` | `int` | 是 | 连续失败次数 | 默认 0 |
| `next_run_at` | `text` | 否 | 下次固定调度时间 | `schedule` 使用 |
| `next_heartbeat_at` | `text` | 否 | 下次心跳时间 | `heartbeat` 使用 |
| `created_at` | `text` | 是 | 创建时间 | ISO 时间 |
| `updated_at` | `text` | 是 | 更新时间 | ISO 时间 |

关键约束：

- 同一家庭内 `code` 唯一
- `owner_scope=member` 时必须存在 `owner_member_id`
- `owner_scope=household` 时 `owner_member_id` 必须为空
- `schedule` 和 `heartbeat` 字段不能混用脏写
- 不能启用没有目标引用或依赖失效的任务定义

#### 3.2.2 `ScheduledTaskRun`

建议新建 `scheduled_task_runs`。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 主键 | UUID |
| `task_definition_id` | `text` | 是 | 所属定义 | 外键 |
| `household_id` | `text` | 是 | 所属家庭 | 非空 |
| `owner_scope` | `varchar(32)` | 是 | 触发时的归属范围快照 | 非空 |
| `owner_member_id` | `text` | 否 | 触发时的归属成员快照 | 可空 |
| `trigger_source` | `varchar(32)` | 是 | `schedule` / `heartbeat` / `manual_retry` | 非空 |
| `scheduled_for` | `text` | 否 | 计划命中时间 | ISO 时间 |
| `status` | `varchar(32)` | 是 | `queued` / `dispatching` / `succeeded` / `failed` / `skipped` / `suppressed` | 非空 |
| `idempotency_key` | `varchar(128)` | 是 | 运行幂等键 | 唯一 |
| `evaluation_snapshot_json` | `text` | 否 | 规则命中摘要 | JSON |
| `dispatch_payload_json` | `text` | 否 | 实际分发载荷 | JSON |
| `target_type` | `varchar(32)` | 是 | 执行目标类型 | 非空 |
| `target_ref_id` | `varchar(100)` | 否 | 目标对象 id | 可空 |
| `target_run_id` | `varchar(100)` | 否 | 关联的 `plugin_job_id` 等 | 可空 |
| `error_code` | `varchar(64)` | 否 | 失败码 | 可空 |
| `error_message` | `varchar(255)` | 否 | 失败说明 | 可空 |
| `started_at` | `text` | 否 | 开始时间 | ISO 时间 |
| `finished_at` | `text` | 否 | 结束时间 | ISO 时间 |
| `created_at` | `text` | 是 | 创建时间 | ISO 时间 |

#### 3.2.3 `ScheduledTaskDelivery`

建议新建 `scheduled_task_deliveries`，用来记录提醒或通知投递。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 主键 | UUID |
| `task_run_id` | `text` | 是 | 关联运行 | 外键 |
| `channel` | `varchar(32)` | 是 | `websocket` / `in_app` / `conversation_entry` | 非空 |
| `recipient_type` | `varchar(32)` | 是 | `household` / `member` / `agent` | 非空 |
| `recipient_ref` | `varchar(100)` | 否 | 接收对象 id | 可空 |
| `status` | `varchar(32)` | 是 | `pending` / `delivered` / `failed` | 非空 |
| `payload_json` | `text` | 否 | 投递内容 | JSON |
| `delivered_at` | `text` | 否 | 投递时间 | ISO 时间 |
| `error_message` | `varchar(255)` | 否 | 投递失败原因 | 可空 |

#### 3.2.4 `ScheduledTaskTemplate`

这不是运行必须表，但建议预留，方便插件和系统种子任务提供家庭级模板。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 主键 | UUID |
| `source_type` | `varchar(32)` | 是 | `builtin` / `plugin` | 非空 |
| `source_ref_id` | `varchar(100)` | 是 | 内置模板 code 或插件 id | 非空 |
| `template_code` | `varchar(64)` | 是 | 模板编码 | 唯一 |
| `default_definition_json` | `text` | 是 | 默认任务定义片段 | JSON |
| `enabled_by_default` | `bool` | 是 | 是否默认启用 | 默认 `false` |

#### 3.2.5 `ScheduledTaskDraft`

这不是持久化主表，第一版可以先落会话态或短期缓存对象，但结构要先定清楚。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `draft_id` | `text` | 是 | 草稿 id | UUID |
| `household_id` | `text` | 是 | 当前家庭 | 非空 |
| `creator_account_id` | `text` | 是 | 发起对话的账号 | 非空 |
| `owner_scope` | `varchar(32)` | 否 | 草稿归属 | `household` / `member` |
| `owner_member_id` | `text` | 否 | 草稿归属成员 | 可空 |
| `intent_summary` | `varchar(255)` | 是 | 从人话抽出的意图摘要 | 非空 |
| `missing_fields_json` | `text` | 否 | 还缺哪些字段 | JSON |
| `draft_payload_json` | `text` | 否 | 已解析的结构化草稿 | JSON |
| `status` | `varchar(32)` | 是 | `drafting` / `awaiting_confirm` / `confirmed` / `cancelled` | 非空 |

### 3.3 接口契约

覆盖需求：1、1A、1B、2、2A、2B、3、4、5、6

#### 3.3.1 `POST /scheduled-tasks`

- 类型：HTTP
- 路径或标识：`/scheduled-tasks`
- 输入：家庭级或成员级任务定义请求体
- 输出：创建后的 `ScheduledTaskDefinition`
- 校验：
  - `trigger_type=schedule` 时必须提供合法调度配置
  - `trigger_type=heartbeat` 时必须提供心跳频率和规则配置
  - `target_type=plugin_job` 时必须校验插件存在、已启用且支持 `schedule`
  - `target_type=agent_reminder` 时必须校验 Agent 存在或可推导
  - `owner_scope=member` 时必须校验当前账号与目标成员关系
  - `owner_scope=household` 时必须校验当前账号是否有创建家庭公共任务的权限
- 错误：依赖对象不存在、调度表达式非法、规则配置非法、插件不支持计划触发、归属权限不足

#### 3.3.2 `GET /scheduled-tasks`

- 类型：HTTP
- 路径或标识：`/scheduled-tasks`
- 输入：`household_id`、`owner_scope?`、`owner_member_id?`、`enabled?`、`trigger_type?`、`target_type?`、`status?`
- 输出：计划任务定义列表
- 校验：沿用家庭访问权限，并按账号自动过滤不该看到的成员私有任务
- 错误：家庭不存在、无权限

#### 3.3.3 `PATCH /scheduled-tasks/{task_id}`

- 类型：HTTP
- 路径或标识：`/scheduled-tasks/{task_id}`
- 输入：局部更新字段，如启停、冷却时间、规则参数、调度时间
- 输出：更新后的任务定义
- 校验：修改后仍需通过完整配置校验和归属权限校验
- 错误：任务不存在、依赖失效、字段组合非法、归属权限不足

#### 3.3.4 `GET /scheduled-task-runs`

- 类型：HTTP
- 路径或标识：`/scheduled-task-runs`
- 输入：`household_id`、`task_definition_id?`、`owner_scope?`、`owner_member_id?`、`status?`、`created_from?`、`created_to?`
- 输出：运行记录列表
- 校验：沿用家庭访问权限，并按账号自动过滤不该看到的成员私有任务运行记录
- 错误：家庭不存在、无权限

#### 3.3.5 内部服务：`scheduler.tick_due_tasks(now)`

- 类型：Function / Service
- 路径或标识：`scheduler.tick_due_tasks(now)`
- 输入：当前时间、批量大小
- 输出：本轮处理的任务定义数、创建的运行数、跳过数、失败数
- 校验：只处理已启用且依赖正常的任务
- 错误：调度计算失败、批量分发失败

#### 3.3.6 内部服务：`scheduler.tick_heartbeat(now)`

- 类型：Function / Service
- 路径或标识：`scheduler.tick_heartbeat(now)`
- 输入：当前时间、批量大小
- 输出：巡检数量、命中数量、抑制数量、失败数量
- 校验：心跳频率必须大于最小阈值，避免极端高频巡检
- 错误：规则读取失败、上下文读取失败、评估异常

#### 3.3.7 内部适配器：`scheduler.dispatch_run(task_run_id)`

- 类型：Function / Service
- 路径或标识：`scheduler.dispatch_run(task_run_id)`
- 输入：计划任务运行 id
- 输出：目标执行结果摘要
- 校验：运行状态必须是 `queued`
- 错误：目标依赖不存在、目标分发失败、重复分发

#### 3.3.8 `POST /scheduled-task-drafts/from-conversation`

- 类型：HTTP / 内部会话入口
- 路径或标识：`/scheduled-task-drafts/from-conversation`
- 输入：自然语言文本、当前会话上下文、可选草稿 id
- 输出：结构化草稿、缺失字段、是否可确认
- 校验：只允许登录用户发起；归属成员默认按账号绑定推导
- 错误：意图不明确、跨成员权限不足、草稿结构非法

#### 3.3.9 `POST /scheduled-task-drafts/{draft_id}/confirm`

- 类型：HTTP / 内部会话入口
- 路径或标识：`/scheduled-task-drafts/{draft_id}/confirm`
- 输入：确认动作、可选补充字段
- 输出：正式任务定义
- 校验：草稿必须完整且仍属于当前账号可操作范围
- 错误：草稿过期、字段仍缺失、权限不足、正式创建失败

## 4. 数据与状态模型

### 4.1 数据关系

- 一个 `Household` 可以有多条 `ScheduledTaskDefinition`
- 一个 `Member` 可以有多条成员私有 `ScheduledTaskDefinition`
- 一个 `Account` 可以创建多条计划任务，但创建者和归属成员不是同一个概念
- 一条 `ScheduledTaskDefinition` 可以有多条 `ScheduledTaskRun`
- 一条 `ScheduledTaskRun` 最多关联一个下游目标运行，例如一个 `plugin_job`
- 一条 `ScheduledTaskRun` 可以有多条 `ScheduledTaskDelivery`
- `plugin_job` 是下游执行目标，不替代计划任务运行主记录

这样拆的原因很简单：

- 计划任务系统关心“为什么主动触发”
- 权限层还要关心“这条任务到底是谁的”
- 插件后台任务系统关心“插件怎么执行”
- 这几件事有关联，但不是一回事，硬揉在一起迟早出脏状态

更具体一点：

- `created_by_account_id` 解决“是谁操作的”
- `owner_member_id` 解决“这条任务归谁”
- `owner_scope=household` 解决“这是全家公共任务，不属于某个单独成员”

### 4.2 状态流转

#### 4.2.1 任务定义状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `active` | 可正常参与调度 | 创建成功且依赖完整 | 被暂停、依赖失效、连续失败过多 |
| `paused` | 人工停用 | 管理员停用 | 再次启用 |
| `error` | 连续失败或配置异常 | 调度计算失败、执行长期失败 | 修复后重置 |
| `invalid_dependency` | 依赖对象失效 | 插件被禁用、Agent 不存在、模板失效 | 依赖恢复或修改配置 |

#### 4.2.2 任务运行状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `queued` | 已创建，待分发 | 调度或心跳命中 | 分发开始 |
| `dispatching` | 正在向目标执行器分发 | 开始调用适配器 | 成功、失败 |
| `succeeded` | 分发成功且已拿到结果引用 | 下游创建成功或提醒投递成功 | 终态 |
| `failed` | 分发失败或依赖错误 | 下游创建失败、参数错误 | 手工重试或终态保留 |
| `skipped` | 本轮明确跳过 | 幂等命中、依赖停用、重复窗口 | 终态 |
| `suppressed` | 规则命中但因冷却或抑制条件不执行 | 冷却窗口、安静时段、访客模式等 | 终态 |

### 4.3 归属与权限规则

#### 4.3.1 家庭公共任务

- 面向整个家庭生效
- 默认只有管理员或具备家庭管理权限的账号可创建和修改
- 运行记录对有家庭管理权限的人可见

#### 4.3.2 成员私有任务

- 只归属于某个成员
- 默认该成员绑定账号可创建、查看、修改自己的任务
- 管理员可以代成员创建、修改或停用
- 普通成员不能查看或编辑其他成员私有任务

#### 4.3.3 账号与成员的关系处理

- 优先使用 `account_member_bindings` 推导当前账号默认归属成员
- 如果账号没有成员绑定，只允许创建家庭公共草稿或要求先明确绑定关系
- 任何需要跨成员创建的操作都必须走管理员权限校验

### 4.4 规则模型

第一版只支持少量正式规则类型，别开放成任意表达式引擎。

#### 4.4.1 `context_insight`

- 直接消费 `ContextOverviewRead.insights`
- 规则示例：命中 `offline_devices`、`child_protection_disabled`、`elder_care_disabled`

#### 4.4.2 `presence`

- 消费 `member_states` 和 `active_member`
- 规则示例：有儿童在家、无人在家、指定成员回家、老人独自在家

#### 4.4.3 `device_summary`

- 消费 `device_summary`
- 规则示例：离线设备数大于阈值、可控设备在线数低于阈值

第一版不做：

- 任意脚本规则
- 跨多天统计规则
- 多家庭联合规则

## 5. 错误处理

### 5.1 错误类型

- `scheduled_task_invalid_config`：计划任务配置不合法
- `scheduled_task_dependency_missing`：目标插件、Agent 或模板不存在
- `scheduled_task_duplicate_window`：当前窗口已存在等价运行
- `scheduled_task_rule_eval_failed`：规则评估失败
- `scheduled_task_dispatch_failed`：分发到目标执行器失败
- `scheduled_task_dependency_blocked`：依赖对象存在但当前不可执行，比如插件已禁用
- `scheduled_task_owner_forbidden`：当前账号无权操作该成员或家庭范围的任务
- `scheduled_task_owner_missing`：成员私有任务缺少明确归属成员
- `scheduled_task_draft_incomplete`：对话草稿还缺关键字段，不能确认创建

### 5.2 错误响应格式

```json
{
  "detail": "当前计划任务依赖的插件已禁用，不能继续启用调度。",
  "error_code": "scheduled_task_dependency_blocked",
  "field": "target_ref_id",
  "timestamp": "2026-03-14T00:00:00Z"
}
```

### 5.3 处理策略

1. 输入配置错误：创建或更新时直接拒绝，不允许脏规则入库。
2. 依赖失效错误：任务定义进入 `invalid_dependency`，停止后续触发。
3. 调度重复错误：使用幂等键收口成 `skipped`，不算真正失败。
4. 规则抑制错误：命中安静时段或冷却窗口时记为 `suppressed`，不升为异常。
5. 下游分发错误：运行记录进入 `failed`，并累计定义级失败次数；超过阈值后把定义标为 `error`。
6. 归属权限错误：直接拒绝创建或修改，不允许先落脏数据后再补权限。
7. 草稿不完整：继续停留在草稿态，由对话入口追问，不进入正式创建。

## 6. 正确性属性

### 6.1 属性 1：同一窗口内不能重复创建等价运行

*对于任何* 一条任务定义和一个确定的调度窗口，系统都应该满足：最多只存在一条有效的计划任务运行记录。

**验证需求：** `requirements.md` 需求 1、需求 2、需求 6

### 6.2 属性 2：插件型计划任务必须复用正式插件后台任务链路

*对于任何* 目标类型为 `plugin_job` 的计划任务运行，系统都应该满足：最终通过 `plugin_job` 创建下游执行，而不是绕过后台任务直接同步执行插件。

**验证需求：** `requirements.md` 需求 3

### 6.3 属性 3：家庭状态规则必须走正式上下文入口

*对于任何* 心跳规则评估，系统都应该满足：家庭状态输入来自统一上下文服务，而不是由计划任务系统自行拼装成员和设备状态。

**验证需求：** `requirements.md` 需求 5

### 6.4 属性 4：主动提醒必须受冷却和风险边界约束

*对于任何* Agent 主动提醒类任务，系统都应该满足：冷却窗口内不重复刷屏，高风险动作默认不能由计划任务直接放行。

**验证需求：** `requirements.md` 需求 4、需求 6

### 6.5 属性 5：账号操作人和任务归属成员必须能区分

*对于任何* 一条计划任务定义，系统都应该满足：能同时回答“是谁创建或修改的”和“这条任务归谁”。

**验证需求：** `requirements.md` 需求 1A、需求 1B

### 6.6 属性 6：对话创建在确认前不能变成正式任务

*对于任何* 一次对话创建流程，系统都应该满足：只有草稿完整且用户确认后，才会生成正式计划任务定义。

**验证需求：** `requirements.md` 需求 2B

## 7. 测试策略

### 7.1 单元测试

- 下一次调度时间计算
- 同一窗口幂等键去重
- 心跳规则评估和冷却抑制
- 插件依赖校验和 Agent 依赖校验
- 账号 / 成员归属校验
- 对话草稿补字段和确认前校验

### 7.2 集成测试

- Alembic migration 创建计划任务相关表
- 固定时间任务创建运行记录并分发到 `plugin_job`
- 心跳任务读取家庭状态后生成提醒运行
- 插件禁用后计划任务定义进入依赖失效状态
- 成员私有任务和家庭公共任务的权限过滤
- 对话草稿确认后转成正式任务定义

### 7.3 端到端测试

- 家庭启用一个“每天固定时间同步插件”的任务后，系统可自动创建插件后台任务
- 家庭启用一个“儿童在家但儿童保护关闭时提醒”的心跳任务后，系统能主动产出提醒
- 停用任务后，不再继续触发新的运行记录
- 成员在前端创建“每天晚上九点提醒我吃药”后，只在自己的任务列表里可见
- 用户通过对话创建任务后，确认成功即可在同一前端管理页看到它

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.1、§3.2.1、§3.2.2、§4.1 | migration + service 集成测试 |
| `requirements.md` 需求 1A、需求 1B | `design.md` §3.2.1、§4.1、§4.3、§6.5 | 权限测试 + 审计测试 |
| `requirements.md` 需求 2 | `design.md` §2.3.1、§2.3.2、§4.2 | 调度计算测试 + 心跳巡检测试 |
| `requirements.md` 需求 2A | `design.md` §2.3.7、§3.3.2、§3.3.4 | 前后端联调 + 权限过滤测试 |
| `requirements.md` 需求 2B | `design.md` §2.3.6、§3.2.5、§3.3.8、§3.3.9、§6.6 | 对话草稿测试 + 确认创建测试 |
| `requirements.md` 需求 3 | `design.md` §2.3.3、§3.3.1、§6.2 | 插件任务联动测试 |
| `requirements.md` 需求 4 | `design.md` §2.3.4、§4.4、§6.4 | Agent 提醒去重与风险测试 |
| `requirements.md` 需求 5 | `design.md` §2.3.2、§4.4、§6.3 | 家庭状态规则评估测试 |
| `requirements.md` 需求 6 | `design.md` §5.3、§6.1、§6.4、§6.5 | 停用、异常、审计测试 |

## 8. 风险与待确认项

### 8.1 风险

- 如果第一版就想同时支持太多规则类型，系统很快会被配置复杂度拖死
- 如果让插件自己自动注册并启用 schedule，家庭级控制权会失控
- 如果家庭状态规则直接读底层表而不是统一上下文服务，很快会出现第二套事实来源
- 如果 Agent 主动提醒没有冷却和抑制策略，用户很快会对整个主动系统失去信任
- 如果账号和成员归属不区分，最后一定会出现“是谁建的”和“任务到底是谁的”两本账
- 如果对话创建不经过确认，用户说一句模糊话就落正式任务，后面只会制造垃圾数据

### 8.2 待确认项

- 第一版 Agent 主动提醒最终走现有哪条投递链最合适：实时事件、站内通知，还是受控会话入口
- 家庭记忆面板里的标签结构是直接在 `MemoriesPage` 扩展，还是升级成统一的家庭知识与计划面板
- 插件模板是放在 manifest 内，还是先放在后端注册表衍生配置里更稳
- 对话创建草稿第一版是存数据库、缓存，还是直接挂当前会话态更合适
