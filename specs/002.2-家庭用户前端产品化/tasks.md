# 任务清单 - 家庭用户前端产品化（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单不是拿来摆样子的，是拿来保证这个前端不会做着做着又退化成另一个管理台。

这里要回答清楚：

- 先做什么
- 后做什么
- 每一步改哪里
- 做完后怎么验

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但要写原因

规则：

- 只有 `状态：DONE` 的任务才能勾选成 `[x]`
- 每做完一个任务，必须立刻回写这里
- 如果任务被卡住，必须把卡点写成人话

---

## 阶段 0：先把方向和边界钉死

- [x] 0.1 明确用户前端和 `admin-web` 的职责分工
  - 状态：DONE
  - 这一步到底做什么：把“开发调试台”和“用户产品前端”彻底分开，避免继续把用户需求堆到 `admin-web`。
  - 做完你能看到什么：新的 Spec 会明确写清用户端是独立应用，`admin-web` 只服务开发和联调。
  - 先依赖什么：无
  - 开始前先看：
    - `apps/admin-web/src/App.tsx`
    - `specs/002.1-家庭问答提醒与场景编排/README.md`
  - 主要改哪里：
    - `specs/002.2-家庭用户前端产品化/README.md`
    - `specs/002.2-家庭用户前端产品化/requirements.md`
    - `specs/002.2-家庭用户前端产品化/design.md`
  - 这一步先不做什么：先不写具体前端代码。
  - 怎么算完成：
    1. 文档里明确写出双前端分工
    2. 文档里明确哪些内容留在 `admin-web`
  - 怎么验证：
    - 人工走查 `README.md`、`requirements.md`、`design.md`
  - 对应需求：`requirements.md` 需求 1
  - 对应设计：`design.md` §1.1、§2.1、§5.0

- [x] 0.2 写清用户前端的需求、设计和页面边界
  - 状态：DONE
  - 这一步到底做什么：把首页、家庭、助手、记忆、设置五大入口和“完整但易用”的配置策略写清楚。
  - 做完你能看到什么：团队知道先做哪些页面、为什么这样分、哪些内容不能暴露给用户。
  - 先依赖什么：0.1
  - 开始前先看：
    - `specs/000-Spec规范/Spec模板/requirements.md`
    - `specs/000-Spec规范/Spec模板/design.md`
  - 主要改哪里：
    - `specs/002.2-家庭用户前端产品化/requirements.md`
    - `specs/002.2-家庭用户前端产品化/design.md`
  - 这一步先不做什么：先不把后端接口实现展开。
  - 怎么算完成：
    1. 需求文档覆盖首页、配置、助手、记忆、主题、国际化
    2. 设计文档覆盖信息架构、路由、视图模型、降级策略
  - 怎么验证：
    - 人工走查需求和设计是否一一对应
  - 对应需求：`requirements.md` 需求 2、3、4、5、6、7、8、9、10
  - 对应设计：`design.md` §1.0、§2.0、§3.0、§4.0、§6.0

- [x] 0.3 补用户前端页面规划、视觉原则和里程碑文档
  - 状态：DONE
  - 这一步到底做什么：把页面规划、视觉风格、实施节奏写成单独文档，避免实现阶段边做边猜。
  - 做完你能看到什么：`docs/` 下有可直接拿来开工和对齐审美的说明文档。
  - 先依赖什么：0.2
  - 开始前先看：
    - `specs/002.2-家庭用户前端产品化/requirements.md`
    - `specs/002.2-家庭用户前端产品化/design.md`
  - 主要改哪里：
    - `specs/002.2-家庭用户前端产品化/docs/20260310-用户前端信息架构与页面规划-v0.1.md`
    - `specs/002.2-家庭用户前端产品化/docs/20260310-用户前端视觉与交互原则-v0.1.md`
    - `specs/002.2-家庭用户前端产品化/docs/20260310-用户前端实施节奏与里程碑-v0.1.md`
  - 这一步先不做什么：先不画高保真稿。
  - 怎么算完成：
    1. 页面规划能指导组件拆分
    2. 视觉原则能指导主题和页面风格
    3. 里程碑文档能指导开发节奏
  - 怎么验证：
    - 人工走查三份文档是否都能回答“做什么、为什么、先后顺序”
  - 对应需求：`requirements.md` 需求 1、2、5、8、10
  - 对应设计：`design.md` §2.1、§3.0、§8.0

