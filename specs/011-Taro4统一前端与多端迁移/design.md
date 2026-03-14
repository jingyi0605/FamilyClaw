# 设计文档 - Taro 4 统一前端与多端迁移

状态：Draft

## 1. 概述

### 1.1 目标

- 建立 `apps/user-app` 作为唯一长期用户前端主应用
- 用 `Taro 4 + React` 同时覆盖 `PC H5`、`iOS`、`Android`、`鸿蒙`
- 把跨端共性逻辑抽到共享层，把平台差异压到适配层
- 用可灰度、可回滚的方式逐步废掉 `apps/user-web`

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4
- `requirements.md` 需求 5
- `requirements.md` 需求 6
- `requirements.md` 需求 7
- `requirements.md` 需求 8

### 1.3 技术约束

- 前端主线只允许使用 `Taro 4 + React`
- `PC` 只考虑浏览器 H5，不做原生桌面端
- iOS / Android 使用 `Taro RN`
- 鸿蒙使用 `Taro Harmony`
- 共享层必须可被多个目标复用，不能再直接绑定浏览器运行时
- 迁移期间 `user-web` 只能做兼容修复，不再承接正式新功能

### 1.4 关键设计判断

- 不在 `user-web` 上继续硬补多端能力，新建 `apps/user-app`
- 不直接把 `user-web` 页面整坨复制到 `user-app`
- 先抽共享层，再迁页面
- 先让 `Taro H5` 吃下核心链路，再扩展原生平台能力
- 迁移成功的标准不是“代码能跑”，而是“旧入口可以被正式替换”

## 2. 架构

### 2.1 目标目录结构

建议按现有 workspace 结构新增并收口到下面这套目录：

```text
apps/
├── user-app/                      # 新的 Taro 4 + React 主应用
├── user-web/                      # 旧网页应用，迁移期只修不增
├── admin-web/
└── api-server/

packages/
├── user-core/                     # 类型、API、schema、业务用例、共享状态模型
├── user-platform/                 # 权限、通知、文件、分享、深链、存储、实时连接适配层
├── user-ui/                       # 跨端基础组件、主题 token、布局基础件
└── user-testing/                  # 测试桩、平台 mock、对齐清单工具
```

这里的核心原则只有一个：  
`user-app` 负责页面壳和平台入口，`packages/*` 负责被多个平台目标复用的东西。

### 2.2 系统结构

整个前端分成四层：

1. 应用壳层
   - `apps/user-app`
   - 负责 Taro 入口、页面路由、分包、平台编译目标、导航壳和页面装配
2. 共享业务层
   - `packages/user-core`
   - 负责类型、API client、业务状态、视图模型、页面用例
3. 平台适配层
   - `packages/user-platform`
   - 负责通知、权限、文件、分享、深链、实时能力统一接口
4. 共享表现层
   - `packages/user-ui`
   - 负责主题 token、通用组件、列表/表单/弹层/空态/错误态等基础表现

### 2.3 平台目标与策略

| 平台 | Taro 目标 | 角色 | 说明 |
| --- | --- | --- | --- |
| PC 浏览器 | `h5` | 第一优先级 | 先替换 `user-web` |
| iOS | `rn` | 第二优先级 | 复用共享层和移动导航壳 |
| Android | `rn` | 第二优先级 | 与 iOS 共享大部分移动实现 |
| 鸿蒙 | `harmony` | 第二优先级 | 共享核心逻辑，保留必要的平台文件分流 |

为什么先打 H5：

- 旧系统是 `user-web`，最容易做功能对齐
- H5 是验证共享层是否抽干净的第一关
- 如果连 H5 都不能平替 `user-web`，谈移动端只是吹牛

