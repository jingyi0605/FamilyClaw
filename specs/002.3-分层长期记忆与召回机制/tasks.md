# 任务文档 - 分层长期记忆与召回机制

状态：Draft

## 2026-03-18 立项记录

- [x] S0 创建 `002.3-分层长期记忆与召回机制` 的 Spec 草案
  - 状态：DONE
  - 这一项到底做什么：把本次分层记忆和召回机制的 `requirements.md`、`design.md`、`tasks.md`、`README.md` 建出来，先把范围、边界和分期写清楚。
  - 做完你能看到什么：后续开发不需要再靠口头描述推进，能直接按 Spec 拆分实现。
  - 先依赖什么：无
  - 开始前先看：
    - `specs/000-Spec规范/Codex-Spec规范文档.md`
    - `specs/000-Spec规范/Spec模板/`
  - 主要改哪里：
    - `specs/002.3-分层长期记忆与召回机制/README.md`
    - `specs/002.3-分层长期记忆与召回机制/requirements.md`
    - `specs/002.3-分层长期记忆与召回机制/design.md`
    - `specs/002.3-分层长期记忆与召回机制/tasks.md`
  - 这一项先不做什么：不直接改业务代码，不提前开数据库 migration。
  - 怎么算完成：
    1. 三份主文档和 README 已经落地。
    2. 分层、检索、写入、注入、分期方案已经写清楚。
  - 怎么验证：
    - 人工通读四份文档，确认能互相对上。
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文

- [x] S1 补充性能评估与准确率验收方案
  - 状态：DONE
  - 这一项到底做什么：把“这套长期记忆到底快不快、准不准、怎样算真的可上线”单独写成人能执行的验收方案，避免后面开发完只能靠感觉说效果不错。
  - 做完你能看到什么：开发、测试和验收时都有同一套基准数据集、压测口径、Recall@K 指标和端到端验收表，不再各说各话。
  - 先依赖什么：S0
  - 开始前先看：
    - `requirements.md` 非功能需求 1、2、3、4
    - `design.md` 7、8.3
  - 主要改哪里：
    - `specs/002.3-分层长期记忆与召回机制/README.md`
    - `specs/002.3-分层长期记忆与召回机制/20260318-性能评估与准确率验收方案.md`
    - `specs/002.3-分层长期记忆与召回机制/tasks.md`
  - 这一项先不做什么：不提前写实现代码，不虚构测试结果，不把验收标准写成无法落地的大词。
  - 怎么算完成：
    1. 已定义基准数据集分层和样本规模。
    2. 已定义延迟、降级、Recall@K 和端到端验收标准。
    3. 已给出每一期的上线门槛和失败判定。
  - 怎么验证：
    - 人工走查验收方案，确认和 `requirements.md`、`design.md` 不冲突。
    - 检查 README 已加入文档入口。
  - 对应需求：`requirements.md` 非功能需求 1、2、3、4，需求 5、需求 7
  - 对应设计：`design.md` 2.3.4、5、7、8.3

## 阶段 1：先把 memory_cards 召回闭环做出来

- [ ] 1.1 给 `memory_cards` 增加 PostgreSQL 召回字段和索引
  - 状态：TODO
  - 这一项到底做什么：先不追求一步到位统一投影，先给现有 `memory_cards` 增加 `search_text`、`search_tsv` 和 `embedding`，把第一版关键词召回和向量召回落下来。
  - 做完你能看到什么：已有长期记忆卡不再只是“能存”，而是能被 PostgreSQL 稳定召回。
  - 先依赖什么：S0
  - 开始前先看：
    - `requirements.md` 需求 2、需求 7
    - `design.md` 3.2.3、5.2、8.3
    - `apps/api-server/migrations/20260311-数据库迁移规范.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/memory/models.py`
    - `apps/api-server/app/modules/memory/repository.py`
    - `apps/api-server/migrations/`
  - 这一项先不做什么：先不把 `L1/L2/L4` 一起塞进统一投影表。
  - 怎么算完成：
    1. `memory_cards` 新增召回字段和索引。
    2. migration 能创建 `GIN` 和 `pgvector` 相关结构。
    3. 旧的记忆读写接口仍然兼容。
  - 怎么验证：
    - Alembic migration 结构检查
    - 模型与 repository 集成测试
  - 对应需求：`requirements.md` 需求 2、需求 7
  - 对应设计：`design.md` 3.2.3、5.2、6.1