- [x] 0.4 检查 `002.2` Spec 是否已经能直接指导实现
  - 状态：DONE
  - 这一步到底做什么：确认需求、设计、任务和补充文档能串起来，不留大空洞。
  - 做完你能看到什么：团队拿着 `002.2` 就能开始实现，不需要再猜“这个页面到底做成什么样”。
  - 先依赖什么：0.1、0.2、0.3
  - 开始前先看：
    - `specs/002.2-家庭用户前端产品化/README.md`
    - `specs/002.2-家庭用户前端产品化/requirements.md`
    - `specs/002.2-家庭用户前端产品化/design.md`
    - `specs/002.2-家庭用户前端产品化/tasks.md`
  - 主要改哪里：当前 Spec 全部文件
  - 这一步先不做什么：先不新增额外需求。
  - 怎么算完成：
    1. 文档间引用关系清楚
    2. 实施阶段可以直接按任务清单推进
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文

---

## 阶段 1：先把产品骨架搭起来

- [x] 1.1 建 `apps/user-web` 应用骨架和基础工程
  - 状态：DONE
  - 这一步到底做什么：新建用户前端应用，不再污染 `admin-web`。
  - 做完你能看到什么：仓库里出现一个能独立启动、构建和路由跳转的 `user-web`。
  - 先依赖什么：0.4
  - 开始前先看：
    - `requirements.md` 需求 1、10
    - `design.md` §1.3「分阶段交付策略」
    - `design.md` §2.2「应用边界与目录建议」
    - `design.md` §3.1「用户前端壳子」
  - 主要改哪里：
    - `apps/user-web/`
    - `package.json`
    - 共享工作区配置
  - 这一步先不做什么：先不做完整业务页面。
  - 怎么算完成：
    1. `user-web` 可独立运行和构建
    2. 基础路由和应用壳子存在
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
  - 对应需求：`requirements.md` 需求 1、10
  - 对应设计：`design.md` §2.2、§3.1

- [x] 1.2 建主题 token、国际化和用户偏好持久化骨架
  - 状态：DONE
  - 这一步到底做什么：把主题和国际化从第一天就做进架构，而不是后补丁。
  - 做完你能看到什么：前端可以切换浅色/深色/长辈模式和中英文，刷新后状态保留。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 8、10
    - `design.md` §2.3.5「主题与语言切换流」
    - `design.md` §4.10「AppearancePreference」
    - `design.md` §5.5「主题与国际化不变量」
  - 主要改哪里：
    - `apps/user-web/src/theme/`
    - `apps/user-web/src/i18n/`
    - `packages/ui/`
    - `packages/i18n/`
  - 这一步先不做什么：先不做品牌级多租户皮肤系统。
  - 怎么算完成：
    1. 主题切换不破坏布局
    2. 文案和日期时间支持国际化
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工切换主题和语言检查
  - 对应需求：`requirements.md` 需求 8、10
  - 对应设计：`design.md` §2.3.5、§4.10、§5.5

- [x] 1.3 建主导航、页面布局和家庭上下文切换
  - 状态：DONE
  - 这一步到底做什么：把首页、家庭、助手、记忆、设置五大入口和当前家庭切换先搭起来。
  - 做完你能看到什么：用户端主框架成型，不再是零散页面。
  - 先依赖什么：1.2
  - 开始前先看：
    - `requirements.md` 需求 1、2、9
    - `design.md` §2.1「产品信息架构」
    - `design.md` §3.1「用户前端壳子」
    - `design.md` §5.1「家庭上下文不变量」
  - 主要改哪里：
    - `apps/user-web/src/App.tsx`
    - `apps/user-web/src/layouts/`
    - `apps/user-web/src/state/`
  - 这一步先不做什么：先不填满每个业务模块。
  - 怎么算完成：
    1. 五个主入口可导航
    2. 当前家庭可切换并驱动页面刷新
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工检查路由切换和家庭切换
  - 对应需求：`requirements.md` 需求 1、2、9
  - 对应设计：`design.md` §2.1、§3.1、§5.1

