# 任务文档 - 用户端 AI 配置中心下沉

状态：Draft

## 当前判断

这份 Spec 要解决的不是“把几个后台表单搬前台”，而是让 `user-web` 真正成为正式产品里的 AI 配置中心。

如果这一步不做完：

- `AI配置` 仍是假入口
- `admin-web` 仍是正式流程依赖
- 对话页就仍会不停冒“没有可用 Agent”这种垃圾提示

---

## 阶段 1：先把供应商适配器层和用户端供应商配置打通

- [x] 1.1 建供应商适配器注册表
  - 状态：DONE
  - 这一步到底做什么：把 `ChatGPT`、`GLM`、`硅基流动`、`KIMI`、`MINIMAX` 等供应商统一收敛成适配器定义。
  - 做完你能看到什么：页面和接口不再为每家供应商各写一套散装逻辑。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2
    - `design.md` §2.1、§3.2、§5.1
  - 主要改哪里：
    - `apps/api-server/app/modules/ai_gateway/`
    - `apps/api-server/app/api/v1/endpoints/`
    - `apps/user-web/src/lib/`
  - 这一步先不做什么：先不做用户端页面。
  - 怎么算完成：
    1. 能返回供应商适配器列表
    2. 每家供应商的字段定义和校验规则可读
  - 怎么验证：
    - `cd apps/api-server && pytest -q`
    - 人工调用适配器接口检查返回结构
  - 对应需求：`requirements.md` 需求 1、需求 2
  - 对应设计：`design.md` §2.1、§3.2、§3.3

- [x] 1.2 做 user-web 正式供应商配置页
  - 状态：DONE
  - 这一步到底做什么：把供应商新增、编辑、启用、停用和校验能力放进 `user-web`。
  - 做完你能看到什么：用户不用再被踢去 `admin-web` 配模型供应商。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 5
    - `design.md` §2.3、§3.1、§5.2
  - 主要改哪里：
    - `apps/user-web/src/pages/`
    - `apps/user-web/src/components/`
    - `apps/user-web/src/lib/api.ts`
    - `apps/user-web/src/lib/types.ts`
  - 这一步先不做什么：先不做 Agent 配置页。
  - 怎么算完成：
    1. 用户端能新增供应商配置
    2. 用户端能编辑和启停供应商配置
    3. 校验失败会明确报错
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工走通新增和编辑流程
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 5
  - 对应设计：`design.md` §2.3、§3.3、§5.2

### 阶段检查

- [x] 1.3 阶段检查：确认供应商配置已不依赖 admin-web
  - 状态：DONE
  - 这一步到底做什么：检查真实用户是不是已经能只靠 `user-web` 完成供应商配置。
  - 做完你能看到什么：AI 配置中心至少站住了一半，不再是假入口。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段相关文件
  - 这一步先不做什么：不扩 Agent 编辑。
  - 怎么算完成：
    1. 供应商配置闭环已在 user-web
    2. `admin-web` 不再是正式依赖
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 5
  - 对应设计：`design.md` §5.2

---

## 阶段 2：把 Agent 配置中心正式下沉到 user-web

- [x] 2.1 做 Agent 列表和详情编辑页
  - 状态：DONE
  - 这一步到底做什么：把 Agent 列表、基础资料、人格、运行时策略和成员认知编辑能力放进 `user-web`。
  - 做完你能看到什么：`AI配置` 终于是真配置，不是只读展示。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 3、需求 5
    - `design.md` §2.3、§3.1、§3.3
    - `../003.1-AI助手人格化设计/`
  - 主要改哪里：
    - `apps/user-web/src/pages/`
    - `apps/user-web/src/components/`
    - `apps/user-web/src/lib/api.ts`
    - `apps/user-web/src/lib/types.ts`
  - 这一步先不做什么：先不做首个管家对话式创建。
  - 怎么算完成：
    1. 用户端能编辑 Agent 资料
    2. 用户端能控制默认入口和可对话状态
    3. 用户端能新增 Agent
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工修改后刷新检查结果一致
  - 对应需求：`requirements.md` 需求 3、需求 5、需求 6
  - 对应设计：`design.md` §2.3、§3.3、§5.2

