# 设计文档 - H5与RN样式共享边界收口

状态：Done

## 1. 概述

### 1.1 目标

- 把 `H5` 与 `RN` 真正应该共享的内容收成唯一契约。
- 把 `H5` 与 `RN` 必须分开的实现边界写清楚。
- 给页面迁移提供稳定的布局模式和平台适配规则。
- 在不破坏现有主题运行时的前提下推进第一批试点页面。

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4
- `requirements.md` 需求 5

### 1.3 技术约束

- `H5` 继续使用 `scss/css`、CSS 变量和浏览器响应式能力。
- `RN` 继续使用 `StyleSheet`、运行时 token bundle 和原生布局能力。
- 当前共享主题运行时已经存在，不允许为这份 Spec 再造第二套主题运行时。
- 兼容层必须允许历史页面短期继续运行，但不能继续成为新代码默认入口。

## 2. 架构

### 2.1 系统结构

整体分四层：

1. **共享契约层**
   - 放基础 token、语义 token、组件语义和页面布局模式。
   - 这是唯一标准源。
2. **H5 适配层**
   - 把共享契约映射成 CSS 变量、页面响应式规则和浏览器专属交互。
3. **RN 适配层**
   - 把共享契约映射成 RN token bundle、`StyleSheet` 输入和原生布局行为。
4. **页面消费层**
   - 页面只组装共享语义和少量业务专属结构，不再重新定义基础视觉规则。

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `shared theme contract` | 定义基础 token、语义 token、组件语义 | 主题资源、默认值 | 统一契约对象 |
| `shared layout modes` | 定义页面布局模式与触屏降级规则 | 平台、宽度、交互方式 | 布局模式结果 |
| `H5 adapter` | 生成 CSS 变量和浏览器专属行为 | 统一契约对象、布局模式 | CSS 变量、H5 响应式行为 |
| `RN adapter` | 生成 RN token bundle 和原生样式输入 | 统一契约对象、布局模式 | foundation/semantic/component token bundle |
| `page layer` | 消费组件语义和布局模式 | 平台适配结果、业务数据 | 页面 UI |

### 2.3 关键流程

#### 2.3.1 主题加载流程

1. 主题运行时读取当前主题资源。
2. 共享契约层把主题资源整理成统一的基础 token、语义 token 和组件语义。
3. `H5` 适配层把契约映射成 CSS 变量。
4. `RN` 适配层把契约映射成 JS token bundle。
5. 页面层只消费适配后的结果，不再直接拼接原始主题值。

#### 2.3.2 页面布局判定流程

1. 页面读取平台信息、视口宽度和交互方式。
2. 共享布局模式先判断这是桌面 `H5`、移动 `H5` 还是 `RN`。
3. 返回标准布局模式，例如 `desktop-dashboard`、`mobile-dashboard`、`native-stack-page`。
4. 页面按布局模式切换结构密度、列数和交互可用性。

#### 2.3.3 移动 H5 降级流程

1. 页面进入窄屏或触屏场景。
2. 布局模式切到移动端语义。
3. 关闭鼠标专属拖拽、hover-only 或细粒度 resize 交互。
4. 保留手机可用操作，例如单列布局、滚动标签、显式按钮操作。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4

- `SharedThemeContract`
  - 跨端唯一的主题契约对象。
- `SharedLayoutModeResolver`
  - 根据平台和宽度返回页面布局模式。
- `H5ThemeAdapter`
  - 负责 CSS 变量和浏览器专属视觉落地。
- `RnThemeAdapter`
  - 负责 RN token bundle 和原生样式落地。
- `SharedPagePatterns`
  - 负责统一的页头、卡片、表单区块、空状态和页面模式语义。

### 3.2 数据结构

覆盖需求：1、2、3

#### 3.2.1 `SharedThemeContract`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `foundation` | `FoundationTokens` | 是 | 原始设计值 | 不包含平台私有实现 |
| `semantic` | `SemanticTokens` | 是 | 带用途的视觉语义 | 命名稳定，可跨端复用 |
| `component` | `ComponentTokens` | 是 | 高频基础组件语义 | 只描述组件语义，不含平台 API |

#### 3.2.2 `PlatformLayoutContext`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `platform` | `'h5' \| 'rn'` | 是 | 当前端类型 | 必须准确区分 |
| `viewportWidth` | `number` | 是 | 可用视口宽度 | `RN` 取窗口宽度 |
| `pointerType` | `'coarse' \| 'fine'` | 否 | 交互方式 | `H5` 可由媒体查询推导 |
| `safeAreaEnabled` | `boolean` | 否 | 是否启用安全区 | 仅 `RN`/移动场景 relevant |

#### 3.2.3 `PageLayoutMode`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | 布局模式标识 | 稳定命名 |
| `columns` | `1 \| 2 \| 3` | 是 | 页面主列数 | 移动 H5 不得超过 1 |
| `allowMouseResize` | `boolean` | 是 | 是否允许鼠标式缩放 | 触屏场景必须为 `false` |
| `allowDragSort` | `boolean` | 是 | 是否允许拖拽排序 | 触屏场景默认 `false` |
| `headerDensity` | `'compact' \| 'regular'` | 是 | 页头密度 | 由平台模式决定 |

### 3.3 接口契约

覆盖需求：1、2、3、5

#### 3.3.1 `resolveSharedThemeContract(themeResource)`

- 类型：Function
- 路径或标识：`packages/user-ui/src/theme/*`
- 输入：主题资源、默认主题值
- 输出：`SharedThemeContract`
- 校验：缺失字段时回退到默认主题，不允许返回半残契约
- 错误：若主题资源非法，返回可恢复错误并使用默认值

#### 3.3.2 `mapThemeContractToCssVariables(contract)`

