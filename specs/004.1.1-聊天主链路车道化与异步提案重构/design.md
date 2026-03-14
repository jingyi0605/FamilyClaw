# 设计文档 - 聊天主链路车道化与异步提案重构

状态：Draft

## 1. 概述

这次不是修一个记忆误判，而是把聊天主链路重新摆正。

旧模型的核心问题有三个：

1. 顶层把“业务意图”当成第一层路由，导致意图类型越长越多。
2. 很多能力其实不是互斥分支，而是“聊天结束后可能顺手产出的提案”。
3. 一旦主路由不准，就开始出现 guardrail、fallback、补提取、分支特判，最后谁都说不清这轮消息到底走了哪几条暗路。

新模型的基本判断很简单：

- 先看这轮请求是否必须立刻做事
- 再看它是否必须立刻拿到真实数据
- 其他都先完成聊天，然后统一做后处理提案

这比按“记忆 / 配置 / 提醒 / 问答 / 闲聊”分业务意图稳定得多。

## 2. 设计目标

### 2.1 目标

- 把主链路稳定在三车道，不再让业务意图树无限扩张
- 只给强实时动作保留前置快判
- 把提案型能力统一下沉到回合后分析
- 严格限制提案证据来源
- 让新增能力以注册分析器的方式接入

### 2.2 非目标

- 不在这份设计里展开每一个插件动作的执行细节
- 不在这里替换所有 UI 样式
- 不在这里解决语音识别前端输入层问题
- 不在这里一次性移除全部旧表和旧接口

## 3. 总体架构

### 3.1 三车道模型

主链路只保留下面三个稳定车道：

1. **快执行车道**
   - 用于设备控制、场景触发、停止中的动作
   - 特点是强实时、有副作用、需要快速回执

2. **实时取数车道**
   - 用于查询设备状态、成员状态、提醒状态、家庭事实
   - 本质上仍然是聊天，只是中间需要同步读取真实数据

3. **异步提案车道**
   - 用于记忆提案、配置建议、提醒草稿、后续可能扩展的偏好或成长提案
   - 不阻塞主回复，回合结束后统一分析

这三个车道按执行约束划分，不按业务名词划分。

### 3.2 新的回合处理流程

一轮聊天请求按下面顺序处理：

1. 写入用户消息，创建回合上下文
2. 执行车道选择器
3. 若命中快执行车道：
   - 解析动作目标
   - 做权限检查
   - 执行动作或要求澄清
   - 返回回执
4. 若命中实时取数车道：
   - 读取所需实时数据
   - 走聊天回答生成
5. 若未命中前两条：
   - 走普通聊天主回复
6. 主回复完成后：
   - 触发统一的提案分析管线
   - 产出一个提案批次
   - 交给策略层决定 ask / auto / ignore

这里最关键的一点是：提案分析不再改写本轮主回复的执行路线。

## 4. 组件设计

### 4.1 车道选择器

车道选择器不再回答“这是 memory_write 还是 config_change”，只回答下面几个稳定问题：

- `needs_fast_execution`
- `needs_realtime_data`
- `has_side_effect`
- `requires_clarification`

输出建议结构：

```json
{
  "lane": "fast_action | realtime_query | free_chat",
  "confidence": 0.0,
  "reason": "人话说明",
  "target_kind": "device_action | scene_action | state_query | none",
  "requires_clarification": false
}
```

说明：

- `free_chat` 在这里不是一个业务意图，只表示“主回复先按聊天处理”
- 记忆、配置、提醒不再作为顶层 lane 出现

### 4.2 第二层轻语义路由方案

这里现在直接定死，不再保留多个备选实现。

唯一方案：

- **`Embedding + Capability Descriptor Retrieval`**

明确不选：

- 关键词主路由
- 小模型分类器
- 再打一轮大模型正文理解

原因很直接：

1. 关键词主路由后续一定会越堆越长，最后退化成补丁表。
2. 小模型分类器需要稳定标注集、训练和回归体系，当前项目阶段不值得先背这套维护成本。
3. 再打一轮大模型做路由太贵，而且会把大部分普通聊天抬成多次 LLM 调用。

