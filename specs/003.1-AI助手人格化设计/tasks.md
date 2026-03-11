# 任务文档 - AI多Agent与管家角色设计

状态：Draft

## 任务总原则

这次别再按“先做一个管家页面，后面再补别的角色”这种懒办法走。

正确顺序应该是：

1. 先立住多 Agent 基座
2. 再把主管家、营养师、健身教练这类角色挂到同一基座上
3. 再把 `AI配置` 和 `对话` 两个前端入口分开
4. 最后再做外观生成、治理和验收

## 当前优先落地拆分

上面的阶段任务能用，但它们现在更适合当**父任务**，不适合直接拿去排今天和这周的开发活。

原因很简单：

- `1.1 新增多 Agent 基础模型` 这种标题太大，里面混了迁移、模型、Schema、Repository、接口约束
- `1.2 做 AI配置聚合读模型` 又把后端接口和前端接入揉在一起
- 当前你已经明确：**先不动 `user-web`，先做后端和 `admin-web`**

所以当前真正能直接开的活，应该先拆成下面这 8 个小任务。

### A1 先建多 Agent 数据表和迁移

- 状态：DONE
- 这一步到底做什么：先把 `family_agents`、`family_agent_soul_profiles`、`family_agent_member_cognitions`、`family_agent_runtime_policies` 这些核心表和迁移建出来。
- 做完你能看到什么：数据库里已经有多 Agent 的真实骨架，不再只有设计文档。
- 先依赖什么：无
- 主要改哪里：
  - `apps/api-server/migrations/versions/`
  - `apps/api-server/app/modules/agent/models.py`
- 实际完成：
  - 已新增 `apps/api-server/app/modules/agent/models.py`
  - 已新增 `apps/api-server/migrations/versions/20260311_0007_create_agent_foundation.py`
  - 已在 `apps/api-server/app/db/models.py` 注册新模型
- 这一步先不做什么：先不做外观生成表，先不碰 `user-web`
- 怎么算完成：
  1. 核心表结构已落库
  2. 一个家庭可以挂多个 Agent
  3. `is_primary` 能表达主管家
- 怎么验证：
  - `cd apps/api-server && pytest -q`
  - 人工检查迁移和 ORM 是否一致
- 对应父任务：1.1

### A2 补 Agent 的 Schema、Repository 和服务骨架

- 状态：DONE
- 这一步到底做什么：把 Agent 的读写 Schema、Repository 和最小服务层先立住，别让接口层直接硬写 SQLAlchemy。
- 做完你能看到什么：后端已经有稳定的 Agent 模块入口，不是散在各个 endpoint 里的临时代码。
- 先依赖什么：A1
- 主要改哪里：
  - `apps/api-server/app/modules/agent/schemas.py`
  - `apps/api-server/app/modules/agent/repository.py`
  - `apps/api-server/app/modules/agent/service.py`
- 实际完成：
  - 已新增 `apps/api-server/app/modules/agent/schemas.py`
  - 已新增 `apps/api-server/app/modules/agent/repository.py`
  - 已新增 `apps/api-server/app/modules/agent/service.py`
  - 已补主管家兜底读取骨架 `resolve_effective_agent`
- 这一步先不做什么：先不接运行时上下文，不做对话路由
- 怎么算完成：
  1. Agent 列表、详情、创建、更新所需 Schema 已齐
  2. Repository 封装了基础查询和写入
  3. 服务层能读主管家和普通 Agent
- 怎么验证：
  - `cd apps/api-server && pytest -q`
  - 人工检查 service 不直接耦合 HTTP 层
- 对应父任务：1.1、1.2

### A3 做 AI配置列表接口和单 Agent 详情接口

- 状态：DONE
- 这一步到底做什么：先把 `AI配置` 真正需要的两个核心接口做出来：Agent 列表摘要、单 Agent 详情。
- 做完你能看到什么：`admin-web` 已经有东西可接，不再只能对着 mock 或设计图发呆。
- 先依赖什么：A2
- 主要改哪里：
  - `apps/api-server/app/api/v1/endpoints/`
  - `apps/api-server/app/modules/agent/service.py`
- 实际完成：
  - 已新增 `apps/api-server/app/api/v1/endpoints/ai_config.py`
  - 已在 `apps/api-server/app/api/v1/router.py` 注册 `ai-config` 路由
  - 已实现 `GET /api/v1/ai-config/{household_id}`
  - 已实现 `GET /api/v1/ai-config/{household_id}/agents/{agent_id}`