- [ ] 1.2 落地 `memory_cards` 的关键词/向量混合查询服务
  - 状态：TODO
  - 这一项到底做什么：把现有基于规则打分的 `query_memory_cards` 改成 PostgreSQL 关键词召回、向量召回和业务权重混排。
  - 做完你能看到什么：用户问到相关事实时，不再只是匹配字符串，而是真正命中更像人的长期记忆。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 2
    - `design.md` 2.3.4、3.3.1、5.2
    - `apps/api-server/app/modules/memory/query_service.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/memory/query_service.py`
    - `apps/api-server/app/modules/memory/context_engine.py`
    - `apps/api-server/app/modules/ai_gateway/`
  - 这一项先不做什么：先不引入多模型、多向量字段，也先不接 `L4`。
  - 怎么算完成：
    1. 查询流程支持关键词召回、向量召回和 Hybrid rerank。
    2. 权限过滤仍然先于召回结果输出。
    3. 向量不可用时能降级到关键词召回。
  - 怎么验证：
    - PostgreSQL 集成测试
    - 权限和降级单元测试
  - 对应需求：`requirements.md` 需求 2、需求 7
  - 对应设计：`design.md` 2.3.4、3.3.1、5.2、6.2

- [ ] 1.3 修复 `free_chat` 的记忆注入并记录 trace
  - 状态：TODO
  - 这一项到底做什么：把 `free_chat` 从“只塞 hot_summary”改成“按组注入真实命中的稳定事实和最近事件”，并把本轮注入来源写进 trace。
  - 做完你能看到什么：调试时能回答“这轮为什么会这么答”，而不是只能猜 prompt 里到底放了什么。
  - 先依赖什么：1.2
  - 开始前先看：
    - `requirements.md` 需求 5、需求 7
    - `design.md` 2.3.4、3.2.6、6.3
    - `apps/api-server/app/modules/conversation/orchestrator.py`
    - `apps/api-server/app/modules/conversation/service.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/conversation/orchestrator.py`
    - `apps/api-server/app/modules/conversation/service.py`
    - `apps/api-server/app/modules/conversation/models.py`
    - `apps/api-server/migrations/`
  - 这一项先不做什么：先不把会话摘要和外部知识一起注入。
  - 怎么算完成：
    1. `free_chat` 至少按“稳定事实”“最近事件”两组注入结果。
    2. 每轮注入的来源 ID、分组、分数能落库或可回放。
    3. 旧会话主链路没有被破坏。
  - 怎么验证：
    - `free_chat` 端到端测试
    - trace 落库集成测试
  - 对应需求：`requirements.md` 需求 5、需求 7
  - 对应设计：`design.md` 2.3.4、3.2.6、6.2、6.3

### 阶段检查

- [ ] 1.4 确认第一期最小闭环可用
  - 状态：TODO
  - 这一项到底做什么：只检查第一期的闭环是不是真的跑通，而不是顺手把第二期、第三期也捎上。
  - 做完你能看到什么：`memory_cards` 已经能查、能注入、能追踪，第一阶段可以独立交付。
  - 先依赖什么：1.1、1.2、1.3
  - 开始前先看：
    - `requirements.md` 需求 2、需求 5、需求 7
    - `design.md` 8.3 第一阶段
  - 主要改哪里：
    - 当前阶段相关实现和测试
  - 这一项先不做什么：先不扩写第二阶段数据表。
  - 怎么算完成：
    1. 召回闭环可演示。
    2. 调试链路能看到本轮注入来源。
    3. 降级路径能正常工作。
  - 怎么验证：
    - 集成回归测试
    - 人工走查一轮完整对话
  - 对应需求：`requirements.md` 需求 2、需求 5、需求 7
  - 对应设计：`design.md` 5、6、7、8.3

## 阶段 2：补齐会话记忆这一层

- [ ] 2.1 新增 `conversation_session_summaries` 真相源
  - 状态：TODO
  - 这一项到底做什么：把“这个 session 正聊到哪、哪些话题没收尾、最近确认过什么”单独落成一张表，不再靠最近 8 条消息硬撑。
  - 做完你能看到什么：会话变长后，系统还能知道本轮之前到底聊到了哪一步。
  - 先依赖什么：1.4
  - 开始前先看：
    - `requirements.md` 需求 1、需求 4
    - `design.md` 3.2.1、4.2.1
    - `docs/开发设计规范/20260316-后端事件循环与周期任务开发规范.md`
    - `apps/api-server/migrations/20260311-数据库迁移规范.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/conversation/models.py`
    - `apps/api-server/app/modules/conversation/repository.py`
    - `apps/api-server/migrations/`
  - 这一项先不做什么：先不做统一 `L1-L4` 投影表。
  - 怎么算完成：
    1. 会话摘要表、模型和 repository 可用。
    2. 能保存摘要、未完成话题和最近确认事项。
  - 怎么验证：
    - migration 检查
    - 模型与 repository 测试
  - 对应需求：`requirements.md` 需求 1、需求 4
  - 对应设计：`design.md` 3.2.1、4.2.1

