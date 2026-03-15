# 任务清单 - Taro 4 统一前端与多端迁移（人话版）

状态：Draft

## 这份文档是干什么的

这不是一份“以后再说”的愿望清单，而是后面真正干活时的施工图。

打开任何一个任务，都应该立刻看明白：

- 这一步到底建什么
- 做完后能看到什么结果
- 依赖什么前提
- 主要动哪些目录
- 这一步故意不做什么
- 怎么判断真的做完了

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已有结果，等待复核
- `DONE`：已完成并回写
- `CANCELLED`：明确取消

规则：

- 只有 `状态：DONE` 的任务才能打勾为 `[x]`
- 任务状态必须实时回写，不允许攒着最后一次性补
- 卡住了就写清楚卡在哪里，别装死

## 阶段 1：先把新主线和共享边界立起来

- [x] 1.1 新建 `apps/user-app` 的 Taro 4 + React 主应用骨架
  - 状态：DONE
  - 当前结果：`apps/user-app` 已从根 workspace 的安装边界里独立出来，并生成了自己的 `package-lock.json`；根脚本已改成通过 `npm --prefix ./apps/user-app` 从仓库根调用；当前轮已确认 `npm run typecheck:user-app`、`npm run build:user-app:h5`、`npm run build:user-app:ios`、`npm run build:user-app:android` 以及 `apps/user-web` 的生产构建都能通过，说明 H5 与 RN 主线和根入口脚本都已经恢复到可用状态；`Harmony` 侧则保留了 `harmony_cpp` 构建脚本、Taro 配置和环境变量接入口，后续有真实外部工程时可以继续接上。
  - 这一步到底做什么：在 workspace 里正式建立新的 Taro 主应用，补齐 H5、RN、Harmony 的基础配置和构建脚本。
  - 做完你能看到什么：仓库里出现新的 `apps/user-app`，并且能按平台目标独立构建。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2
    - `design.md` 2.1、2.3
  - 主要改哪里：
    - `apps/user-app/`
    - 根目录 `package.json`
    - 后续需要的 Taro 配置文件
  - 这一步先不做什么：先不迁业务页面，先把新应用壳搭起来。
  - 怎么算完成：
    1. `apps/user-app` 目录可独立安装，并能从仓库根触发类型检查和主平台构建
    2. H5、iOS、Android 目标构建可用，`Harmony` 至少保留明确脚本入口和配置接点
  - 怎么验证：
    - 执行 `npm run typecheck:user-app`
    - 执行 `npm run build:user-app:h5`
    - 执行 `npm run build:user-app:ios`
    - 执行 `npm run build:user-app:android`
    - 执行 `npm run build:user-app:harmony`，确认在缺少外部工程时返回明确的 `harmony.projectPath` 配置提示
    - 人工检查目录和配置文件
  - 对应需求：`requirements.md` 需求 1、需求 2
  - 对应设计：`design.md` 2.1、2.3、3.3.5

- [x] 1.2 建立共享包和平台适配包的目录边界
  - 状态：DONE
  - 当前结果：`packages/user-core`、`packages/user-platform`、`packages/user-ui`、`packages/user-testing` 已建立完成；`user-app` 已通过 workspace 依赖接入这些共享包。
  - 这一步到底做什么：创建 `user-core`、`user-platform`、`user-ui`、`user-testing` 这些共享包，把未来的公共逻辑先收口。
  - 做完你能看到什么：后面迁页面时，有固定地方放共享逻辑，不会再把所有代码塞回应用目录。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 8
    - `design.md` 2.1、2.2
  - 主要改哪里：
    - `packages/user-core/`
    - `packages/user-platform/`
    - `packages/user-ui/`
    - `packages/user-testing/`
  - 这一步先不做什么：先不追求所有模块都填满，先把边界立住。
  - 怎么算完成：
    1. 共享包可以被 `user-app` 引用
    2. 目录职责写清楚，没有功能归属模糊区
  - 怎么验证：
    - workspace 引用验证
    - 人工检查目录职责
  - 对应需求：`requirements.md` 需求 3、需求 8
  - 对应设计：`design.md` 2.1、2.2、3.4