- [x] 1.4 检查产品骨架是不是已经站稳
  - 状态：DONE
  - 这一步到底做什么：只检查骨架是否足够稳，别还没站稳就急着堆功能。
  - 做完你能看到什么：后面做业务页时不会反复拆壳子。
  - 先依赖什么：1.1、1.2、1.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：阶段 1 全部相关文件
  - 这一步先不做什么：不扩新页面范围。
  - 怎么算完成：
    1. 应用骨架、主题、i18n、导航、家庭上下文都已可用
    2. `admin-web` 与 `user-web` 分工没有被破坏
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工走查
  - 对应需求：`requirements.md` 需求 1、8、10
  - 对应设计：`design.md` §1.3、§2.0、§3.1、§5.0、§5.5

---

## 阶段 2：把首页和家庭配置做成真入口

- [ ] 2.0 先把真实数据接入顺序钉住，再按顺序替换模拟数据
  - 状态：IN_PROGRESS
  - 当前结论：先做“全局数据底座和家庭上下文”，再做“家庭页主数据读链路”，再做“首页聚合”，最后做“设置里的设备 / HA / AI 持久化”。助手和记忆留在阶段 3，不混进这轮。
  - 这一步到底做什么：把 `user-web` 现有页面、模拟数据和后端接口对应关系先梳理清楚，避免一上来同时改 5 个页面最后到处返工。
  - 做完你能看到什么：`tasks.md` 里会明确写清“先接哪一页、为什么先接、依赖什么接口、卡点是什么”。
  - 先依赖什么：1.4
  - 开始前先看：
    - `apps/user-web/src/state/household.tsx`
    - `apps/user-web/src/pages/HomePage.tsx`
    - `apps/user-web/src/pages/FamilyPage.tsx`
    - `apps/user-web/src/pages/SettingsPage.tsx`
    - `apps/admin-web/src/lib/api.ts`
    - `apps/api-server/app/api/v1/endpoints/`
  - 主要改哪里：
    - `specs/002.2-家庭用户前端产品化/tasks.md`
  - 这一步先不做什么：
    - 先不碰助手页和记忆页
    - 先不为了接前端去扩后端新接口
    - 先不做视觉微调
  - 推荐接入顺序：
    1. **全局数据底座 + 当前家庭上下文**
       - 先接 `GET /api/v1/households`、`GET /api/v1/households/{id}`
       - 把 `apps/user-web/src/state/household.tsx` 从 `MOCK_HOUSEHOLDS` 切到真实请求
       - 原因：首页、家庭页、设置页都依赖当前家庭，没有这一步，后面全是假的
    2. **家庭页真实数据（概览 / 房间 / 成员 / 关系）**
       - 接 `GET /api/v1/households/{id}`、`GET /api/v1/context/configs/{household_id}`、`GET /api/v1/rooms`、`GET /api/v1/members`、`GET /api/v1/member-relationships`、`GET /api/v1/member-preferences/{member_id}`
       - 先把页面读数据切真，再补最小可用编辑表单
       - 原因：这些页面字段和后端主数据一一对应，先接稳它们，首页的聚合规则才不容易写歪
    3. **首页第一批真实数据（优先只读，不先上编辑）**
       - 先接 `GET /api/v1/context/overview`、`GET /api/v1/rooms`、`GET /api/v1/members`、`GET /api/v1/devices`、`GET /api/v1/reminders/overview`
       - 先把欢迎区、关键指标、房间状态、成员状态、设备状态换成真实数据
       - “最近事件”先用现有接口里能稳定拿到的提醒 / 洞察 / 设备同步结果做收敛，缺的部分明确降级，不硬拼假日志
       - 原因：首页是聚合页，最好在家庭主数据已经跑通后再做视图模型收敛
    4. **设置页里的设备与集成**
       - 接 `GET /api/v1/devices`、`POST /api/v1/devices/sync/ha`，必要时结合 `GET /api/v1/context/overview`
       - 先做设备列表、房间归属、同步结果和 HA 健康提示
       - 原因：这是现有后端最完整、最容易直接复用的一组设置接口
    5. **设置页里的 AI / 通知 / 家庭模式持久化**
       - 优先复用 `GET|PUT /api/v1/context/configs/{household_id}`、`GET /api/v1/ai/runtime-defaults`、`GET /api/v1/ai/routes`
       - 只接现在后端已经有产品语义承载的字段；像“助手名称”“回复语气”“通知方式”这类如果后端还没有稳定字段，就先记成缺口，不瞎映射
       - 原因：这部分最容易把用户配置和底层 provider 细节搅在一起，必须最后做
  - 当前卡点：
    1. 现有很多阶段 2 接口还是 `admin` 角色保护，`user-web` 这轮接入会先复用现有接口完成“去 mock”，后续再和后端把 member 视角补齐
    2. 首页“最近事件流”和设置页部分用户偏好，还没有完全一一对应的后端产品字段，需要前端先做保守映射和降级说明
  - 怎么算完成：
    1. 接入顺序和依赖已经写清楚
    2. 团队按这个顺序能直接开工，不需要再猜先后
  - 怎么验证：
    - 人工走查任务顺序是否覆盖 `首页`、`家庭`、`设置`
    - 检查每一步是否都写了依赖接口和明确不做什么

