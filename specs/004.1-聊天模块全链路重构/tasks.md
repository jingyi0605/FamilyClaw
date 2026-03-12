# 任务文档 - 聊天模块全链路重构

状态：Draft

## 使用说明

这份任务文档只做一件事：告诉后续实现时，先干什么，后干什么，每一步改哪里，怎么验收。

任务编号格式：`阶段.序号`

状态说明：

- `未开始`
- `进行中`
- `已完成`
- `阻塞`

---

## 阶段 0：先把现状说清楚

- [x] 0.1 完成聊天模块现状审查和问题归档
  - 状态：已完成（2026-03-12）
  - 这一步到底做什么：把当前聊天页、`family_qa`、上下文组合、`llm-task`、本地缓存和数据库现状全部查清楚，别带着误判开工。
  - 做完以后能看到什么结果：已经确认当前问题包括前端 8 秒超时误判、服务端无真实会话、多轮上下文缺失、本地伪持久化、`memory_extraction` 未接线。
  - 这一步依赖什么：无。
  - 开始前先看：
    - `apps/user-web/src/pages/ConversationPage.tsx`
    - `apps/user-web/src/lib/api.ts`
    - `apps/api-server/app/modules/family_qa/service.py`
    - `apps/api-server/app/modules/family_qa/fact_view_service.py`
    - `apps/api-server/app/modules/llm_task/definitions.py`
  - 主要改哪些文件：本 Spec 文档。
  - 这一步明确不做什么：不改任何业务实现。
  - 怎么验证是不是真的做完了：
    1. 关键问题列表能说清楚
    2. 后续需求、设计、任务能基于这一步继续展开
  - 对应需求：全部需求
  - 对应设计：`design.md` 全文

---

## 阶段 1：先把后端真实会话建出来

- [x] 1.1 设计并落地聊天会话表、消息表、记忆候选表
  - 状态：已完成（2026-03-12）
  - 这一步到底做什么：给聊天模块补上真正的数据底座，让会话、消息和记忆候选都能落到数据库。
  - 做完以后能看到什么结果：数据库里不再只有 `qa_query_logs`，而是能查到真正的聊天会话和消息。
  - 这一步依赖什么：0.1
  - 开始前先看：
    - `design.md` §3
    - `apps/api-server/migrations/20260311-数据库迁移规范.md`
    - `apps/api-server/app/modules/family_qa/models.py`
  - 主要改哪些文件：
    - `apps/api-server/app/modules/conversation/`
    - `apps/api-server/migrations/versions/`
  - 这一步明确不做什么：先不改前端页面。
  - 怎么验证是不是真的做完了：
    1. Alembic migration 可执行
    2. 新表结构和设计一致
    3. `python -m unittest apps/api-server/tests/test_conversation_foundation.py`
  - 对应需求：需求 1、需求 5、需求 7、需求 8
  - 对应设计：`design.md` §3、§9、§10

- [x] 1.2 提供聊天会话和消息查询接口
  - 状态：已完成（2026-03-12）
  - 这一步到底做什么：让前端能从服务端拉会话列表、会话详情和消息记录。
  - 做完以后能看到什么结果：前端已经有条件摆脱 `localStorage` 作为事实来源。
  - 这一步依赖什么：1.1
  - 开始前先看：
    - `design.md` §6.1
    - `apps/api-server/app/api/v1/router.py`
  - 主要改哪些文件：
    - `apps/api-server/app/api/v1/endpoints/`
    - `apps/api-server/app/modules/conversation/service.py`
    - `apps/api-server/app/modules/conversation/schemas.py`
  - 这一步明确不做什么：先不接流式回复。
  - 怎么验证是不是真的做完了：
    1. 能创建会话
    2. 能拉会话列表
    3. 能拉单会话消息详情
    4. `python -m unittest apps/api-server/tests/test_conversation_foundation.py`
  - 对应需求：需求 1、需求 6、需求 8
  - 对应设计：`design.md` §4、§6

