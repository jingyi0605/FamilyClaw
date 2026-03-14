# 设计文档 - 聊天模块全链路重构

状态：Draft

## 1. 概述

### 1.1 目标

把当前 `/conversation` 页面从“本地伪会话 + 单轮问答接口”改成“服务端真实会话 + 多轮上下文 + 可恢复消息流”。

### 1.2 这次不追求什么

- 不把普通聊天和初始化向导强行合成一套页面
- 不让普通聊天自动直接改 Agent 配置
- 不为了“理论统一”把现有 `family_qa`、`bootstrap`、`memory` 模块全部推倒重来

### 1.3 当前实现的核心问题

1. 页面消息来自 `localStorage`，不是服务端真实会话。
2. `/conversation` 调的是单轮 `family_qa`，没有 `session_id`，没有历史消息输入。
3. 前端默认 8 秒超时，后端模型成功调用可能更慢，导致“后端成功、前端报错”。
4. 后端已经能组合家庭、Agent、记忆上下文，但没有把聊天历史当成正式输入。
5. `memory_extraction` 任务定义已经存在，但聊天链路根本没调用。

## 2. 总体方案

### 2.1 方案一句话

新增服务端聊天会话与消息模型，聊天页完全以服务端数据为准；每轮对话由后端统一完成“写入用户消息 → 组合上下文 → 调模型 → 写入助手消息 → 运行提取任务 → 推送状态更新”。

### 2.2 分层结构

#### A. 持久化层

- 新增聊天会话表
- 新增聊天消息表
- 新增记忆候选表

`qa_query_logs` 继续保留，但它退回审计和统计角色，不再冒充聊天历史。

#### B. 编排层

- 新增聊天服务 `conversation service`
- 统一处理会话创建、消息顺序、Agent 解析、上下文组合、模型调用、降级和提取任务

#### C. 输出层

- 前端改为读取服务端会话
- 发送和回复使用流式事件或长轮询结果更新
- 本地缓存只保留非常短期的 UI 状态，不再保存权威消息

## 3. 数据模型

### 3.1 `conversation_sessions`

建议字段：

- `id`
- `household_id`
- `requester_member_id`
- `session_mode`：`family_chat` / `agent_bootstrap` / `agent_config`
- `active_agent_id`
- `title`
- `status`：`active` / `archived` / `failed`
- `last_message_at`
- `created_at`
- `updated_at`

说明：

- 普通聊天默认 `session_mode = family_chat`
- 初始化向导暂时继续沿用原有 bootstrap 表，不强行迁移；后续如果合并，再做第二阶段

### 3.2 `conversation_messages`

建议字段：

- `id`
- `session_id`
- `request_id`
- `seq`
- `role`：`user` / `assistant` / `system`
- `message_type`：`text` / `error` / `memory_candidate_notice`
- `content`
- `status`：`pending` / `streaming` / `completed` / `failed`
- `effective_agent_id`
- `ai_provider_code`
- `ai_trace_id`
- `degraded`
- `error_code`
- `facts_json`
- `suggestions_json`
- `created_at`
- `updated_at`

说明：

- 这样前端就能准确展示“发送中”“流式中”“失败”“完成”。
- `facts_json` 和 `suggestions_json` 继续保留，避免把现有家庭问答能力丢掉。

### 3.3 `conversation_memory_candidates`

建议字段：

- `id`
- `session_id`
- `source_message_id`
- `requester_member_id`
- `status`：`pending_review` / `confirmed` / `dismissed`
- `memory_type`
- `title`
- `summary`
- `content_json`
- `confidence`
- `created_at`
- `updated_at`

说明：

- 候选先存下来，再由用户确认是否写入正式记忆卡。
- 这样能复用 `memory_extraction`，又不会让系统悄悄乱记。

## 4. 后端消息编排

### 4.1 单轮处理流程

一轮普通聊天按下面顺序执行：

1. 校验 `household_id`、当前用户和可用 Agent
2. 创建或加载会话
3. 写入用户消息，状态记为 `completed`
4. 创建助手占位消息，状态记为 `pending`
5. 先做一层 AI 意图识别，只判断“这轮更像什么”，不直接执行任何动作
6. 如果识别结果低置信度，直接回落到 `free_chat`
7. 按识别结果进入对应能力层：`structured_qa` / `free_chat` / `config_extraction` / `memory_extraction` / `reminder_extraction`
8. 如果识别到动作类意图，再做对应的信息提取
9. 提取出的动作继续走策略层，由 `ask / notify / auto` 决定是否执行
10. 逐步更新助手消息内容和状态
11. 完成后写入 `facts`、`suggestions`、`trace_id`、`provider_code`
12. 对需要补充长期信息的普通对话，再执行保守的 `memory_extraction`
13. 生成记忆候选，等待用户确认
14. 同步写审计日志和 `qa_query_logs`