- [ ] 2.1 做首页 / 仪表盘聚合页
  - 状态：IN_PROGRESS
  - 当前进度：已完成首页产品化骨架；欢迎区、关键指标、房间状态、成员状态、设备状态、最近事件已切到真实 API（`households / context/overview / rooms / members / devices / reminders/overview`）并支持局部降级。天气类展示已改成家庭状态摘要。仍待补更细的聚合视图模型和人工联调截图。
  - 这一步到底做什么：把家庭状态、房间、成员、设备和最近事件收敛到一个真正可用的首页。
  - 做完你能看到什么：用户打开系统第一眼就知道“家里现在怎么样”。
  - 先依赖什么：1.4
  - 开始前先看：
    - `requirements.md` 需求 2、9
    - `design.md` §2.3.1「首页聚合流」
    - `design.md` §3.2「首页 / 仪表盘」
    - `design.md` §4.2「DashboardOverview」
  - 主要改哪里：
    - `apps/user-web/src/pages/dashboard/`
    - `apps/user-web/src/components/dashboard/`
    - 聚合接口或视图模型相关文件
  - 这一步先不做什么：先不做复杂 BI 统计。
  - 怎么算完成：
    1. 首页能展示核心家庭状态
    2. 异常和快捷动作都有明确入口
    3. 局部接口失败时页面仍能用
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工检查正常态、空态、降级态
  - 对应需求：`requirements.md` 需求 2、9
  - 对应设计：`design.md` §2.3.1、§3.2、§4.2、§6.0

- [ ] 2.2 做家庭、房间、成员和关系管理页
  - 状态：IN_PROGRESS
  - 当前进度：家庭概览 / 房间 / 成员 / 关系页面已切到真实读接口（`households / context/overview / rooms / members / devices / member-relationships / member-preferences`）；新增房间 / 成员 / 关系已接到现有写接口；成员偏好也已接到现有 `member-preferences/{member_id}` upsert 接口。更复杂的成员权限和房间编辑仍待后续补。
  - 这一步到底做什么：把家庭结构管理从调试台迁出来，做成用户能用的产品页。
  - 做完你能看到什么：用户前端能直接维护家庭、房间、成员和关系。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 3、9
    - `design.md` §2.3.2「家庭配置编辑流」
    - `design.md` §3.3「家庭概览、房间、成员、关系」
    - `design.md` §4.3、§4.4、§4.5
  - 主要改哪里：
    - `apps/user-web/src/pages/family/`
    - `apps/user-web/src/components/family/`
  - 这一步先不做什么：先不做特别复杂的拖拽式关系编辑器。
  - 怎么算完成：
    1. 家庭、房间、成员、关系页面都可进入
    2. 编辑有清晰校验和保存反馈
    3. 关系表达不再只靠表格
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工检查新增、编辑、切换和提示
  - 对应需求：`requirements.md` 需求 3、9
  - 对应设计：`design.md` §2.3.2、§3.3、§4.3、§4.4、§4.5、§6.1

