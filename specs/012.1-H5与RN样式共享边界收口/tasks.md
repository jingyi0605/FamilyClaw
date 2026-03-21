# 任务清单 - H5与RN样式共享边界收口（人话版）

状态：Done

## 这份文档是干什么的

这份任务清单不是拿来堆术语的，是拿来告诉后面接手的人：

- 先把共享边界立起来。
- 再把平台适配层切干净。
- 然后拿高频页面试点。
- 最后用检查和文档把规则钉死。

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已有结果，等复核
- `DONE`：已完成并回写状态
- `CANCELLED`：取消，不做了，但必须写原因

---

## 阶段 1：先把共享契约和平台边界写死

- [x] 1.1 盘清当前 H5、RN 和共享主题层的真实职责
  - 状态：DONE
  - 这一阶段到底做什么：把现有 `themeRuntime`、`H5 ThemeProvider`、`RN tokens`、页面样式入口逐个盘清，确认哪些已经是共享层，哪些还是假共享。
  - 做完你能看到什么：团队能明确说出当前哪些文件是真标准源，哪些只是平台实现。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 5
    - `design.md` 2.1、2.2、3.3
    - `apps/user-app/src/runtime/shared/theme-plugin/themeRuntime.ts`
    - `apps/user-app/src/runtime/h5-shell/theme/ThemeProvider.tsx`
    - `apps/user-app/src/runtime/rn-shell/tokens.ts`
  - 主要改哪里：
    - `specs/012.1-H5与RN样式共享边界收口/`
    - 如有必要补充 `docs/` 说明
  - 这一阶段先不做什么：先不改页面代码，先别碰大规模迁移。
  - 怎么算完成：
    1. 共享层、H5 适配层、RN 适配层的职责表写清楚。
    2. 当前错误边界和重复定义点有清单。
  - 怎么验证：
    - 人工走查
    - 对照现有代码目录核查
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 5
  - 对应设计：`design.md` 2.1、2.2、3.3、5

- [x] 1.2 定义共享契约和页面布局模式
  - 状态：DONE
  - 这一阶段到底做什么：把基础 token、语义 token、组件语义和页面布局模式整理成稳定契约，别再让页面自己猜。
  - 做完你能看到什么：跨端共享层不再只共享主题值，还能共享页面模式和交互降级规则。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 3
    - `design.md` 2.3、3.2、4.1、4.2
  - 主要改哪里：
    - `packages/user-ui/src/theme/`
    - `apps/user-app/src/runtime/shared/` 下新增或调整共享布局模块
  - 这一阶段先不做什么：先不做具体页面落地。
  - 怎么算完成：
    1. 共享契约数据结构稳定。
    2. 布局模式能覆盖桌面 H5、移动 H5、RN 三种主要场景。
  - 怎么验证：
    - 类型检查
    - 布局模式单元测试
  - 对应需求：`requirements.md` 需求 1、需求 3
  - 对应设计：`design.md` 2.3、3.2、4.1、4.2、6.3

### 阶段检查

- [x] 1.3 阶段检查：确认共享边界不是空话
  - 状态：DONE
  - 这一阶段到底做什么：只检查共享契约和平台边界是不是已经能指导后续实现，不扩范围。
  - 做完你能看到什么：后面的人拿到这份 Spec，不会继续问“到底共用什么”。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：当前 Spec 全部文档
  - 这一阶段先不做什么：不新增实现任务
  - 怎么算完成：
    1. 边界表足够清楚。
    2. 后续任务不再建立在模糊前提上。
  - 怎么验证：
    - 人工复核
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3
  - 对应设计：`design.md` 2、3、4、6

---

## 阶段 2：把 H5 和 RN 的适配层接到同一份契约上

- [x] 2.1 收口 H5 适配层，只负责 CSS 变量和浏览器行为
  - 状态：DONE
  - 这一阶段到底做什么：让 H5 只做 CSS 变量映射、响应式和浏览器专属交互，不再在页面里偷偷维护第二份语义。
  - 做完你能看到什么：H5 页面拿到的视觉规则都能回溯到共享契约。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 5
    - `design.md` 3.3、5
    - `apps/user-app/src/runtime/h5-shell/theme/`
    - `apps/user-app/h5-styles/`
  - 主要改哪里：
    - `apps/user-app/src/runtime/h5-shell/theme/`
    - `apps/user-app/h5-styles/`
  - 这一阶段先不做什么：先不处理 RN。
  - 怎么算完成：
    1. H5 适配层只消费共享契约。
    2. 浏览器专属行为不反向进入共享层。
  - 怎么验证：
    - 类型检查
    - H5 主题切换回归检查
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 5
  - 对应设计：`design.md` 2.2、3.3、5、6.2

