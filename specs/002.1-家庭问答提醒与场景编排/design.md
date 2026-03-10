# 设计文档 - 家庭问答提醒与场景编排

状态：Draft

## 1. 概述

### 1.1 Spec 定位

`Spec 002.1` 是 `Spec 002` 的上层服务子 Spec。

如果说 `Spec 002` 解决的是“系统知道这个家当前发生了什么”，那么本 Spec 解决的是“系统拿这些信息去做什么”。

当前阶段只做三类最值得做、最能演示、也最能继续往上承接的能力：

1. **家庭问答 v1**：只读查询、可解释、可裁剪
2. **提醒与广播 v1**：可配置、可调度、可确认、可升级
3. **模板化场景编排 v1**：有限模板、有限条件、有限动作、强守卫
4. **AI 供应商抽象层 v1**：统一模型供应商配置、能力路由、隐私裁剪与降级策略

### 1.2 范围边界

本设计只解决首期可闭环能力：

- 围绕家庭状态、设备状态、提醒状态和基础记忆摘要的问答
- 围绕问答、提醒文案生成、场景解释的 AI 供应商抽象层
- 围绕定时与上下文触发的提醒
- 围绕三类模板场景的编排与执行
- 围绕后台治理的服务中心页面

明确不做：

- 任意自然语言到任意动作的全自动智能体
- 通用可视化规则引擎
- 大规模异步工作流平台
- 全量记忆中心或相册问答引擎

### 1.3 分阶段交付策略

为了控制复杂度，按下面顺序推进：

1. **先做 AI 模型网关、结构化事实视图与权限裁剪**
2. **再做问答 API v1 与提醒任务管理**
3. **然后做提醒调度、送达、确认、升级**
4. **最后做模板场景、冲突治理和管理台集成**

这意味着：

- AI 供应商先做统一抽象层
- 问答先只读
- 提醒先规则化
- 场景先模板化

不要反过来。反过来就是过度设计。

---

## 2. 架构设计

### 2.1 模块拆分

本 Spec 建议在现有 `api-server` 基础上新增或扩展以下模块：

1. `family_qa`
   - 问答请求入口
   - 结构化事实视图拼装
   - 权限裁剪与回答生成
2. `ai_gateway`
   - 供应商适配器抽象
   - 能力路由、主备切换与超时重试
   - 请求脱敏、结果归一化与调用审计
3. `ai_provider_admin`
   - AI 供应商档案管理
   - 能力路由配置
   - 密钥引用与部署配置映射
4. `reminder`
   - 提醒任务 CRUD
   - 提醒总览查询
   - 提醒运行状态机
5. `reminder_scheduler`
   - 定时扫描
   - 条件评估
   - 运行创建与幂等控制
6. `delivery`
   - 送达渠道抽象
   - 房间/成员/设备路由
   - 升级策略执行
7. `scene_engine`
   - 模板场景注册
   - 触发评估
   - 守卫、冲突、冷却判断
8. `scene_execution`
   - 场景步骤执行
   - 执行日志与回执聚合
9. `service_center_admin`
   - 服务中心管理台页面
   - `context-center` 摘要联动

### 2.2 运行时依赖

- `SQLite`：提醒任务、运行记录、场景模板、执行日志等持久化
- `Redis`：短时去重键、调度游标、热点问答建议缓存、运行中的场景锁
- 外部或本地 `AI Providers`：OpenAI 兼容云模型、自建网关、本地模型服务等统一接入目标
- 部署侧 `Secret Store / ENV`：保存供应商密钥与敏感接入信息
- `Spec 002 context API`：成员状态、房间占用、设备摘要与当前家庭上下文
- `Spec 001 household/member/device/permission`：家庭主数据、权限与偏好
- `Home Assistant`：设备动作执行与设备状态查询
- `Admin Web`：服务中心页面、问答试运行、提醒与场景管理

### 2.3 核心数据流

#### §2.3.1 问答查询流