### 阶段检查

- [x] 1.3 阶段检查：新主线是不是已经站住了
  - 状态：DONE
  - 当前结果：新主线目录、共享包边界、`user-app` 独立安装边界、H5 构建链和 RN 构建链都已经真实存在，不再是纸面结构；从仓库根触发的 `user-app` 类型检查、H5 构建、iOS/Android 构建以及 `user-web` 生产构建都已重新打通；`user-web` 侧也已移除对新共享运行时的直接耦合，重新回到兼容维护边界；`Harmony` 现阶段不强行启动适配，但已保留后续接入所需的脚本入口和配置接点。
  - 这一步到底做什么：确认新应用和共享包已经成为真实存在的主线，而不是 PPT 架构。
  - 做完你能看到什么：后面迁业务时，不需要再为目录、脚手架、构建目标重新返工。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：当前 Spec 相关文档和新建目录
  - 这一步先不做什么：不开始搬业务页面。
  - 怎么算完成：
    1. 新应用壳和共享包边界清楚
    2. H5 与 RN 主线已可验证，`Harmony` 构建入口和接入位已保留
  - 怎么验证：
    - 人工走查
    - `user-app` 类型检查、H5 构建、iOS/Android 构建验证
    - `user-web` 生产构建验证
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 8
  - 对应设计：`design.md` 2.1、2.2、2.3

## 阶段 2：把 user-web 可复用的业务层抽干净

- [x] 2.1 抽离共享类型、API client 和领域模型
  - 状态：DONE
  - 当前结果：已把首页、家庭、设置迁移会用到的核心领域模型和 API client 抽到 `user-core`，覆盖认证、家庭、地区、房间、成员、关系、设备、上下文、提醒和 locale；`user-web` 的 `api.ts` 已改为直接复用共享 request client 和核心 API，`lib/types.ts` 里的房间/家庭/设置相关类型也已改为回收共享定义。
  - 这一步到底做什么：把 `user-web` 里的 `types`、`api`、通用 schema 和领域模型移到 `user-core`。
  - 做完你能看到什么：页面迁移时不需要重复抄接口和类型。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 4、需求 8
    - `design.md` 2.2、3.1、3.2
    - `apps/user-web/src/lib/`
  - 主要改哪里：
    - `packages/user-core/`
    - `apps/user-web/src/lib/`
    - `apps/user-app/`
  - 这一步先不做什么：先不碰平台 API 和页面 UI。
  - 怎么算完成：
    1. 共享类型和 API 能被新旧前端同时消费
    2. 旧页面里重复定义明显减少
  - 怎么验证：
    - 类型检查
    - 新旧两端引用验证
  - 对应需求：`requirements.md` 需求 4、需求 8
  - 对应设计：`design.md` 2.2、3.1、3.2

- [x] 2.2 抽离认证、家庭、主题、语言和实时状态模型
  - 状态：DONE
  - 当前结果：认证清理、家庭摘要、setup 读取、主题偏好、语言偏好与 locale 解析都已进入 `user-core`；实时协议校验、URL 构造和浏览器 websocket client 已进入 `user-platform/realtime`；`user-web` 现已通过兼容桥接消费共享 auth / household / setup helper，通过共享规则消费 theme / locale，并把实时协议切到平台适配层；`user-app` 设置页已直接消费共享主题和语言偏好。
  - 这一步到底做什么：把 `user-web` 里真正属于业务状态的部分抽到共享层，把只属于浏览器的部分剥掉。
  - 做完你能看到什么：登录、家庭切换、主题、语言、实时会话这些逻辑能在新应用里复用。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 4、需求 8
    - `design.md` 2.2、4.1、4.2
    - `apps/user-web/src/state/`
    - `apps/user-web/src/i18n/`
    - `apps/user-web/src/theme/`
  - 主要改哪里：
    - `packages/user-core/state/`
    - `packages/user-ui/`
    - `apps/user-web/src/state/`
    - `apps/user-app/`
  - 这一步先不做什么：先不处理权限、通知、文件等平台能力。
  - 怎么算完成：
    1. 共享状态不再直接依赖浏览器 API
    2. 新应用能消费这些状态模型
  - 怎么验证：
    - 状态层单元测试
    - 新应用集成验证
  - 对应需求：`requirements.md` 需求 3、需求 4、需求 8
  - 对应设计：`design.md` 2.2、4.1、4.2、6.1