- 类型：Function
- 路径或标识：`apps/user-app/src/runtime/h5-shell/theme/*`
- 输入：`SharedThemeContract`
- 输出：CSS 变量映射
- 校验：只能消费共享契约，不允许从页面层读取散装变量
- 错误：映射缺失时记录错误并回退到默认变量

#### 3.3.3 `mapThemeContractToRnTokens(contract)`

- 类型：Function
- 路径或标识：`apps/user-app/src/runtime/rn-shell/*`
- 输入：`SharedThemeContract`
- 输出：RN foundation/semantic/component token bundle
- 校验：只生成 RN 可消费结果，不带浏览器专属字段
- 错误：字段缺失时回退到默认 token bundle

#### 3.3.4 `resolvePageLayoutMode(context)`

- 类型：Function
- 路径或标识：共享页面布局模块
- 输入：`PlatformLayoutContext`
- 输出：`PageLayoutMode`
- 校验：移动 H5 与 `RN` 必须强制单列或触屏友好模式
- 错误：上下文不完整时回退到最保守的单列模式

## 4. 数据与状态模型

### 4.1 数据关系

- 主题资源是输入。
- `SharedThemeContract` 是跨端共同消费的中间层。
- `H5 adapter` 和 `RN adapter` 都只依赖 `SharedThemeContract`。
- 页面布局模式独立于主题契约，但同样属于共享层输出。
- 页面层同时消费“主题语义”和“布局模式”，不再直接操作原始主题值。

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `contract_ready` | 共享契约已准备好 | 主题资源解析成功 | 主题切换或资源失效 |
| `adapter_ready` | 平台适配结果已生成 | 平台映射成功 | 页面重建或主题切换 |
| `page_legacy` | 页面仍在兼容层 | 尚未迁移完成 | 页面完成共享模式迁移 |
| `page_migrated` | 页面已切到共享模式 | 页面接入共享组件和布局模式 | 新需求导致再次拆分 |

## 5. 错误处理

### 5.1 错误类型

- `theme_contract_missing`：共享契约字段不完整。
- `platform_adapter_invalid`：平台适配结果缺失关键字段。
- `layout_mode_resolution_failed`：布局模式判定失败。
- `legacy_page_bypass`：页面绕过共享层直接写平台散装样式。

### 5.2 错误响应格式

```json
{
  "detail": "共享样式契约生成失败，已回退到默认主题。",
  "error_code": "theme_contract_missing",
  "field": "semantic.surface.card",
  "timestamp": "2026-03-21T00:00:00Z"
}
```

### 5.3 处理策略

1. 契约缺失：回退默认主题，阻止页面继续消费半残数据。
2. 平台映射失败：保守回退到默认 token，不让页面直接崩。
3. 布局模式判定失败：默认回退单列、禁用复杂交互。
4. 发现页面绕过共享层：通过样式守卫、代码审查和迁移清单阻止扩散。

## 6. 正确性属性

### 6.1 属性 1：共享契约必须先于平台实现

*对于任何* 新增跨端视觉语义，系统都应该先定义共享契约，再补 `H5` 和 `RN` 适配层。

**验证需求：** `requirements.md` 需求 1、需求 2

### 6.2 属性 2：平台实现不得反向污染共享层

*对于任何* 浏览器专属或原生专属样式能力，系统都应该留在平台适配层，而不是反向进入共享契约。

**验证需求：** `requirements.md` 需求 2

### 6.3 属性 3：移动触屏场景不得继续暴露鼠标专属交互

*对于任何* 窄屏或触屏页面，系统都应该优先提供可点击、可滚动、可单手操作的结构，而不是继续依赖拖拽和鼠标 resize。

**验证需求：** `requirements.md` 需求 3

### 6.4 属性 4：历史页面兼容只允许过渡，不允许扩散

*对于任何* 尚未迁移完成的历史页面，系统都应该允许它暂时通过兼容层运行，但不得再成为新页面默认模板。

**验证需求：** `requirements.md` 需求 4、需求 5

## 7. 测试策略

### 7.1 单元测试

- 共享契约解析测试。
- `H5` CSS 变量映射测试。
- `RN` token bundle 映射测试。
- 页面布局模式判定测试。

### 7.2 集成测试

- 主题切换后 `H5` 与 `RN` 仍能拿到一致语义。
- `H5` 窄屏模式正确降级为移动布局。
- 兼容页面与已迁移页面能同时运行。

### 7.3 端到端测试

- 首页在桌面 `H5`、手机 `H5`、`RN` 上信息层级一致。
- 设置页在主题切换后主区块与表单区块无明显回归。

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` 2.1、3.2、3.3 | 代码走查 + 单元测试 |
| `requirements.md` 需求 2 | `design.md` 2.2、3.3、6.2 | 代码走查 + 样式守卫 |
| `requirements.md` 需求 3 | `design.md` 2.3、4.2、6.3 | 布局模式测试 + 人工验收 |
| `requirements.md` 需求 4 | `design.md` 5、7 | 迁移清单 + 分批回归 |
| `requirements.md` 需求 5 | `design.md` 3.3、5、7 | 类型检查 + 主题回归检查 |

## 8. 风险与待确认项

### 8.1 风险

- 如果共享契约只停在主题层，不继续收口布局模式和组件语义，页面层还是会继续乱。
- 如果第一批试点挑得太复杂，团队会再次陷入“先修一页再说”的局部补丁路线。
- 如果兼容层不设退出边界，历史页面会永远挂在兼容模式里不动。

### 8.2 待确认项

- 第一批试点是否优先覆盖 `home`、`settings`、`assistant` 三类页面。
- 是否需要为共享布局模式单独建立跨端 hook 或 helper 目录。
- 是否需要把当前移动 H5 适配规则抽成更通用的页面模式文档。