- 建议最小接口：
  1. `GET /api/v1/ai-config/{household_id}`
  2. `GET /api/v1/ai-config/{household_id}/agents/{agent_id}`
- 这一步先不做什么：先不做新增角色向导，先不做复杂筛选
- 怎么算完成：
  1. 能返回多个 Agent 摘要
  2. 能返回单 Agent 的人格、成员认知、运行时策略摘要
  3. 不影响现有成员和图谱接口
- 怎么验证：
  - `cd apps/api-server && pytest -q`
  - 人工调用接口检查返回字段
- 对应父任务：1.2

### A4 做 Soul、成员认知、运行时策略更新接口

- 状态：DONE
- 这一步到底做什么：把 `admin-web` 真要编辑的内容接成真保存，而不是只停留在只读详情。
- 做完你能看到什么：可以单独修改某个 Agent 的人格、成员认知和运行时策略。
- 先依赖什么：A3
- 主要改哪里：
  - `apps/api-server/app/api/v1/endpoints/`
  - `apps/api-server/app/modules/agent/service.py`
  - `apps/api-server/app/modules/agent/repository.py`
- 实际完成：
  - 已在 `apps/api-server/app/modules/agent/schemas.py` 新增更新用 Schema
  - 已在 `apps/api-server/app/modules/agent/service.py` 实现 `upsert_agent_soul`
  - 已在 `apps/api-server/app/modules/agent/service.py` 实现 `upsert_agent_member_cognitions`
  - 已在 `apps/api-server/app/modules/agent/service.py` 实现 `upsert_agent_runtime_policy`
  - 已在 `apps/api-server/app/api/v1/endpoints/ai_config.py` 新增 3 个 `PUT` 接口
- 建议最小接口：
  1. `PUT /api/v1/ai-config/{household_id}/agents/{agent_id}/soul`
  2. `PUT /api/v1/ai-config/{household_id}/agents/{agent_id}/member-cognitions`
  3. `PUT /api/v1/ai-config/{household_id}/agents/{agent_id}/runtime-policy`
- 这一步先不做什么：先不做批量导入，不做复杂审批流
- 怎么算完成：
  1. `soul` 可单独保存并版本化
  2. 成员认知可按 Agent 更新
  3. 是否可在对话页直达等策略可单独保存
- 怎么验证：
  - `cd apps/api-server && pytest -q`
  - 人工检查更新后重新读取接口结果
- 对应父任务：2.1、2.2

### A5 补主管家兜底和多 Agent 运行时选择骨架

- 状态：TODO
- 这一步到底做什么：先把运行时“默认用主管家、允许指定其他 Agent”的服务骨架立住，别等对话页开做时再现补。
- 做完你能看到什么：后端已经能回答“当前这次请求到底该用哪个 Agent”。
- 先依赖什么：A4
- 主要改哪里：
  - `apps/api-server/app/modules/agent/service.py`
  - `apps/api-server/app/modules/family_qa/`
- 这一步先不做什么：先不做复杂自动路由推荐
- 怎么算完成：
  1. 没指定 Agent 时默认回主管家
  2. 指定 Agent 时能读取对应人格和策略
  3. 无效 Agent 会安全降级
- 怎么验证：
  - `cd apps/api-server && pytest -q`
  - 人工检查主管家兜底逻辑
- 对应父任务：2.1、2.4

### A6 在 `admin-web` 做 AI配置列表页

- 状态：DONE
- 这一步到底做什么：先把 `admin-web` 里的 AI配置总览页做出来，展示多个 Agent 的列表、角色、状态和主 Agent 标记。
- 做完你能看到什么：团队终于有一个能看多 Agent 全貌的管理入口。
- 先依赖什么：A3
- 主要改哪里：
  - `apps/admin-web/src/App.tsx`
  - `apps/admin-web/src/pages/`
  - `apps/admin-web/src/lib/api.ts`
- 实际完成：
  - 已新增 `apps/admin-web/src/pages/AiConfigPage.tsx`
  - 已在 `apps/admin-web/src/App.tsx` 注册 `/ai-config` 路由
  - 已在 `apps/admin-web/src/lib/api.ts` 新增 Agent 列表和详情读取方法
  - 已在 `apps/admin-web/src/types.ts` 新增 Agent 相关类型