`Admin Web / Voice UI` → `family_qa` → 组装 `QaFactView` → 权限裁剪 → `ai_gateway`（或模板回答）→ 回答生成 → 审计日志

要点：

- 回答先基于结构化事实，不要先依赖大模型自由发挥
- 业务模块不得直接绑定某家供应商 SDK，必须经过模型网关
- 回答中必须能区分“事实”和“推断”
- 首期只做只读，不带设备执行

#### §2.3.2 提醒调度流

`ReminderTask` → `reminder_scheduler` 定时扫描 → 触发条件评估 → 创建 `ReminderRun` → 写入待送达队列

要点：

- 以“任务”和“运行”分离，避免后续状态打架
- 同一调度槽位只能创建一个有效运行
- 支持定时与条件触发两类入口

#### §2.3.3 提醒送达与确认流

`ReminderRun` → `delivery` 选择成员/房间/渠道 → 创建 `DeliveryAttempt` → 等待 `AckEvent` → 超时后升级

要点：

- 送达与确认分开建模
- 未确认不是失败，只是未完成
- 升级依赖确认状态，不依赖猜测

#### §2.3.4 场景触发评估流

外部事件 / 定时器 / 手动触发 → `scene_engine` 选择模板 → 评估条件与守卫 → 冲突/冷却判断 → 生成 `SceneExecution`

要点：

- 首期只支持模板注册，不支持任意图式编排
- 条件和守卫先结构化，再执行
- 同一触发源的去重键必须稳定

#### §2.3.5 场景执行与审计流

`SceneExecution` → 逐步执行提醒/广播/上下文更新/设备动作 → 聚合步骤结果 → 写审计与事件记录 → 回写服务中心总览

要点：

- 步骤级结果必须落库
- 失败允许部分成功，但必须讲清楚哪里失败
- 高风险动作不允许被模板偷偷绕过确认

#### §2.3.6 AI 能力路由与降级流

业务模块（问答/提醒/场景解释） → `ai_gateway` → 读取 `AiCapabilityRoute` → 选择主供应商 → 请求脱敏与模板拼装 → 调用适配器 → 结果归一化 → 失败时回退到备供应商或模板回答

要点：

- 路由以“能力”为单位，而不是以“页面”或“模块”硬编码
- 首期至少要支持 `qa_generation`、`reminder_copywriting`、`scene_explanation` 三类能力
- 未来保留 `embedding`、`rerank`、`stt`、`tts`、`vision` 能力位，但当前不要求全部实现
- 降级必须明确，不允许 provider 挂了以后业务模块自己各写一套土办法

---

## 3. 组件与接口

### 3.0 AI 模型供应商抽象与能力路由

#### 3.0.1 设计目标

这层不是为了炫技，而是为了避免以后系统里到处散落：

- `if provider == openai`
- `if provider == local`
- `if provider == xxx`

这种代码一多，整个系统会迅速烂掉。

模型网关层必须把以下事情统一收住：

1. 供应商能力注册
2. 主备路由
3. 超时、重试、熔断
4. 请求脱敏与隐私阻断
5. 响应归一化
6. 调用审计与成本统计

#### 3.0.2 能力分层

模型能力按“用途”拆分，不按供应商拆分：

- `qa_generation`：家庭问答自然语言生成
- `qa_structured_answer`：严格 JSON / 结构化回答
- `reminder_copywriting`：提醒文案润色与差异化表达
- `scene_explanation`：场景执行解释与预览说明
- `embedding`：向量化
- `rerank`：检索重排
- `stt`：语音转文本
- `tts`：文本转语音
- `vision`：图像理解

当前 Spec 首期强依赖前三项，后五项作为统一抽象预留能力位。

#### 3.0.3 供应商适配器接口

建议内部抽象：

- `ChatGenerationProvider`
- `StructuredOutputProvider`
- `EmbeddingProvider`
- `RerankProvider`
- `SpeechToTextProvider`
- `TextToSpeechProvider`
- `VisionProvider`

