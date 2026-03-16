# 设计文档 - user-app界面标准化与样式收口

状态：Draft

## 1. 概述

### 1.1 目标

- 结束 `user-app` 当前样式来源分裂的问题
- 建立一套跨端可复用、H5 主题可落地的 UI 标准
- 在 `packages/user-ui` 中补齐语义 token 和高频基础组件
- 说清楚 H5 下 `designWidth`、`pxtransform`、样式文件单位和行内样式单位到底怎么用
- 用分阶段迁移替代“一次性重写所有页面”

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4
- `requirements.md` 需求 5
- `requirements.md` 需求 6
- `requirements.md` 需求 7

### 1.3 技术约束

- 前端主应用：`apps/user-app`
- 共享 UI 包：`packages/user-ui`
- 现有 H5 主题入口：`apps/user-app/src/runtime/h5-shell/theme/tokens.ts`
- 现有 H5 CSS 变量注入：`apps/user-app/src/runtime/h5-shell/theme/ThemeProvider.tsx`
- 当前全局设计稿基准：`apps/user-app/config/index.ts` 中的 `designWidth: 750`
- 当前 H5 配置没有额外覆盖 `pxtransform`，等于默认吃 Taro 的 H5 换算规则
- 当前零散基础件：`apps/user-app/src/components/AppUi.tsx`
- 当前共享基础件：`packages/user-ui/src/components/*`
- 不启动新服务，不新增编译产物，不修改 `user-web`

## 2. 总体方案

### 2.1 核心思路

不要再让页面自己定义“按钮长什么样、卡片长什么样、正文多大号”。

这次收口按四层做：

1. **设计 token 层**
   - 定义颜色、字号、间距、圆角、阴影、边框这些最底层值
2. **语义 token 层**
   - 把原始值映射成“页面背景”“主卡片背景”“正文颜色”“危险按钮背景”这类用途变量
3. **基础组件层**
   - 封装 `Text`、`Card`、`Button`、`Input`、`Section`、`Tag`、`Field` 等基础件和变体
4. **业务页面层**
   - 页面只组合基础件和少量业务特有布局，不再自己随手发明视觉规则

### 2.2 唯一标准源

当前最完整的 token 定义其实在 `apps/user-app/src/runtime/h5-shell/theme/tokens.ts`。但这个文件现在是 H5 壳层私有实现，不是正式的共享标准源。

收口后改成下面这个关系：

| 层 | 责任 | 主要位置 |
| --- | --- | --- |
| 设计 token | 定义原始颜色、字号、圆角、间距、阴影 | `packages/user-ui/src/theme/` |
| 语义 token | 定义跨端消费的命名和分组 | `packages/user-ui/src/theme/` |
| H5 变量注入 | 把共享 token 映射成 CSS 变量 | `apps/user-app/src/runtime/h5-shell/theme/` |
| 页面消费 | 用共享 token 和基础组件渲染页面 | `apps/user-app/src/` |

结论很简单：**标准源要搬到 `packages/user-ui`，H5 运行时只负责把它注入成 CSS 变量，不再自己偷偷维护一套。**

### 2.3 不破坏现有页面的兼容策略

第一轮不能指望所有页面立刻全迁完，所以需要兼容层。

兼容策略如下：

1. 保留现有 H5 CSS 变量名称
2. `packages/user-ui` 新导出的 token 继续能读这些 CSS 变量
3. 新基础组件优先消费新的语义 token
4. 旧页面在迁移前允许继续跑，但不允许继续扩散同类写法

这样做的好处是：

- 不会一上来把主题切换搞死
- 不需要全仓同时改完
- 可以边收口共享层，边逐页迁移

### 2.4 `designWidth` 的边界

`designWidth` 只回答一个问题：**这套页面源码按哪份设计稿宽度来换算。**

它不负责解决下面这些问题：

- 页面作者按浏览器默认 `16px` 心智手写 `rem`
- JSX/TS 行内样式直接写固定 `'24px'`
- 同一个页面里同时混用“会被 Taro 转换的尺寸”和“不会被 Taro 转换的尺寸”

所以这次设计里把边界写死：