- [ ] 2.2 建立会话摘要刷新服务和阈值触发
  - 状态：TODO
  - 这一项到底做什么：把会话摘要从“表结构存在”推进到“达到阈值会自动刷新”，并且不阻塞主链路。
  - 做完你能看到什么：对话聊多了以后，会话记忆能稳定刷新，而不是永远是一张空表。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 4、需求 7
    - `design.md` 2.3.3、3.3.2、5.2
    - `docs/开发设计规范/20260316-后端事件循环与周期任务开发规范.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/conversation/service.py`
    - `apps/api-server/app/modules/conversation/`
    - `apps/api-server/app/modules/llm_task/`
  - 这一项先不做什么：先不做复杂的 token 级压缩策略。
  - 怎么算完成：
    1. 达到阈值或结束态时会触发摘要刷新。
    2. 刷新失败时会留下状态和日志，不拖垮主请求。
  - 怎么验证：
    - 阈值触发测试
    - 异常降级测试
  - 对应需求：`requirements.md` 需求 4、需求 7
  - 对应设计：`design.md` 2.3.3、3.3.2、4.2.1、5.2

- [ ] 2.3 让会话记忆参与 free_chat 召回
  - 状态：TODO
  - 这一项到底做什么：把 `L1` 正式接进召回链路，让 `session_summary` 成为 prompt 注入的一组，而不是悬在表里没人读。
  - 做完你能看到什么：同一会话里继续追问时，AI 不再只靠最近几条消息硬猜上下文。
  - 先依赖什么：2.2
  - 开始前先看：
    - `requirements.md` 需求 4、需求 5
    - `design.md` 2.3.4、3.3.1、6.3
  - 主要改哪里：
    - `apps/api-server/app/modules/memory/query_service.py`
    - `apps/api-server/app/modules/conversation/orchestrator.py`
    - `apps/api-server/app/modules/conversation/service.py`
  - 这一项先不做什么：先不把 `L2/L4` 一起统一进单表投影。
  - 怎么算完成：
    1. `free_chat` 有 `session_summary` 注入组。
    2. trace 能区分这条来源于 `L1`。
  - 怎么验证：
    - 连续追问场景端到端测试
    - 注入 trace 检查
  - 对应需求：`requirements.md` 需求 4、需求 5
  - 对应设计：`design.md` 2.3.3、2.3.4、3.2.1、6.3

### 阶段检查

- [ ] 2.4 确认会话记忆已经从“概念”变成“主链路输入”
  - 状态：TODO
  - 这一项到底做什么：检查 `L1` 会话记忆已经被真实写入、真实读取、真实注入，而不是只补了一张表。
  - 做完你能看到什么：第二阶段交付后，会话层记忆是活的，不是摆设。
  - 先依赖什么：2.1、2.2、2.3
  - 开始前先看：
    - `requirements.md` 需求 4、需求 5
    - `design.md` 8.3 第二阶段
  - 主要改哪里：
    - 当前阶段相关实现和测试
  - 这一项先不做什么：先不导入外部知识。
  - 怎么算完成：
    1. `L1` 数据可刷新、可召回、可注入。
    2. 失败时有可观测降级。
  - 怎么验证：
    - 集成回归测试
    - 人工走查多轮对话
  - 对应需求：`requirements.md` 需求 4、需求 5、需求 7
  - 对应设计：`design.md` 2.3.3、2.3.4、5、8.3

## 阶段 3：把情节记忆和外部知识纳入统一召回

- [ ] 3.1 新增 `episodic_memory_entries` 和基础提升链路
  - 状态：TODO
  - 这一项到底做什么：把时间锚点明确的事件和会话摘要收进 `L2`，并支持按重复次数提升成 `L3`。
  - 做完你能看到什么：系统不再把所有“发生过的事”都粗暴塞进 `memory_cards`。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 需求 1、需求 3
    - `design.md` 2.3.2、3.2.2、6.4
    - `apps/api-server/migrations/20260311-数据库迁移规范.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/memory/`
    - `apps/api-server/migrations/`
  - 这一项先不做什么：先不导入规则文档。
  - 怎么算完成：
    1. `L2` 真相源表和服务可用。
    2. 重复观察可触发提升到 `memory_cards`。
  - 怎么验证：
    - 事件写入和提升测试
    - 来源追踪测试
  - 对应需求：`requirements.md` 需求 1、需求 3
  - 对应设计：`design.md` 2.3.2、3.2.2、6.4