- [x] 2.3 建立功能对齐清单并冻结 user-web 的功能入口范围
  - 状态：DONE
  - 当前结果：`packages/user-testing` 对齐 registry 已补到页面入口 + 共享层落点两个维度，细到认证 helper、主题偏好、语言偏好、实时协议、首页/家庭/设置共享模型这些子功能；`docs/20260315-user-web功能对齐清单初稿.md` 已同步更新；冻结规则继续生效，`user-web` 仍处于“只修不增”。
  - 这一步到底做什么：把 `user-web` 现有功能全部列出来，标明哪些必须迁、哪些可以丢、哪些已经迁、哪些还堵着。
  - 做完你能看到什么：后面不会再靠脑子记迁移进度，也不会删着删着才发现漏功能。
  - 先依赖什么：2.2
  - 开始前先看：
    - `requirements.md` 需求 4、需求 6、需求 7
    - `design.md` 2.6、2.7、3.3.3、4.2
    - `apps/user-web/src/pages/`
  - 主要改哪里：
    - `specs/011-.../docs/`
    - `packages/user-testing/`
    - `tasks.md`
  - 这一步先不做什么：先不切流，不删旧代码。
  - 怎么算完成：
    1. 每条核心功能都有迁移状态
    2. `user-web` 新增功能入口被明确冻结
  - 怎么验证：
    - 人工走查
    - 对齐清单抽样核对
  - 对应需求：`requirements.md` 需求 4、需求 6、需求 7
  - 对应设计：`design.md` 2.6、2.7、3.3.3

### 阶段检查

- [x] 2.4 阶段检查：共享层是不是已经足够支撑迁页面
  - 状态：DONE
  - 当前结果：阶段 2 的退出条件已满足。类型、API、状态、主题、语言、实时都已经有共享落点；旧前端已经开始复用这些共享能力，而不是继续维护一套平行实现；功能对齐清单也已经细化到可指导 3.1 / 3.2 的程度。
  - 这一步到底做什么：确认迁移不是停留在“文件挪了一下”，而是真的把共享逻辑抽出来了。
  - 做完你能看到什么：后面迁页面时，主要是在装页面壳，而不是重新造业务逻辑。
  - 先依赖什么：2.1、2.2、2.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：当前 Spec 和共享层目录
  - 这一步先不做什么：不急着删 `user-web`
  - 怎么算完成：
    1. 类型、API、状态、主题、语言、实时已有共享落点
    2. 功能对齐清单已经可用
  - 怎么验证：
    - `user-app` 类型检查通过
    - `user-web` 类型检查通过
    - `user-app` H5 构建通过
    - `user-web` 生产构建通过
    - 共享层引用走查
  - 对应需求：`requirements.md` 需求 3、需求 4、需求 7、需求 8
  - 对应设计：`design.md` 2.2、2.6、2.7、4.1

## 阶段 3：先让 Taro H5 平替 user-web 核心链路

