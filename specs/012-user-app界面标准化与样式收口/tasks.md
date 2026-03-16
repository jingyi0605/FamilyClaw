# 任务清单 - user-app界面标准化与样式收口（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单不是为了摆格式，是为了让后面真正开始改 `user-app` 时，不会一会儿改 token，一会儿改页面，一会儿又回头补基础组件，最后什么都没收口。

这里要回答清楚：

- 先做什么
- 后做什么
- 主要改哪里
- 这一步明确不做什么
- 怎么判断这一步真的完成了

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：不做了，但必须写明原因

规则：

- 只有 `状态：DONE` 的任务才能勾成 `[x]`
- 每完成一个任务，必须立刻更新这里
- 如果范围变了，先改任务，再继续写代码

---

## 阶段 1：先把标准源和基础规则立起来

- [x] 1.1 盘点现有 token、单位体系和硬编码样式，明确唯一标准源
  - 状态：DONE
  - 这一 step 到底做什么：把 `user-app` 现有 H5 token、`user-ui` token、`designWidth`、Taro H5 尺寸换算方式、手写 `rem` 和高频硬编码样式一起清点，定出以后到底以哪套为准。
  - 做完你能看到什么：团队不再争论“应该跟 `ThemeProvider` 走还是跟 `user-ui` 走”“这里该写 `rem` 还是 `px`”，文档里有明确答案。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1、需求 5、需求 7
    - `design.md` 2.2、2.4、3.1、3.5
    - `apps/user-app/src/runtime/h5-shell/theme/tokens.ts`
    - `packages/user-ui/src/theme/tokens.ts`
    - `apps/user-app/config/index.ts`
  - 主要改哪里：
    - `packages/user-ui/src/theme/`
    - `apps/user-app/src/runtime/h5-shell/theme/`
    - `apps/user-app/config/`
    - `specs/012-user-app界面标准化与样式收口/`
  - 这一 step 先不做什么：先不改业务页面，不先追求视觉焕新。
  - 怎么算完成：
    1. 唯一标准源和兼容映射方式写清楚
    2. `designWidth` 和单位体系边界写清楚
    3. token 分层和命名规则落到共享层目录结构
  - 怎么验证：
    - 人工走查文档和目录结构
    - 参考 `docs/20260316-user-app现状样式审计清单.md`
    - 参考 `docs/20260316-H5单位策略与designWidth边界.md`
  - 本轮结果（2026-03-16）：
    1. 已补充手写 `rem` 热点清单，确认 `runtime/h5-shell/styles/index.h5.scss`、`pages/setup/index.h5.scss`、`pages/home/index.h5.scss`、`pages/setup/WelcomeStep.css` 是当前主要集中区。
    2. 已补充 JSX/TS 行内固定尺寸清单，确认 `AppUi.tsx`、`AuthShellPage.tsx`、`MainShellPage.tsx`、`AppShellPage.tsx`、`runtime/guard.tsx`、`setup/index.h5.tsx` 仍在继续走固定像素链路。
    3. 已补充 token 来源审计，确认当前实际存在三套来源：`packages/user-ui/src/theme/tokens.ts` 的薄 token、`apps/user-app/src/runtime/h5-shell/theme/tokens.ts` 的完整主题 token、`apps/user-app/src/pages/login/theme-presets.ts` 的登录页 preset。
    4. 已把职责边界写清楚：`packages/user-ui` 作为唯一上游标准源，`apps/user-app/src/runtime/h5-shell/theme` 只保留 H5 主题选择和 CSS 变量映射职责，不再作为 canonical token 定义位置。
  - 对应需求：`requirements.md` 需求 1、需求 5、需求 7
  - 对应设计：`design.md` 2.2、2.3、2.4、3.1、3.5