- [ ] 2.3 做设备、HA 和 AI 易用配置页
  - 状态：IN_PROGRESS
  - 当前进度：设置页二级导航和 6 个子页面骨架已完成；主题切换、语言切换、长辈模式已可工作；设备与集成页已切到真实 API（`context/overview / devices / rooms / devices/sync/ha`）；AI 配置已接入真实的隐私级别字段，并继续接入了 `voice_fast_path_enabled / guest_mode_enabled / child_protection_enabled / elder_care_watch_enabled` 这些家庭服务开关；通知偏好已接入真实的免打扰开关和时段（`context/configs`）。其余像助手称呼、回复语气、通知方式、通知范围等字段，后端还没有稳定的用户态配置承载，当前已在页面里明确提示，不做假映射。
  - 这一步到底做什么：把设备、HA、AI 这些完整配置能力收进 `设置` 入口，但全部换成用户看得懂的话。
  - 做完你能看到什么：用户在 `设置` 里就能完成设备、HA、AI 配置，但不会看到一堆开发者术语。
  - 先依赖什么：2.2
  - 开始前先看：
    - `requirements.md` 需求 4、5、8、9
    - `design.md` §3.4「设置中的设备、HA 与 AI 易用配置」
    - `design.md` §5.2「易用配置不变量」
    - `design.md` §6.1「配置页面错误处理」
  - 主要改哪里：
    - `apps/user-web/src/pages/integrations/`
    - `apps/user-web/src/pages/ai-settings/`
    - `apps/user-web/src/components/settings/`
  - 这一步先不做什么：先不把 provider 调试能力搬进用户端。
  - 怎么算完成：
    1. HA 状态与同步范围可理解
    2. AI 配置支持完整产品级设置
    3. 这些配置明确出现在 `设置` 入口下
    4. 高风险设置有解释和保守默认值
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工检查配置保存与风险提示
  - 对应需求：`requirements.md` 需求 4、5、8、9
  - 对应设计：`design.md` §3.4、§5.2、§6.1

- [ ] 2.4 检查首页和家庭配置是不是已经形成可演示闭环
  - 状态：TODO
  - 这一步到底做什么：确认用户端已经能承担“看状态 + 改配置”的基本任务。
  - 做完你能看到什么：用户前端不再只是空壳，而是已经有可演示产品价值。
  - 先依赖什么：2.1、2.2、2.3
  - 开始前先看：
    - `requirements.md` 需求 2、3、4、5、8、9
    - `design.md` §2.3.1、§2.3.2、§3.2、§3.3、§3.4
  - 主要改哪里：阶段 2 全部相关文件
  - 这一步先不做什么：先不扩到助手和记忆。
  - 怎么算完成：
    1. 首页和家庭配置链路能跑通
    2. 用户端配置能力已经明显区别于 `admin-web`
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工走查
  - 对应需求：`requirements.md` 需求 2、3、4、5、8、9
  - 对应设计：`design.md` §2.3.1、§2.3.2、§3.2、§3.3、§3.4

---

## 阶段 3：把助手和记忆做成产品中心