统一输出结构应至少包含：

- `provider_code`
- `model_name`
- `capability`
- `trace_id`
- `latency_ms`
- `usage`
- `finish_reason`
- `raw_response_ref`
- `normalized_output`

#### 3.0.4 配置来源

配置分两层：

1. **静态部署配置**
   - 通过 `app/core/config.py` 和 `.env` 提供默认网关行为
   - 例如默认超时、默认本地优先、是否允许远端供应商、默认密钥引用前缀
2. **动态业务配置**
   - 通过数据库中的 `AiProviderProfile` 与 `AiCapabilityRoute` 存储可切换档案
   - 用于不同家庭、不同环境、不同能力的路由切换

说明：

- 密钥不写入业务表
- 业务表只存 `secret_ref`
- 真正密钥由环境变量或密钥管理器提供

#### 3.0.5 管理接口

建议新增：

- `GET /api/v1/ai/providers`
- `POST /api/v1/ai/providers`
- `PATCH /api/v1/ai/providers/{provider_profile_id}`
- `GET /api/v1/ai/routes`
- `PUT /api/v1/ai/routes/{capability}`

这些接口当前主要面向管理员和运维，不强制在首期前端就交付完整配置页，但后端契约必须先规划清楚。

#### 3.0.6 降级策略

每个能力至少支持 4 种策略：

1. `template_only`：完全不走模型，只用模板回答
2. `primary_then_fallback`：先主供应商，失败再切备供应商
3. `local_only`：仅允许本地模型
4. `local_preferred_then_cloud`：优先本地，失败再切云端

首期问答默认建议：

- 事实视图稳定时：`template_only` 或 `local_preferred_then_cloud`
- 敏感家庭：优先 `local_only`
- 管理台调试：允许 `primary_then_fallback`

### 3.1 家庭问答查询接口

建议新增：

- `POST /api/v1/family-qa/query`

#### 输入

```json
{
  "household_id": "uuid",
  "requester_member_id": "uuid 或 null",
  "question": "爷爷今天吃药了吗？",
  "channel": "admin_web",
  "context": {
    "room_id": "uuid 或 null",
    "active_member_id": "uuid 或 null"
  }
}
```

#### 输出

```json
{
  "answer_type": "reminder_status",
  "answer": "今天晚饭后的服药提醒已经触发，但还没有确认完成。",
  "confidence": 0.91,
  "facts": [
    {
      "type": "reminder_run",
      "label": "晚饭后服药提醒",
      "source": "reminder_runs",
      "occurred_at": "2026-03-09T18:30:00Z",
      "visibility": "family",
      "inferred": false
    }
  ],
  "degraded": false,
  "suggestions": [
    "查看提醒详情",
    "手动再次提醒"
  ]
}
```

#### 首期支持问题类型

- 成员在家/房间状态
- 设备开关与基础健康状态
- 今日安排/课程/共享提醒
- 提醒是否已触发/已确认/已完成
- 模板场景是否启用、最近是否执行

#### 校验约束

- `household_id` 必填
- `question` 不可为空
- `requester_member_id` 若存在必须属于当前家庭
- 问答只读，不接受动作参数

#### 错误返回

- `400`：问题为空、字段缺失
- `403`：无权查看目标信息
- `404`：家庭或成员不存在
- `422`：问题不在支持范围内且无法安全降级

### 3.2 热门问题与建议接口

建议新增：

- `GET /api/v1/family-qa/suggestions?household_id=<id>`

用途：

- 给管理台和语音入口提供快捷问句
- 缓存家庭级高频问法
- 把可回答的范围直接暴露出来，减少空转

### 3.3 提醒任务管理接口

建议新增：

- `GET /api/v1/reminders?household_id=<id>`
- `POST /api/v1/reminders`
- `PATCH /api/v1/reminders/{reminder_id}`
- `DELETE /api/v1/reminders/{reminder_id}`