- 这一步先不做什么：先不做复杂视觉打磨
- 怎么算完成：
  1. 能看到多个 Agent 卡片或列表
  2. 能区分主管家和专业 Agent
  3. 能点击进入单 Agent 配置页
- 怎么验证：
  - `cd apps/admin-web && npm.cmd run build`
  - 人工走查列表加载、空态和错误态
- 对应父任务：3.1

### A7 在 `admin-web` 做单 Agent 配置页

- 状态：TODO
- 这一步到底做什么：把单个 Agent 的 `soul`、成员认知和运行时策略做成真实可编辑表单。
- 做完你能看到什么：管理员可以真正改主管家、营养师、健身教练这些角色的配置。
- 先依赖什么：A4、A6
- 主要改哪里：
  - `apps/admin-web/src/pages/`
  - `apps/admin-web/src/components/`
  - `apps/admin-web/src/lib/api.ts`
- 这一步先不做什么：先不做外观生成和图片管理
- 怎么算完成：
  1. `soul` 可编辑并保存
  2. 成员认知可查看和保存
  3. 运行时策略可编辑并保存
- 怎么验证：
  - `cd apps/admin-web && npm.cmd run build`
  - 人工修改后刷新，确认保存结果一致
- 对应父任务：3.1、3.2

### A8 当前阶段检查：确认已经能支撑 AI配置页联调

- 状态：TODO
- 这一步到底做什么：只检查当前这轮“后端 + admin-web”是不是已经能支撑真实联调，不去顺手扩 `user-web`。
- 做完你能看到什么：你可以很明确地说，这套多 Agent 不是停在设计稿，而是已经有后端和管理入口。
- 先依赖什么：A1、A2、A3、A4、A5、A6、A7
- 主要改哪里：
  - 当前 Spec
  - `apps/api-server/`
  - `apps/admin-web/`
- 这一步先不做什么：先不扩 `user-web` 的 AI配置页和对话页
- 怎么算完成：
  1. 后端接口可联调
  2. `admin-web` 可查看和编辑多 Agent 配置
  3. 主管家兜底逻辑明确
- 怎么验证：
  - `cd apps/api-server && pytest -q`
  - `cd apps/admin-web && npm.cmd run build`
  - 人工按联调清单走一遍
- 对应父任务：1.3、2.5、3.4

## 父任务和当前拆分的对应关系

- `1.1 新增多 Agent 基础模型` = A1 + A2
- `1.2 做 AI配置聚合读模型` = A3
- `2.1 接各 Agent 的 Soul 配置与运行时人格上下文` = A4 + A5 的一部分
- `2.2 接各 Agent 的成员认知` = A4
- `2.4 做对话页的 Agent 上下文切换能力` = A5 的后端部分
- `3.1 保留 AI配置 作为统一多Agent设置入口` = A6 + A7 的管理侧部分

如果按你现在的优先级，真正应该排活的是：**A1 → A2 → A3 → A4 → A6 → A7 → A5 → A8**。

---

## 阶段 1：先把多Agent骨架搭出来

- [ ] 1.1 新增多 Agent 基础模型
  - 状态：DONE
  - 当前进度：A1 和 A2 已完成，核心表、ORM、Alembic 迁移、Schema、Repository 和服务骨架都已落地。下一步进入 1.2 和阶段检查。
  - 这一步到底做什么：为家庭新增统一的 Agent 数据模型和 Schema，包括 Agent 基础身份、`soul`、成员认知、外观档案和运行时策略。
  - 做完你能看到什么：后端里终于有多 Agent 的正式骨架，不再只有一个模糊助手对象。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 3、需求 5
    - `design.md` §3.1、§3.4、§4.1
  - 主要改哪里：
    - `apps/api-server/migrations/versions/`
    - `apps/api-server/app/modules/agent/`
  - 这一步先不做什么：先不接前端，不接多模态生成，不碰长期记忆主表。
  - 怎么算完成：
    1. Agent 基础数据模型和 Schema 已齐
    2. 一个家庭可拥有主管家和多个专业 Agent
    3. `soul`、成员认知、外观和运行时策略有明确存储位置
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - 人工检查迁移、模型、Schema 是否对应
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3、需求 5
  - 对应设计：`design.md` §3.1、§3.4、§4.1

