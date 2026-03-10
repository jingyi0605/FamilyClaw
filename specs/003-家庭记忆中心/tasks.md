# 任务文档 - 家庭记忆中心

状态：Draft

## 任务总原则

这次别犯一个常见错误：一上来就想做“聪明记忆”。真正第一步不是聪明，而是把数据结构立住。

所以任务顺序固定成这样：

1. 先把事件流水和记忆卡落地
2. 再把检索和 Context Engine 接起来
3. 再把问答、提醒、场景、前端记忆页串起来
4. 最后做回填、治理、验收

---

## 阶段 1：把长期记忆的地基打出来

- [x] 1.1 新增长期记忆模块和数据库迁移
  - 状态：DONE
  - 这一步到底做什么：把 `event_records`、`memory_cards`、`memory_card_members`、`memory_card_revisions` 这些真正需要长期保存的表和模型建出来。
  - 做完你能看到什么：后端已经有能持久化长期记忆的真实数据结构，不再只有文档里的名字。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1、2、5
    - `design.md` §3.2「数据模型」
    - `docs/家庭版OpenClaw-系统架构图说明与数据库设计草案-v0.1.md`
  - 主要改哪里：
    - `apps/api-server/migrations/versions/`
    - `apps/api-server/app/modules/memory/models.py`
    - `apps/api-server/app/modules/memory/schemas.py`
    - `apps/api-server/app/modules/memory/repository.py`
  - 这一步先不做什么：先不接前端，不做复杂检索，不上向量库。
  - 怎么算完成：
    1. 数据表、ORM、Schema 能对应上
    2. 表结构能表达状态、权限、去重和 revision
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - 检查迁移文件和模型字段是否一致
  - 对应需求：`requirements.md` 需求 1、2、5
  - 对应设计：`design.md` §3.2、§4.1、§4.2

- [x] 1.2 做统一事件写回服务
  - 状态：DONE
  - 这一步到底做什么：把长期记忆入口收口成一个服务，不允许提醒、场景、问答、人工录入以后各写各的。
  - 做完你能看到什么：任何模块都可以写 `event_records`，并带幂等键和处理状态。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1
    - `design.md` §2.3.1「记忆写回流程」
    - `design.md` §3.5.3「POST /api/v1/memories/events」
  - 主要改哪里：
    - `apps/api-server/app/modules/memory/service.py`
    - `apps/api-server/app/modules/memory/schemas.py`
    - `apps/api-server/app/api/v1/endpoints/memories.py`
  - 这一步先不做什么：先不做记忆提炼，只保证事件落库和幂等。
  - 怎么算完成：
    1. 可以写入事件流水
    2. 重复事件不会造成重复数据爆炸
    3. 失败事件可标记重试
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - 手工调用事件写回接口验证幂等
  - 对应需求：`requirements.md` 需求 1
  - 对应设计：`design.md` §2.3.1、§3.2.1、§5.3

- [x] 1.3 阶段检查：确认长期记忆不是空中楼阁
  - 状态：DONE
  - 这一步到底做什么：检查当前阶段是不是已经把长期记忆的“硬盘”建出来了，而不是还在画图。
  - 做完你能看到什么：数据表、模型、事件写回入口已经站稳，后面可以往上接逻辑。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不加新来源，不加 UI。
  - 怎么算完成：
    1. 数据结构和事件入口稳定
    2. 已知缺口已经明确记录
  - 怎么验证：
    - 人工走查
    - 关键测试通过
  - 对应需求：`requirements.md` 需求 1、2
  - 对应设计：`design.md` §2.1、§3.2、§4.1

---

## 阶段 2：把长期记忆真正变成可检索能力

- [x] 2.1 做记忆提炼、去重和 revision 服务
  - 状态：DONE
  - 这一步到底做什么：把事件流水提炼成事实记忆、偏好记忆、关系记忆和事件记忆，并支持更正、失效、删除。
  - 做完你能看到什么：系统不只会记事件，还会生成可服务的记忆卡。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2、5
    - `design.md` §2.3.1「记忆写回流程」
    - `design.md` §2.3.4「纠错与删除流程」
    - `design.md` §3.2.2、§3.2.4
  - 主要改哪里：
    - `apps/api-server/app/modules/memory/service.py`
    - `apps/api-server/app/modules/memory/repository.py`
    - `apps/api-server/app/modules/memory/models.py`
  - 这一步先不做什么：先不引入 AI 做复杂抽取，第一版优先规则和结构化映射。
  - 怎么算完成：
    1. 事件可以生成或更新记忆卡
    2. 纠错、失效、删除会写 revision
    3. 重复事实不会无脑生成重复卡
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - 人工构造重复和冲突事件验证去重
  - 对应需求：`requirements.md` 需求 2、5
  - 对应设计：`design.md` §2.3.1、§2.3.4、§3.2.2、§3.2.4、§4.2