### 4.2 上下文组合

每轮模型输入必须包含四块：

1. **会话历史**
   - 最近 N 条有效消息
   - 同一会话内按顺序截断
   - 不把失败占位消息当正常上下文
2. **家庭实时上下文**
   - 复用 `context.service` 和 `fact_view_service`
3. **Agent 上下文**
   - 复用 `build_agent_runtime_context`
4. **记忆上下文**
   - 复用 `build_memory_context_bundle`

这里最关键的一点：现有上下文组合能力不需要推倒，只需要把“会话历史”补进去，变成正式聊天输入。

### 4.3 模型调用策略

- 普通聊天优先走流式返回，避免前端长时间空白
- 如果当前供应商不支持流式，允许后端一次性返回，但前端不能再用 8 秒短超时硬掐
- 后端要输出明确失败原因，前端只展示后端真实状态，不再自行编造通用失败文案

### 4.4 与 `family_qa` 的关系

保留 `family_qa` 的两部分价值：

- 规则草稿生成
- `facts`、`suggestions`、审计日志

但它不再直接充当前端聊天接口。新聊天服务可以在内部复用：

- `build_qa_fact_view`
- `_answer_from_fact_view` 的规则草稿思路
- 现有 `qa_generation` 能力路由

也就是说，保留已有积累，但别再拿它充当“会话服务”。

## 5. `llm-task` 复用方案

### 5.1 AI 意图识别

聊天主路由不再靠关键词表。

这次要加一层明确的 `conversation_intent_detection`：

- 输入：当前消息、最近几轮对话、会话模式
- 输出：`primary_intent`、`secondary_intents`、`confidence`、`reason`、`candidate_actions`
- 作用：只负责识别，不负责执行

识别目标至少包括：

- `free_chat`
- `structured_qa`
- `config_change`
- `memory_write`
- `reminder_create`

内部路由可以映射到现有能力名，比如：

- `config_change -> config_extraction`
- `memory_write -> memory_extraction`
- `reminder_create -> reminder_extraction`

如果识别置信度不够，就按 `free_chat` 回落。宁可保守，也不要乱改配置、乱写记忆、乱建提醒。

### 5.2 配置提取

当前已经有：

- `butler_bootstrap`
- `butler_bootstrap_extract`

这部分继续保留在初始化向导场景中使用，不重复造轮子。

普通聊天默认不自动改配置，但也不能蠢到只能靠按钮入口。

新的边界是：

1. `agent_config` 模式下，配置提取可以被护栏强制开启
2. 普通聊天里，如果 AI 明确认定用户在改助手配置，也允许进入 `config_extraction`
3. 真正是否应用配置，仍然交给策略层，不允许识别后直接执行

这样处理的核心原因很简单：自然语言里确实会出现“以后你就叫阿福”这种明确配置请求，但“你叫什么”这种普通对话绝不能再被错杀。

### 5.3 记忆提取

聊天模块正式接入 `memory_extraction`：

- 输入：最近若干轮对话文本、成员上下文、当前问题
- 输出：记忆候选列表
- 落点：`conversation_memory_candidates`

确认逻辑：

1. 候选生成后前端显示“建议写入记忆”
2. 用户确认后才调用正式记忆写入服务
3. 用户忽略后只更新候选状态，不写正式记忆卡

### 5.4 提醒提取

提醒也要按同样分层处理：

1. 先由 AI 判断这轮是不是 `reminder_create`
2. 再调用 `reminder_extraction` 提取标题、说明、触发时间
3. 最后由策略层决定是 `ask`、`notify` 还是 `auto`

别再把“看到提醒关键词就顺手建动作”这种脏逻辑塞回 orchestrator。

### 5.5 为什么不用“自动直接落库”

因为这东西风险太大。

- 聊天里经常有试探、玩笑、口误
- 直接自动写长期记忆，很容易把垃圾写进系统

先生成候选，再让用户确认，这是更稳的做法。

## 6. 接口设计

### 6.1 REST 接口

建议新增：

- `POST /api/v1/conversations/sessions`
  - 创建新会话
- `GET /api/v1/conversations/sessions?household_id=...`
  - 拉会话列表
- `GET /api/v1/conversations/sessions/{session_id}`
  - 拉单个会话详情和消息
- `POST /api/v1/conversations/sessions/{session_id}/turns`
  - 发送一轮用户消息
- `POST /api/v1/conversations/memory-candidates/{candidate_id}/confirm`
  - 把候选写成正式记忆
- `POST /api/v1/conversations/memory-candidates/{candidate_id}/dismiss`
  - 忽略候选

### 6.2 实时接口

优先复用现有实时事件风格，新增聊天专用事件：