#### 4.2.1 路由分层

第二层轻语义路由只在第一层硬信号没有命中时运行。

第一层硬信号包括：

- `session_mode`
- UI 显式动作入口
- 结构化 payload
- 已存在的待确认动作或待处理提案
- 语音快控 channel

只有这些都没命中，才进入第二层语义检索。

#### 4.2.2 Descriptor 设计

系统不再维护一堆业务意图关键词，而是维护一组能力描述文本。

最少包含下面几类 descriptor：

- `fast_action.device_control`
- `realtime_query.state_query`
- `free_chat.normal_chat`
- `proposal.memory_candidate`
- `proposal.config_candidate`
- `proposal.reminder_candidate`

每个 descriptor 不只是一句定义，还应包含：

- 1 条主描述
- 5 到 10 条典型用户表达样例
- 可选的负例说明

这样新增能力时，只需要新增 descriptor，不需要改顶层路由判断核心。

#### 4.2.3 路由输出

第二层语义路由输出两类结果：

1. 车道建议
2. 提案 gate 建议

建议输出结构：

```json
{
  "lane_scores": [
    {"lane": "fast_action", "descriptor_id": "fast_action.device_control", "score": 0.0},
    {"lane": "realtime_query", "descriptor_id": "realtime_query.state_query", "score": 0.0},
    {"lane": "free_chat", "descriptor_id": "free_chat.normal_chat", "score": 0.0}
  ],
  "proposal_gate_scores": [
    {"proposal_kind": "memory_write", "descriptor_id": "proposal.memory_candidate", "score": 0.0},
    {"proposal_kind": "config_apply", "descriptor_id": "proposal.config_candidate", "score": 0.0},
    {"proposal_kind": "reminder_create", "descriptor_id": "proposal.reminder_candidate", "score": 0.0}
  ]
}
```

#### 4.2.4 第一版阈值

第一版先给出工程基线，而不是等实现时随便拍脑袋：

- Top1 lane score `< 0.55`：保守回到 `free_chat`
- Top1 lane score `>= 0.55` 且 `Top1 - Top2 >= 0.08`：命中 Top1 lane
- 分差不足：进入澄清或保守回落
- proposal gate score `>= 0.62`：允许进入提案门控
- proposal gate score `< 0.62`：不触发统一提案提取

这些值不是神圣常量，但它们是第一版必须明确落地的默认值。

#### 4.2.5 为什么这个方案最合适

这套方案最大的好处不是“看起来高级”，而是它最符合后续扩展方式：

- 以后增加的是能力，不是越来越长的意图枚举
- 以后维护的是 descriptor，不是越来越长的 if/else
- 成本远低于再打一轮大模型
- 实施成本远低于训练和维护小模型分类器

### 4.3 Embedding 供应策略

Embedding 供应方式现在也直接定死，不留多个方向摇摆。

默认策略：

- **内置轻量 Embedding 模型**

扩展策略：

- **支持用户自定义 Embedding 提供方并切换使用**

#### 4.3.1 为什么必须内置

如果默认不内置，语义路由就会变成“先做一大堆接入工作才能跑”，这很蠢。

内置的目的不是追求最强，而是保证：

- 开箱可用
- 本地开发可用
- 没有外部配置时也能跑完整主链路

内置模型要求：

- 轻量
- 推理成本可控
- 适合短文本语义相似度
- 能覆盖中文家庭对话的基本检索需求

这里直接给出默认模型，不再留空：

- **默认内置模型：`BAAI/bge-small-zh-v1.5`**

选择它的原因：

- 当前主场景是中文家庭对话，不需要先为多语言做额外成本
- 它是中文向量模型，不是泛多语言折中方案
- 它属于 small 档，资源占用明显低于 base / large
- 第一版 descriptor 路由和 proposal gate 更看重短文本相似度，不需要大尺寸模型

默认规格直接写死：

- `model_name`: `BAAI/bge-small-zh-v1.5`
- `vector_dimension`: `512`
- `max_tokens`: `512`
- `provider_code`: `builtin_bge_small_zh_v15`

第一版不推荐默认内置这些模型：