- [ ] 1.2 做 AI配置聚合读模型
  - 状态：IN_PROGRESS
  - 当前进度：A3 已完成最小只读接口，A4 也已完成最小写接口，现在已经能读 Agent 列表 / 详情，并更新 `soul`、成员认知和运行时策略。后续如果要把外观摘要也并进来，再继续扩这一层读模型。
  - 这一步到底做什么：把多个 Agent 的摘要、状态、角色类型和配置入口聚合成一份给 AI配置页面用的读模型。
  - 做完你能看到什么：前端有稳定的 AI配置数据入口，不用自己拼一堆接口。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 6
    - `design.md` §3.3、§5.1、§6.1
  - 主要改哪里：
    - `apps/api-server/app/modules/agent/service.py`
    - `apps/api-server/app/api/v1/endpoints/`
    - `apps/user-web/src/lib/api.ts`
  - 这一步先不做什么：先不改对话页，不改成员页和图谱页。
  - 怎么算完成：
    1. 有统一的 AI配置接口
    2. 可返回多个 Agent 摘要
    3. 成员列表和图谱接口保持不变
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - 人工调用接口检查返回结构
  - 对应需求：`requirements.md` 需求 1、需求 6
  - 对应设计：`design.md` §3.3、§5.1、§6.1、§6.2

- [ ] 1.3 阶段检查：确认已经不是单助手模式
  - 状态：TODO
  - 这一步到底做什么：检查这一阶段是不是已经从“一个助手”真正变成了“多 Agent 基座”。
  - 做完你能看到什么：后续加管家、营养师、健身教练时，不需要再改底层结构。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不提前去做外观生成和前端细节。
  - 怎么算完成：
    1. Agent 基座和 AI配置读模型已站稳
    2. “不进成员、不进图谱”的边界已明确
  - 怎么验证：
    - 人工走查
    - 关键接口测试通过
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 6
  - 对应设计：`design.md` §3、§4、§5、§6

---

## 阶段 2：把人格、认知和记忆真正接到多Agent运行时

- [ ] 2.1 接各 Agent 的 Soul 配置与运行时人格上下文
  - 状态：IN_PROGRESS
  - 当前进度：A4 已完成 `soul` 的写接口和主管家兜底骨架，但真正把人格接进 `family_qa` 运行时上下文还没开始。
  - 这一步到底做什么：让每个 Agent 的响应都不再只靠临时 prompt，而是读取各自生效的 `soul` 配置。
  - 做完你能看到什么：管家、营养师、健身教练不再只是换个名字，而是有各自稳定人格。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3、需求 8
    - `design.md` §5.3、§8.1、§8.2、§8.3
  - 主要改哪里：
    - `apps/api-server/app/modules/agent/service.py`
    - `apps/api-server/app/modules/family_qa/`
    - `apps/api-server/app/modules/context/`
  - 这一步先不做什么：先不做自动角色漂移和复杂自学习。
  - 怎么算完成：
    1. 能读取和更新某个 Agent 的生效 `soul`
    2. 运行时能按 `agent_id` 拼入人格上下文
    3. `soul` 变更有版本可追踪
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - 人工检查不同 Agent 的上下文预览差异
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 8
  - 对应设计：`design.md` §5.3、§8.1、§8.2、§8.3

- [ ] 2.2 接各 Agent 的成员认知
  - 状态：IN_PROGRESS
  - 当前进度：A4 已完成成员认知的写接口，但还没把这些认知真正接进问答运行时和管理页展示。
  - 这一步到底做什么：让不同 Agent 知道它面对的是谁、该怎么称呼、该注意什么。
  - 做完你能看到什么：同一个家庭成员面对不同 Agent 时，能感受到合理的角色差异。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 8
    - `design.md` §4.1.3、§5.4、§8.1
  - 主要改哪里：
    - `apps/api-server/app/modules/agent/`
  - 这一步先不做什么：先不让这些认知进入家庭图谱或成员关系接口。
  - 怎么算完成：
    1. 可为每个 Agent 独立配置成员认知
    2. 运行时能按 `agent_id + member_id` 读取对应认知
    3. 这些认知只在 AI配置和对话相关链路可见
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - 人工切换不同 Agent 和成员验证认知差异
  - 对应需求：`requirements.md` 需求 3、需求 8
  - 对应设计：`design.md` §4.1.3、§5.4、§7、§8.1