#### 核心输入字段

- `household_id`
- `owner_member_id`
- `target_member_ids`
- `reminder_type`：`personal|family|medication|course|announcement`
- `schedule_kind`：`once|recurring|contextual`
- `schedule_rule`
- `priority`：`low|normal|high|urgent`
- `preferred_room_ids`
- `delivery_channels`
- `ack_required`
- `escalation_policy`
- `enabled`

#### 设计要点

- `schedule_rule` 先放 JSON，不做一堆子表
- `contextual` 类型提醒可以绑定简单条件，例如“成员到家后 10 分钟内”
- 删除任务不删除历史运行，只把配置状态关闭

### 3.4 提醒总览、手动触发与确认接口

建议新增：

- `GET /api/v1/reminders/overview?household_id=<id>`
- `POST /api/v1/reminders/{reminder_id}/trigger`
- `POST /api/v1/reminder-runs/{run_id}/ack`

#### `ack` 输入

```json
{
  "member_id": "uuid",
  "action": "done",
  "channel": "speaker",
  "note": "已服药"
}
```

#### `ack` 语义

- `heard`：已听到，但未完成
- `done`：已完成
- `dismissed`：忽略
- `delegated`：转交给其他成员

### 3.5 场景模板与手动触发接口

建议新增：

- `GET /api/v1/scenes/templates?household_id=<id>`
- `PUT /api/v1/scenes/templates/{template_code}`
- `POST /api/v1/scenes/templates/{template_code}/preview`
- `POST /api/v1/scenes/templates/{template_code}/trigger`

#### 首期模板

- `smart_homecoming`
- `child_bedtime`
- `elder_care`

#### `preview` 输出重点

- 当前命中的触发条件
- 未通过的守卫条件
- 计划执行步骤
- 需要确认的高风险动作

#### `trigger` 设计要点

- 手动触发允许管理员验证场景链路
- 手动触发也必须写入场景执行日志
- 手动触发不能绕过高风险守卫

### 3.6 场景执行查询接口

建议新增：

- `GET /api/v1/scenes/executions?household_id=<id>`
- `GET /api/v1/scenes/executions/{execution_id}`

用途：

- 展示最近执行记录
- 查看步骤成功/失败详情
- 追踪冲突跳过、冷却拦截、守卫命中原因

### 3.7 管理台页面设计

建议新增服务中心页面：

- 路由：`/service-center`

页面分四层：

1. **服务总览 Hero**
   - 当前家庭服务健康度
   - 今日提醒数量
   - 最近场景执行
   - 问答可用状态
2. **问答工作台**
   - 热门问题
   - 输入框
   - 回答结果
   - 证据事实列表
3. **提醒与广播面板**
   - 提醒列表
   - 今日运行状态
   - 手动触发
   - 确认/重试/暂停
4. **场景编排面板**
   - 模板启停
   - 模板参数覆盖
   - 预览/手动触发
   - 最近执行日志

同时在 `/context-center` 展示摘要卡：

- 今日待确认提醒
- 最近一次场景执行
- 常见问答入口

不要把所有管理操作都塞进 `/context-center`。那页面已经够重了。

---

## 4. 数据模型

### 4.0 AI 供应商配置模型

#### 4.0.1 `AiProviderProfile`

建议表：`ai_provider_profiles`

字段：

- `id`
- `provider_code`
- `display_name`
- `transport_type`：`openai_compatible|native_sdk|local_gateway`
- `base_url`
- `api_version`
- `secret_ref`
- `enabled`
- `supported_capabilities_json`
- `privacy_level`：`local_only|private_cloud|public_cloud`
- `latency_budget_ms`
- `cost_policy_json`
- `extra_config_json`
- `updated_at`

说明：

- `supported_capabilities_json` 描述这个档案支持哪些能力
- `secret_ref` 指向环境变量或密钥管理器键名
- 不保存明文密钥

#### 4.0.2 `AiCapabilityRoute`