- [x] 1.3 建聊天实时事件通道或等价流式返回
  - 状态：已完成（2026-03-12）
  - 这一步到底做什么：把聊天实时链路统一接到 WebSocket，不再额外维护 SSE。
  - 做完以后能看到什么结果：聊天页能看到“发送中”“逐步出字”“完成”或“真实错误”，而且实时协议和项目现有实时体系一致。
  - 这一步依赖什么：1.2
  - 开始前先看：
    - `design.md` §4.3、§6.2
    - `apps/api-server/app/api/v1/endpoints/realtime.py`
    - `apps/user-web/src/lib/realtime.ts`
  - 主要改哪些文件：
    - `apps/api-server/app/api/v1/endpoints/realtime*.py`
    - `apps/api-server/app/modules/conversation/`
    - `apps/user-web/src/lib/`
  - 这一步明确不做什么：先不改记忆候选展示。
  - 怎么验证是不是真的做完了：
    1. 长回复可流式返回
    2. 供应商慢于 8 秒时前端不再误报失败
    3. 失败时能看到明确错误事件
    4. `python -m unittest tests/test_conversation_foundation.py`
    5. `python -m unittest tests/test_realtime_ws.py`
  - 对应需求：需求 4、需求 6、需求 8
  - 对应设计：`design.md` §4.3、§6.2、§8

---

## 阶段 2：把聊天真正改成多轮上下文

- [x] 2.1 接入多轮会话历史和现有上下文组合
  - 状态：已完成（2026-03-12）
  - 这一步到底做什么：让每轮回复真正带上会话历史、家庭上下文、Agent 上下文和记忆上下文。
  - 做完以后能看到什么结果：继续追问不再是截上一条回答凑问题，而是真正的多轮对话。
  - 这一步依赖什么：1.2、1.3
  - 开始前先看：
    - `design.md` §4.2
    - `apps/api-server/app/modules/family_qa/fact_view_service.py`
    - `apps/api-server/app/modules/agent/service.py`
    - `apps/api-server/app/modules/memory/context_engine.py`
  - 主要改哪些文件：
    - `apps/api-server/app/modules/conversation/service.py`
    - `apps/api-server/app/modules/family_qa/`
    - `apps/api-server/app/modules/ai_gateway/provider_runtime.py`
  - 这一步明确不做什么：先不处理记忆候选确认 UI。
  - 怎么验证是不是真的做完了：
    1. 同一会话第二轮会用到第一轮历史
    2. 权限裁剪仍然生效
    3. Agent 切换后旧上下文不会串到新会话
    4. `python -m unittest tests/test_conversation_foundation.py`
  - 对应需求：需求 2、需求 3、需求 7
  - 对应设计：`design.md` §2、§4、§10

- [ ] 2.2 复用现有 `family_qa` 规则草稿和审计能力
  - 状态：未开始
  - 这一步到底做什么：把 `family_qa` 里已经有价值的结构化事实、建议问题和审计记录接到新聊天服务里。
  - 做完以后能看到什么结果：新聊天链路不会把原来可用的 `facts` 和 `suggestions` 全丢掉。
  - 这一步依赖什么：2.1
  - 开始前先看：
    - `design.md` §4.4
    - `apps/api-server/app/modules/family_qa/service.py`
  - 主要改哪些文件：
    - `apps/api-server/app/modules/conversation/service.py`
    - `apps/api-server/app/modules/family_qa/service.py`
  - 这一步明确不做什么：不保留旧的前端直接调用 `family_qa` 方式。
  - 怎么验证是不是真的做完了：
    1. 聊天消息里仍能带 `facts`、`suggestions`
    2. `qa_query_logs` 继续可用于排错和审计
  - 对应需求：需求 3、需求 7、需求 8
  - 对应设计：`design.md` §4.4、§9.2

---

## 阶段 3：把 `llm-task` 真正接到聊天链路