- [x] 1.2 建立共享 token 分层，并把 H5 变量映射和单位策略一起收口
  - 状态：DONE
  - 这一 step 到底做什么：把设计 token、语义 token、H5 变量映射和 H5 单位规则接起来，让共享层真正变成上游。
  - 做完你能看到什么：H5 壳层不再偷偷维护另一套值，页面也不再混着三套尺寸语义写样式。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 5、需求 6
    - `design.md` 3.1、3.2、3.4、3.5
    - `apps/user-app/src/runtime/h5-shell/theme/ThemeProvider.tsx`
  - 主要改哪里：
    - `packages/user-ui/src/theme/`
    - `apps/user-app/src/runtime/h5-shell/theme/tokens.ts`
    - `apps/user-app/src/runtime/h5-shell/theme/ThemeProvider.tsx`
    - 视情况补 `apps/user-app/config/` 中的说明或配置
  - 这一 step 先不做什么：先不批量替换页面里的旧样式。
  - 怎么算完成：
    1. 共享 token 有清楚的导出入口
    2. H5 变量注入继续可用
    3. 行内样式、样式文件和 token 的单位规则写清楚
    4. 现有主题切换没有被打坏
  - 怎么验证：
    - 类型检查
    - 手工检查主题切换
    - 人工检查单位策略说明
  - 本轮结果（2026-03-16）：
    1. `packages/user-ui/src/theme/themes.ts` 已承接完整主题定义和 CSS 变量映射 helper，完整主题值不再只留在 H5 私有目录。
    2. `packages/user-ui/src/theme/tokens.ts` 已拆出 foundation token、semantic token、component token，并保留 `userAppTokens` 兼容出口，避免第一轮就打碎现有页面。
    3. `apps/user-app/src/runtime/h5-shell/theme/ThemeProvider.tsx` 已改为消费共享主题定义和共享 CSS 变量映射，不再手写一份 H5 专属变量表。
    4. `apps/user-app/src/runtime/h5-shell/theme/tokens.ts` 已降级为兼容导出层，H5 主题层只保留适配职责。
    5. `apps/user-app/src/pages/login/theme-presets.ts` 已改为从共享主题派生，第三套登录页 preset 不再手抄 token 值。
    6. `packages/user-ui/src/components/PageSection.tsx` 与 `packages/user-ui/src/components/StatusCard.tsx` 已改为消费 component token，开始建立共享组件变体链路。
  - 本轮验证补充：
    - 已对本轮改动文件执行定向 TypeScript 编译，改动链路本身通过。
    - 1.2 落地当时，全量 `npm.cmd --prefix apps/user-app run typecheck` 曾被仓库已有的 `apps/user-app/src/pages/family/LegacyFamilyPage.tsx` 语法错误阻断；当前最新全量验证结果以任务 2.2 的验证补充为准。
  - 对应需求：`requirements.md` 需求 1、需求 5、需求 6
  - 对应设计：`design.md` 2.3、2.4、3.1、3.4、3.5、7