- [ ] 3.1 建立新应用的主导航壳、认证壳和页面路由
  - 状态：TODO
  - 这一步到底做什么：把登录、初始化向导、主导航壳和基础路由在 `user-app` 里跑起来。
  - 做完你能看到什么：H5 版新应用已经像一个完整产品，而不是只有几个孤立页面。
  - 先依赖什么：2.4
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 4
    - `design.md` 2.5.1、3.1、3.5
  - 主要改哪里：
    - `apps/user-app/src/`
    - `packages/user-ui/`
    - `packages/user-core/state/`
  - 这一步先不做什么：先不迁所有业务页。
  - 怎么算完成：
    1. H5 可以走完应用启动到主壳进入
    2. 基础路由和导航结构稳定
  - 怎么验证：
    - H5 手工回归
    - 启动链路测试
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 4
  - 对应设计：`design.md` 2.5.1、3.1、3.5、4.2.1

- [ ] 3.2 迁首页、家庭、设置三条高频链路
  - 状态：TODO
  - 这一步到底做什么：优先迁最容易暴露结构问题的高频页面，不先碰低频边角功能。
  - 做完你能看到什么：用户常用基础链路在 H5 新应用里已经可用。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 4
    - `design.md` 2.5.2、3.5
    - `apps/user-web/src/pages/HomePage.tsx`
    - `apps/user-web/src/pages/FamilyPage.tsx`
    - `apps/user-web/src/pages/Settings*.tsx`
  - 主要改哪里：
    - `apps/user-app/src/pages/`
    - `packages/user-core/features/`
    - `packages/user-ui/`
  - 这一步先不做什么：先不迁所有设置子页面的边角功能。
  - 怎么算完成：
    1. 首页、家庭、设置在 H5 可用
    2. 数据加载、保存、错误态和空态都能工作
  - 怎么验证：
    - H5 手工回归
    - 高优先级页面回归测试
  - 对应需求：`requirements.md` 需求 4、需求 8
  - 对应设计：`design.md` 2.5.2、3.1、3.5

- [ ] 3.3 迁助手、记忆和其余核心业务链路
  - 状态：TODO
  - 这一步到底做什么：把聊天、记忆、插件相关用户端能力迁到 `user-app`，补齐真正能替换旧前端的主链。
  - 做完你能看到什么：新 H5 不再只是“能看首页”，而是真能用。
  - 先依赖什么：3.2
  - 开始前先看：
    - `requirements.md` 需求 4、需求 5
    - `design.md` 2.5.2、2.5.3、3.3.2
    - `apps/user-web/src/pages/AssistantPage.tsx`
    - `apps/user-web/src/pages/MemoriesPage.tsx`
  - 主要改哪里：
    - `apps/user-app/src/pages/assistant/`
    - `apps/user-app/src/pages/memories/`
    - `packages/user-core/features/assistant/`
    - `packages/user-core/features/memories/`
  - 这一步先不做什么：先不做移动端专有交互优化。
  - 怎么算完成：
    1. 助手和记忆主链在 H5 可用
    2. 实时连接和降级逻辑在新应用里稳定
  - 怎么验证：
    - H5 手工回归
    - 实时链路测试
  - 对应需求：`requirements.md` 需求 4、需求 5
  - 对应设计：`design.md` 2.5.2、2.5.3、3.3.2、5.3

- [ ] 3.4 完成 H5 灰度切流与 user-web 平替验证
  - 状态：TODO
  - 这一步到底做什么：让一部分真实入口切到 `user-app` H5，验证新旧切换不是纸上谈兵。
  - 做完你能看到什么：`user-app` H5 开始接真实流量，`user-web` 退到保底角色。
  - 先依赖什么：3.3
  - 开始前先看：
    - `requirements.md` 需求 4、需求 6、需求 7
    - `design.md` 2.6、2.7、6.2
  - 主要改哪里：
    - H5 发布入口
    - 网关或部署配置
    - 功能对齐清单
  - 这一步先不做什么：先不删旧应用代码。
  - 怎么算完成：
    1. H5 可灰度接流
    2. 回滚路径已验证
    3. `user-web` 进入只保底阶段
  - 怎么验证：
    - 灰度发布验证
    - 回滚演练
  - 对应需求：`requirements.md` 需求 4、需求 6、需求 7
  - 对应设计：`design.md` 2.6、2.7、6.2、6.3