- [x] 2.2 收口 RN 适配层，只负责原生 token bundle 和样式输入
  - 状态：DONE
  - 这一阶段到底做什么：让 RN 从同一份共享契约生成 token bundle，但继续保留 SafeArea、触摸反馈和原生布局细节。
  - 做完你能看到什么：RN 不再自己偷偷长出一套新的视觉语义定义。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 5
    - `design.md` 3.3、4、5
    - `apps/user-app/src/runtime/rn-shell/`
  - 主要改哪里：
    - `apps/user-app/src/runtime/rn-shell/`
    - 如有必要补充 `packages/user-ui/src/theme/`
  - 这一阶段先不做什么：先不批量改 RN 页面。
  - 怎么算完成：
    1. RN token bundle 全部来自共享契约。
    2. 原生专属能力仍只留在 RN 层。
  - 怎么验证：
    - 类型检查
    - RN token bundle 单元测试
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 5
  - 对应设计：`design.md` 2.2、3.3、4.1、5、6.2

### 阶段检查

- [x] 2.3 阶段检查：确认 H5 和 RN 已经接到同一份上游
  - 状态：DONE
  - 这一阶段到底做什么：只检查两端适配层有没有重新分叉，不扩新页面。
  - 做完你能看到什么：后面改页面时，不会再发现两端其实没吃同一套规则。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：当前 Spec 文档和相关适配层文件
  - 这一阶段先不做什么：不进页面试点
  - 怎么算完成：
    1. 两端都能追溯到同一份共享契约。
    2. 平台实现分工仍然清晰。
  - 怎么验证：
    - 人工走查
    - 对照代码入口核查
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 5
  - 对应设计：`design.md` 2、3、4、5

---

## 阶段 3：拿高频页面做第一批试点

- [x] 3.1 先把首页和设置页切到共享布局模式
  - 状态：DONE
  - 这一阶段到底做什么：拿 `home` 和 `settings` 这两类高频页面接入共享布局模式和共享组件语义，验证移动 H5 与 RN 的边界不是纸上谈兵。
  - 做完你能看到什么：同一页面在桌面 H5、手机 H5、RN 上至少信息层级和交互优先级一致。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 3、需求 4、需求 5
    - `design.md` 2.3、5、7
    - `apps/user-app/src/pages/home/`
    - `apps/user-app/src/pages/settings/`
  - 主要改哪里：
    - `apps/user-app/src/pages/home/`
    - `apps/user-app/src/pages/settings/`
    - 对应 H5 样式和 RN 页面文件
  - 这一阶段先不做什么：先不碰最重的历史页面。
  - 怎么算完成：
    1. 首页和设置页能按共享布局模式运行。
    2. 移动 H5 不再暴露明显鼠标专属交互。
  - 怎么验证：
    - 类型检查
    - 手机 H5 / 桌面 H5 / RN 人工验收
  - 对应需求：`requirements.md` 需求 3、需求 4、需求 5
  - 对应设计：`design.md` 2.3、4.2、5、6.3、7

- [x] 3.2 再拿助手页验证复杂交互边界
  - 状态：DONE
  - 这一阶段到底做什么：拿 `assistant` 这种既有复杂桌面布局、又有移动降级需求的页面做第二个试点，验证桌面增强交互和移动降级能共存。
  - 做完你能看到什么：团队知道哪些复杂交互只该留在桌面 H5，哪些操作必须变成手机友好模式。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 3、需求 4
    - `design.md` 2.3、5、6.3
    - `apps/user-app/src/pages/assistant/`
  - 主要改哪里：
    - `apps/user-app/src/pages/assistant/`
    - 对应 H5/RN 页面文件
  - 这一阶段先不做什么：先不处理剩余低频页面。
  - 怎么算完成：
    1. 助手页的桌面增强交互和移动降级规则明确。
    2. 页面不再把平台差异硬塞进共享层。
  - 怎么验证：
    - 类型检查
    - 人工验收
  - 对应需求：`requirements.md` 需求 2、需求 3、需求 4
  - 对应设计：`design.md` 2.3、5、6.2、6.3、7

### 阶段检查