- [ ] 2.3 复用记忆中心承接多 Agent 长期记忆
  - 状态：TODO
  - 这一步到底做什么：把所有 Agent 的长期记忆读取和写回接到已经完成的家庭记忆中心，而不是每个角色单开一套。
  - 做完你能看到什么：多个 Agent 有独立记忆视角，但底层只有一套家庭记忆真相。
  - 先依赖什么：2.2
  - 开始前先看：
    - `requirements.md` 需求 4、需求 8
    - `design.md` §3.5、§4.2、§4.3、§5.5
    - `specs/003-家庭记忆中心/requirements.md`
    - `specs/003-家庭记忆中心/design.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/memory/`
    - `apps/api-server/app/modules/agent/`
    - `apps/api-server/app/modules/family_qa/`
  - 这一步先不做什么：先不重构 `Spec 003` 主表结构，优先复用现有 `payload_json` 和 `content_json`。
  - 怎么算完成：
    1. 任意 Agent 读取长期记忆走现有记忆中心
    2. Agent 相关长期线索写回统一记忆入口
    3. 记忆纠错、失效、删除会影响对应 Agent 后续表现
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - 人工构造纠错和删除流程，验证查询结果变化
  - 对应需求：`requirements.md` 需求 4、需求 8
  - 对应设计：`design.md` §3.5、§4.2、§4.3、§5.5、§8.3

- [ ] 2.4 做对话页的 Agent 上下文切换能力
  - 状态：TODO
  - 这一步到底做什么：让对话页默认使用主管家，并支持显式切换到其他已启用 Agent。
  - 做完你能看到什么：产品层开始体现多 Agent，而不是只有配置表。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 7、需求 8
    - `design.md` §5.6、§7.1、§8
  - 主要改哪里：
    - `apps/user-web/src/pages/`
    - `apps/api-server/app/modules/agent/`
  - 这一步先不做什么：第一版先不做复杂自动路由。
  - 怎么算完成：
    1. 对话页默认使用主管家
    2. 可手动切换到其他 Agent
    3. 不同 Agent 切换后上下文和表现能变化
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工切换不同 Agent 验证对话体验
  - 对应需求：`requirements.md` 需求 7、需求 8
  - 对应设计：`design.md` §5.6、§7.1、§8

- [ ] 2.5 阶段检查：确认多Agent已经进运行时主链路
  - 状态：TODO
  - 这一步到底做什么：检查 `soul`、成员认知、长期记忆和对话切换是不是已经真的进入主链路。
  - 做完你能看到什么：多 Agent 不再只是配置概念，而是真的能工作。
  - 先依赖什么：2.1、2.2、2.3、2.4
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不追加复杂自动路由和花哨交互。
  - 怎么算完成：
    1. 运行时上下文已按 Agent 维度组装
    2. 对话页已能切换 Agent
    3. 降级路径已明确
  - 怎么验证：
    - 人工走查
    - 关键对话流程验证
  - 对应需求：`requirements.md` 需求 3、需求 4、需求 7、需求 8
  - 对应设计：`design.md` §5、§7、§8、§9

---

## 阶段 3：把前端入口理顺成 AI配置 + 对话

- [ ] 3.1 保留 AI配置 作为统一多Agent设置入口
  - 状态：TODO
  - 这一步到底做什么：把原本可能被改成“管家设置”的入口保留为 `AI配置`，并改造成多 Agent 管理页。
  - 做完你能看到什么：用户知道这里是在管理整个 AI 体系，不只是某一个管家角色。
  - 先依赖什么：2.5
  - 开始前先看：
    - `requirements.md` 需求 1、需求 6
    - `design.md` §3.3、§5.1、§7.1
  - 主要改哪里：
    - `apps/user-web/src/pages/SettingsPage.tsx`
    - `apps/user-web/src/lib/api.ts`
    - `apps/user-web/src/lib/types.ts`
    - `apps/user-web/src/i18n/`
  - 这一步先不做什么：先不把配置和对话混到一个页面。
  - 怎么算完成：
    1. 设置入口仍叫 AI配置
    2. AI配置页能展示多个 Agent
    3. 可进入单个 Agent 配置页
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工检查导航和配置流
  - 对应需求：`requirements.md` 需求 1、需求 6
  - 对应设计：`design.md` §3.3、§5.1、§5.2、§7.1