### 阶段检查

- [ ] 3.5 阶段检查：H5 是不是真的可以替 user-web 说话了
  - 状态：TODO
  - 这一步到底做什么：确认 H5 新应用已经不是演示品，而是可以正式接班。
  - 做完你能看到什么：后面做移动端时，不会再被 H5 主线拖回去返工。
  - 先依赖什么：3.1、3.2、3.3、3.4
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - 功能对齐清单
  - 主要改哪里：当前 Spec 文档与对齐清单
  - 这一步先不做什么：不立刻删除 `user-web`
  - 怎么算完成：
    1. H5 核心链路达到退出标准
    2. 灰度和回滚已验证
  - 怎么验证：
    - 核心链路验收
    - 对齐清单复核
  - 对应需求：`requirements.md` 需求 4、需求 6、需求 7
  - 对应设计：`design.md` 2.6、2.7、6.2

## 阶段 4：补齐移动端和鸿蒙的平台能力

- [ ] 4.0 接入外部鸿蒙工程并验证 `harmony_cpp` 构建
  - 状态：BLOCKED
  - 当前结果：当前仓库已经保留 `harmony_cpp` 构建脚本、Taro 配置以及 `HARMONY_PROJECT_PATH` / `HARMONY_HAP_NAME` 接入口；但仓库内还没有可供接入的真实鸿蒙外部工程。
  - 阻塞说明：必须先有可用的鸿蒙工程目录，才能继续验证 `harmony_cpp` 构建和后续平台能力。
  - 这一步到底做什么：把外部鸿蒙工程和 `user-app` 接起来，确认当前预留的构建入口不是摆设。
  - 做完你能看到什么：`user-app` 可以把产物编译到真实鸿蒙工程里，而不是只停留在“脚本存在”。
  - 先依赖什么：3.5
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3
    - `design.md` 2.3、3.3.5、3.4
    - `apps/user-app/config/platform/harmony.ts`
  - 主要改哪里：
    - 外部鸿蒙工程目录
    - `apps/user-app/config/platform/harmony.ts`
    - 根目录脚本与当前 Spec
  - 这一步先不做什么：先不做鸿蒙页面细节适配和平台能力扩展。
  - 怎么算完成：
    1. 已提供真实鸿蒙工程目录并通过环境变量接入
    2. `npm run build:user-app:harmony` 可输出到对应鸿蒙工程
  - 怎么验证：
    - 配置 `HARMONY_PROJECT_PATH`
    - 执行 `npm run build:user-app:harmony`
    - 人工检查鸿蒙工程产物
  - 对应需求：`requirements.md` 需求 2、需求 3
  - 对应设计：`design.md` 2.3、3.3.5、3.4

- [ ] 4.1 落地统一存储、深链、分享和实时连接适配层
  - 状态：TODO
  - 这一步到底做什么：把最容易在多端炸开的基础平台能力先统一。
  - 做完你能看到什么：页面不再需要知道自己运行在 H5、RN 还是 Harmony。
  - 先依赖什么：3.5
  - 开始前先看：
    - `requirements.md` 需求 3、需求 5
    - `design.md` 3.3.2、3.4、4.3、6.1
  - 主要改哪里：
    - `packages/user-platform/`
    - `apps/user-app/`
  - 这一步先不做什么：先不做权限弹窗和推送 token。
  - 怎么算完成：
    1. 存储、深链、分享、实时连接走统一接口
    2. H5、RN、Harmony 都有对应实现或明确降级
  - 怎么验证：
    - 适配层单元测试
    - 多平台集成验证
  - 对应需求：`requirements.md` 需求 3、需求 5
  - 对应设计：`design.md` 3.3.2、3.4、4.3、6.1