- `BAAI/bge-base-zh-v1.5`：更重，当前主路由收益不值这个成本
- `BAAI/bge-large-zh-v1.5`：太重，不适合默认本地内置
- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`：泛多语言更灵活，但当前中文家庭场景优先级低于中文专用模型

#### 4.3.2 为什么还要支持用户自定义

因为不同用户对 Embedding 的要求会不同：

- 有的人更在意成本
- 有的人更在意中文语义效果
- 有的人已经有自己的模型供应商

所以系统不能把 Embedding 写死成唯一实现。

#### 4.3.3 提供方接口

建议统一成 Embedding Provider 接口：

```python
class EmbeddingProvider(Protocol):
    provider_code: str

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...
```

系统至少内置两个层次：

1. 内置默认 provider
2. 外部配置 provider

运行时由配置决定当前启用哪个 provider。

第一版建议的模块落点直接定下来：

- provider 抽象：`apps/api-server/app/modules/embedding/provider.py`
- provider 注册表：`apps/api-server/app/modules/embedding/provider_registry.py`
- 内置默认 provider：`apps/api-server/app/modules/embedding/providers/builtin_bge_small_zh_v15.py`
- 外部 provider：`apps/api-server/app/modules/embedding/providers/remote_openai_compatible.py`
- capability descriptor：`apps/api-server/app/modules/conversation/capability_descriptors.py`
- 语义路由器：`apps/api-server/app/modules/conversation/semantic_router.py`

不要把这套逻辑继续塞回 `conversation/orchestrator.py` 里。那样过几轮又会变脏。

#### 4.3.4 配置原则

配置至少包含：

- `provider_code`
- `model_name`
- `endpoint`（如需要）
- `api_key`（如需要）
- `timeout_ms`
- `vector_dimension`
- `enabled`
- `fallback_to_builtin`

建议直接落到 `apps/api-server/app/core/config.py`，字段命名先统一成下面这套：

- `embedding_default_provider_code`
- `embedding_builtin_model_name`
- `embedding_builtin_cache_dir`
- `embedding_default_timeout_ms`
- `embedding_provider_configs`

对应环境变量建议：

- `FAMILYCLAW_EMBEDDING_DEFAULT_PROVIDER_CODE`
- `FAMILYCLAW_EMBEDDING_BUILTIN_MODEL_NAME`
- `FAMILYCLAW_EMBEDDING_BUILTIN_CACHE_DIR`
- `FAMILYCLAW_EMBEDDING_DEFAULT_TIMEOUT_MS`
- `FAMILYCLAW_EMBEDDING_PROVIDER_CONFIGS`

默认值建议直接写死：

- `embedding_default_provider_code = "builtin_bge_small_zh_v15"`
- `embedding_builtin_model_name = "BAAI/bge-small-zh-v1.5"`
- `embedding_default_timeout_ms = 3000`
- `embedding_builtin_cache_dir = "apps/api-server/data/models/embeddings"`

默认行为：

- 未配置外部 provider：使用内置 provider
- 配置了外部 provider 且健康检查通过：使用外部 provider
- 外部 provider 不可用且允许回退：回退到内置 provider
- 外部 provider 不可用且不允许回退：关闭新语义路由并保留 `004.1` 基线

第一版建议不要把外部 provider 设计成自动负载均衡。

原因很简单：

- 语义路由层不值得一上来就搞复杂调度
- 先保证“内置可用、外部可替换、故障可回退”就够了
- 复杂调度以后真有需要再加

#### 4.3.5 缓存与预计算

为了避免每次请求都重复算 descriptor embedding：

- descriptor embedding 必须预计算并缓存
- 用户消息 embedding 按请求计算
- descriptor 更新后触发重建缓存

这部分是语义路由成本可控的关键，不是优化项，是默认要求。

#### 4.3.6 建议代码结构草图

第一版不要把所有逻辑继续堆回 `conversation/orchestrator.py`。建议直接按下面的结构拆：

```text
apps/api-server/app/
├─ core/
│  └─ config.py
├─ modules/
│  ├─ embedding/
│  │  ├─ provider.py
│  │  ├─ provider_registry.py
│  │  ├─ service.py
│  │  └─ providers/
│  │     ├─ builtin_bge_small_zh_v15.py
│  │     └─ remote_openai_compatible.py
│  └─ conversation/
│     ├─ semantic_router.py
│     ├─ capability_descriptors.py
│     ├─ proposal_pipeline.py
│     ├─ proposal_analyzers.py
│     ├─ proposal_policy.py
│     ├─ orchestrator.py
│     ├─ service.py
│     ├─ models.py
│     └─ repository.py
```

各模块职责直接定下来：

- `embedding/provider.py`
  - 定义 `EmbeddingProvider` 协议
  - 只定义接口，不写业务逻辑

- `embedding/provider_registry.py`
  - 注册内置 provider 和外部 provider
  - 按配置返回当前启用的 provider

- `embedding/service.py`
  - 统一封装 `embed_texts`
  - 处理 provider 切换、超时、回退、健康检查

- `embedding/providers/builtin_bge_small_zh_v15.py`
  - 封装默认内置模型加载和推理
  - 只负责本地模型，不掺杂业务判断

- `embedding/providers/remote_openai_compatible.py`
  - 封装用户自定义远端 Embedding provider
  - 只做兼容 API 调用和异常处理

- `conversation/capability_descriptors.py`
  - 放 lane descriptor 和 proposal descriptor
  - 提供 descriptor 的版本号、内容和样例

- `conversation/semantic_router.py`
  - 负责第二层语义路由
  - 输入用户消息和硬信号结果
  - 输出 lane score 和 proposal gate score

- `conversation/proposal_pipeline.py`
  - 负责统一 proposal gate 和统一提案提取
  - 不在这里做 UI 映射

- `conversation/proposal_analyzers.py`
  - 负责 memory/config/reminder analyzer 的逻辑校验和归并
  - 默认不允许每个 analyzer 自己再打一轮大模型

- `conversation/proposal_policy.py`
  - 负责 `ask / auto / ignore`
  - 不负责提案提取

- `conversation/orchestrator.py`
  - 负责第一层硬信号、车道调度、主回复编排
  - 不继续膨胀成“什么都管”的超级文件

- `conversation/service.py`
  - 负责请求落库、调用 orchestrator、写日志、兼容旧入口

建议第一版实现顺序也固定：

1. 先落 `embedding/`
2. 再落 `capability_descriptors.py`
3. 再落 `semantic_router.py`
4. 再落 `proposal_pipeline.py`
5. 最后才回头改 `orchestrator.py` 和 `service.py`

不要一上来就直接在原有 `orchestrator.py` 里硬改，那样最容易把当前链路打坏。

### 4.4 聊天回答层

聊天回答层只负责完成本轮用户可见回复。

它允许：

- 使用会话历史
- 使用家庭上下文
- 使用 Agent 设定
- 使用长期记忆上下文
- 在需要时调用实时取数能力

它不负责：

- 直接产出正式记忆
- 直接决定配置生效
- 直接把提醒草稿落成任务

### 4.5 提案分析管线

提案分析在主回复完成后统一执行。输入不是“某个业务意图”，而是本轮回合证据。

统一输入结构建议为：

```json
{
  "session_id": "xxx",
  "request_id": "xxx",
  "turn_messages": [
    {"message_id": "u1", "role": "user", "content": "..."},
    {"message_id": "a1", "role": "assistant", "content": "..."}
  ],
  "trusted_events": [],
  "conversation_history_excerpt": [],
  "lane_result": {},
  "main_reply_summary": "本轮回复摘要"
}
```

然后由多个分析器并行或串行执行：

- `memory_proposal_analyzer`
- `config_proposal_analyzer`
- `reminder_proposal_analyzer`

未来可以新增：

- `preference_proposal_analyzer`
- `relationship_proposal_analyzer`
- `growth_proposal_analyzer`

这里要写死一个非常关键的实现约束：

- **多个 analyzer 是逻辑组件，不代表多个独立 LLM 调用。**

默认实现必须是：

1. 先用第二层语义路由输出的 proposal gate 做门控
2. 只有命中 gate 的回合才进入提案提取
3. 提案提取默认只执行一次统一的 `proposal_batch_extraction`
4. 这一轮统一输出多类提案项，再由各 analyzer 做后续校验和归并

也就是说：

- analyzer 可以有多个
- 但大模型提取默认最多一次

如果把每个 analyzer 都实现成单独一次 LLM 调用，这套设计就会退化成新一轮臃肿链路，必须避免。

#### 4.5.1 统一提案提取输出

建议统一提取输出结构：

```json
{
  "memory_items": [],
  "config_items": [],
  "reminder_items": []
}
```

统一提取之后：

- `memory_proposal_analyzer` 负责记忆项校验、去重、证据边界复查
- `config_proposal_analyzer` 负责配置项校验和归一化
- `reminder_proposal_analyzer` 负责提醒草稿校验和完整性检查

#### 4.5.2 LLM 调用预算

新链路的默认预算不是“每加一个 analyzer 多打一轮”，而是：

- 普通闲聊，无提案：`1` 次 LLM
- 普通闲聊，有提案：`2` 次 LLM
- 实时查询：`1` 次 LLM，实时取数不是 LLM
- 快执行动作：`0` 到 `1` 次 LLM，优先不用大模型

设计目标是让多数轮次维持在 `1` 次 LLM，少数复杂轮次最多 `2` 次。

### 4.6 分析器注册表

新增一个统一注册表，主链路不再感知每种提案能力的细节。

注册表最少提供：

- 分析器名称
- 适用条件
- 风险等级
- 默认策略类别
- 分析函数入口

建议接口：

```python
class ProposalAnalyzer(Protocol):
    name: str
    proposal_kind: str
    default_policy_category: str

    def supports(self, turn_context: TurnProposalContext) -> bool: ...
    def analyze(self, turn_context: TurnProposalContext) -> list[ProposalDraft]: ...