- [x] 3.3 阶段检查：确认第一批试点已经形成新基线
  - 状态：DONE
  - 这一阶段到底做什么：检查这次试点是不是已经能成为后续页面默认模板，而不是只修了几个特例。
  - 做完你能看到什么：后面新页面知道该站在哪一边，不会继续回到散装样式老路。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：当前试点页面和文档
  - 这一阶段先不做什么：不追求一口气把剩余页面做完
  - 怎么算完成：
    1. 试点页面已证明共享边界可落地。
    2. 剩余页面有清楚的后续顺序。
  - 怎么验证：
    - 人工复核
    - 回归记录核查
  - 对应需求：`requirements.md` 需求 3、需求 4、需求 5
  - 对应设计：`design.md` 5、7、8

---

## 阶段 4：补规则、检查和交接文档

- [x] 4.1 把共享边界和迁移规则写进补充文档
  - 状态：DONE
  - 这一阶段到底做什么：把“哪些共享、哪些不共享、平台适配怎么做、页面先迁谁”写成接手文档，别让规则继续靠聊天记录传。
  - 做完你能看到什么：新人打开文档就能知道下一步该看哪里。
  - 先依赖什么：3.3
  - 开始前先看：
    - `requirements.md` 需求 4、需求 5
    - `design.md` 8
  - 主要改哪里：
    - `specs/012.1-H5与RN样式共享边界收口/docs/`
  - 这一阶段先不做什么：不新增实现范围
  - 怎么算完成：
    1. 边界说明、试点结论和剩余迁移名单都有文档。
    2. 接手入口清晰。
  - 怎么验证：
    - 人工走查文档
  - 对应需求：`requirements.md` 需求 4、需求 5
  - 对应设计：`design.md` 8

- [x] 4.2 补样式守卫和评审口径
  - 状态：DONE
  - 这一阶段到底做什么：把“不要再乱共享样式”和“不要再往页面里堆散装样式”变成可执行检查，而不只是嘴上说。
  - 做完你能看到什么：后续代码评审有明确判断标准。
  - 先依赖什么：3.3
  - 开始前先看：
    - `requirements.md` 需求 2、需求 5
    - `design.md` 5.3、7
    - 当前 `check-style-guard` 相关脚本
  - 主要改哪里：
    - `apps/user-app/scripts/`
    - 相关文档或检查说明
  - 这一阶段先不做什么：不追求一版守卫覆盖所有边缘情况。
  - 怎么算完成：
    1. 样式守卫或评审口径能覆盖最常见错误做法。
    2. 团队知道哪些情况必须打回。
  - 怎么验证：
    - 运行检查脚本
    - 人工构造典型违规案例
  - 对应需求：`requirements.md` 需求 2、需求 5
  - 对应设计：`design.md` 5.3、7、8

### 最终检查

- [x] 4.3 最终检查点
  - 状态：DONE
  - 这一阶段到底做什么：确认这份子 Spec 真的能支撑后续落地，而不是只停在讨论层。
  - 做完你能看到什么：需求、设计、任务、补充文档和验证口径能一一对上。
  - 先依赖什么：4.1、4.2
  - 开始前先看：
    - `README.md`
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一阶段先不做什么：不临时扩大范围
  - 怎么算完成：
    1. 共享边界、平台边界、试点顺序和验证口径都清楚。
    2. 后续任何人都能直接接着推进。
  - 怎么验证：
    - 按 Spec 自检清单人工复核
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文

- [x] 4.4 补齐登录页移动端验收记录
  - 状态：DONE
  - 这一阶段到底做什么：把登录页在手机浏览器里的补充收口单独记下来，别让这次修正只留在代码 diff 里。
  - 做完你能看到什么：后面的人能直接知道这次到底修了什么、该怎么验，不需要再翻样式文件猜。
  - 先依赖什么：4.3
  - 开始前先看：
    - `apps/user-app/src/runtime/h5-shell/components/LoginPage.tsx`
    - `apps/user-app/h5-styles/runtime/index.scss`
  - 主要改哪里：
    - `apps/user-app/h5-styles/runtime/index.scss`
    - `specs/012.1-H5与RN样式共享边界收口/docs/20260321-登录页移动端补充验收.md`
  - 这一阶段先不做什么：不改登录逻辑，不把 H5 的 `scss` 往 RN 里硬塞。
  - 怎么算完成：
    1. 移动端登录卡片宽度、输入控件尺寸和顶部留白都收口到可用状态。
    2. 补充验收文档能说明这次修改范围和验证方法。
  - 怎么验证：
    - 桌面浏览器设备模式人工验收
    - 真机访问 dev server 局域网地址人工验收
  - 对应需求：`requirements.md` 需求 2、需求 4、需求 5
  - 对应设计：`design.md` 5、8

