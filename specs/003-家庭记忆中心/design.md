# 设计文档 - 家庭记忆中心

状态：Draft

## 1. 概述

### 1.1 目标

- 把家庭长期记忆从概念变成真实可落库、可检索、可治理的能力
- 在不破坏现有上下文中心、问答、提醒链路的前提下，补齐长期记忆层
- 用最简单但可演进的方式实现长期记忆，不在第一版引入不必要复杂度

### 1.2 覆盖需求

- `requirements.md` 需求 1：统一记忆写回入口
- `requirements.md` 需求 2：结构化长期记忆卡
- `requirements.md` 需求 3：长期记忆接入 Context Engine
- `requirements.md` 需求 4：长期记忆检索与问答接入
- `requirements.md` 需求 5：记忆纠错、失效和删除治理
- `requirements.md` 需求 6：管理台与用户端记忆中心接入

### 1.3 当前现状判断

当前代码已经有几块能直接复用的地基：

- `apps/api-server/app/modules/context/service.py`：可生成家庭实时上下文总览
- `apps/api-server/app/modules/context/cache_service.py`：已有轻量上下文缓存
- `apps/api-server/app/modules/family_qa/fact_view_service.py`：可把上下文、提醒、场景拼成问答事实视图
- `apps/api-server/app/modules/family_qa/schemas.py`：已预留 `QaMemorySummary`
- `apps/user-web/src/pages/MemoriesPage.tsx`：已有记忆页面外壳，但仍是 mock

当前缺口也很清楚：

- 还没有真正的 `memory_cards`、`memory_card_members`、`event_records` 实现
- 问答服务还没有实际走长期记忆检索
- 上下文缓存还是“当前状态缓存”，不是长期记忆上下文引擎
- 提醒、场景、在家状态、问答结果还没统一写回

### 1.4 技术约束与设计原则

- 后端：`Python + FastAPI + SQLAlchemy`
- 前端：`React`
- 数据存储：当前以 `SQLite` 为主，后续可演进
- 缓存：当前已有本地内存缓存能力，后续可换 `Redis`
- 认证授权：沿用现有 admin / member actor 体系

设计原则：

1. **先保留原始事件，再生成摘要**。这点借鉴 `lossless-claw` 的思路，原始上下文不能先天丢失。
2. **先做结构化检索，再谈语义检索**。第一版先把数据结构做对，不先堆向量库。
3. **上下文按目标裁剪，不做全量拼接**。这点借鉴 OpenClaw 的长期记忆与 Context Engine 思路。
4. **绝不破坏现有接口**。当前 `context`、`family_qa`、`reminder`、`scene` 先保留现有行为，逐步接入长期记忆。

## 2. 架构

### 2.1 系统结构

家庭记忆中心采用“两层数据 + 一个拼装引擎”的结构：

1. **事件流水层**
   - 保存原始事实来源
   - append-only
   - 支持重放、幂等、追责

2. **长期记忆层**
   - 保存可直接服务问答、提醒、陪伴的结构化记忆
   - 支持更正、失效、删除、权限过滤

3. **Context Engine**
   - 按请求类型、成员身份、权限范围、token 预算拼装上下文
   - 合并实时上下文、长期记忆、最近事件、待处理事项

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `memory_event_ingestor` | 接收各模块写回事件 | presence / reminder / scene / qa / manual | `event_records` |
| `memory_extractor` | 从事件提炼记忆卡 | `event_records` | `memory_cards`、`memory_card_members` |
| `memory_revision_service` | 处理纠错、失效、删除 | 人工操作、系统合并 | `memory_card_revisions`、有效记忆状态 |
| `memory_query_service` | 搜索和筛选长期记忆 | 查询条件、权限范围 | 记忆候选集 |
| `context_engine` | 拼装服务上下文 | 实时上下文、长期记忆、最近事件、权限 | `MemoryContextBundle` |
| `memory_api` | 提供前端与内部接口 | HTTP 请求 | 列表、详情、查询、修订结果 |

### 2.3 关键流程

#### 2.3.1 记忆写回流程

1. `presence`、`reminder`、`scene`、`family_qa`、前端人工录入调用统一写回入口。
2. 系统先写 `event_records`，保证原始事件落库。
3. `memory_extractor` 判断是否值得生成或更新记忆卡。
4. 如命中去重键，则更新已有记忆卡而不是新增重复卡。
5. 记忆卡变更后刷新热摘要和上下文缓存。

#### 2.3.2 长期记忆检索流程

1. 问答或前端请求先拿到 actor 和 household。
2. 系统生成权限范围：可见成员、可见房间、可见可见性级别。
3. 先做结构化筛选：成员、类型、时间、状态、可见性。
4. 再做关键词检索和轻量排序。
5. 输出候选记忆，并生成可解释事实引用。

