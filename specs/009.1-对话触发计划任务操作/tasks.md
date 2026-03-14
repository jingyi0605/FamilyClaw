# 任务清单 - 对话触发计划任务操作（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单只管一件事：把计划任务真正接进聊天主链。

做这个 Spec 时，你应该一眼看明白：

- 哪一步是在识别计划任务意图
- 哪一步是在 proposal 主链里落地
- 哪一步是在 confirm 时创建正式任务
- 哪一步是在验收“这不是另一套私有入口”

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但要写原因

## 阶段 1：先把聊天提案接进来

- [x] 1.1 在 proposal analyzer 里新增计划任务提案
  - 状态：DONE
  - 这一步到底做什么：给现有 proposal analyzer 增加 `scheduled_task_create`，让聊天里能识别计划任务意图并产出正式提案。
  - 做完你能看到什么：用户发一句明确的计划任务请求后，对话结果里会多出一条计划任务提案，而不是只能走独立草稿接口。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` §2.3.1
    - `apps/api-server/app/modules/conversation/proposal_analyzers.py`
    - `apps/api-server/app/modules/scheduler/draft_service.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/conversation/proposal_analyzers.py`
    - `apps/api-server/app/modules/conversation/proposal_pipeline.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不处理复杂多轮追问。
  - 怎么算完成：
    1. 提案列表里能看到 `scheduled_task_create`
    2. 提案 payload 里有草稿摘要、缺失字段和可确认标记
  - 怎么验证：
    - 对话提案生成测试
  - 对应需求：`requirements.md` 需求 1、需求 4
  - 对应设计：`design.md` §2.3.1、§3.2

- [x] 1.2 把 confirm 接到正式计划任务创建逻辑
  - 状态：DONE
  - 这一步到底做什么：让用户确认计划任务提案后，系统能通过正式 scheduler service 创建任务，而不是停在提案记录里。
  - 做完你能看到什么：proposal item confirm 成功后，数据库里真的会出现正式计划任务定义。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3
    - `design.md` §2.3.2、§2.3.3
    - `apps/api-server/app/modules/conversation/service.py`
    - `apps/api-server/app/modules/scheduler/service.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/conversation/service.py`
    - `apps/api-server/app/modules/scheduler/draft_service.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做聊天里直接编辑、启停、删除任务。
  - 怎么算完成：
    1. confirm 后能创建正式任务
    2. dismiss 后不会创建任务
    3. 越权和依赖失效时会明确失败
  - 怎么验证：
    - proposal confirm / dismiss 集成测试
  - 对应需求：`requirements.md` 需求 2、需求 3
  - 对应设计：`design.md` §2.3.2、§2.3.3、§5.2

- [x] 1.3 阶段检查：聊天主链里是否已经有原生计划任务提案
  - 状态：DONE
  - 这一步到底做什么：确认计划任务已经是聊天 proposal 的正式一种，而不是旁路接口。
  - 做完你能看到什么：用户不需要切换入口，就能在正常聊天里创建计划任务。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不扩到前端专门卡片样式。
  - 怎么算完成：
    1. 提案生成和确认链路都能跑通
    2. 现有记忆 / 配置 / 提醒提案没有被破坏
  - 怎么验证：
    - 集成测试
    - 人工走查 proposal payload
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3、需求 4
  - 对应设计：`design.md` §2.3、§6.1、§6.2

## 阶段 2：把缺字段和前端展示补清楚

- [x] 2.1 明确缺失字段返回和前端展示结构
  - 状态：DONE
  - 这一步到底做什么：把“还缺什么字段”“现在能不能确认”“给用户看的摘要是什么”收成稳定结构，方便前端直接渲染。
  - 做完你能看到什么：前端拿到 proposal item 后，不需要猜字段，也不需要解析一堆内部术语。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 4
    - `design.md` §3.2、§4.2
    - `apps/api-server/app/modules/conversation/schemas.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/conversation/`
    - `apps/api-server/app/modules/scheduler/schemas.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做真正多轮追问编排器。
  - 怎么算完成：
    1. proposal payload 里的人话字段稳定
    2. 缺失字段列表稳定可用
  - 怎么验证：
    - schema 测试
    - API 返回结构检查
  - 对应需求：`requirements.md` 需求 4
  - 对应设计：`design.md` §3.2、§4.2

- [x] 2.2 补聊天主链端到端验收
  - 状态：DONE
  - 这一步到底做什么：把“用户发消息 -> 生成计划任务提案 -> confirm -> 任务落库”整条链一次性验透。
  - 做完你能看到什么：后续前端接入时不用再猜后端到底是不是通的。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：
    - `apps/api-server/tests/`
  - 这一步先不做什么：不补完整聊天 UI。
  - 怎么算完成：
    1. 正常创建链路通过
    2. 缺字段、dismiss、越权、依赖失效都被覆盖
  - 怎么验证：
    - 端到端或集成测试
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` §2.3、§5、§7

- [x] 2.3 最终检查：这条能力是不是已经值得前端接入
  - 状态：DONE
  - 这一步到底做什么：最后确认计划任务聊天提案已经能给前端稳定接，不再只是后端半成品。
  - 做完你能看到什么：前端可以放心把计划任务提案当正式卡片接入，而不是实验字段。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：当前 Spec 全部文件
  - 这一步先不做什么：不做完整任务管理页，只把聊天里的创建、更新、暂停、恢复、删除提案补到主链。
  - 怎么算完成：
    1. 提案生成、确认、取消、失败都可解释
    2. 字段结构稳定
    3. 和现有 proposal 主链不打架
  - 怎么验证：
    - 按验收清单逐项核对
  - 本轮补充结果：
    1. 已支持一次性计划任务 `once`
    2. 已支持聊天里的更新 / 暂停 / 恢复 / 删除 proposal
    3. 已补最小可用的插件目标与更多条件规则解析
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