- [x] 2.2 把配置结果接入对话主链路
  - 状态：DONE
  - 这一步到底做什么：确保供应商和 Agent 配置不是摆设，而是真的影响对话页。
  - 做完你能看到什么：默认 Agent、可切换列表、人格表现和可用供应商都会跟配置一致。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 6
    - `design.md` §2.2、§5.3、§7
  - 主要改哪里：
    - `apps/user-web/src/pages/ConversationPage.tsx`
    - `apps/api-server/app/modules/agent/`
    - `apps/api-server/app/modules/ai_gateway/`
  - 这一步先不做什么：先不做外观系统。
  - 怎么算完成：
    1. 默认 Agent 跟配置一致
    2. 可切换 Agent 跟配置一致
    3. 供应商可用性变化能影响对话
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工改配置后测试对话行为变化
  - 对应需求：`requirements.md` 需求 6
  - 对应设计：`design.md` §2.2、§5.3、§7

### 阶段检查

- [x] 2.3 阶段检查：确认 AI 配置中心已经是正式入口
  - 状态：DONE
  - 这一步到底做什么：检查 `user-web` 的 AI 配置是不是已经能承担正式产品职责。
  - 做完你能看到什么：用户不再需要被赶去后台，正式配置中心开始成立。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段全部相关文件
  - 这一步先不做什么：不扩 onboarding。
  - 怎么算完成：
    1. 供应商配置闭环成立
    2. Agent 配置闭环成立
    3. 对话主链路受配置影响
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、需求 3、需求 5、需求 6
  - 对应设计：`design.md` §2、§5、§7

---

## 阶段 3：补首个管家对话式创建和与 003.2 的复用

- [ ] 3.1 做首个管家对话式创建流程
  - 状态：TODO
  - 这一步到底做什么：让用户能通过一段引导式对话创建第一个管家 Agent。
  - 做完你能看到什么：首个管家的创建不再是冷冰冰表单，而是一段真正可用的引导流程。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 4
    - `design.md` §2.3、§3.3、§5.3
  - 主要改哪里：
    - `apps/user-web/src/pages/`
    - `apps/user-web/src/components/`
    - `apps/api-server/app/modules/agent/`
  - 这一步先不做什么：先不做复杂多轮长记忆引导。
  - 怎么算完成：
    1. 用户可通过对话生成首个管家草稿
    2. 用户确认后可创建默认管家 Agent
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工走通一次创建流程
  - 对应需求：`requirements.md` 需求 4
  - 对应设计：`design.md` §2.3、§3.3、§5.3

- [ ] 3.2 把首个管家创建能力接给 003.2 向导复用
  - 状态：TODO
  - 这一步到底做什么：把对话式创建器做成可复用能力，既能在 AI 配置中心里用，也能嵌进新家庭初始化向导。
  - 做完你能看到什么：不会出现一套 onboarding 创建逻辑、一套设置页创建逻辑的双份垃圾。
  - 先依赖什么：3.1、`003.2` 对应能力
  - 开始前先看：
    - `requirements.md` 需求 4、需求 5
    - `design.md` §2.1、§5.3
    - `../003.2-新家庭初始化与强制向导/`
  - 主要改哪里：
    - `apps/user-web/src/components/`
    - `apps/user-web/src/pages/`
    - `apps/user-web/src/lib/`
  - 这一步先不做什么：先不扩展成所有 Agent 的统一对话式创建器。
  - 怎么算完成：
    1. 同一套创建器可在两处复用
    2. 不存在两套分叉逻辑
  - 怎么验证：
    - 人工在 AI 配置中心和向导里各走一遍
  - 对应需求：`requirements.md` 需求 4、需求 5
  - 对应设计：`design.md` §2.1、§5.3

### 最终检查

- [ ] 3.3 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认 `user-web` 已经成为正式 AI 配置中心，而不是半成品页面。
  - 做完你能看到什么：供应商、Agent、首个管家创建和对话联动都能闭环。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一步先不做什么：不再继续扩新范围。
  - 怎么算完成：
    1. 供应商配置、Agent 配置、首个管家创建都已在 user-web 闭环
    2. admin-web 不再是正式产品必要入口
    3. 对话主链路能反映最新配置
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工按验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
