# 设计文档 - 分层长期记忆与召回机制

状态：Draft

## 1. 概述

### 1.1 目标

- 把当前“有记忆卡片但没有完整召回”的状态，收口成一套真正能支撑问答主链路的长期记忆系统。
- 明确 `L0-L4` 的语义边界，让不同来源的数据不再混在一起。
- 用 PostgreSQL 现有能力完成第一版关键词召回、语义召回和混合排序，不额外引入新的基础设施依赖。
- 用最小闭环分三期推进，先把 `memory_cards` 和 `free_chat` 修好，再补会话记忆和统一召回。

### 1.2 覆盖需求

- `requirements.md` 需求 1：分层记忆边界
- `requirements.md` 需求 2：PostgreSQL 混合召回
- `requirements.md` 需求 3：分离写入路径
- `requirements.md` 需求 4：会话记忆
- `requirements.md` 需求 5：free_chat 分组注入
- `requirements.md` 需求 6：统一纳入外部知识
- `requirements.md` 需求 7：兼容和降级

### 1.3 技术约束

- 后端：`Python + FastAPI + SQLAlchemy`
- 数据存储：`PostgreSQL`
- 向量能力：`pgvector`
- 关键词索引：`tsvector + GIN`
- 后台任务：沿用现有后端事件循环与周期任务规范，不新开阻塞式常驻线程
- 兼容性：保留现有 `memory_cards`、事件写入、纠错接口，不破坏当前调用方

### 1.4 设计原则

1. 真相源和召回投影必须分开。真相源负责表达业务事实，召回投影负责检索效率。
2. 先消灭特殊情况。不要让 `free_chat`、`family_qa`、插件事件各走一套记忆格式。
3. 先做能落地的闭环，再扩展来源。第一期不追求“一次建成通用平台”。
4. 不破坏现有用户空间。老接口继续可用，新能力默认向下兼容。

## 2. 架构

### 2.1 系统结构

整体分成五块：

1. 写入入口层
   - 显式记忆指令
   - 插件/系统事件
   - 会话摘要刷新
   - 外部知识导入

2. 分层真相源
   - `L1 conversation_session_summaries`
   - `L2 episodic_memory_entries`
   - `L3 memory_cards`
   - `L4 knowledge_documents`

3. 召回投影层
   - 第一阶段：直接在 `memory_cards` 上增加召回字段
   - 第三阶段：收口到统一 `memory_recall_documents`

4. 查询与排序层
   - 权限过滤
   - 关键词召回
   - 向量召回
   - Hybrid rerank

5. 对话注入层
   - `free_chat` 分组注入
   - 注入 trace 持久化
   - debug 与回放

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `memory_ingest_service` | 统一收口显式记忆、事件记忆、会话摘要和外部知识写入 | 对话、事件、文档 | 分层真相源记录 |
| `session_summary_service` | 刷新会话摘要、未完成话题、最近确认事项 | `conversation_messages`、提案执行结果 | `conversation_session_summaries` |
| `episodic_memory_service` | 从事件和会话摘要生成情节记忆 | `event_records`、会话摘要 | `episodic_memory_entries` |
| `semantic_promotion_service` | 把重复观察提升成稳定语义记忆 | 情节记忆、事件聚合 | `memory_cards` |
| `memory_projection_service` | 刷新 `tsvector`、`embedding` 和统一召回投影 | `L1-L4` 真相源 | 召回投影字段或 `memory_recall_documents` |
| `memory_query_service` | 检索、排序、分组和权限过滤 | 查询条件、actor、requester_member_id | 分组召回结果 |
| `conversation_memory_injection_service` | 组装 `free_chat` 的记忆注入内容并落 trace | 对话请求、召回结果 | prompt 片段、trace 记录 |

### 2.3 关键流程

#### 2.3.1 用户明确说“记住”

1. `ConversationIntent` 命中 `memory_write`。
2. 生成 `memory candidate`，允许根据置信度和策略自动确认。
3. 确认后直接进入 `memory_cards`，因为这是稳定事实候选。
4. 同步刷新其关键词投影，异步刷新向量投影。
5. 把本次创建结果写入 action/result 和调试日志。

#### 2.3.2 事件进入情节层并视情况提升