- [ ] 3.2 将原助手页面改造成对话页
  - 状态：TODO
  - 这一步到底做什么：把原来的“助手页面”入口、标题、文案和主数据源整体改成“对话”。
  - 做完你能看到什么：面向用户的页面表达的是交互场景，而不是底层角色实现。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 7、需求 8
    - `design.md` §3.3、§5.6、§7.1
  - 主要改哪里：
    - `apps/user-web/src/pages/`
    - `apps/user-web/src/lib/api.ts`
    - `apps/user-web/src/i18n/`
  - 这一步先不做什么：第一版先不做复杂自动路由推荐。
  - 怎么算完成：
    1. 原助手入口已改为对话
    2. 对话页默认使用主管家
    3. 对话页支持切换其他已启用 Agent
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工检查入口、标题和 Agent 切换体验
  - 对应需求：`requirements.md` 需求 7、需求 8
  - 对应设计：`design.md` §3.3、§5.6、§7.1、§8

- [ ] 3.3 接外观生成与发布流程
  - 状态：TODO
  - 这一步到底做什么：把各 Agent 的外观生成真正接到 `ai_gateway`，支持生成候选图、人工选择和发布。
  - 做完你能看到什么：管家、营养师、健身教练等角色都有具象外观，而且是可治理的。
  - 先依赖什么：3.2
  - 开始前先看：
    - `requirements.md` 需求 5、需求 8
    - `design.md` §5.7、§6.1、§8.3、§9
  - 主要改哪里：
    - `apps/api-server/app/modules/ai_gateway/`
    - `apps/api-server/app/modules/agent/`
    - `apps/admin-web/src/`
    - `apps/user-web/src/pages/`
  - 这一步先不做什么：先不做实时动态形象。
  - 怎么算完成：
    1. 能提交某个 Agent 的外观生成请求
    2. 能查看候选结果并选中发布
    3. 失败时不会影响对应 Agent 服务
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - `cd apps/admin-web && npm.cmd run build`
    - 人工走通一次生成到发布流程
  - 对应需求：`requirements.md` 需求 5、需求 8
  - 对应设计：`design.md` §5.7、§6.1、§8.3、§9

- [ ] 3.4 阶段检查：确认前端已经是 AI配置 + 对话
  - 状态：TODO
  - 这一步到底做什么：检查产品入口、页面和主链路是不是已经统一成“AI配置 + 对话”。
  - 做完你能看到什么：概念统一，页面统一，数据也统一。
  - 先依赖什么：3.1、3.2、3.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不再临时加新概念。
  - 怎么算完成：
    1. 设置侧已是 AI配置
    2. 交互侧已是对话
    3. 对话和配置职责已分开
  - 怎么验证：
    - 人工走查
    - 前后端构建通过
  - 对应需求：`requirements.md` 需求 6、需求 7、需求 8
  - 对应设计：`design.md` §3.3、§5、§6、§7、§8

---

## 阶段 4：补治理、文档和最终验收

- [ ] 4.1 补联调、权限与回滚文档
  - 状态：TODO
  - 这一步到底做什么：把多 Agent 配置、记忆复用、对话切换、外观生成失败、权限边界和回滚方式都写清楚。
  - 做完你能看到什么：后续不是只有开发能接，联调、验收和回退也有章法。
  - 先依赖什么：3.4
  - 开始前先看：
    - `requirements.md`
    - `design.md` §8、§9
    - `tasks.md`
  - 主要改哪里：
    - `specs/003.1-AI助手人格化设计/docs/`
    - `specs/003.1-AI助手人格化设计/README.md`
  - 这一步先不做什么：不扩新能力。
  - 怎么算完成：
    1. 联调口径清楚
    2. 权限和降级说明齐全
    3. 回滚步骤可执行
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` §8、§9、§10

- [ ] 4.2 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认这套设计真的把单助手模式升级成了多 Agent 架构，而不是只改了几个名字。
  - 做完你能看到什么：需求、设计、实现、验证证据都能一一对上。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件及对应实现文件
  - 这一步先不做什么：不再加新范围。
  - 怎么算完成：
    1. 系统里已具备正式的多 Agent 基座
    2. 管家已是默认主 Agent，但不是唯一 Agent
    3. AI配置与对话入口已分离
    4. 长期记忆复用链路成立，没有第二套记忆系统
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - `cd apps/admin-web && npm.cmd run build`
    - `cd apps/user-web && npm.cmd run build`
    - 按验收清单人工走查
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