- [x] 2.2 做记忆检索服务和热摘要
  - 状态：DONE
  - 这一步到底做什么：把长期记忆从“存在数据库里”变成“能被问答和页面快速找到”。
  - 做完你能看到什么：可以按成员、类型、关键词、时间和权限查到相关记忆。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 3、4、6
    - `design.md` §2.3.2「长期记忆检索流程」
    - `design.md` §3.3「检索与排序策略」
    - `design.md` §3.5.1、§3.5.6
  - 主要改哪里：
    - `apps/api-server/app/modules/memory/query_service.py`
    - `apps/api-server/app/modules/memory/schemas.py`
    - `apps/api-server/app/api/v1/endpoints/memories.py`
  - 这一步先不做什么：先不接语义向量检索。
  - 怎么算完成：
    1. 列表查询和内部检索都可用
    2. 权限过滤生效
    3. 热摘要会在写入后刷新
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - 人工用不同 actor 验证搜索结果差异
  - 对应需求：`requirements.md` 需求 3、4、6
  - 对应设计：`design.md` §2.3.2、§3.3、§3.5.1、§3.5.6

- [ ] 2.3 做 Context Engine 并接到家庭问答
  - 状态：TODO
  - 这一步到底做什么：把实时上下文和长期记忆拼成真正可用的上下文包，再接到 `family_qa`。
  - 做完你能看到什么：`QaMemorySummary` 不再是“暂未接入”，问答可以同时利用当前状态和长期记忆。
  - 先依赖什么：2.2
  - 开始前先看：
    - `requirements.md` 需求 3、4
    - `design.md` §2.3.3「Context Engine 拼装流程」
    - `design.md` §3.4「Context Engine 设计」
    - `design.md` §3.6.4、§3.6.5
  - 主要改哪里：
    - `apps/api-server/app/modules/memory/context_engine.py`
    - `apps/api-server/app/modules/family_qa/fact_view_service.py`
    - `apps/api-server/app/modules/family_qa/service.py`
    - `apps/api-server/app/modules/family_qa/schemas.py`
  - 这一步先不做什么：先不重写全部问答策略，只把长期记忆接进去。
  - 怎么算完成：
    1. Context Engine 能按能力裁剪上下文
    2. `family_qa` 能引用长期记忆
    3. 记忆不可用时还能降级回旧逻辑
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - 人工验证“实时状态 + 长期偏好/事件”混合问答
  - 对应需求：`requirements.md` 需求 3、4
  - 对应设计：`design.md` §2.3.3、§3.4、§3.6.4、§6.2

- [ ] 2.4 阶段检查：确认长期记忆已经接到服务主链路
  - 状态：TODO
  - 这一步到底做什么：检查长期记忆是不是已经被真正使用，而不是表建好了却没人读。
  - 做完你能看到什么：事件、记忆、问答三段链路已经连通。
  - 先依赖什么：2.1、2.2、2.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不加前端新需求。
  - 怎么算完成：
    1. 记忆可写、可查、可用于问答
    2. 降级路径和权限路径已走通
  - 怎么验证：
    - 人工走查
    - 关键服务测试通过
  - 对应需求：`requirements.md` 需求 3、4、5
  - 对应设计：`design.md` §3.3、§3.4、§4.1、§5.2

---

## 阶段 3：把提醒、场景、前端记忆页都接上

- [ ] 3.1 把提醒、场景、在家状态接到统一记忆写回
  - 状态：TODO
  - 这一步到底做什么：把现在已经存在的业务模块接入长期记忆，而不是让记忆模块孤零零待着。
  - 做完你能看到什么：提醒执行、场景执行、在家状态变化都能留下长期痕迹。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 需求 1、2、4
    - `design.md` §3.6.1、§3.6.2、§3.6.3
    - `design.md` §6.1「迁移顺序」
  - 主要改哪里：
    - `apps/api-server/app/modules/presence/service.py`
    - `apps/api-server/app/modules/reminder/service.py`
    - `apps/api-server/app/modules/scene/service.py`
    - `apps/api-server/app/modules/memory/service.py`
  - 这一步先不做什么：先不接照片、语音多模态。
  - 怎么算完成：
    1. 三类来源都会写事件
    2. 关键结果能生成长期记忆
    3. 不破坏原有业务主链路
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - 人工触发三类来源验证事件与记忆生成
  - 对应需求：`requirements.md` 需求 1、2、4
  - 对应设计：`design.md` §2.3.1、§3.6.1、§3.6.2、§3.6.3、§6.2

- [ ] 3.2 接管理台记忆中心页面
  - 状态：TODO
  - 这一步到底做什么：让管理员能看到、筛选、纠错、失效和删除真实记忆。
  - 做完你能看到什么：管理台不再只能看上下文和服务摘要，而是能管理长期记忆。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 5、6
    - `design.md` §3.5「API 设计」
    - `design.md` §3.6.4、§3.6.5
  - 主要改哪里：
    - `apps/admin-web/src/pages/`
    - `apps/admin-web/src/lib/api.ts`
    - `apps/api-server/app/api/v1/endpoints/memories.py`
  - 这一步先不做什么：先不做复杂统计大盘。
  - 怎么算完成：
    1. 管理台能查询记忆列表和详情
    2. 能做纠错、失效、删除
    3. 能看到处理状态和权限信息
  - 怎么验证：
    - `cd apps/admin-web && npm.cmd run build`
    - 人工走查管理台主链路
  - 对应需求：`requirements.md` 需求 5、6
  - 对应设计：`design.md` §3.5、§5.3、§6.2、§7.4