建议表：`ai_capability_routes`

字段：

- `id`
- `capability`
- `household_id` 或 `null`
- `primary_provider_profile_id`
- `fallback_provider_profile_ids_json`
- `routing_mode`
- `timeout_ms`
- `max_retry_count`
- `allow_remote`
- `prompt_policy_json`
- `response_policy_json`
- `enabled`
- `updated_at`

说明：

- 允许全局默认路由，也允许家庭级覆盖
- `routing_mode` 对应 `template_only / primary_then_fallback / local_only / local_preferred_then_cloud`
- `allow_remote=false` 时不能把请求送出本地边界

#### 4.0.3 `AiModelCallLog`

建议表：`ai_model_call_logs`

字段：

- `id`
- `capability`
- `provider_code`
- `model_name`
- `household_id`
- `requester_member_id`
- `trace_id`
- `input_policy`
- `masked_fields_json`
- `latency_ms`
- `usage_json`
- `status`
- `fallback_used`
- `error_code`
- `created_at`

说明：

- 不强行保存完整原始 prompt 与完整原始响应
- 首期只保留必要审计元数据、脱敏信息和引用
- 如需保存原文，必须经过额外隐私开关控制

### 4.1 `QaFactView`

用途：问答时临时拼装的家庭事实视图，不一定落库。

建议字段：

- `household_id`
- `generated_at`
- `requester_member_id`
- `active_member`
- `member_states`
- `room_occupancy`
- `device_summary`
- `device_states`
- `reminder_summary`
- `scene_summary`
- `memory_summary`
- `permission_scope`

说明：

- 这是回答的事实底座
- 先拼装再裁剪，不要先裁一半再拼，容易丢信息

### 4.2 `QaQueryLog`

建议表：`qa_query_logs`

字段：

- `id`
- `household_id`
- `requester_member_id`
- `question`
- `answer_type`
- `answer_summary`
- `confidence`
- `degraded`
- `facts_json`
- `created_at`

说明：

- 记录问答请求与结果摘要
- 不强行存整段长回答全文，首期只存摘要与证据引用

### 4.3 `ReminderTask`

建议表：`reminder_tasks`

字段：

- `id`
- `household_id`
- `owner_member_id`
- `title`
- `description`
- `reminder_type`
- `target_member_ids_json`
- `preferred_room_ids_json`
- `schedule_kind`
- `schedule_rule_json`
- `priority`
- `delivery_channels_json`
- `ack_required`
- `escalation_policy_json`
- `enabled`
- `version`
- `updated_by`
- `updated_at`

### 4.4 `ReminderRun`

建议表：`reminder_runs`

字段：

- `id`
- `task_id`
- `household_id`
- `schedule_slot_key`
- `trigger_reason`
- `planned_at`
- `started_at`
- `finished_at`
- `status`：`pending|delivering|acked|expired|cancelled|failed`
- `context_snapshot_json`
- `result_summary_json`

说明：

- `schedule_slot_key` 用于保证同一槽位幂等
- `context_snapshot_json` 用于事后解释为什么当时这么触达

### 4.5 `ReminderDeliveryAttempt`

建议表：`reminder_delivery_attempts`

字段：

- `id`
- `run_id`
- `target_member_id`
- `target_room_id`
- `channel`
- `attempt_index`
- `planned_at`
- `sent_at`
- `status`：`queued|sent|heard|failed|skipped`
- `provider_result_json`
- `failure_reason`

### 4.6 `ReminderAckEvent`

建议表：`reminder_ack_events`

字段：

- `id`
- `run_id`
- `member_id`
- `action`：`heard|done|dismissed|delegated`
- `note`
- `created_at`

### 4.7 `SceneTemplate`

建议表：`scene_templates`

字段：

- `id`
- `household_id`
- `template_code`
- `name`
- `description`
- `enabled`
- `priority`
- `cooldown_seconds`
- `trigger_json`
- `conditions_json`
- `guards_json`
- `actions_json`
- `rollout_policy_json`
- `version`
- `updated_by`
- `updated_at`