#### 2.3.3 Context Engine 拼装流程

1. 根据能力类型选择上下文模板，如 `family_qa`、`assistant_chat`、`reminder_broadcast`。
2. 拉取实时上下文：活跃成员、在家状态、房间占用、设备概览。
3. 拉取长期记忆：事实、偏好、关系、近期重要事件。
4. 合并待处理事项：提醒、运行中场景、未确认事件。
5. 在预算内裁剪输出，形成结构化 `MemoryContextBundle`。

#### 2.3.4 纠错与删除流程

1. 前端发起更正、失效或删除请求。
2. 系统先做权限校验。
3. 生成 `memory_card_revisions` 记录。
4. 更新当前有效记忆状态。
5. 刷新热摘要、搜索结果和上下文缓存。

#### 2.3.5 历史回填流程

1. 从现有 `presence_events`、提醒流水、场景执行记录中读取历史记录。
2. 转换成统一 `event_records`。
3. 按幂等键逐批写入。
4. 执行提炼流程生成首批长期记忆卡。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5、6

- `app/modules/memory/models.py`
- `app/modules/memory/schemas.py`
- `app/modules/memory/repository.py`
- `app/modules/memory/service.py`
- `app/modules/memory/context_engine.py`
- `app/api/v1/endpoints/memories.py`

### 3.2 数据模型

#### 3.2.1 `event_records`

用途：

- 保存所有可沉淀为长期记忆的原始输入
- 作为回放、重试和追责的唯一事实来源

字段建议：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `text pk` | 事件 ID |
| `household_id` | `text fk` | 所属家庭 |
| `event_type` | `varchar(50)` | `presence_changed` / `reminder_done` / `scene_executed` / `qa_confirmed` / `memory_manual_created` |
| `source_type` | `varchar(30)` | `presence` / `reminder` / `scene` / `qa` / `admin` / `member` |
| `source_ref` | `text nullable` | 来源对象 ID |
| `subject_member_id` | `text nullable fk` | 主要关联成员 |
| `room_id` | `text nullable fk` | 关联房间 |
| `payload_json` | `text` | 原始事件内容 |
| `dedupe_key` | `text nullable` | 幂等键 |
| `processing_status` | `varchar(20)` | `pending` / `processed` / `failed` / `ignored` |
| `generate_memory_card` | `integer` | 是否尝试生成记忆 |
| `failure_reason` | `text nullable` | 失败原因 |
| `occurred_at` | `text` | 事件发生时间 |
| `created_at` | `text` | 写入时间 |
| `processed_at` | `text nullable` | 处理完成时间 |

关键规则：

- `event_records` append-only，不做物理覆盖更新
- `dedupe_key` 命中时只更新处理状态，不新增重复记忆
- 所有外部来源先落事件，再做后续提炼

#### 3.2.2 `memory_cards`

用途：

- 保存可直接服务于问答、提醒和陪伴的结构化长期记忆

字段建议：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `text pk` | 记忆 ID |
| `household_id` | `text fk` | 所属家庭 |
| `memory_type` | `varchar(30)` | `fact` / `event` / `preference` / `relation` / `growth` |
| `title` | `varchar(200)` | 标题 |
| `summary` | `text` | 人类可读摘要 |
| `normalized_text` | `text` | 用于检索的归一化文本 |
| `content_json` | `text` | 结构化正文 |
| `status` | `varchar(20)` | `active` / `pending_review` / `invalidated` / `deleted` |
| `visibility` | `varchar(30)` | `public` / `family` / `private` / `sensitive` |
| `importance` | `integer` | 1~5 |
| `confidence` | `real` | 0~1 |
| `subject_member_id` | `text nullable fk` | 主体成员 |
| `source_event_id` | `text nullable fk` | 来源事件 |
| `dedupe_key` | `text nullable` | 去重键 |
| `effective_at` | `text nullable` | 生效时间 |
| `last_observed_at` | `text nullable` | 最近一次被观察到 |
| `created_by` | `varchar(30)` | `system` / `admin` / `member` |
| `created_at` | `text` | 创建时间 |
| `updated_at` | `text` | 更新时间 |
| `invalidated_at` | `text nullable` | 失效时间 |

关键规则：

- 同一长期事实优先更新旧卡，而不是生成多张内容等价的卡
- `status != active` 的卡默认不参与上下文拼装
- `visibility` 必须参与查询和上下文过滤

#### 3.2.3 `memory_card_members`

用途：

- 显式维护记忆卡和成员的关系