- [ ] 4.2 落地权限、文件、相机和上传能力
  - 状态：TODO
  - 这一步到底做什么：把通知之外最容易产生平台差异的权限与文件能力统一起来。
  - 做完你能看到什么：页面可以在不同平台上可靠地申请权限、选文件、拍照和上传。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 5
    - `design.md` 2.5.3、3.2.2、3.3.2
  - 主要改哪里：
    - `packages/user-platform/permissions/`
    - `packages/user-platform/files/`
    - `apps/user-app/src/pages/settings/`
  - 这一步先不做什么：先不做所有边角媒体能力。
  - 怎么算完成：
    1. 权限状态统一
    2. 文件选择和拍照在目标平台可用或有明确降级
  - 怎么验证：
    - 真机验证
    - 权限状态回归测试
  - 对应需求：`requirements.md` 需求 3、需求 5
  - 对应设计：`design.md` 2.5.3、3.2.2、5.3

- [ ] 4.3 落地通知注册、通知偏好和通知跳转
  - 状态：TODO
  - 这一步到底做什么：把用户最关心的提醒能力正式接到多端上，而不是继续留占位页。
  - 做完你能看到什么：用户可以在不同平台上看到真实通知能力，而不是假开关。
  - 先依赖什么：4.2
  - 开始前先看：
    - `requirements.md` 需求 5
    - `design.md` 3.2.3、3.3.4、5.3
    - 当前通知相关后端接口
  - 主要改哪里：
    - `packages/user-platform/notifications/`
    - `packages/user-core/features/settings/`
    - `apps/user-app/src/pages/settings/notifications/`
    - `apps/api-server/` 相关接口
  - 这一步先不做什么：先不做复杂营销推送。
  - 怎么算完成：
    1. 通知 token 可注册和注销
    2. 通知偏好有统一模型
    3. 通知点击可回到应用内正确页面
  - 怎么验证：
    - 真机通知联调
    - 偏好写回验证
  - 对应需求：`requirements.md` 需求 5
  - 对应设计：`design.md` 3.2.3、3.3.4、5.3

- [ ] 4.4 做移动端和鸿蒙的导航、布局与安全区适配
  - 状态：TODO
  - 这一步到底做什么：把页面在手机上真正做得能用，而不是简单缩窄网页。
  - 做完你能看到什么：iOS、Android、鸿蒙上的导航、底部栏、安全区、键盘顶起和手势行为稳定可用。
  - 先依赖什么：4.3
  - 开始前先看：
    - `requirements.md` 需求 2、需求 5
    - `design.md` 2.3、3.4、3.5
  - 主要改哪里：
    - `apps/user-app/src/layouts/`
    - `packages/user-ui/`
    - 各平台样式与平台文件
  - 这一步先不做什么：先不追求每个平台都长得完全一样。
  - 怎么算完成：
    1. 主要页面在三种移动目标上可用
    2. 安全区和导航行为稳定
  - 怎么验证：
    - 真机手工回归
    - 关键页面截图对比
  - 对应需求：`requirements.md` 需求 2、需求 5
  - 对应设计：`design.md` 2.3、3.4、3.5

### 阶段检查

- [ ] 4.5 阶段检查：平台能力是不是已经真正收口
  - 状态：TODO
  - 这一步到底做什么：确认通知、权限、文件、分享、深链、存储、实时这些东西没有重新漏回页面层。
  - 做完你能看到什么：平台差异已经主要待在适配层，而不是业务页面里到处冒头。
  - 先依赖什么：4.0、4.1、4.2、4.3、4.4
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：适配层、页面层和当前 Spec
  - 这一步先不做什么：不提前宣布移动端可正式发布。
  - 怎么算完成：
    1. 页面层直连平台 API 的场景被清掉
    2. 平台能力失败时有统一降级
  - 怎么验证：
    - 代码审查
    - 多平台能力回归测试
  - 对应需求：`requirements.md` 需求 3、需求 5、需求 8
  - 对应设计：`design.md` 3.3.2、3.4、5.3、6.1