### 2.4 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `user-app/app.config.ts` | 管理页面、分包、导航和平台编译配置 | 页面注册、Taro 配置 | 应用壳配置 |
| `user-core/api` | 封装后端接口和响应类型 | 请求参数、环境配置 | 领域数据 |
| `user-core/features/*` | 管理登录、家庭、助手、记忆、设置等业务用例 | API 结果、用户操作 | 页面视图模型 |
| `user-core/state` | 管理共享状态和缓存策略 | 业务事件、生命周期 | 状态切片 |
| `user-platform/storage` | 封装本地存储 | key、value | 统一存储结果 |
| `user-platform/permissions` | 封装权限查询和申请 | 权限类型 | 授权状态 |
| `user-platform/notifications` | 封装通知注册、token、开关和跳转 | 通知策略、平台上下文 | 注册状态、通知事件 |
| `user-platform/files` | 封装文件选择、拍照、上传准备 | 来源类型、限制条件 | 文件句柄、上传输入 |
| `user-platform/realtime` | 封装实时连接、重连和降级 | 会话 ID、认证态 | 统一事件流 |
| `user-ui` | 提供跨端基础组件和主题 | 视图模型、主题 token | 可复用表现组件 |

### 2.5 关键流程

#### 2.5.1 新应用启动与环境初始化

1. `user-app` 启动后读取平台目标、环境配置和本地持久化状态。
2. 共享层恢复认证态、当前家庭、语言、主题和上次入口。
3. 平台适配层完成能力探测，返回当前平台支持的通知、权限、文件、分享、深链能力摘要。
4. 页面壳根据认证态和能力摘要进入登录、初始化向导或主应用。

#### 2.5.2 H5 平替 user-web

1. 先在 `user-app` 中建立与 `user-web` 对齐的页面路由和信息架构。
2. 共享层接管 `user-web` 当前 API、类型和核心状态逻辑。
3. H5 页面逐条替换核心用户链路。
4. 对齐清单满足退出条件后，把 H5 主入口切到 `user-app`。

#### 2.5.3 权限与通知

1. 页面调用统一权限服务，而不是直接碰平台 API。
2. 平台适配层根据目标平台执行真实查询和申请。
3. 结果被转换为统一状态：`granted / denied / blocked / unavailable / unknown`。
4. 通知注册、token 上报、通知点击跳转也走同一套服务。

#### 2.5.4 页面迁移

1. 先盘点 `user-web` 的页面和关键链路。
2. 抽取共享逻辑到 `user-core`。
3. 用 `user-ui` 和 Taro 组件重建页面壳。
4. 平台特有差异通过 `*.h5.ts`、`*.rn.ts`、`*.harmony.ts` 文件处理。

### 2.6 迁移策略

迁移分成四个大阶段：

1. 建新壳
   - 新建 `apps/user-app`
   - 建立 workspace 脚本、Taro 配置、分平台构建入口
2. 抽共享层
   - 把 `user-web` 里可复用的类型、API、状态、主题、i18n、实时逻辑拆出来
3. H5 平替
   - 让 `user-app` 的 H5 版本接管核心用户链路
4. 原生扩展与切流
   - 实现移动平台能力
   - 完成灰度、验收、回滚和 `user-web` 退场

### 2.7 user-web 退场策略

`user-web` 不是永久并行应用。它的生命周期必须被明确约束：

- 阶段 A：允许正常维护
  - `spec011` 立项前的现状
- 阶段 B：只修不增
  - `user-app` 启动后进入此阶段
  - 新功能默认只进 `user-app`
- 阶段 C：只保底
  - H5 已覆盖核心链路后
  - `user-web` 只保留阻断级缺陷修复
- 阶段 D：正式删除
  - 达到退出条件后，从仓库移除

退出条件至少包括：

1. `user-app` H5 核心链路对齐完成
2. 多端构建和发布链路可用
3. 通知、权限、文件、实时能力已通过平台验收
4. 灰度和回滚演练完成
5. 功能对齐清单无阻断缺口

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5、8

- `AppShell`
  - 新应用总壳，负责认证态、导航壳、平台能力摘要和主布局
- `BootstrapService`
  - 统一拉取认证态、家庭上下文、偏好设置和平台能力摘要
- `PlatformCapabilityService`
  - 对外暴露权限、通知、文件、分享、深链、实时、存储统一能力
- `FeatureParityRegistry`
  - 记录 `user-web` 和 `user-app` 的功能对齐状态
- `ReleaseGateService`
  - 控制灰度、入口切换和回滚条件

### 3.2 数据结构

覆盖需求：3、4、5、6、7