字段建议：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `memory_id` | `text fk` | 记忆 ID |
| `member_id` | `text fk` | 成员 ID |
| `relation_role` | `varchar(30)` | `subject` / `participant` / `mentioned` / `owner` |

约束：

- `primary key(memory_id, member_id, relation_role)`

#### 3.2.4 `memory_card_revisions`

用途：

- 保存更正、合并、失效、删除历史

字段建议：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `text pk` | 修订 ID |
| `memory_id` | `text fk` | 记忆 ID |
| `revision_no` | `integer` | 版本号 |
| `action` | `varchar(30)` | `create` / `correct` / `merge` / `invalidate` / `delete` |
| `before_json` | `text nullable` | 变更前快照 |
| `after_json` | `text nullable` | 变更后快照 |
| `reason` | `text nullable` | 原因 |
| `actor_type` | `varchar(30)` | `system` / `admin` / `member` |
| `actor_id` | `text nullable` | 操作者 |
| `created_at` | `text` | 创建时间 |

### 3.3 检索与排序策略

#### 3.3.1 第一版检索策略

第一版不做花哨东西，按下面顺序来：

1. 权限过滤
2. 结构化筛选
3. 关键词匹配
4. 简单排序

排序建议分数：

- 成员直接命中：`+40`
- `memory_type` 与问题意图一致：`+20`
- 最近 30 天事件：`+15`
- `importance >= 4`：`+10`
- `confidence >= 0.8`：`+10`
- 敏感记忆：无权限直接过滤

#### 3.3.2 热摘要策略

热摘要不是新的事实源，只是缓存层。

建议缓存两类结果：

- 按家庭维度：近期重要事件、全局偏好变化、提醒未完成事项
- 按成员维度：高频偏好、近期事件、关系摘要

缓存来源：

- `memory_cards`
- `event_records`
- `context/service.py` 当前实时上下文

缓存失效条件：

- 记忆卡新增、更新、失效、删除
- 提醒状态变化
- 成员在家状态发生显著变化

### 3.4 Context Engine 设计

#### 3.4.1 目标

Context Engine 不是“再做一个缓存”，而是负责把当前请求真正需要的上下文拼出来。

#### 3.4.2 输入切片

输入至少包含以下切片：

- `request_profile`
  - `household_id`
  - `requester_member_id`
  - `capability`
  - `channel`
- `live_context_slice`
  - 活跃成员
  - 成员状态
  - 房间占用
  - 设备摘要
- `memory_slice`
  - 事实记忆
  - 偏好记忆
  - 关系记忆
  - 最近事件记忆
- `task_slice`
  - 待处理提醒
  - 运行中场景
- `guardrail_slice`
  - 权限范围
  - 脱敏规则
  - 降级标记

#### 3.4.3 输出结构

建议定义 `MemoryContextBundle`：

| 字段 | 说明 |
| --- | --- |
| `household_id` | 家庭 ID |
| `requester_member_id` | 请求者成员 |
| `capability` | 当前能力 |
| `live_context_summary` | 实时上下文摘要 |
| `memory_facts` | 结构化长期记忆列表 |
| `recent_events` | 最近事件列表 |
| `pending_items` | 待处理提醒和场景摘要 |
| `masked_sections` | 被权限或降级裁掉的部分 |
| `degraded` | 是否降级 |
| `generated_at` | 生成时间 |

#### 3.4.4 裁剪规则

- `family_qa`：优先成员事实、偏好、关系、近期事件
- `assistant_chat`：优先当前聊天对象相关的长期记忆和最近互动
- `reminder_broadcast`：优先提醒对象、房间上下文、静默规则
- `scene_explanation`：优先触发事件、受影响成员、冲突偏好

### 3.5 API 设计

#### 3.5.1 `GET /api/v1/memories`

用途：

- 查询记忆列表

输入：

- `household_id`
- `memory_type`
- `member_id`
- `status`
- `visibility`
- `query`
- `limit`
- `cursor`

输出：

- 记忆列表
- 总数或分页游标
- 降级标记

错误处理：

- 无权限：`403`
- 家庭不存在：`404`
- 查询参数非法：`422`

#### 3.5.2 `GET /api/v1/memories/{memory_id}`

用途：

- 查看记忆详情和修订历史摘要

#### 3.5.3 `POST /api/v1/memories/events`

用途：

- 写入统一事件流水

调用方：

- 内部模块优先使用，不直接暴露给普通用户端

#### 3.5.4 `POST /api/v1/memories/cards/manual`

用途：

- 管理员或授权成员手动创建记忆

#### 3.5.5 `POST /api/v1/memories/{memory_id}/corrections`

用途：