说明：

- 先用单表 + JSON，避免首期拆成一堆规则子表
- 模板代码固定，允许有限参数覆盖

### 4.8 `SceneExecution`

建议表：`scene_executions`

字段：

- `id`
- `template_id`
- `household_id`
- `trigger_key`
- `trigger_source`
- `started_at`
- `finished_at`
- `status`：`planned|running|success|partial|skipped|blocked|failed`
- `guard_result_json`
- `conflict_result_json`
- `context_snapshot_json`
- `summary_json`

### 4.9 `SceneExecutionStep`

建议表：`scene_execution_steps`

字段：

- `id`
- `execution_id`
- `step_index`
- `step_type`：`reminder|broadcast|device_action|context_update`
- `target_ref`
- `request_json`
- `result_json`
- `status`：`planned|success|skipped|failed|blocked`
- `started_at`
- `finished_at`

---

## 5. 正确性属性与业务不变量

### 5.0 AI 模型网关不变量

1. 业务模块不得直接依赖具体模型供应商 SDK，所有模型调用都必须经过模型网关。
2. 模型路由必须按“能力”配置，而不是散落在业务代码条件分支里。
3. 明文密钥不得进入业务数据库；数据库只能保存密钥引用。
4. 当能力路由声明 `allow_remote=false` 或 `local_only` 时，任何请求都不得绕过该策略发往云端。
5. 同一次业务请求若发生供应商回退，最终响应必须能标识主供应商失败与回退路径。

### 5.1 问答不变量

1. 问答是只读路径，不得偷偷触发设备动作。
2. 任何回答都必须可关联到结构化事实或显式推断。
3. 权限裁剪发生在响应前，不能先返回再屏蔽。
4. 信息不足时必须降级成“不确定”，不能幻想。

### 5.2 提醒调度不变量

1. 同一个 `ReminderTask + schedule_slot_key` 最多只有一个有效 `ReminderRun`。
2. 禁用任务不得创建新运行，但历史运行可继续查询。
3. 已过期运行不得重新进入送达状态。
4. 调度器重启后只能补触发未完成槽位，不能重复轰炸。

### 5.3 提醒确认不变量

1. 一个 `done` 确认必须结束后续升级。
2. `dismissed` 不等于 `done`，必须保留语义差异。
3. `delegated` 必须保留原 run，不重新伪造新任务。
4. 确认事件必须有明确成员来源或管理员来源。

### 5.4 场景安全不变量

1. 高风险设备动作不能被模板绕过确认。
2. 敏感房间和儿童保护限制优先于普通场景便利性。
3. 私密提醒不得在公共广播中泄露具体内容。
4. 场景执行结果必须可解释“为什么执行/为什么没执行”。

### 5.5 场景冲突与冷却不变量

1. 同一 `template_code + trigger_key` 在冷却窗口内不能重复执行。
2. 同一设备同一时刻若被多个场景竞争，按优先级与守卫决策唯一执行路径。
3. 手动触发可覆盖普通自动场景，但不能覆盖高风险守卫。
4. `partial` 状态必须包含逐步结果，不能只给一个空洞失败码。

---

## 6. 错误处理与降级

### 6.0 AI 供应商错误处理

- `400`：能力路由配置非法、供应商能力不匹配
- `403`：请求数据被隐私策略阻断，禁止发送到目标供应商
- `409`：当前能力路由被禁用或冲突
- `422`：结构化输出校验失败且无安全降级结果
- `429`：供应商限流
- `502`：供应商调用失败或返回非法数据
- `504`：供应商超时

降级策略：

- 主供应商超时 → 切备供应商或模板回答
- 结构化输出不合法 → 回退到模板回答或更严格的结构化模型
- 远端受限 → 阻断并返回“当前策略禁止使用外部模型”
- 成本或配额超限 → 切本地模板模式并打标为降级