1. 如果真实设计稿基准就是 `750`，那就不允许为了修某个页面的尺寸异常去随手改全局 `designWidth`
2. 只有在设计稿基准本身就配错时，才允许调整 `designWidth`
3. 调整 `designWidth` 属于高风险全局改动，必须先做样式审计和回归验证

结论很直接：**`designWidth` 可以修“设计稿基准配错”，不能修“单位体系混乱”。**

## 3. Token 设计

### 3.1 Token 分层

建议把共享 token 拆成三组，而不是继续堆成一个大对象：

#### 3.1.1 Foundation Token

原始值，不带业务语义。

建议至少包括：

- `color.*`
- `font.family.*`
- `font.size.*`
- `font.weight.*`
- `lineHeight.*`
- `spacing.*`
- `radius.*`
- `shadow.*`
- `border.width.*`

#### 3.1.2 Semantic Token

面向页面和组件消费。

建议至少包括：

- `surface.page`
- `surface.card`
- `surface.cardMuted`
- `surface.input`
- `text.primary`
- `text.secondary`
- `text.tertiary`
- `text.inverse`
- `border.default`
- `border.subtle`
- `action.primary.*`
- `action.secondary.*`
- `state.success.*`
- `state.warning.*`
- `state.danger.*`

#### 3.1.3 Component Token

只服务高频基础组件，用来减少组件内部重复拼样式。

建议至少包括：

- `button.primary`
- `button.secondary`
- `button.ghost`
- `card.default`
- `card.muted`
- `input.default`
- `tag.info`
- `tag.success`
- `tag.warning`
- `tag.danger`

### 3.2 字体和字号阶梯

这次必须把字号说死，否则页面还是会继续乱写。

建议基础阶梯保持少而稳：

| 名称 | 用途 |
| --- | --- |
| `xs` | 辅助说明、标签 |
| `sm` | 次级说明、表单提示 |
| `md` | 正文默认字号 |
| `lg` | 小标题、强调正文 |
| `xl` | 区块标题 |
| `xxl` | 页面主标题 |
| `hero` | 首页或大视觉主标题 |

同时补齐：

- `font.family.base`
- `font.family.mono`
- `font.weight.regular`
- `font.weight.medium`
- `font.weight.semibold`
- `lineHeight.tight`
- `lineHeight.normal`
- `lineHeight.relaxed`

### 3.3 间距和圆角

间距和圆角必须减少自由发挥。

建议规则：

- 页面和区块布局优先只用统一 `spacing` 阶梯
- 卡片、输入框、标签、按钮各自只允许使用少数固定圆角级别
- 不再允许页面随手写 `10px / 14px / 18px / 22px` 这种临时值，除非是明确例外

### 3.4 H5 CSS 变量映射

H5 运行时仍然需要 CSS 变量，因为现有页面和 SCSS 已经在大量消费它们。

这里不推倒重来，而是做映射：

1. 共享 token 生成语义对象
2. `ThemeProvider` 读取语义对象
3. `ThemeProvider` 继续写入现有 CSS 变量名
4. 新增缺失的变量名时，先在共享层定义，再由 `ThemeProvider` 注入

这保证 H5 页面继续能跑，也让共享层真正成为上游。

### 3.5 H5 单位策略

这部分必须明确，不然后面会继续踩坑。

#### 3.5.1 样式文件中的源码单位

在 `.scss/.css` 里，默认只允许把 `px` 当成**设计稿尺寸源码单位**。

这里的意思不是“浏览器固定像素”，而是：

- 交给 Taro H5 `pxtransform` 继续换算
- 开发者写的是设计稿尺寸
- 编译后怎么落成 `rem`，是构建层的事，不是页面层自己决定

#### 3.5.2 禁止手写 `rem`

默认禁止在 H5 页面样式里手写 `rem`，原因很简单：

- `rem` 直接绑定 Taro H5 根字号
- 旧页面、普通网页样式和设计稿思维下写出来的 `rem`，很容易带着错误心智进入项目
- 一旦根字号因为 `designWidth`、`baseFontSize`、`maxRootSize` 变化，页面会整体失真

允许例外只有两类：