- [ ] 3.3 把用户端记忆页从 mock 换成真实数据
  - 状态：TODO
  - 这一步到底做什么：把 `apps/user-web/src/pages/MemoriesPage.tsx` 后面的假数据拆掉，接上真正的长期记忆 API。
  - 做完你能看到什么：用户端记忆页终于不是样板戏，而是能看真实记忆、权限遮罩和纠错入口。
  - 先依赖什么：3.2
  - 开始前先看：
    - `requirements.md` 需求 6
    - `design.md` §3.5.1、§3.5.2、§3.5.5
    - `design.md` §6.2「向后兼容」
  - 主要改哪里：
    - `apps/user-web/src/pages/MemoriesPage.tsx`
    - `apps/user-web/src/state/`
    - `apps/user-web/src/i18n/`
  - 这一步先不做什么：先不追求完整视觉升级。
  - 怎么算完成：
    1. 用户端展示真实长期记忆
    2. 只显示用户有权限看的内容
    3. 可发起纠错或失效建议
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工切换不同身份验证展示差异
  - 对应需求：`requirements.md` 需求 6
  - 对应设计：`design.md` §3.5、§5.3、§6.2、§7.4

- [ ] 3.4 阶段检查：确认记忆中心已经不是摆设
  - 状态：TODO
  - 这一步到底做什么：检查长期记忆是不是已经真正贯穿后端、管理台、用户端，而不是局部可用。
  - 做完你能看到什么：后台有数据、前台能看、问答能用、治理可做。
  - 先依赖什么：3.1、3.2、3.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不追加照片、向量检索这些新范围。
  - 怎么算完成：
    1. 三端链路已经连起来
    2. mock 已经被真实数据替换
    3. 主要权限与降级路径明确
  - 怎么验证：
    - 人工走查
    - 前后端构建通过
  - 对应需求：`requirements.md` 需求 4、5、6
  - 对应设计：`design.md` §3.5、§3.6、§6.2、§7.4

---

## 阶段 4：做回填、治理和最终验收

- [ ] 4.1 做历史数据回填和重放脚本
  - 状态：TODO
  - 这一步到底做什么：把现在已经存在的提醒、场景、在家状态历史数据补进长期记忆，不然系统只能记住上线之后的事。
  - 做完你能看到什么：已有数据也能进入长期记忆中心。
  - 先依赖什么：3.4
  - 开始前先看：
    - `requirements.md` 需求 1、2、5
    - `design.md` §2.3.5「历史回填流程」
    - `design.md` §6.1「迁移顺序」
  - 主要改哪里：
    - `apps/api-server/app/modules/memory/backfill.py`
    - `apps/api-server/app/modules/memory/service.py`
    - `specs/003-家庭记忆中心/docs/`
  - 这一步先不做什么：先不做跨家庭导入导出。
  - 怎么算完成：
    1. 可从现有业务表回填事件和记忆
    2. 重复执行不会制造重复数据
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - 人工重复执行回填验证幂等
  - 对应需求：`requirements.md` 需求 1、2、5
  - 对应设计：`design.md` §2.3.5、§4.2、§6.1

- [ ] 4.2 补治理、观测和验收文档
  - 状态：TODO
  - 这一步到底做什么：把记忆错误怎么查、权限怎么验、回滚怎么做写清楚，别让后续接手的人踩雷。
  - 做完你能看到什么：这个 Spec 不只是能开发，还能联调、验收、回滚。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md`
    - `design.md` §5、§6、§8
    - `tasks.md`
  - 主要改哪里：
    - `specs/003-家庭记忆中心/docs/`
    - `specs/003-家庭记忆中心/README.md`
  - 这一步先不做什么：不扩新功能。
  - 怎么算完成：
    1. 联调说明齐全
    2. 权限和降级验收口径清楚
    3. 回滚说明可执行
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` §5、§6、§7、§8

- [ ] 4.3 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认家庭记忆中心真的成立了，而不是“表面上有模块名”。
  - 做完你能看到什么：长期记忆已经成为家庭问答、提醒、前端页面和治理链路的一部分。
  - 先依赖什么：4.1、4.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件及对应实现文件
  - 这一步先不做什么：不临时加新方向。
  - 怎么算完成：
    1. 长期记忆可写、可查、可治理、可服务
    2. 实时上下文和长期记忆已经形成完整链路
    3. 现有模块未被破坏
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - `cd apps/admin-web && npm.cmd run build`
    - `cd apps/user-web && npm.cmd run build`
    - 按验收清单人工走查
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