- [x] 4.5 收紧登录页移动端首屏信息量
  - 状态：DONE
  - 这一阶段到底做什么：继续把手机登录页里不该抢空间的品牌说明收掉，让首屏只保留必要识别和登录操作。
  - 做完你能看到什么：手机视图进入页面后，用户先看到的是更大的登录卡片，而不是宣传文案和 feature 列表。
  - 先依赖什么：4.4
  - 开始前先看：
    - `apps/user-app/src/runtime/h5-shell/components/LoginPage.tsx`
    - `apps/user-app/h5-styles/runtime/index.scss`
  - 主要改哪里：
    - `apps/user-app/h5-styles/runtime/index.scss`
    - `docs/Documentation/使用指南/首次登录与初始化.md`
    - `specs/012.1-H5与RN样式共享边界收口/docs/20260321-登录页移动端补充验收.md`
  - 这一阶段先不做什么：不删除 DOM 结构，不影响桌面 H5 的品牌展示。
  - 怎么算完成：
    1. 移动端下 `.login-brand__desc` 和 `.login-brand__features` 不再占首屏空间。
    2. 登录表单宽度和内边距继续扩大，触屏可用面积更稳定。
  - 怎么验证：
    - 桌面浏览器设备模式人工验收
    - 真机访问 dev server 局域网地址人工验收
  - 对应需求：`requirements.md` 需求 2、需求 4、需求 5
  - 对应设计：`design.md` 5、8

- [x] 4.6 修正登录页移动端横向留白与居中基线
  - 状态：DONE
  - 这一阶段到底做什么：去掉移动端容器多余的横向留白，让 LOGO、名称、slogan 和登录卡片都沿同一条中心线排布。
  - 做完你能看到什么：手机宽度下页面不会再缩成中间一条，品牌区和表单区都接近满宽且居中。
  - 先依赖什么：4.5
  - 开始前先看：
    - `apps/user-app/h5-styles/runtime/index.scss`
    - `apps/user-app/src/runtime/h5-shell/components/LoginPage.tsx`
  - 主要改哪里：
    - `apps/user-app/h5-styles/runtime/index.scss`
    - `docs/Documentation/使用指南/首次登录与初始化.md`
  - 这一阶段先不做什么：不改登录逻辑，不新增另一套移动端页面。
  - 怎么算完成：
    1. 移动端两侧留白显著收缩。
    2. 品牌区和登录卡片都沿页面中心线显示。
  - 怎么验证：
    - 桌面浏览器设备模式人工验收
    - 真机访问 dev server 局域网地址人工验收
  - 对应需求：`requirements.md` 需求 2、需求 4、需求 5
  - 对应设计：`design.md` 5、8

- [x] 4.7 竖屏移动端切成全宽登录卡片
  - 状态：DONE
  - 这一阶段到底做什么：把竖屏手机视图从“放大后的桌面卡片”改成真正的移动端全宽卡片布局。
  - 做完你能看到什么：竖屏手机下登录卡片不再右偏或超出屏幕，而是按页面宽度铺开，像原生移动端页面。
  - 先依赖什么：4.6
  - 开始前先看：
    - `apps/user-app/h5-styles/runtime/index.scss`
    - `apps/user-app/src/runtime/h5-shell/components/LoginPage.tsx`
  - 主要改哪里：
    - `apps/user-app/h5-styles/runtime/index.scss`
    - `docs/Documentation/使用指南/首次登录与初始化.md`
  - 这一阶段先不做什么：不拆新的移动端专用页面，不改登录接口和表单逻辑。
  - 怎么算完成：
    1. 竖屏手机宽度下页面没有横向溢出。
    2. 登录表单变成全宽卡片，品牌区与表单区都稳定居中。
  - 怎么验证：
    - 桌面浏览器设备模式人工验收
    - 真机访问 dev server 局域网地址人工验收
  - 对应需求：`requirements.md` 需求 2、需求 4、需求 5
  - 对应设计：`design.md` 5、8

- [x] 4.8 清理登录页历史样式覆盖入口
  - 状态：DONE
  - 这一阶段到底做什么：把 H5 登录页仍然在加载的历史样式入口断开，避免旧规则把新的移动端布局重新盖掉。
  - 做完你能看到什么：登录卡片宽度、居中和移动端断点终于由当前运行时样式决定，不再被旧 `login.scss` 拖回去。
  - 先依赖什么：4.7
  - 开始前先看：
    - `apps/user-app/src/pages/login/styles-entry.h5.ts`
    - `apps/user-app/h5-styles/pages/login.scss`
    - `apps/user-app/h5-styles/runtime/index.scss`
  - 主要改哪里：
    - `apps/user-app/src/pages/login/styles-entry.h5.ts`
    - `specs/012.1-H5与RN样式共享边界收口/docs/20260321-登录页移动端补充验收.md`
  - 这一阶段先不做什么：不删除历史样式文件本身，先只切断当前 H5 登录页的加载入口。
  - 怎么算完成：
    1. H5 登录页不再加载 `pages/login.scss`。
    2. 登录页宽度和留白由 `runtime/index.scss` 的当前规则接管。
  - 怎么验证：
    - 搜索登录页样式入口确认旧样式未再引入
    - 桌面浏览器设备模式人工验收
  - 对应需求：`requirements.md` 需求 2、需求 4、需求 5
  - 对应设计：`design.md` 5、8