```

好处很直接：

- 新增提案能力不需要改顶层路由器
- 失败隔离更清楚
- 主链路复杂度稳定

## 5. 证据模型

### 5.1 证据来源分类

把回合内的数据先分类，再决定哪些分析器能用：

- `user_message`
- `system_event`
- `trusted_external_event`
- `assistant_message`

其中：

- `assistant_message` 可以用于对话语义理解
- `assistant_message` 不可以直接作为记忆、配置等事实提案的唯一证据

### 5.2 各类提案的证据边界

#### 记忆提案

允许：

- 用户明确表达的长期偏好
- 用户明确说明的关系、习惯、重要事件
- 系统或外部可信事件

不允许：

- 助手讲的故事
- 助手做的总结本身
- 助手为了陪聊编出的情节

#### 配置提案

允许：

- 用户明确要求改名字
- 用户明确要求改说话风格
- 用户明确要求改人格标签

不允许：

- 助手自我发挥建议的设定
- 仅由助手复述产生的配置草稿

#### 提醒提案

允许：

- 用户明确表达未来事项和时间
- 用户表达的不完整提醒线索，作为草稿候选

不允许：

- 助手主动发散出的提醒建议直接落执行

## 6. 数据模型

### 6.1 新增提案批次表

建议新增 `conversation_proposal_batches`：

- `id`
- `session_id`
- `request_id`
- `source_message_ids_json`
- `source_roles_json`
- `lane_json`
- `status`：`pending_policy` / `partially_applied` / `completed` / `ignored`
- `created_at`
- `updated_at`

作用：

- 一轮回合一个统一提案容器
- 后续 UI 不再看到三张互相无关的“写入记忆”卡

### 6.2 新增提案项表

建议新增 `conversation_proposal_items`：

- `id`
- `batch_id`
- `proposal_kind`：如 `memory_write` / `config_apply` / `reminder_create`
- `policy_category`
- `status`
- `title`
- `summary`
- `evidence_message_ids_json`
- `evidence_roles_json`
- `dedupe_key`
- `confidence`
- `payload_json`
- `created_at`
- `updated_at`

### 6.3 与旧表的关系

项目早期不再为了兼容长期维护双轨。

处理原则直接定下来：

1. 新链路直接以 `conversation_proposal_batches` 和 `conversation_proposal_items` 为默认读写模型
2. 旧的 `conversation_memory_candidates` 和 `conversation_action_records` 不再作为主读模型继续扩展
3. 旧入口如果还存在，只允许短期辅助排查，不再作为正式产品能力前提
4. 后续直接清理旧表写入口，而不是继续叠兼容视图

## 7. 策略层

### 7.1 统一策略判定

每条提案项统一经过策略层处理：

- `ask`：展示待确认卡片
- `auto`：自动执行并留痕
- `ignore`：记录但不打扰用户

策略输入至少包括：

- `proposal_kind`
- `risk_level`
- `actor`
- `household_policy`
- `evidence_strength`

### 7.2 为什么不能让分析器直接决定执行

因为分析器擅长的是“判断像不像”，不是“决定该不该做”。

如果把执行权下放给分析器，系统又会回到旧问题：

- 每类能力都自己写确认规则
- 每类能力都自己写 fallback
- 主链路再次失控

## 8. 与当前实现的映射关系

### 8.1 当前坏味道

当前实现至少有这些结构性问题：

- 顶层路由把 `memory_write`、`config_change`、`reminder_create` 都当成主意图
- `free_chat` 结束后又有一条保守记忆补提取暗路
- 记忆提取直接使用用户消息和助手消息拼接文本
- 模型产出几个候选，就直接展开成几条动作记录

### 8.2 新链路如何替换旧链路

替换顺序改成直接切换：

1. 保留现有消息表和会话表
2. 把顶层意图识别缩成车道选择器
3. 把 `memory_write` / `config_change` / `reminder_create` 从顶层主路由移出
4. 新增提案批次和提案项模型
5. 前后端直接切到新提案和新动作模型
6. 下线“保守补提取”、旧候选、旧确认入口这类暗路

## 9. 错误处理

需要单独区分下面几类错误：

- 快执行目标不明确
- 快执行权限不足
- 实时取数失败
- 主聊天回复失败
- 某个提案分析器失败
- 策略层失败
- 提案确认执行失败

处理原则：

- 主回复失败和提案分析失败分开处理
- 单个分析器失败不拖垮整轮聊天
- 提案失败要能追溯到 analyzer、证据和 policy

## 10. 正确性约束

1. 一轮请求最多只有一个提案批次。
2. 一个提案批次可以有 0 到多条提案项。
3. 记忆和配置提案不能仅由 `assistant_message` 作为事实依据。
4. 快执行车道只能用于强实时副作用动作。
5. 新增提案能力时，不应要求修改主链路车道选择核心逻辑。
6. 提案分析失败不能回滚已完成的主聊天回复。

## 11. 风险与回滚

### 11.1 主要风险

- 直接切换后，旧入口如果还有残留调用会立刻暴露
- 车道选择器过宽，导致太多请求误入快执行
- 新提案模型未完全打通时，用户可能暂时看不到预期确认入口

### 11.2 回滚策略

- 新链路仍然挂功能开关
- 回滚目标改成“上一版稳定发布”，不再强调回到 `004.1` 代码结构
- 不再新增兼容映射层来换取回滚便利

## 12. 测试策略

### 12.1 后端

- 车道选择器测试：快执行 / 实时取数 / 普通聊天
- Embedding descriptor 检索测试：lane 命中、proposal gate 命中、低分回退
- 内置 provider 与外部 provider 切换测试
- 外部 provider 故障回退到内置 provider 测试
- 主回复完成后提案分析不阻塞响应测试
- 单轮只触发一次统一提案提取测试
- 记忆提案证据边界测试
- 单轮多提案项收口测试
- 单个分析器失败隔离测试
- 新提案读模型和新确认入口测试

### 12.2 前端

- 同一回合展示统一提案批次测试
- 待确认提案展示与忽略测试
- 新提案和新动作入口直接切换测试

### 12.3 联调

- “开灯”这类指令保持快速执行
- “讲个笑话”不会产生记忆提案
- “以后叫你暖暖，语气温柔一点”先正常回复，再产出配置提案
- “明天早上八点提醒我带钥匙”先回复，再出现提醒草稿提案