- [x] 3.1 把 `memory_extraction` 接到聊天回合后处理
  - 状态：已完成（2026-03-12）
  - 这一步到底做什么：让普通聊天在合适时机自动生成记忆候选，而不是只靠用户手动“写入记忆”。
  - 做完以后能看到什么结果：助手回复后，页面可以提示“识别到可记住的信息”。
  - 这一步依赖什么：1.1、2.1
  - 开始前先看：
    - `design.md` §5.2
    - `apps/api-server/app/modules/llm_task/definitions.py`
    - `apps/api-server/app/modules/llm_task/invoke.py`
    - `apps/api-server/app/modules/memory/service.py`
  - 主要改哪些文件：
    - `apps/api-server/app/modules/conversation/service.py`
    - `apps/api-server/app/modules/llm_task/`
    - `apps/api-server/app/modules/memory/`
  - 这一步明确不做什么：先不自动落正式记忆卡。
  - 怎么验证是不是真的做完了：
    1. 聊天结束后能生成记忆候选
    2. 候选不会直接落库成正式记忆
    3. 候选内容能追溯到来源消息
    4. `python -m unittest tests/test_conversation_foundation.py`
  - 对应需求：需求 5、需求 8
  - 对应设计：`design.md` §3.3、§5.2、§5.3

- [x] 3.2 增加记忆候选确认和忽略流程
  - 状态：已完成（2026-03-12）
  - 这一步到底做什么：给用户一个受控入口，决定哪些候选真的写入记忆中心。
  - 做完以后能看到什么结果：聊天页可以确认或忽略记忆候选，记忆页能看到确认后的正式内容。
  - 这一步依赖什么：3.1
  - 开始前先看：
    - `design.md` §5.2、§6.1、§7.2
    - `apps/user-web/src/pages/ConversationPage.tsx`
    - `apps/api-server/app/modules/memory/service.py`
  - 主要改哪些文件：
    - `apps/user-web/src/pages/ConversationPage.tsx`
    - `apps/user-web/src/lib/api.ts`
    - `apps/api-server/app/api/v1/endpoints/`
  - 这一步明确不做什么：不做复杂批量审核后台。
  - 怎么验证是不是真的做完了：
    1. 候选可确认
    2. 候选可忽略
    3. 确认后记忆页能看到正式卡片
    4. `python -m unittest tests/test_conversation_foundation.py`
  - 对应需求：需求 5、需求 6
  - 对应设计：`design.md` §5.2、§6.1、§7.2

- [ ] 3.3 明确配置提取边界并复用现有 bootstrap 提取逻辑
  - 状态：未开始
  - 这一步到底做什么：把“哪些聊天能提配置，哪些不能”写死到实现里，别让普通闲聊乱改 Agent 配置。
  - 做完以后能看到什么结果：初始化向导继续可用，普通聊天不再有隐形配置副作用。
  - 这一步依赖什么：2.1
  - 开始前先看：
    - `design.md` §5.1
    - `apps/api-server/app/modules/agent/bootstrap_service.py`
  - 主要改哪些文件：
    - `apps/api-server/app/modules/conversation/service.py`
    - `apps/api-server/app/modules/agent/bootstrap_service.py`
    - `apps/user-web/src/pages/ConversationPage.tsx`
  - 这一步明确不做什么：不把普通聊天直接做成 AI 配置页面。
  - 怎么验证是不是真的做完了：
    1. bootstrap 提取链路不受影响
    2. 普通聊天不会自动覆盖 Agent 配置
    3. 显式配置模式时才允许生成配置建议
  - 对应需求：需求 5、需求 7
  - 对应设计：`design.md` §5.1、§9.3、§10

---

## 阶段 4：切前端事实来源并做兼容清理