1. 插件、提醒、场景、状态变化进入 `event_records`。
2. `episodic_memory_service` 把值得记住的事件写入 `episodic_memory_entries`。
3. 若同一 `promotion_key` 在时间窗口内重复命中超过阈值，则触发 `semantic_promotion_service`。
4. 提升后更新或创建 `memory_cards`，并保留来源追踪关系。

#### 2.3.3 会话摘要生成

1. 对话轮结束后检查本会话距离上次摘要的消息增量、确认事项增量和空闲时间。
2. 达到阈值或进入结束态时，异步刷新 `conversation_session_summaries`。
3. 摘要内容包括：
   - 当前在聊什么
   - 哪些话题还没收尾
   - 最近已确认的动作或结论
4. 摘要刷新后进入召回投影。

#### 2.3.4 free_chat 召回与注入

1. 以当前用户消息为 query。
2. 先基于 `household/member/visibility` 过滤。
3. 分别对目标层进行关键词和向量召回。
4. 执行 Hybrid rerank。
5. 按分组输出：
   - `stable_facts`
   - `recent_events`
   - `session_summary`
6. 写入 `conversation_memory_reads`，记录本轮注入来源和排序结果。
7. 生成 prompt 片段送入 `orchestrator`。

#### 2.3.5 外部知识导入

1. 插件原始记录、规则文档和说明文档通过适配器导入。
2. 写入 `knowledge_documents` 或保留原始来源引用。
3. 生成 `L4` 召回投影。
4. 在权限允许时参与统一召回。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5、6、7

- `app/modules/memory/`：保留为记忆领域核心模块，继续承载 `memory_cards` 和记忆查询能力。
- `app/modules/conversation/`：负责会话摘要触发、`free_chat` 注入和注入 trace。
- `app/modules/plugin/`：负责把插件原始记录暴露给外部知识导入链路。
- `app/modules/llm_task/`：继续承载显式记忆提案提取，不另起一套入口。

### 3.2 数据结构

覆盖需求：1、2、3、4、5、6

#### 3.2.1 `conversation_session_summaries`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 摘要 ID | 主键 |
| `session_id` | `text` | 是 | 对话会话 ID | 唯一索引，关联 `conversation_sessions.id` |
| `household_id` | `text` | 是 | 家庭 ID | 索引 |
| `requester_member_id` | `text` | 否 | 发起成员 | 索引 |
| `summary` | `text` | 是 | 会话滚动摘要 | 非空 |
| `open_topics_json` | `text` | 是 | 未完成话题列表 | 默认 `[]` |
| `recent_confirmations_json` | `text` | 是 | 最近确认事项 | 默认 `[]` |
| `covered_message_seq` | `integer` | 是 | 已覆盖到的最后消息序号 | 非负 |
| `status` | `varchar(20)` | 是 | `fresh/stale/rebuilding/failed` | 索引 |
| `generated_at` | `text` | 是 | 最近生成时间 | 非空 |
| `updated_at` | `text` | 是 | 最近更新时间 | 非空 |

#### 3.2.2 `episodic_memory_entries`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 情节记忆 ID | 主键 |
| `household_id` | `text` | 是 | 家庭 ID | 索引 |
| `subject_member_id` | `text` | 否 | 主要关联成员 | 索引 |
| `source_kind` | `varchar(30)` | 是 | `event/session_summary/manual` | 索引 |
| `source_id` | `text` | 是 | 来源记录 ID | 唯一约束的一部分 |
| `title` | `varchar(200)` | 是 | 情节标题 | 非空 |
| `summary` | `text` | 是 | 情节摘要 | 非空 |
| `content_json` | `text` | 是 | 结构化内容 | 默认 `{}` |
| `visibility` | `varchar(30)` | 是 | 可见范围 | 索引 |
| `importance` | `integer` | 是 | 业务重要度 | 1~5 |
| `confidence` | `float` | 是 | 置信度 | 0~1 |
| `promotion_key` | `text` | 否 | 语义提升聚合键 | 索引 |
| `occurred_at` | `text` | 是 | 事件时间锚点 | 索引 |
| `status` | `varchar(20)` | 是 | `active/superseded/deleted` | 索引 |
| `created_at` | `text` | 是 | 创建时间 | 非空 |
| `updated_at` | `text` | 是 | 更新时间 | 非空 |