- `session.snapshot`
- `user.message.accepted`
- `assistant.message.started`
- `assistant.chunk`
- `assistant.done`
- `assistant.error`
- `memory.candidates.ready`

这样做的好处是：

- 聊天页可以流式渲染
- 事件模型和当前 bootstrap 实时通道风格保持一致
- 不需要前端再自己猜消息状态

### 6.3 调试日志接口

普通用户聊天页不应该直接展示 `intent_detection`、主路由、策略模式这些技术细节。

但后端必须保留一条可选调试链路，不然线上出问题时只能靠猜。

这条链路的要求是：

- 默认关闭，不影响普通会话
- 通过环境变量统一开启，比如 `FAMILYCLAW_CONVERSATION_DEBUG_LOG_ENABLED=true`
- 单独存到调试日志表，不混进普通消息详情
- 同时写入 `apps/api-server/data/logs/conversation-debug.log`，便于直接按文件排查
- 能按 `request_id` 拉出某一轮完整处理流程

至少要记录这些阶段：

1. 收到用户请求
2. AI 意图识别结果
3. 主路由选择结果
4. 动作策略层结果
5. 是否触发保守记忆补提取
6. 本轮完成或失败

这样做的好处很实际：主页面保持干净，排障时又能看到每轮到底怎么走的。

## 7. 前端设计

### 7.1 数据源切换

聊天页改成：

- 会话列表来自服务端
- 当前消息来自服务端
- 本地只留 UI 缓存，比如当前输入框草稿、滚动位置、最近打开的会话 ID

### 7.2 页面行为

- 首次进入页面：拉最近会话
- 点击新建对话：创建服务端会话
- 发送消息：提交一轮 turn
- 收到流式块：更新助手消息
- 收到失败：保留用户消息和失败记录，允许重试
- 收到记忆候选：显示确认入口

### 7.3 本地缓存策略

允许保留的本地数据：

- 输入框未发送草稿
- 当前展开的会话 ID
- 极短期的 UI 优化信息

不再保留：

- 完整消息历史
- 作为事实来源的会话列表

### 7.4 Agent 切换规则

- 空会话切换 Agent：直接修改当前会话 Agent
- 已有消息会话切换 Agent：强制新建会话

这条规则保留当前页面里“避免上下文串线”的正确部分，但把实现落到服务端真实会话里。

## 8. 错误处理

### 8.1 需要区分的错误

- 会话不存在
- 会话不属于当前用户或家庭
- 当前 Agent 不可用
- 上下文构建失败
- 模型供应商失败
- 流式中断
- 请求超时
- 记忆候选确认失败

### 8.2 前端展示原则

- 展示真实错误原因
- 不再用统一的安慰句掩盖所有失败
- 失败消息要保留上下文，方便用户重试
- 调试细节默认不在主聊天页直出，需要时走独立调试接口

## 9. 兼容与迁移

### 9.1 对旧前端缓存的处理

首次进入新聊天页时：

- 发现旧 `localStorage` 会话数据，可提示“旧本地对话不会继续作为正式会话使用”
- 可选提供“一次性导入最近 N 条本地消息”为新草稿会话
- 如果不导入，至少要明确清理口径

### 9.2 对旧后端日志的处理

- `qa_query_logs` 保留，不迁移成聊天会话源数据
- 它继续用于审计、统计和问题排查

### 9.3 对初始化向导的处理

- `ButlerBootstrapConversation` 本次不强制迁移到新聊天表
- 只要求事件风格、超时策略和 `llm-task` 使用方式保持一致

## 10. 正确性约束

1. 同一会话内消息序号必须严格递增。
2. 同一条助手消息在完成后不能再回退到 `pending`。
3. 已失败的一轮消息不能当作下一轮会话上下文的正式助手回复。
4. 记忆候选只有在用户确认后才能写入正式记忆卡。
5. 普通聊天模式不能自动覆盖 Agent 配置。
6. 服务端会话必须是聊天历史的唯一事实来源。

## 11. 测试策略

### 11.1 后端

- 会话创建、查询、权限校验测试
- 多轮消息顺序与上下文截断测试
- LLM 调用成功、超时、供应商失败、模板降级测试
- 记忆候选生成、确认、忽略测试
- 兼容 `qa_query_logs` 与现有 Agent/Memory 服务测试

### 11.2 前端

- 会话列表与消息恢复测试
- 发送、流式更新、失败重试测试
- Agent 切换时的新会话逻辑测试
- 登出后缓存隔离测试

### 11.3 联调

- 真供应商延迟超过 8 秒时仍正确出结果
- 刷新页面后恢复同一会话
- 新设备登录后读取同一服务端会话
- 记忆候选确认后能在记忆页看到新增内容