#### 3.2.1 `AppPlatformTarget`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `platform` | `h5 | rn-ios | rn-android | harmony` | 是 | 当前运行平台 | 枚举 |
| `runtime` | `h5 | rn | harmony` | 是 | 当前运行时 | 枚举 |
| `supports_push` | `boolean` | 是 | 是否支持推送注册 | 只读 |
| `supports_file_picker` | `boolean` | 是 | 是否支持文件选择 | 只读 |
| `supports_camera` | `boolean` | 是 | 是否支持拍照 | 只读 |
| `supports_share` | `boolean` | 是 | 是否支持系统分享 | 只读 |
| `supports_deeplink` | `boolean` | 是 | 是否支持深链唤起 | 只读 |

#### 3.2.2 `PermissionStatus`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `permission` | `notification | camera | photo | location | file` | 是 | 权限类型 | 枚举 |
| `status` | `granted | denied | blocked | unavailable | unknown` | 是 | 当前权限状态 | 枚举 |
| `can_request` | `boolean` | 是 | 当前是否还能主动申请 | 只读 |
| `reason` | `string | null` | 否 | 降级或失败原因 | 可空 |

#### 3.2.3 `NotificationPreference`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `member_id` | `string` | 是 | 所属成员 | 外键语义 |
| `channel` | `in_app | push | channel_plugin` | 是 | 通知渠道 | 枚举 |
| `enabled` | `boolean` | 是 | 是否启用 | 非空 |
| `quiet_hours_enabled` | `boolean` | 是 | 是否开启免打扰 | 非空 |
| `quiet_hours_start` | `string | null` | 否 | 开始时间 | `HH:mm` |
| `quiet_hours_end` | `string | null` | 否 | 结束时间 | `HH:mm` |
| `platform_overrides` | `Record<string, unknown> | null` | 否 | 平台特有策略 | 可空 |

#### 3.2.4 `FeatureParityItem`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `feature_key` | `string` | 是 | 功能唯一标识 | 唯一 |
| `legacy_entry` | `string` | 是 | 旧入口位置 | 非空 |
| `new_entry` | `string | null` | 否 | 新入口位置 | 可空 |
| `status` | `not_started | in_progress | ready | blocked | dropped` | 是 | 迁移状态 | 枚举 |
| `blocking_reason` | `string | null` | 否 | 阻塞原因 | 可空 |
| `owner` | `string | null` | 否 | 负责人 | 可空 |

### 3.3 接口契约

覆盖需求：4、5、6、7、8

#### 3.3.1 `BootstrapService.load()`

- 类型：Function / Service
- 输入：
  - 当前认证态
  - 平台目标
  - 本地持久化上下文
- 输出：
  - `actor`
  - `households`
  - `current_household`
  - `preferences`
  - `platform_capabilities`
  - `feature_gates`
- 校验：
  - 必须保证认证态和当前家庭一致
  - 本地缓存失效时优先以后端状态为准
- 错误：
  - 认证失效
  - 初始化超时
  - 配置不完整

#### 3.3.2 `PlatformCapabilityService`

- 类型：Function / Service
- 对外接口：
  - `getPlatformTarget()`
  - `getPermissionStatus(permission)`
  - `requestPermission(permission)`
  - `registerPushToken()`
  - `openSystemSettings()`
  - `pickFile(options)`
  - `captureMedia(options)`
  - `share(payload)`
  - `parseDeepLink(url)`
  - `connectRealtime(options)`
- 输入：
  - 权限类型、分享载荷、文件选择约束、实时连接参数
- 输出：
  - 统一结构结果，不暴露平台原始杂乱格式
- 校验：
  - 页面层只能依赖这个接口，不得直接调平台原生 API
- 错误：
  - 能力不可用
  - 权限拒绝
  - 用户取消
  - 平台实现失败

#### 3.3.3 `FeatureParityRegistry`

- 类型：HTTP / File / Tooling
- 路径或标识：
  - `docs/20260314-Taro4多端迁移阶段与切换原则.md`
  - `specs/011-.../tasks.md`
  - 后续可扩展为 `packages/user-testing/parity/*.json`
- 输入：
  - `user-web` 页面清单
  - `user-app` 实现状态
- 输出：
  - 功能对齐矩阵
  - 阻塞项列表
  - 下线前核对结果
