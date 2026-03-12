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
5. 组合上下文
6. 调用模型，优先流式返回
7. 逐步更新助手消息内容和状态
8. 完成后写入 `facts`、`suggestions`、`trace_id`、`provider_code`
9. 对本轮或最近若干轮会话执行 `memory_extraction`
10. 生成记忆候选，等待用户确认
11. 同步写审计日志和 `qa_query_logs`

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

### 5.1 配置提取

当前已经有：

- `butler_bootstrap`
- `butler_bootstrap_extract`

这部分继续保留在初始化向导场景中使用，不重复造轮子。

普通聊天默认不自动改配置。只有以下两种情况才允许触发配置提取：

1. 会话模式明确是 `agent_config`
2. 用户显式点击“转成配置建议”之类的受控入口

这样做的原因很简单：不能让一句闲聊把 Agent 配置改了。

### 5.2 记忆提取

聊天模块正式接入 `memory_extraction`：

- 输入：最近若干轮对话文本、成员上下文、当前问题
- 输出：记忆候选列表
- 落点：`conversation_memory_candidates`

确认逻辑：

1. 候选生成后前端显示“建议写入记忆”
2. 用户确认后才调用正式记忆写入服务
3. 用户忽略后只更新候选状态，不写正式记忆卡

### 5.3 为什么不用“自动直接落库”

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