#### 3.2.3 `memory_cards`

保留现有真相源角色，继续承载 `L3` 稳定事实、偏好和关系。第一阶段在不破坏旧接口的前提下新增以下字段：

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `search_text` | `text` | 否 | 召回使用的归一化文本 | 阶段 1 新增 |
| `search_tsv` | `tsvector` | 否 | PostgreSQL 关键词投影 | GIN 索引 |
| `embedding` | `vector` | 否 | `pgvector` 向量投影 | 向量索引 |
| `projection_version` | `integer` | 是 | 投影版本号 | 默认 1 |
| `projection_updated_at` | `text` | 否 | 最近投影刷新时间 | 允许为空 |

说明：

- `memory_cards` 仍然是 `L3` 真相源，不因为检索需要改变语义。
- 第一阶段允许把召回投影直接放在 `memory_cards`，尽快闭环。
- 第三阶段会把统一召回迁移到独立 `memory_recall_documents`，届时这些字段可保留为兼容或下线。

#### 3.2.4 `knowledge_documents`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 外部知识 ID | 主键 |
| `household_id` | `text` | 是 | 家庭 ID | 索引 |
| `source_kind` | `varchar(30)` | 是 | `plugin_raw_record/doc/rule` | 索引 |
| `source_ref` | `text` | 是 | 来源引用 | 唯一约束的一部分 |
| `title` | `varchar(200)` | 是 | 标题 | 非空 |
| `summary` | `text` | 是 | 摘要 | 非空 |
| `body_text` | `text` | 是 | 可检索正文 | 非空 |
| `visibility` | `varchar(30)` | 是 | 可见范围 | 索引 |
| `updated_at` | `text` | 是 | 来源更新时间 | 非空 |
| `status` | `varchar(20)` | 是 | `active/archived` | 索引 |

#### 3.2.5 `memory_recall_documents`

这是第三阶段的统一召回投影表。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 召回文档 ID | 主键 |
| `household_id` | `text` | 是 | 家庭 ID | 索引 |
| `layer` | `varchar(10)` | 是 | `L1/L2/L3/L4` | 索引 |
| `source_kind` | `varchar(30)` | 是 | 来源类型 | 索引 |
| `source_id` | `text` | 是 | 来源 ID | 唯一约束的一部分 |
| `subject_member_id` | `text` | 否 | 关联成员 | 索引 |
| `visibility` | `varchar(30)` | 是 | 可见范围 | 索引 |
| `group_hint` | `varchar(30)` | 是 | `session_summary/recent_event/stable_fact/external_knowledge` | 索引 |
| `search_text` | `text` | 是 | 归一化召回文本 | 非空 |
| `search_tsv` | `tsvector` | 是 | 关键词投影 | GIN 索引 |
| `embedding` | `vector` | 否 | 向量投影 | 向量索引 |
| `importance` | `integer` | 是 | 重要度 | 1~5 |
| `confidence` | `float` | 是 | 置信度 | 0~1 |
| `occurred_at` | `text` | 否 | 时间锚点 | 索引 |
| `updated_at` | `text` | 是 | 最近投影时间 | 非空 |
| `status` | `varchar(20)` | 是 | `ready/stale/failed` | 索引 |

#### 3.2.6 `conversation_memory_reads`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 读取记录 ID | 主键 |
| `session_id` | `text` | 是 | 对话会话 ID | 索引 |
| `request_id` | `text` | 是 | 请求 ID | 索引 |
| `group_name` | `varchar(30)` | 是 | 注入分组 | 索引 |
| `layer` | `varchar(10)` | 是 | 所属层级 | 索引 |
| `source_kind` | `varchar(30)` | 是 | 来源类型 | 索引 |
| `source_id` | `text` | 是 | 来源 ID | 索引 |
| `score` | `float` | 是 | 最终注入分数 | 非负 |
| `rank` | `integer` | 是 | 分组内排序 | 非负 |
| `reason_json` | `text` | 是 | 命中原因、排序因子 | 默认 `{}` |
| `created_at` | `text` | 是 | 记录时间 | 非空 |

### 3.3 接口契约