- 校验：
  - 所有核心功能必须能映射到对齐项
- 错误：
  - 无映射项
  - 状态未更新

#### 3.3.4 通知注册接口

- 类型：HTTP
- 建议路径：
  - `POST /api/v1/app/device-tokens`
  - `DELETE /api/v1/app/device-tokens/{token_id}`
  - `GET /api/v1/members/{member_id}/notification-preferences`
  - `PUT /api/v1/members/{member_id}/notification-preferences`
- 输入：
  - 设备 token
  - 平台类型
  - 应用版本
  - 成员通知偏好
- 输出：
  - 注册结果
  - 当前通知策略
- 校验：
  - token 必须与成员和平台绑定
  - 偏好配置必须能落到统一模型
- 错误：
  - token 无效
  - 平台不支持
  - 权限未授予

#### 3.3.5 构建与发布接口

- 类型：Workspace Script / CI Job
- 标识：
  - `npm run build:user-app:h5`
  - `npm run build:user-app:ios`
  - `npm run build:user-app:android`
  - `npm run build:user-app:harmony`
- 输入：
  - 环境配置
  - 平台目标
  - 版本号
- 输出：
  - 对应平台构建产物
- 校验：
  - 四个平台构建必须互不污染环境
- 错误：
  - 平台配置缺失
  - 构建脚本失效

### 3.4 平台文件约定

覆盖需求：2、3、5、8

建议使用下面的文件约定：

- `index.ts`
  - 共享默认实现或导出
- `index.h5.ts`
  - H5 专有实现
- `index.rn.ts`
  - iOS / Android 通用实现
- `index.harmony.ts`
  - 鸿蒙实现

只有在共享实现走不通时才分平台，不要一上来就拆三份。

### 3.5 页面与分包策略

覆盖需求：2、4、8

建议主包先承载：

- 登录
- 初始化向导
- 首页
- 主导航壳

建议分包拆分：

- `family`
- `assistant`
- `memories`
- `settings`
- `plugins`

这样做的好处很简单：  
高频首屏先轻，低频复杂页后加载，不要把全部业务一次性塞进启动包。

## 4. 数据与状态模型

### 4.1 数据关系

- 一个成员对应一套通知偏好
- 一个运行平台对应一组能力摘要
- 一个页面功能对应一个对齐清单项
- `user-app` 页面不直接拥有平台能力细节，只依赖共享层和适配层
- `user-web` 到 `user-app` 的迁移状态必须能被追踪，而不是靠口头记忆

### 4.2 状态流转

#### 4.2.1 应用启动状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `booting` | 正在初始化应用 | 应用启动 | 完成启动检查 |
| `unauthenticated` | 未登录 | 鉴权无效 | 登录成功 |
| `hydrating` | 正在恢复本地上下文 | 登录后恢复缓存 | 完成恢复 |
| `ready` | 主应用可用 | 认证和上下文就绪 | 进入异常态或登出 |
| `degraded` | 部分能力不可用 | 平台能力或关键接口异常 | 异常恢复 |

#### 4.2.2 功能迁移状态

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `not_started` | 还没迁 | 尚未开始 | 开始实施 |
| `in_progress` | 正在迁 | 已开始开发 | 验收完成或阻塞 |
| `ready` | 已可切流 | 功能对齐完成 | 正式接管 |
| `blocked` | 被问题卡住 | 存在阻断缺口 | 问题解除 |
| `dropped` | 决定不迁 | 需求确认取消 | 终态 |

### 4.3 持久化策略

- 认证态、当前家庭、主题、语言、最近入口需要本地持久化
- 本地持久化必须通过 `user-platform/storage`
- 不允许在页面和状态文件里直接调用 `localStorage`、`sessionStorage` 等浏览器 API
- 平台侧存储失败时要有明确降级，不得导致主流程直接崩溃

## 5. 错误处理

### 5.1 错误类型

- `app_bootstrap_failed`
  - 启动初始化失败
- `platform_capability_unavailable`
  - 当前平台不支持某项能力
- `permission_request_failed`
  - 权限申请失败
- `notification_registration_failed`
  - 通知注册失败
- `legacy_parity_incomplete`
  - 功能对齐未完成，不能切流