- 记忆纠错、失效、删除

输入：

- `action`
- `reason`
- `patch`

#### 3.5.6 `POST /api/v1/memories/query`

用途：

- 供问答和助手调用的结构化检索入口

### 3.6 与现有模块的集成点

#### 3.6.1 `presence`

- `apps/api-server/app/modules/presence/service.py`
- 成员在家状态变化时写 `presence_changed` 事件
- 重要状态切换可生成事件记忆或事实更新

#### 3.6.2 `reminder`

- `apps/api-server/app/modules/reminder/service.py`
- 提醒创建、确认、升级时写事件
- 用于生成长期提醒偏好、依从性和关键完成记录

#### 3.6.3 `scene`

- `apps/api-server/app/modules/scene/service.py`
- 场景执行成功/失败写事件
- 重要联动结果可沉淀为事件记忆

#### 3.6.4 `family_qa`

- `apps/api-server/app/modules/family_qa/fact_view_service.py`
- `apps/api-server/app/modules/family_qa/service.py`
- 用 `memory_query_service` 替换现在的“记忆暂未接入”占位
- 问答结果本身也可选择性回写记忆事件

#### 3.6.5 `context`

- `apps/api-server/app/modules/context/service.py`
- 继续负责实时上下文
- 由新的 `context_engine` 在其之上拼长期记忆切片

## 4. 正确性约束

### 4.1 不变量

1. 每条有效记忆卡都必须能追到至少一个来源事件或人工创建记录。
2. 无权限 actor 永远不能通过列表、详情或上下文拼装拿到敏感记忆正文。
3. 失效或删除后的记忆卡不能继续进入 `family_qa` 或 Context Engine 结果。
4. 事件写回失败不应破坏原有提醒、问答、场景主流程。

### 4.2 幂等规则

1. 同一来源重复写入必须由 `dedupe_key` 收敛。
2. 回填脚本重复执行不得制造重复长期记忆。
3. 纠错操作必须基于 revision 序号，避免覆盖并发修改。

## 5. 错误处理

### 5.1 写回失败

- 保留 `event_records`
- 标记 `processing_status=failed`
- 记录 `failure_reason`
- 支持后台重试或人工回放

### 5.2 检索失败或缓存不可用

- 退回数据库直接查询
- 在响应中标记 `degraded=true`
- 不影响现有上下文与问答主链路

### 5.3 权限失败

- 返回 `403`
- 审计日志记录 actor、目标记忆和操作类型

### 5.4 数据冲突

- 去重键冲突时优先更新旧卡
- revision 冲突时拒绝写入并要求重新获取最新版本

## 6. 迁移与兼容策略

### 6.1 迁移顺序

1. 新增表和模块，不动现有接口行为
2. 先接写回，不立刻切掉旧问答逻辑
3. 再接 `family_qa` 的长期记忆检索
4. 最后替换前端 mock 和记忆中心页面

### 6.2 向后兼容

- `context/overview` 保持原接口不变
- `family_qa` 在记忆未命中或模块关闭时继续使用原有 fact view 能力
- 用户端和管理台在接口未接完前保留降级提示

### 6.3 功能开关

建议增加：

- `memory_center_enabled`
- `memory_writeback_enabled`
- `memory_context_engine_enabled`
- `memory_backfill_enabled`

## 7. 测试策略

### 7.1 单元测试

- 事件去重
- 记忆提炼
- 权限过滤
- revision 冲突

### 7.2 服务测试

- `POST /memories/events`
- `GET /memories`
- `POST /memories/query`
- `POST /memories/{id}/corrections`

### 7.3 集成测试

- `presence -> event_records -> memory_cards`
- `reminder -> event_records -> memory_cards`
- `family_qa + memory_query_service`
- `context_engine + permission_scope`

### 7.4 前端验收

- 管理台记忆中心查询、筛选、纠错、删除
- 用户端记忆页从 mock 切到真实数据
- 权限遮罩和降级提示可见

## 8. 风险与回滚

### 8.1 主要风险

- 记忆重复爆炸
- 权限泄露
- LLM 参与提炼时引入幻觉
- 热摘要与真实数据不一致

### 8.2 控制办法

- 第一版优先规则提炼，AI 只做补充摘要，不做唯一事实来源
- 统一幂等键和 revision 机制
- Context Engine 先权限过滤，再做拼装
- 热摘要随写操作显式失效

### 8.3 回滚策略

- 关闭 `memory_context_engine_enabled`，问答回退到现有 fact view
- 关闭 `memory_writeback_enabled`，主流程继续运行但暂停长期记忆新增
- 保留已写事件与记忆数据，便于后续重新启用