- [x] 4.1 聊天页改成以服务端会话为准
  - 状态：已完成（2026-03-12）
  - 这一步到底做什么：把聊天页的会话列表、消息区、发送状态、错误状态全部切到服务端。
  - 做完以后能看到什么结果：刷新页面、重新登录、换设备都能看到一致会话。
  - 这一步依赖什么：1.2、1.3、2.1
  - 开始前先看：
    - `design.md` §7
    - `apps/user-web/src/pages/ConversationPage.tsx`
    - `apps/user-web/src/lib/api.ts`
  - 主要改哪些文件：
    - `apps/user-web/src/pages/ConversationPage.tsx`
    - `apps/user-web/src/components/`
    - `apps/user-web/src/lib/api.ts`
  - 这一步明确不做什么：先不删旧代码里所有辅助 UI 样式。
  - 怎么验证是不是真的做完了：
    1. 会话列表来自服务端
    2. 消息历史来自服务端
    3. 本地缓存不再是唯一事实来源
    4. `cd apps/user-web && npm.cmd run build`
  - 对应需求：需求 1、需求 2、需求 6
  - 对应设计：`design.md` §7

- [ ] 4.2 清理旧本地缓存逻辑并补隔离策略
  - 状态：未开始
  - 这一步到底做什么：去掉当前那套会串账号、串成员、串设备语义的本地伪持久化。
  - 做完以后能看到什么结果：聊天数据隔离清楚，登出后不会把前一个人的记录直接暴露给下一个人。
  - 这一步依赖什么：4.1
  - 开始前先看：
    - `design.md` §7.3、§9.1
    - `apps/user-web/src/state/auth.tsx`
    - `apps/user-web/src/pages/ConversationPage.tsx`
  - 主要改哪些文件：
    - `apps/user-web/src/pages/ConversationPage.tsx`
    - `apps/user-web/src/state/auth.tsx`
    - `apps/user-web/src/state/household.tsx`
  - 这一步明确不做什么：不做复杂离线消息同步。
  - 怎么验证是不是真的做完了：
    1. 登出后不会残留正式聊天历史
    2. 旧缓存迁移或清理口径明确
    3. 多账号切换不串会话
  - 对应需求：需求 1、需求 6、需求 7
  - 对应设计：`design.md` §7.3、§9.1

---

## 阶段 5：测试、验收和收尾

- [ ] 5.1 补后端和前端测试
  - 状态：未开始
  - 这一步到底做什么：把这次重构里最容易坏的地方用测试钉住。
  - 做完以后能看到什么结果：后续改聊天相关代码时，不会一点信心都没有。
  - 这一步依赖什么：1.1 至 4.2
  - 开始前先看：
    - `design.md` §11
    - 当前相关测试目录
  - 主要改哪些文件：
    - `apps/api-server/tests/`
    - `apps/user-web/` 对应测试文件
  - 这一步明确不做什么：不补和本次范围无关的历史烂测试。
  - 怎么验证是不是真的做完了：
    1. 会话与消息核心测试通过
    2. 发送、流式、失败、记忆候选核心测试通过
  - 对应需求：全部需求
  - 对应设计：`design.md` §11

- [ ] 5.2 形成联调与验收清单
  - 状态：未开始
  - 这一步到底做什么：把“怎么验收聊天真的好了”写成清单，别靠口头感觉。
  - 做完以后能看到什么结果：后续联调和验收的人有明确步骤可照着做。
  - 这一步依赖什么：5.1
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `docs/`
  - 主要改哪些文件：
    - `specs/004.1-聊天模块全链路重构/docs/`
  - 这一步明确不做什么：不扩展新功能。
  - 怎么验证是不是真的做完了：
    1. 验收步骤覆盖主要场景
    2. 每个场景有预期结果
  - 对应需求：需求 8
  - 对应设计：`design.md` §11

- [ ] 5.3 最终检查点
  - 状态：未开始
  - 这一步到底做什么：确认聊天模块已经从“看起来像聊天”变成“真正能用的聊天系统”。
  - 做完以后能看到什么结果：需求、设计、任务、测试、联调证据可以一一对上。
  - 这一步依赖什么：5.1、5.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪些文件：当前 Spec 全部文件和本次实现涉及文件
  - 这一步明确不做什么：不再追加新范围
  - 怎么验证是不是真的做完了：
    1. 服务端真实会话可用
    2. 多轮上下文可用
    3. 超时误判消失
    4. 记忆提取候选可用
    5. 普通聊天不会误改配置
  - 对应需求：全部需求
  - 对应设计：`design.md` 全文