- [x] 1.3 阶段检查：确认样式标准已经收口到共享层
  - 状态：DONE
  - 这一 step 到底做什么：只检查底座，不急着扩范围。
  - 做完你能看到什么：后面开始改组件时，不会发现底层变量还在打架。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段相关共享层文件
  - 这一 step 先不做什么：不新增页面迁移工作。
  - 怎么算完成：
    1. 共享层成为正式上游
    2. H5 运行时只是映射层，不再是标准源
    3. `designWidth` 和单位使用规则不再处于口口相传状态
  - 怎么验证：
    - 人工走查
  - 本轮结果（2026-03-16）：
    1. 已把 H5 主题变量写入动作收口到 `apps/user-app/src/runtime/h5-shell/theme/applyThemeDocument.ts`，`ThemeProvider.tsx` 与登录页不再各自展开 `document.documentElement.style`。
    2. 已确认 `packages/user-ui/src/theme/themes.ts` 继续持有完整主题值、主题列表和 CSS 变量映射；`apps/user-app/src/runtime/h5-shell/theme/tokens.ts` 只剩兼容导出职责，没有再回流成标准源。
    3. 已把 `apps/user-app/src/pages/login/theme-presets.ts` 降成登录页主题元数据投影，不再缓存一份 preset 变量表，也不再单独承担 DOM 注入职责。
    4. 已在 `design.md` 补清边界：共享层负责 canonical theme，H5 运行时只保留主题状态与 DOM 映射入口，页面层不能再复制 preset 或变量注入逻辑。
    5. 已修正 `packages/user-ui/package.json` 的运行时入口，改为直接指向 `src/index.ts`；避免 H5 运行时继续吃陈旧 `dist/index.js`，导致 `userAppThemes` 在前端变成 `undefined`。
    6. 已把 `packages/user-ui/src/index.ts` 中 H5 构建链路不兼容的 `export { ..., type X } from ...` 改成独立 `export type`，避免 webpack 在源码入口上直接报语法错误。
    7. 进一步移除了 `packages/user-ui/src/index.ts` 的根入口类型导出，把 `ThemeProvider`、`theme-presets.ts`、H5 `tokens.ts` 改成从共享值推导类型，规避当前 H5 webpack 链路对根入口 `export type` 的解析缺陷。
    8. 已确认真正缺口在 `apps/user-app` 的 H5 webpack 转译规则：工作区包源码没有通过 `compile.include` 进入 Babel/TS 链路。现已改为把 `packages/user-core`、`packages/user-platform`、`packages/user-testing`、`packages/user-ui` 统一纳入 `compile.include`，并把 H5 别名明确指向源码入口，不再依赖 `dist/*.js`。
    9. 已补齐 `@familyclaw/user-platform/web` 的源码别名，避免 H5 页面在切到工作区源码入口后找不到 web 子路径。
    10. 已清理 `apps/user-app/config/index.ts` 里的残留合并冲突标记，并显式增加 `workspaceScript` Babel 规则，让工作区包源码即使不依赖 `dist/*.js` 也能稳定走 TS/Babel 转译。
  - 对应需求：`requirements.md` 需求 1、需求 5、需求 6、需求 7
  - 对应设计：`design.md` 2.2、2.3、2.4、3.4、3.5

---

## 阶段 2：把高频基础组件和公共组合件收口

- [x] 2.1 在 `packages/user-ui` 里补齐高频基础组件和变体
  - 状态：DONE
  - 这一 step 到底做什么：把按钮、卡片、输入框、文本、标签、字段这些高频基础件补齐，别再让页面自己拼。
  - 做完你能看到什么：新页面实现常见 UI 时，有正式的共享组件可用。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 2、需求 4
    - `design.md` 4.1、4.2、4.3
    - `packages/user-ui/src/components/`
    - `apps/user-app/src/components/AppUi.tsx`
  - 主要改哪里：
    - `packages/user-ui/src/components/`
    - `packages/user-ui/src/index.ts`
    - 视情况调整 `packages/user-ui/src/theme/`
  - 这一 step 先不做什么：先不碰大型历史页面。
  - 怎么算完成：
    1. 高复用基础件有稳定导出
    2. 常见变体不再需要页面自己重复写样式
  - 怎么验证：
    - 组件渲染测试
    - 类型检查
  - 本轮结果（2026-03-16）：
    1. 已在 `packages/user-ui/src/components/` 新增 `UiText`、`UiButton`、`UiInput`、`UiCard`、`UiTag`、`FormField`、`EmptyStateCard`，并通过 `packages/user-ui/src/index.ts` 给出稳定导出入口。
    2. 已把 `packages/user-ui/src/theme/tokens.ts` 补齐文本、按钮、输入框、卡片、标签、字段、空态的 component token 变体，页面不必再手写同一套字号、圆角和边框。
    3. 已让 `PageSection`、`StatusCard` 改为消费新的共享基础件，而不是继续各自拼一套卡片和文本样式。
  - 对应需求：`requirements.md` 需求 2、需求 4
  - 对应设计：`design.md` 4.1、4.2、4.3