- `release_gate_blocked`
  - 不满足发布或下线条件

### 5.2 错误响应格式

```json
{
  "detail": "当前平台暂不支持文件选择",
  "error_code": "platform_capability_unavailable",
  "field": null,
  "timestamp": "2026-03-14T00:00:00Z"
}
```

### 5.3 处理策略

1. 平台能力不可用
   - 返回明确降级说明
   - 页面显示禁用态，不展示假可用按钮
2. 权限拒绝
   - 保留当前页面上下文
   - 提供再次申请或跳系统设置入口
3. 通知注册失败
   - 不影响主业务页面使用
   - 在设置页给出明确失败摘要
4. 功能对齐未完成
   - 阻止入口切换和旧应用下线
5. 构建或发布阻断
   - 不影响其他平台产物
   - 明确标记具体平台失败

## 6. 正确性属性

### 6.1 页面层不得直接依赖浏览器特有 API

对于任何需要访问存储、权限、通知、文件、分享、深链、实时能力的页面，系统都应该通过平台适配层访问，而不是直接调用浏览器或原生平台 API。

**验证需求：** 需求 3、需求 8

### 6.2 H5 不完成核心链路对齐就不能替换 user-web

对于任何准备切到 `user-app` H5 的发布动作，系统都应该先满足功能对齐清单中的核心链路退出条件。

**验证需求：** 需求 4、需求 6、需求 7

### 6.3 user-web 不得在迁移期继续承接正式新功能

对于任何迁移立项后的新增用户端需求，系统都应该默认进入 `user-app`，除非它属于旧系统阻断级缺陷修复。

**验证需求：** 需求 1、需求 7

## 7. 测试策略

### 7.1 单元测试

- `user-core` 的 API client、视图模型、状态逻辑
- `user-platform` 的权限、通知、存储、深链、文件、分享、实时适配器
- 功能对齐清单校验工具

### 7.2 集成测试

- 应用启动到主壳进入的链路
- 登录、初始化向导、家庭切换、设置保存、通知偏好写回
- H5、RN、Harmony 的平台能力统一返回

### 7.3 端到端测试

- H5 核心用户链路平替 `user-web`
- iOS / Android 的登录、通知、权限、文件上传、实时会话
- 鸿蒙的登录、通知、权限、文件上传、实时会话
- 灰度切流和回滚验证

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` 2.1、2.6、2.7 | 架构评审、目录检查、迁移策略检查 |
| `requirements.md` 需求 2 | `design.md` 2.3、3.4 | 多平台构建验证、端到端测试 |
| `requirements.md` 需求 3 | `design.md` 2.2、3.3、3.4、4.3 | 代码审查、适配层单元测试 |
| `requirements.md` 需求 4 | `design.md` 2.5.2、2.7、4.2 | 功能对齐清单、H5 回归测试 |
| `requirements.md` 需求 5 | `design.md` 2.5.3、3.2.2、3.3.2、3.3.4 | 权限与通知测试、设置页联调 |
| `requirements.md` 需求 6 | `design.md` 2.6、2.7、5.3 | 灰度与回滚演练 |
| `requirements.md` 需求 7 | `design.md` 2.6、2.7、6.3 | 流程检查、需求流向审计 |
| `requirements.md` 需求 8 | `design.md` 2.1、2.2、3.4 | 代码结构检查、扩展性评审 |

## 8. 风险与待确认项

### 8.1 风险

- `user-web` 当前页面很大，特别是家庭页和全局样式，抽共享层时如果不先切边界，很容易把旧问题原样搬进新应用
- Taro 在不同目标上的组件和能力边界不完全相同，共享率不可能是 100%
- 通知、文件、权限、分享这些能力如果后端策略模型不统一，前端适配层会被迫写很多脏映射
- 如果迁移期间继续给 `user-web` 加新功能，整个计划会无限延期

### 8.2 待确认项

- iOS / Android 推送服务的服务商和证书管理方式由谁负责
- 鸿蒙目标的构建、签名、分发环境由谁维护
- 通知 token 注册接口是否复用现有成员偏好模型，还是单独新建 app 设备注册接口
- 当前 `user-web` 的哪些页面可以明确不迁，哪些必须完整平替