- [ ] 3.1 做 AI 助手多会话与连续对话页
  - 状态：IN_PROGRESS
  - 当前进度：已把助手页从纯模拟数据切到真实 `family-qa/suggestions` 和 `family-qa/query`；当前保留本地会话壳，支持新建、切换、连续追问，并能显示真实回答、降级状态、事实引用和推荐追问。快捷动作里“转为提醒”“写入记忆”也已接到现有 `reminders` 和 `memories/cards/manual` 接口。真正的服务端会话持久化还没做。
  - 这一步到底做什么：把助手做成真正能长期使用的对话中心，不是一次性问答框。
  - 做完你能看到什么：用户能管理多个会话，并在同一会话中持续追问。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 需求 6、9
    - `design.md` §2.3.3「助手会话流」
    - `design.md` §3.5「助手页面」
    - `design.md` §4.7、§4.8
  - 主要改哪里：
    - `apps/user-web/src/pages/assistant/`
    - `apps/user-web/src/components/assistant/`
  - 这一步先不做什么：先不做复杂的多模态输入。
  - 怎么算完成：
    1. 多会话、新建会话、切换会话可用
    2. 连续对话上下文稳定
    3. 降级状态和记忆引用状态可见
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工走查多轮对话和失败降级
  - 对应需求：`requirements.md` 需求 6、9
  - 对应设计：`design.md` §2.3.3、§3.5、§4.7、§4.8、§6.2

- [ ] 3.2 做家庭记忆列表、详情和纠错管理
  - 状态：IN_PROGRESS
  - 当前进度：记忆页已切到真实 `memories/cards`，支持分类切换、搜索、列表和详情抽屉，能展示来源、可见范围、状态和更新时间。纠错 / 失效 / 删除已接到现有 `memories/cards/{id}/corrections` 接口，修订历史也已接到现有 `memories/cards/{id}/revisions`，并支持展开查看 `before / after` 详情。当前仍缺更细的权限提示和更友好的编辑交互。
  - 这一步到底做什么：把家庭记忆做成可查、可改、可控的页面，而不是黑盒存储。
  - 做完你能看到什么：用户能查看来源、纠错、失效标记和可见范围。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 7、9
    - `design.md` §2.3.4「记忆检索与纠错流」
    - `design.md` §3.6「记忆页面」
    - `design.md` §4.9「MemoryRecord」
  - 主要改哪里：
    - `apps/user-web/src/pages/memories/`
    - `apps/user-web/src/components/memory/`
  - 这一步先不做什么：先不做复杂自动聚类。
  - 怎么算完成：
    1. 记忆列表和详情可用
    2. 纠错、失效标记和删除有反馈
    3. 敏感记忆遵守可见范围
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工检查搜索、筛选、编辑和权限提示
  - 对应需求：`requirements.md` 需求 7、9
  - 对应设计：`design.md` §2.3.4、§3.6、§4.9、§5.4、§6.3