覆盖需求：2、3、4、5、6、7

#### 3.3.1 `build_memory_recall_bundle(...)`

- 类型：函数 / 服务接口
- 输入：
  - `household_id`
  - `requester_member_id`
  - `actor`
  - `query`
  - `capability`
  - `session_id`
- 输出：
  - `session_summary_hits`
  - `recent_event_hits`
  - `stable_fact_hits`
  - `external_knowledge_hits`
  - `degraded`
  - `trace_items`
- 校验：
  - 必须先做权限过滤
  - 必须支持降级到关键词召回
- 错误：
  - 召回异常返回降级结果，不直接抛出致命错误给主链路

#### 3.3.2 `refresh_session_summary(...)`

- 类型：函数 / 后台任务
- 输入：
  - `session_id`
  - `trigger_reason`
  - `force`
- 输出：
  - 最新 `conversation_session_summaries`
- 校验：
  - 只处理存在的会话
  - 只有达到阈值或 `force=true` 时才刷新
- 错误：
  - 刷新失败更新 `status=failed` 并记录日志

#### 3.3.3 `promote_episodic_to_semantic(...)`

- 类型：后台任务 / 聚合函数
- 输入：
  - `household_id`
  - `promotion_key`
  - `window`
  - `threshold`
- 输出：
  - 新建或更新的 `memory_card`
- 校验：
  - 必须基于时间窗口和重复次数
  - 必须保留来源追踪
- 错误：
  - 失败不能删除原始情节层记录

#### 3.3.4 `preview_memory_context_bundle`

现有接口继续保留，但返回结构扩展为真正分组后的 recall bundle。

- 类型：HTTP
- 路径：`POST /memories/context-bundle/preview`
- 输入：现有 `household_id/requester_member_id/question/capability`
- 输出：新增分组后的 recall 结果和 `degraded` 标记
- 错误：保持现有 API 风格，不改错误语义

## 4. 数据与状态模型

### 4.1 数据关系

- `conversation_messages` 是 `L0` 的原始消息来源。
- `conversation_session_summaries` 由 `conversation_messages` 和提案执行结果生成，属于 `L1` 真相源。
- `event_records` 是事件原始输入，`episodic_memory_entries` 是从事件和会话摘要提炼出来的 `L2` 真相源。
- `memory_cards` 是 `L3` 真相源，来自显式确认和 `L2 -> L3` 提升。
- `knowledge_documents` 是 `L4` 真相源，来自插件原始记录或规则文档导入。
- `memory_recall_documents` 是 `L1-L4` 的统一投影，不替代任何真相源。
- `conversation_memory_reads` 只记录“读了什么”，不改变真相源内容。

### 4.2 状态流转

#### 4.2.1 会话摘要状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `fresh` | 当前摘要可直接使用 | 刷新成功 | 新消息达到阈值 |
| `stale` | 摘要存在但需要重刷 | 新增消息或确认事项超阈值 | 进入重建 |
| `rebuilding` | 正在异步刷新 | 任务启动 | 成功或失败 |
| `failed` | 最近一次刷新失败 | 刷新异常 | 下次重试成功 |

#### 4.2.2 情节记忆状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `active` | 可参与召回 | 创建成功 | 被替代或删除 |
| `superseded` | 已被更高层或更新记录替代 | Promotion 或合并 | 保留历史 |
| `deleted` | 不再参与召回 | 人工删除或失效 | 无 |

#### 4.2.3 召回投影状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `ready` | 可参与召回 | 投影成功 | 来源变更 |
| `stale` | 来源已变更，需要刷新 | 来源更新 | 刷新成功 |
| `failed` | 刷新失败 | 投影异常 | 下次刷新成功 |

## 5. 错误处理

### 5.1 错误类型

- `memory_projection_extension_missing`：`pgvector` 不可用
- `memory_embedding_unavailable`：embedding 提供方不可用
- `memory_permission_denied`：权限过滤不通过
- `session_summary_refresh_failed`：会话摘要刷新失败
- `semantic_promotion_failed`：情节提升失败
- `memory_recall_degraded`：召回进入降级模式

### 5.2 处理策略

1. `pgvector` 不可用：
   - 系统启动时探测扩展
   - 降级到关键词召回
   - 在调试输出和健康检查里明确标记降级