### 6.1 问答错误处理

- `400`：问题为空、上下文字段非法
- `403`：无权限读取目标事实
- `422`：当前问题不在首期支持范围，且无法安全降级
- `503`：事实视图关键依赖不可用且无降级数据

降级策略：

- 记忆摘要不可用 → 仅用上下文与提醒事实回答
- 设备状态缺失 → 返回“当前无法确认设备状态”
- 提醒服务不可用 → 只回答静态任务配置，不回答最新执行状态

### 6.2 提醒错误处理

- `400`：调度规则或升级策略格式非法
- `404`：成员/房间/任务不存在
- `409`：同一槽位已存在运行
- `422`：提醒目标与家庭边界冲突

降级策略：

- 某送达渠道失败 → 切到次优渠道或升级策略
- 房间路由失败 → 回退成员级默认渠道
- 外部播报不可用 → 记录失败并保留待确认状态

### 6.3 场景错误处理

- `400`：模板参数非法或不支持自由扩展
- `403`：手动触发越权
- `409`：命中冷却或冲突锁
- `422`：触发不满足模板条件
- `502`：下游设备动作执行失败

降级策略：

- 设备动作失败 → 场景可进入 `partial`
- 广播失败 → 视优先级改为通知/日志提示
- 高风险动作未确认 → 场景进入 `blocked`

### 6.4 回滚与恢复策略

- 提醒任务更新采用版本号，失败回滚到上一个可用版本
- 场景模板更新失败不得影响当前已启用版本
- 调度器恢复时按 `schedule_slot_key` 补偿，不按“现在时间全量补跑”
- 手动触发失败必须保留完整失败记录，便于复盘

---

## 7. 测试策略

### 7.1 单元测试

覆盖：

- AI 能力路由选择与回退
- 请求脱敏与隐私阻断
- 问答问题分类与事实裁剪
- 提醒槽位计算与幂等键生成
- 升级策略状态流转
- 场景守卫、冷却和冲突判断

### 7.2 集成测试

覆盖：

- `ai gateway` → provider route → fallback → normalized output
- `family-qa/query` → 事实组装 → 权限裁剪 → 回答输出
- `reminder task` → `reminder run` → `delivery attempt` → `ack`
- `scene template` → `preview` → `trigger` → `device-actions`

### 7.3 场景回放测试

至少回放三条代表链路：

1. 智能回家
2. 儿童睡前
3. 老人关怀提醒

要求验证：

- 触发条件是否准确
- 守卫是否生效
- 执行日志是否完整
- 问答是否能追问到结果

### 7.4 管理台联调

联调页面：

- `/service-center`
- `/context-center`

联调重点：

- 问答结果与事实引用一致
- 提醒确认后状态即时刷新
- 场景预览与真实执行结果一致性
- 执行失败后的错误说明与审计可追踪

---

## 8. 风险与延期项

### 8.1 当前明确风险

1. `Spec 003` 完整记忆中心尚未落地，问答首期主要依赖上下文与结构化摘要，不应承诺全量记忆问答。
2. 提醒送达渠道首期可能只有管理台、日志与音箱播报的骨架，真实渠道多样性需要后续扩展。
3. 场景模板依赖 `Spec 002` 的设备动作可用性与上下文准确性，上游抖动会直接影响体验。
4. 多供应商模型返回风格、结构化稳定性与时延差异很大，如果没有统一网关和强约束输出，业务层会迅速被污染。
5. 本地模型与云模型的能力差距、成本差距和隐私边界差异明显，必须由路由策略显式处理，不能靠人工约定。

### 8.2 当前明确延期

- 通用自由编排引擎
- 复杂多轮问答代理
- 自然语言直接生成新场景
- 高级健康建议与医疗级解释
- 跨终端强一致提醒同步
- 完整 AI 供应商配置前端治理台

结论很简单：先把可解释、可验证、可审计的家庭服务闭环做出来，再谈更聪明的东西。