- [x] 2.2 把 `AppUi.tsx` 的通用能力归并进共享层
  - 状态：DONE
  - 这一 step 到底做什么：把现在散在 `AppUi.tsx` 里的通用组件收口成正式共享件，避免同仓库两套基础组件并行生长。
  - 做完你能看到什么：`AppUi.tsx` 变成薄兼容层或直接被替换，团队知道以后该从哪里拿基础件。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 7
    - `design.md` 4.4
    - `apps/user-app/src/components/AppUi.tsx`
  - 主要改哪里：
    - `apps/user-app/src/components/AppUi.tsx`
    - `packages/user-ui/src/components/`
    - `packages/user-ui/src/index.ts`
  - 这一 step 先不做什么：先不要求业务页一夜之间全部切完。
  - 怎么算完成：
    1. 通用组件不再分裂在两个入口
    2. 迁移入口清楚，旧入口只剩兼容职责
  - 怎么验证：
    - 人工走查导入路径
    - 类型检查
  - 本轮结果（2026-03-16）：
    1. `apps/user-app/src/components/AppUi.tsx` 已降成兼容层，`SectionNote`、`FormField`、`TextInput`、`PrimaryButton`、`SecondaryButton`、`EmptyStateCard` 优先包装共享基础件，不再自己维护完整视觉实现。
    2. `AuthShellPage.tsx`、`MainShellPage.tsx` 已开始直接消费 `UiButton`、`UiCard`、`UiText`，壳层里的固定字号和按钮样式不再各写一套。
    3. 这一步只收公共件和壳层，不碰 `home`、`setup`、`assistant` 等重页面，保持兼容迁移顺序不失控。
  - 本轮验证补充：
    - 已重新执行 `npm.cmd --prefix apps/user-app run typecheck`，当前全量通过。
  - 对应需求：`requirements.md` 需求 2、需求 7
  - 对应设计：`design.md` 4.1、4.4

- [ ] 2.3 阶段检查：确认共享基础件已经能支撑页面迁移
  - 状态：TODO
  - 这一 step 到底做什么：检查共享层是不是已经够用，别一边迁页面一边再回头补基础轮子。
  - 做完你能看到什么：后面的页面迁移有稳定底座，不会改三页就发现基础件不够。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段相关共享组件文件
  - 这一 step 先不做什么：不新增更多组件类别。
  - 怎么算完成：
    1. 第一批基础件和变体够支撑高频页面
    2. 重复样式模式已经能被共享件覆盖
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 4
  - 对应设计：`design.md` 4、5.1

---

## 阶段 3：按优先级迁移公共页面和业务页面

- [ ] 3.1 迁移公共壳层和高频公共区块
  - 状态：TODO
  - 这一 step 到底做什么：先把所有页面都会经过的壳层、导航、区块标题、状态卡片和表单区块改到统一标准上。
  - 做完你能看到什么：哪怕业务页没全改完，整体页面基线已经统一，不会继续从壳层开始长歪。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 3、需求 6
    - `design.md` 5.1、5.2
    - `apps/user-app/src/components/AppShellPage.tsx`
    - `apps/user-app/src/components/AuthShellPage.tsx`
    - `apps/user-app/src/components/MainShellPage.tsx`
  - 主要改哪里：
    - `apps/user-app/src/components/`
    - `apps/user-app/src/pages/home/`
    - `apps/user-app/src/pages/login/`
  - 这一 step 先不做什么：先不碰历史最重的大页面。
  - 怎么算完成：
    1. 壳层、区块标题、按钮和卡片视觉明显统一
    2. 公共区块不再重复写同一类样式
  - 怎么验证：
    - 类型检查
    - 手工验收首页、登录页、主要壳层
  - 对应需求：`requirements.md` 需求 3、需求 6
  - 对应设计：`design.md` 5.1、5.2、7

- [ ] 3.2 分批迁移设置页和其他高频业务页面
  - 状态：TODO
  - 这一 step 到底做什么：用共享基础件和 token 分批替换高频页面里的散装样式，把重复实现收掉。
  - 做完你能看到什么：高频业务页不再各长各的，后续新功能也更容易接着写。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 3、需求 4、需求 5
    - `design.md` 3.5、5.1、5.2、5.3
    - `apps/user-app/src/pages/settings/`
    - `apps/user-app/src/pages/setup/`
    - `apps/user-app/src/pages/assistant/`
  - 主要改哪里：
    - `apps/user-app/src/pages/settings/`
    - `apps/user-app/src/pages/setup/`
    - `apps/user-app/src/pages/assistant/`
    - 视情况补 `packages/user-ui/src/components/`
  - 这一 step 先不做什么：先不全面重构 `LegacyFamilyPage.tsx` 这类大历史页面。
  - 怎么算完成：
    1. 高复用业务区块吃到统一标准
    2. 页面中的典型硬编码样式显著减少
    3. 手写 `rem` 和行内固定尺寸在第一批迁移页中显著减少
  - 怎么验证：
    - 类型检查
    - 手工验收设置页和高频业务页
  - 对应需求：`requirements.md` 需求 3、需求 4、需求 5
  - 对应设计：`design.md` 3.5、5.1、5.2、5.3