1. 明确要跟随根字号缩放的全局壳层布局
2. 已经审计并确认依赖根字号的历史样式，暂时无法迁移

但这两类例外都必须单独注明原因，不能当默认写法。

#### 3.5.3 JSX/TS 行内样式单位

JSX/TS 行内样式不能再直接写 `'24px'` 这种值，因为它不会自动进入和样式文件同一套换算链路。

正式规则如下：

1. 优先不用行内尺寸，改成共享组件和 token
2. 如果必须在 JSX/TS 中写设计稿尺寸，统一通过显式转换函数处理
3. 如果必须写固定浏览器像素，必须注明原因，只允许用于明确的例外场景

换句话说：**行内样式尺寸必须显式声明语义，不能再伪装成和样式文件里的 `px` 是一回事。**

#### 3.5.4 `clamp()` 的使用边界

`clamp()` 本身没有罪，问题在于你拿什么单位做 `clamp()`。

规则如下：

- 允许 `clamp(px, vw, px)` 这种写法，用来做 H5 视口响应
- 禁止 `clamp(rem, vw, rem)` 这种写法作为默认方案
- 如果 `clamp()` 里使用设计稿尺寸，优先来自 token 或明确的尺寸常量

#### 3.5.5 固定像素的例外

有些场景确实需要固定浏览器像素或规避 Taro 换算，例如：

- 某些精确图形尺寸
- 与第三方 DOM 结构强绑定的局部样式
- 已确认不能跟设计稿缩放走的局部视觉部件

这些场景允许例外，但必须满足：

1. 例外只留在局部，不扩散成页面默认写法
2. 文档和代码里都说清原因
3. 不得拿它替代共享 token 和基础组件

## 4. 组件设计

### 4.1 基础组件分层

建议共享层按下面分：

| 层级 | 作用 | 例子 |
| --- | --- | --- |
| Primitive | 最薄的基础承载组件 | `UiText`、`UiView` |
| Pattern | 带明确视觉变体的基础组件 | `UiButton`、`UiCard`、`UiInput`、`UiTag` |
| Composite | 常见组合件 | `FormField`、`SectionNote`、`EmptyStateCard`、`PageSection` |

原则很简单：

- 能在多个页面复用的，进 `packages/user-ui`
- 只对某个业务页面成立的，不要硬塞进共享层

### 4.2 第一批必须收口的基础件

第一批建议直接收口这些：

1. `Text`
2. `Button`
3. `Input`
4. `Card`
5. `Section`
6. `Tag`
7. `Field`
8. `EmptyState`

它们能覆盖现在 `AppUi.tsx`、`MainShellPage.tsx`、壳层和设置页里最大的一批重复样式。

### 4.3 组件变体规则

每个基础件不要做成无限制自由拼装，要先收口常见变体。

示例：

- `UiButton`
  - `primary`
  - `secondary`
  - `ghost`
  - `danger`
- `UiCard`
  - `default`
  - `muted`
  - `warning`
- `UiText`
  - `body`
  - `caption`
  - `title`
  - `sectionTitle`

这样做的目的不是炫技，是防止页面继续重复写同一套边框、字号和背景。

### 4.4 现有组件的归并策略

当前有两个明显重叠的入口：

- `packages/user-ui/src/components/*`
- `apps/user-app/src/components/AppUi.tsx`

处理方式：

1. 先把 `AppUi.tsx` 里通用的部件归并到 `packages/user-ui`
2. `AppUi.tsx` 短期可以作为兼容导出层
3. 等页面切完后，再把兼容层缩薄或删除

## 5. 页面迁移方案

### 5.1 迁移优先级

不要先碰最巨大的历史页面，先拿高复用和高可见度区域开刀。

建议顺序：

1. 公共壳层和共享组件
2. 登录、入口、主页、设置壳层
3. 高复用业务面板和表单
4. 剩余页面
5. 旧页面遗留样式清理

### 5.2 第一批迁移范围

第一批建议覆盖：

- `apps/user-app/src/components/AppShellPage.tsx`
- `apps/user-app/src/components/AuthShellPage.tsx`
- `apps/user-app/src/components/MainShellPage.tsx`
- `apps/user-app/src/components/AppUi.tsx`
- `apps/user-app/src/pages/home/*`
- `apps/user-app/src/pages/login/*`
- `apps/user-app/src/pages/settings/*` 中高频公共区块