- [ ] 3.3 打通助手到提醒、场景和记忆的快捷动作
  - 状态：IN_PROGRESS
  - 当前进度：助手页里的“转为提醒”“写入记忆”已经接到现有 `reminders` 和 `memories/cards/manual` 接口，并补了前端确认表单；家庭页也已经补上基于现有接口的新增房间、成员、关系表单（`rooms / members / member-relationships`）。场景动作和页面跳转还没接。
  - 这一步到底做什么：让助手回答不是停在一段文字，而是能继续转成家庭服务动作。
  - 做完你能看到什么：用户可以把回答转成提醒、写入记忆或跳转相关家庭页面。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md` 需求 5、6、7
    - `design.md` §2.3.3「助手会话流」
    - `design.md` §3.5「助手页面」
    - `design.md` §3.6「记忆页面」
  - 主要改哪里：
    - `apps/user-web/src/components/assistant/`
    - `apps/user-web/src/lib/actions/`
    - 相关页面跳转与弹层
  - 这一步先不做什么：先不做完全自动执行的高风险动作。
  - 怎么算完成：
    1. 回答后能触发快捷动作
    2. 快捷动作有明确确认和结果反馈
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工检查助手到提醒、记忆的转化链路
  - 对应需求：`requirements.md` 需求 5、6、7
  - 对应设计：`design.md` §2.3.3、§3.5、§3.6、§5.2、§6.2

- [ ] 3.4 检查助手和记忆是不是已经形成产品中心
  - 状态：TODO
  - 这一步到底做什么：确认用户端的核心价值已经立住，而不是只有几个静态页面。
  - 做完你能看到什么：首页、配置、助手、记忆已经形成一套能演示的产品主线。
  - 先依赖什么：3.1、3.2、3.3
  - 开始前先看：
    - `requirements.md` 需求 5、6、7、9
    - `design.md` §2.3.3、§2.3.4、§3.5、§3.6
  - 主要改哪里：阶段 3 全部相关文件
  - 这一步先不做什么：先不追求视觉终稿。
  - 怎么算完成：
    1. 助手与记忆主链路稳定
    2. 快捷动作链路清楚
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工走查
  - 对应需求：`requirements.md` 需求 5、6、7、9
  - 对应设计：`design.md` §2.3.3、§2.3.4、§3.5、§3.6

---

## 阶段 4：做产品化收口和验收

- [ ] 4.1 做空态、错误态、骨架屏和降级提示统一规范
  - 状态：TODO
  - 这一步到底做什么：把产品失败时的表现也设计好，别只管成功截图。
  - 做完你能看到什么：空态、报错、弱网、降级都有一致体验。
  - 先依赖什么：3.4
  - 开始前先看：
    - `requirements.md` 需求 9
    - `design.md` §6.0「错误处理与降级」
  - 主要改哪里：
    - `apps/user-web/src/components/feedback/`
    - 各业务页面的错误与空态组件
  - 这一步先不做什么：先不做复杂动画特效。
  - 怎么算完成：
    1. 各主页面都有统一空态和错误态
    2. 助手降级和首页局部失败提示一致
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工制造接口失败验证
  - 对应需求：`requirements.md` 需求 9
  - 对应设计：`design.md` §6.0、§6.1、§6.2、§6.3、§6.4

- [ ] 4.2 做响应式、无障碍和长辈友好模式收口
  - 状态：IN_PROGRESS
  - 当前进度：已实现长辈友好模式。正在添加全站移动端响应式布局适配（平板与手机优先，包含底部导航栏支持）。
  - 这一步到底做什么：让这套前端不只是在开发机上好看，而是真的能给不同家庭成员用，不论电脑还是手机。
  - 做完你能看到什么：桌面、平板、手机、较大字号和高对比模式都能正常使用。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 需求 8
    - `design.md` §3.7「设置页面」
    - `design.md` §7.4「视觉与国际化验证」
  - 主要改哪里：
    - `apps/user-web/src/styles/`
    - `packages/ui/`
    - `apps/user-web/src/pages/settings/`
  - 这一步先不做什么：先不高保真优化复杂的移动端交互动画。
  - 怎么算完成：
    1. 长辈模式可切换
    2. 关键页面支持响应式（电脑宽屏、平板、手机自动适配单列和底部导航）
    3. 核心操作支持更高可读性
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工做断点和高对比检查
  - 对应需求：`requirements.md` 需求 8
  - 对应设计：`design.md` §3.7、§4.10、§5.5、§7.4

- [ ] 4.3 补联调说明、视觉走查和验收记录
  - 状态：TODO
  - 这一步到底做什么：把这套用户前端怎么联调、怎么验、当前哪些地方还只是占位写清楚。
  - 做完你能看到什么：后续接手的人知道怎么跑、怎么验、哪里还没完。
  - 先依赖什么：4.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/20260310-用户前端实施节奏与里程碑-v0.1.md`
  - 主要改哪里：
    - `specs/002.2-家庭用户前端产品化/docs/`
  - 这一步先不做什么：不额外扩需求。
  - 怎么算完成：
    1. 联调说明齐全
    2. 验收口径清楚
    3. 已知限制明确记录
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` §7.0、§8.0

- [ ] 4.4 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认这套用户前端真的已经成为产品，不是漂亮点的后台。
  - 做完你能看到什么：可以进入持续迭代，而不是回头重做结构。
  - 先依赖什么：4.1、4.2、4.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 和用户前端实现相关文件
  - 这一步先不做什么：不临时加大功能。
  - 怎么算完成：
    1. 首页、家庭、助手、记忆、设置形成产品闭环
    2. 用户端与 `admin-web` 分工稳定
    3. 主题、国际化和长辈模式都在主链路上
  - 怎么验证：
    - `cd apps/user-web && npm.cmd run build`
    - 人工按验收清单走查
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