- [ ] 3.3 阶段检查：确认第一轮页面迁移已经形成新基线
  - 状态：TODO
  - 这一 step 到底做什么：检查这次迁移是不是已经把公共规则立住了，而不是只改了几页截图。
  - 做完你能看到什么：团队后续新增页面时，默认会站在新标准上，而不是回到老路。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段相关页面和共享组件
  - 这一 step 先不做什么：不在这一步追求全量历史清债。
  - 怎么算完成：
    1. 公共页面基线已经统一
    2. 剩余未迁移区域有明确名单和后续顺序
  - 怎么验证：
    - 人工走查
  - 对应需求：`requirements.md` 需求 3、需求 7
  - 对应设计：`design.md` 5、8

---

## 阶段 4：补规则、检查和交接文档

- [ ] 4.1 加入阻止新增散装样式的检查规则
  - 状态：TODO
  - 这一 step 到底做什么：把“不要再写硬编码样式”从口头要求变成能执行的检查点。
  - 做完你能看到什么：后续 PR 不容易再把仓库带回老路。
  - 先依赖什么：3.3
  - 开始前先看：
    - `requirements.md` 需求 4、需求 5
    - `design.md` 3.5、6.1、6.2、6.3
  - 主要改哪里：
    - `apps/user-app/` 下相关配置或检查脚本
    - 视情况补充共享层使用说明
  - 这一 step 先不做什么：先不追求覆盖所有边缘例外。
  - 怎么算完成：
    1. 有最小可执行的规则或脚本
    2. 团队知道哪些写法现在不允许再新增
    3. 至少能拦住新增手写 `rem` 和新增行内固定尺寸两类高频问题
  - 怎么验证：
    - 运行检查脚本
    - 人工构造典型违规样式验证
  - 对应需求：`requirements.md` 需求 4、需求 5
  - 对应设计：`design.md` 3.5、6.1、6.2、6.3

- [ ] 4.2 补充 token 对照表、迁移清单和验收说明
  - 状态：TODO
  - 这一 step 到底做什么：把“现有 token 对应什么、哪些页面已迁移、哪些还没迁、`designWidth` 和单位规则怎么用”写进补充文档，方便后续接手。
  - 做完你能看到什么：不是只有代码改了，接手的人也知道怎么看、怎么继续、怎么避免再踩单位坑。
  - 先依赖什么：4.1
  - 开始前先看：
    - `requirements.md` 需求 5、需求 7
    - `design.md` 8
    - `docs/README.md`
  - 主要改哪里：
    - `specs/012-user-app界面标准化与样式收口/docs/`
  - 这一 step 先不做什么：不新增新的实施范围。
  - 怎么算完成：
    1. token 对照表清楚
    2. 页面迁移清单清楚
    3. 单位策略清楚
    4. 验收口径清楚
  - 怎么验证：
    - 人工走查文档
  - 对应需求：`requirements.md` 需求 5、需求 7
  - 对应设计：`design.md` 7、8

- [ ] 4.3 最终检查点
  - 状态：TODO
  - 这一 step 到底做什么：确认这份 Spec 真能指导完整落地，而不是只停在“方向正确”的空话上。
  - 做完你能看到什么：需求、设计、任务、补充文档能一一对上，后面谁接着做都知道怎么推进。
  - 先依赖什么：4.1、4.2
  - 开始前先看：
    - `README.md`
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文档
  - 这一 step 先不做什么：不临时加新范围。
  - 怎么算完成：
    1. 任务顺序清楚
    2. 关键风险写明
    3. 剩余边界写明
  - 怎么验证：
    - 按 Spec 清单人工复核
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