- [ ] 3.2 新增 `knowledge_documents` 并接入插件原始记录/规则文档
  - 状态：TODO
  - 这一项到底做什么：把插件原始记录、说明文档和规则文档整理成 `L4` 真相源，别再让每个模块自己偷偷读一份。
  - 做完你能看到什么：外部知识也能走统一召回，不再是旁门左道。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 需求 6
    - `design.md` 2.3.5、3.2.4
    - `docs/开发设计规范/20260317-插件启用禁用统一规则.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/`
    - `apps/api-server/app/modules/memory/`
    - `apps/api-server/migrations/`
  - 这一项先不做什么：先不做任意文件系统自动扫描导入。
  - 怎么算完成：
    1. `L4` 真相源和导入适配器可用。
    2. 来源信息、可见性和更新时间能保留下来。
  - 怎么验证：
    - 插件原始记录导入测试
    - 规则文档导入测试
  - 对应需求：`requirements.md` 需求 6
  - 对应设计：`design.md` 2.3.5、3.2.4、6.2

- [ ] 3.3 建立统一 `memory_recall_documents` 投影并收口 `L1-L4`
  - 状态：TODO
  - 这一项到底做什么：把第一阶段临时放在 `memory_cards` 上的投影能力，收口成真正统一的 `L1-L4` 召回投影。
  - 做完你能看到什么：查询服务面对的是一套统一召回模型，不用再对每层单独补越来越多分支。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 5、需求 6
    - `design.md` 3.2.5、4.1、8.3
    - `apps/api-server/migrations/20260311-数据库迁移规范.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/memory/`
    - `apps/api-server/app/modules/conversation/`
    - `apps/api-server/migrations/`
  - 这一项先不做什么：先不引入独立外部向量数据库。
  - 怎么算完成：
    1. `L1/L2/L3/L4` 都能进入统一投影。
    2. 查询服务统一按组输出 recall 结果。
    3. 真相源和投影边界清晰，不互相污染。
  - 怎么验证：
    - 统一召回集成测试
    - 分组注入端到端测试
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 5、需求 6
  - 对应设计：`design.md` 3.2.5、4.1、6.1、6.3

### 阶段检查

- [ ] 3.4 确认最终形态已经是“结构化真相源 + 召回投影 + 主链路注入”
  - 状态：TODO
  - 这一项到底做什么：检查最终交付是否真达到了目标形态，而不是只有几张新表和几段零散逻辑。
  - 做完你能看到什么：项目已经具备长期记忆分层存储和统一召回的基本能力。
  - 先依赖什么：3.1、3.2、3.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：
    - 当前阶段相关实现、文档和测试
  - 这一项先不做什么：不再顺手扩到新的知识治理系统。
  - 怎么算完成：
    1. `L1-L4` 已有清晰真相源和统一召回。
    2. `free_chat` 正式依赖真实 recall 结果。
    3. trace 和降级能力都可用。
  - 怎么验证：
    - 端到端回归测试
    - 文档走查
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文

## 阶段 4：文档、回归和交付收口

- [ ] 4.1 同步正式文档和运维排障说明
  - 状态：TODO
  - 这一项到底做什么：只要实现影响安装、配置、用户可见行为和排障流程，就把正式文档一起补齐。
  - 做完你能看到什么：后面接手的人不会面对“代码改了，文档还是旧的”这种垃圾状态。
  - 先依赖什么：3.4
  - 开始前先看：
    - `requirements.md` 需求 7
    - `design.md` 5、7、8
    - `docs/Documentation/`
  - 主要改哪里：
    - `docs/Documentation/`
    - 相关开发者文档和排障文档
  - 这一项先不做什么：不额外写营销式说明文案。
  - 怎么算完成：
    1. 安装、配置、召回降级、排障说明都更新完成。
    2. 文档和实现口径一致。
  - 怎么验证：
    - 文档走查
    - 配置示例检查
  - 对应需求：`requirements.md` 需求 7
  - 对应设计：`design.md` 5、7、8

- [ ] 4.2 最终检查点
  - 状态：TODO
  - 这一项到底做什么：确认需求、设计、任务、实现和文档是能对上的，不留“后面再补”的口子。
  - 做完你能看到什么：这个 Spec 可以直接作为开发与验收依据，而不是半成品。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - 正式文档
  - 主要改哪里：
    - 当前 Spec 全部文件
    - 相关正式文档
  - 这一项先不做什么：不再追加新需求。
  - 怎么算完成：
    1. 每个阶段任务都能映射到需求和设计。
    2. 验证方式明确且可执行。
    3. 残余风险和后续边界写清楚。
  - 怎么验证：
    - 按 Spec 全量走查
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