2. embedding 失败：
   - 不覆盖旧投影
   - 保留 `tsvector` 查询
   - 异步重试，不阻塞当前回答

3. 权限过滤失败：
   - 在注入前截断
   - 不把异常数据写进 prompt 或 trace

4. 会话摘要失败：
   - 标记 `failed`
   - 下轮不阻塞主链路，继续使用最近 `fresh/stale` 版本或直接退回最近消息

## 6. 正确性属性

### 6.1 真相源优先于召回投影

对于任何一条记忆，只允许真相源更新事实内容；召回投影可以重建、失效或延迟刷新，但不得反向改写真相源。

**验证需求：** 需求 2、需求 7

### 6.2 权限过滤必须早于 prompt 注入

对于任何 actor，只允许把该 actor 可见的数据进入召回结果和 prompt 注入，调试链路也不得越权泄露内容。

**验证需求：** 需求 5、需求 7

### 6.3 注入 trace 必须和实际注入一致

对于任何一轮 `free_chat`，`conversation_memory_reads` 里的来源集合必须与实际拼进 prompt 的来源集合一一对应。

**验证需求：** 需求 5

### 6.4 情节提升不丢原始来源

对于任何从 `L2` 提升到 `L3` 的事实，都必须保留来源事件或来源会话摘要的追踪关系。

**验证需求：** 需求 3

## 7. 测试策略

### 7.1 单元测试

- Hybrid rerank 分数计算
- 权限过滤
- 会话摘要阈值判定
- 情节提升阈值判定
- 分组注入格式化

### 7.2 集成测试

- PostgreSQL `tsvector + GIN` 查询
- `pgvector` 查询和降级逻辑
- `memory_cards` 投影刷新
- `conversation_session_summaries` 刷新
- `free_chat` 注入 trace 落库

### 7.3 端到端测试

- 用户明确“记住”后，下轮 `free_chat` 能命中该记忆
- 重复观察触发语义提升后，能从稳定事实组召回
- 会话聊天达到阈值后，会话摘要参与下一轮注入
- 规则文档导入后，外部知识组可被召回

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| 需求 1 | 2.1、3.2、4.1 | 模型和服务集成测试 |
| 需求 2 | 2.3.4、3.2.3、3.2.5 | PostgreSQL 集成测试 |
| 需求 3 | 2.3.1、2.3.2、3.3.3 | 事件写入与提升测试 |
| 需求 4 | 2.3.3、3.2.1、4.2.1 | 会话摘要刷新测试 |
| 需求 5 | 2.3.4、3.3.1、3.2.6 | `free_chat` 注入端到端测试 |
| 需求 6 | 2.3.5、3.2.4、3.2.5 | 外部知识导入与召回测试 |
| 需求 7 | 5、6 | 回归测试与降级测试 |

## 8. 风险与待确认项

### 8.1 风险

- `pgvector` 扩展在开发、测试、生产环境的安装一致性需要先确认。
- embedding 模型和维度一旦切换，会带来重建成本。
- 会话摘要如果刷新太频繁，会增加后台负担；太慢又会让 `L1` 失去价值。
- 第三阶段把多来源统一进召回投影时，如果边界没收好，最容易重新长出复杂分支。

### 8.2 待确认项

- 第一阶段向量模型使用哪一个现有 AI 供应商能力作为默认 embedding 来源。
- `conversation_session_summaries` 的刷新阈值是按“新增消息数”还是“新增 token 数”为主。
- `L4` 外部知识的默认可见性是否允许 `family` 级共享，还是必须逐来源声明。

### 8.3 分期落地策略

#### 第一期：最小闭环

- 给 `memory_cards` 增加 `search_text/search_tsv/embedding`
- 打通 PostgreSQL 关键词召回和向量召回
- 修复 `free_chat` 注入，按组注入并写 trace

#### 第二期：会话记忆

- 新增 `conversation_session_summaries`
- 建立会话摘要刷新服务
- 让 `L1` 正式参与召回

#### 第三期：统一召回

- 新增 `episodic_memory_entries`、`knowledge_documents`
- 建立 `memory_recall_documents`
- 把 `L1/L2/L3/L4` 全部收口进统一召回链路