- [x] 4.9 收回竖屏移动端过宽卡片
  - 状态：DONE
  - 这一阶段到底做什么：把上一轮过宽、过高的竖屏登录卡片收回到合理范围，避免继续挤占上方品牌区。
  - 做完你能看到什么：竖屏手机下登录卡片仍然足够大，但不会再像整块白板一样压住 LOGO 和产品名称。
  - 先依赖什么：4.8
  - 开始前先看：
    - `apps/user-app/h5-styles/runtime/index.scss`
  - 主要改哪里：
    - `apps/user-app/h5-styles/runtime/index.scss`
    - `docs/Documentation/使用指南/首次登录与初始化.md`
  - 这一阶段先不做什么：不回滚移动端单列布局，不恢复旧的窄卡片规则。
  - 怎么算完成：
    1. 竖屏移动端登录卡片最大宽度回到合理值。
    2. 品牌区和表单区之间有明确间距，不再互相挤占。
  - 怎么验证：
    - 桌面浏览器设备模式人工验收
    - 真机访问 dev server 局域网地址人工验收
  - 对应需求：`requirements.md` 需求 2、需求 4、需求 5
  - 对应设计：`design.md` 5、8

- [x] 4.10 修正登录页外层滚动容器导致的右侧空白
  - 状态：DONE
  - 这一阶段到底做什么：给 H5 登录页挂专用宿主类，接管 `body` 和 `taro_page` 的滚动与宽度，消掉右侧异常竖条。
  - 做完你能看到什么：登录页右侧不再保留多余滚动槽，页面内容宽度由登录页自己控制。
  - 先依赖什么：4.9
  - 开始前先看：
    - `apps/user-app/src/runtime/h5-shell/components/LoginPage.tsx`
    - `apps/user-app/h5-styles/runtime/index.scss`
  - 主要改哪里：
    - `apps/user-app/src/runtime/h5-shell/components/LoginPage.tsx`
    - `apps/user-app/h5-styles/runtime/index.scss`
    - `docs/Documentation/使用指南/首次登录与初始化.md`
  - 这一阶段先不做什么：不改登录接口逻辑，不再恢复历史登录页样式入口。
  - 怎么算完成：
    1. 登录页场景下外层页面容器不再强制保留右侧滚动槽。
    2. 登录页右侧异常空白消失，横向不再溢出。
  - 怎么验证：
    - 桌面浏览器设备模式人工验收
    - 搜索确认登录页宿主类已挂到 `body` 和 `taro_page`
  - 对应需求：`requirements.md` 需求 2、需求 4、需求 5
  - 对应设计：`design.md` 5、8

- [x] 4.11 收口登录页竖屏移动端比例与垂直节奏
  - 状态：DONE
  - 这一阶段到底做什么：把仍然偏像 PC 缩略图的品牌区和登录卡片重新按手机比例收口，避免顶部拥挤和字号失衡。
  - 做完你能看到什么：LOGO、产品名称、欢迎语和登录卡片会整体下移到更自然的位置，尺寸也更接近移动端页面，而不是桌面布局压缩版。
  - 先依赖什么：4.10
  - 开始前先看：
    - `apps/user-app/h5-styles/runtime/index.scss`
  - 主要改哪里：
    - `apps/user-app/h5-styles/runtime/index.scss`
    - `docs/Documentation/使用指南/首次登录与初始化.md`
  - 这一阶段先不做什么：不恢复旧登录页样式，不改单独的 H5 组件结构。
  - 怎么算完成：
    1. 竖屏移动端品牌区和表单区最大宽度都落在合理手机尺寸范围。
    2. 整体内容不再贴顶，看起来不再像 PC 缩略图。
  - 怎么验证：
    - 桌面浏览器设备模式人工验收
    - 真机访问 dev server 局域网地址人工验收
  - 对应需求：`requirements.md` 需求 2、需求 4、需求 5
  - 对应设计：`design.md` 5、8