## 阶段 5：多端发布、切流和 user-web 下线

- [ ] 5.1 建立四个平台的 CI/CD、环境矩阵和版本管理
  - 状态：TODO
  - 这一步到底做什么：把 H5、iOS、Android、鸿蒙的构建、环境变量、版本号和发布动作全部收口。
  - 做完你能看到什么：多端发布不是靠手工拼命令，而是有固定流水线。
  - 先依赖什么：4.5
  - 开始前先看：
    - `requirements.md` 需求 2、需求 6
    - `design.md` 3.3.5、5.3
  - 主要改哪里：
    - CI 配置
    - 根目录脚本
    - `apps/user-app` 平台配置
  - 这一步先不做什么：先不追求自动化商店提审全覆盖。
  - 怎么算完成：
    1. 四个平台都有明确构建流水线
    2. 环境和版本管理不互相污染
  - 怎么验证：
    - 流水线演练
    - 产物检查
  - 对应需求：`requirements.md` 需求 2、需求 6
  - 对应设计：`design.md` 2.3、3.3.5、5.3

- [ ] 5.2 做完整灰度、回滚和验收演练
  - 状态：TODO
  - 这一步到底做什么：在正式宣布新前端接班前，把最容易出事故的切流和回滚先演练一遍。
  - 做完你能看到什么：出问题时知道怎么退，不会现场瞎改。
  - 先依赖什么：5.1
  - 开始前先看：
    - `requirements.md` 需求 6
    - `design.md` 2.6、2.7、5.3
    - 功能对齐清单
  - 主要改哪里：
    - 发布配置
    - 灰度开关
    - 运维文档
  - 这一步先不做什么：先不删旧代码。
  - 怎么算完成：
    1. 灰度切流跑通过
    2. 回滚路径跑通过
    3. 验收结果有文档记录
  - 怎么验证：
    - 预发演练
    - 人工验收
  - 对应需求：`requirements.md` 需求 6
  - 对应设计：`design.md` 2.6、2.7、6.2

- [ ] 5.3 正式下线 user-web 并清理仓库残留
  - 状态：TODO
  - 这一步到底做什么：在退出条件满足后，正式把 `user-web` 从主线里移除，而不是继续挂着吃维护成本。
  - 做完你能看到什么：仓库里只剩一条用户前端主线，没有真假主应用之分。
  - 先依赖什么：5.2
  - 开始前先看：
    - `requirements.md` 需求 1、需求 6、需求 7
    - `design.md` 2.7、6.2、6.3
    - 功能对齐清单
  - 主要改哪里：
    - `apps/user-web/`
    - 根目录 workspace 配置
    - 发布入口与项目文档
  - 这一步先不做什么：不在退出条件不满足时强删旧应用。
  - 怎么算完成：
    1. `user-web` 已不再承接流量
    2. 仓库里旧前端被正式移除或归档
    3. 文档和脚本都只指向新主线
  - 怎么验证：
    - 入口检查
    - 仓库结构检查
    - 回滚关闭确认
  - 对应需求：`requirements.md` 需求 1、需求 6、需求 7
  - 对应设计：`design.md` 2.7、6.2、6.3

### 最终检查

- [ ] 5.4 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认这次迁移不是“新应用能跑了”，而是真的完成了主线切换。
  - 做完你能看到什么：PC 和移动多端都走同一条正式前端主线，`user-web` 不再是历史包袱。
  - 先依赖什么：5.1、5.2、5.3
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 相关全部文档和发布记录
  - 这一步先不做什么：不再扩新范围。
  - 怎么算完成：
    1. 多端主线切换完成
    2. 功能对齐、灰度、回滚、下线都有证据
    3. 后续团队不会再把需求写回旧前端
  - 怎么验证：
    - 按 Spec 验收清单逐项核对
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