原因很简单：

- 这些位置复用度高
- 改完最能形成新基线
- 风险可控，不会一上来就陷进超大历史页面

### 5.3 暂缓迁移的区域

这些先别急着重写：

- `LegacyFamilyPage.tsx` 这种历史包袱很重的大页面
- 依赖大量独立 H5 样式文件且视觉结构复杂的页面
- 带强业务实验性质的页面

策略不是不做，而是等基础件站稳后再处理。

## 6. 规则和约束

### 6.1 新增代码约束

新增或改造 `user-app` 前端代码时，默认遵守：

1. 文本颜色、背景色、字号、间距、圆角优先用 token
2. 常见按钮、卡片、输入框优先用共享基础件
3. 页面层避免新增大段内联 `style`
4. H5 样式文件默认用设计稿 `px`，禁止把手写 `rem` 当默认单位
5. JSX/TS 行内尺寸禁止直接混写固定 `'24px'` 一类值
6. 特殊平台样式必须注明原因和边界

### 6.2 检查方式

首版不一定要上很重的 lint 插件，但至少要有能跑的检查点。

建议：

- 扫描典型硬编码模式
- 扫描新增手写 `rem`
- 扫描新增行内固定尺寸
- 在代码审查中明确阻止新增散装样式
- 在 `tasks.md` 中记录哪些目录已经进入强约束区

### 6.3 允许的例外

下面这些情况可以保留少量页面私有样式：

- 强业务图形展示
- 平台差异导致的必要适配
- 短期兼容旧页面时的过渡代码
- 明确需要固定浏览器像素的局部视觉部件

但例外必须满足两点：

1. 说清为什么不能进共享层
2. 不得重复实现已经存在的公共变体

## 7. 测试策略

### 7.1 单元测试

- token 映射正确性
- 基础组件变体样式输出
- H5 CSS 变量映射逻辑

### 7.2 集成测试

- 公共壳层迁移后页面仍能正常渲染
- 表单和卡片基础件替换后交互不回归
- 主题切换后关键变量仍能生效

### 7.3 手工验收

- 登录页、首页、设置页检查视觉一致性
- 检查同类按钮、卡片、表单字段是否统一
- 检查 H5 主题切换前后核心页面是否明显异常
- 检查 `setup-guard`、`assistant` 一类对单位敏感的区域是否仍有整体放大问题

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` 2.2、3.4 | 代码走查 + 导出入口检查 |
| `requirements.md` 需求 2 | `design.md` 3、4 | 组件测试 + 人工验收 |
| `requirements.md` 需求 3 | `design.md` 5 | 页面迁移验收 |
| `requirements.md` 需求 4 | `design.md` 6 | 检查脚本 + 代码审查规则 |
| `requirements.md` 需求 5 | `design.md` 2.4、3.5、6 | 单位规则走查 + 配置检查 |
| `requirements.md` 需求 6 | `design.md` 2.3、3.4、7 | 主题回归检查 + 类型检查 |
| `requirements.md` 需求 7 | `design.md` 全文 | 文档走查 |

## 8. 风险与待确认项

### 8.1 风险

- 如果共享层只做 token，不补基础组件，页面还是会继续写重复样式
- 如果直接把 H5 token 和共享 token 各自维护，最后会变成两套标准
- 如果第一轮就去重写最重的历史页面，项目会被拖进泥潭
- 如果不把单位规则写死，后面会继续出现“样式文件里写 `px`、页面里写 `rem`、JSX 里写固定像素”三套尺寸语义并存
- 如果误把修改 `designWidth` 当成默认修复手段，现有依赖 Taro 换算的页面可能整体回归

### 8.2 待确认项

- 第一版是否需要把字体族也完全收口到共享层
- 是否需要为 SCSS 页面提供一份 token 对照表，方便迁移
- 检查硬编码样式是先用脚本扫描，还是直接上 lint 规则
- 是否需要在 H5 配置中补充 `pxtransform` 相关参数说明或限制
