# 设计文档 - 第三方插件仪表盘卡片开放

状态：Draft

## 1. 概述

### 1.1 目标

- 给现有插件系统补一条正式的首页卡片开放链路
- 让首页从“硬编码卡片注册表”收口成“统一卡片模型 + 统一聚合接口 + 统一渲染器”
- 保证第三方插件只能提供声明和数据，不能把任意前端代码塞进首页
- 保证插件卡片故障只影响自己，不破坏首页主链路

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4
- `requirements.md` 需求 5

### 1.3 技术约束

- 后端：继续复用 `apps/api-server` 现有插件 manifest、插件配置协议、插件启停和后台任务体系
- 前端：只修改 `apps/user-app`，不新增 `user-web` 功能
- 数据存储：继续使用现有数据库与 Alembic migration，不允许绕过迁移系统补表
- 认证授权：首页读取沿用当前成员态访问控制；插件卡片的管理和配置入口继续走现有权限边界
- 安全边界：第一版明确禁止第三方直接注入 React 组件、HTML、CSS、JavaScript

## 2. 架构

### 2.1 系统结构

整体结构分五层：

1. **卡片声明层**
   - 插件在 manifest 里声明 `dashboard_cards`
   - 说明卡片放哪里、用什么模板、允许哪些动作
2. **卡片快照层**
   - 插件运行后把展示数据写成卡片快照
   - 首页只读快照，不直接执行插件
3. **布局层**
   - 系统按成员保存首页卡片顺序、显隐和尺寸偏好
   - 统一管理内置卡片和插件卡片
4. **首页聚合层**
   - 后端聚合内置卡片、插件卡片、布局
   - 清理无效卡片，生成前端可直接消费的首页模型
5. **统一渲染层**
   - `user-app` 首页只认官方模板
   - 插件只提供数据，不控制渲染器实现

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `PluginManifest.dashboard_cards` | 声明插件卡片元数据 | 插件 manifest | 卡片定义 |
| `PluginDashboardCardService` | 校验卡片声明、管理快照读写 | 插件、快照、家庭上下文 | 快照记录、聚合结果 |
| `MemberDashboardLayoutService` | 保存和清理成员布局 | 成员、卡片列表、布局请求 | 标准布局 |
| `HomeDashboardAggregator` | 合并内置卡片、插件卡片、布局 | 家庭、成员、快照 | 首页读模型 |
| `HomeCardRenderer` | 按模板渲染首页卡片 | 首页读模型 | 统一 UI |

### 2.3 关键流程

#### 2.3.1 插件声明首页卡片

1. 插件在 manifest 中增加 `dashboard_cards`。
2. 系统加载 manifest 时校验卡片位置、模板、尺寸、动作和文案键。
3. 合法声明进入插件注册结果；非法声明阻止该插件卡片能力生效。
4. 没声明 `dashboard_cards` 的插件继续作为普通插件存在。

#### 2.3.2 插件生成卡片快照

1. 插件通过受控后端入口提交某张卡片的快照数据。
2. 后端按卡片定义校验模板字段、动作字段、大小限制和过期时间。
3. 校验通过后写入卡片快照表，并更新生成时间与状态。
4. 校验失败时记录错误状态，不污染首页聚合结果。

#### 2.3.3 用户打开首页

1. 前端请求统一首页接口。
2. 后端读取当前成员布局。
3. 后端读取内置卡片数据和当前家庭下所有可见插件卡片快照。
4. 聚合层剔除失效、禁用、权限不足或声明非法的卡片。
5. 后端返回首页读模型，前端统一渲染。

#### 2.3.4 用户调整首页布局

1. 用户拖动、隐藏或恢复首页卡片。
2. 前端提交新的成员布局。
3. 后端校验卡片 key 是否存在、是否可见、是否重复。
4. 后端保存标准化布局，并在读取时自动补齐新卡片、剔除失效卡片。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5

- `PluginManifestDashboardCardSpec`：manifest 中的单张卡片定义
- `PluginDashboardCardSnapshot`：某张插件卡片的最新展示快照
- `MemberDashboardLayout`：成员首页布局持久化模型
- `HomeDashboardRead`：首页聚合读模型
- `HomeDashboardCardRenderer`：`user-app` 的统一卡片渲染器

### 3.2 数据结构

覆盖需求：1、2、3、4、5

#### 3.2.1 `PluginManifestDashboardCardSpec`

第一版只支持 `placement = home`，只支持有限模板。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `card_key` | string | 是 | 插件内稳定卡片键 | 同一插件内唯一 |
| `placement` | string | 是 | 卡片放置位置 | 第一版仅支持 `home` |
| `template_type` | string | 是 | 官方模板类型 | 仅支持 `metric` / `status_list` / `timeline` / `insight` / `action_group` |
| `size` | string | 是 | 默认尺寸 | 仅支持 `half` / `full` |
| `title_key` | string | 是 | i18n 标题 key | 不能为空 |
| `subtitle_key` | string | 否 | i18n 副标题 key | 可为空 |
| `empty_state_key` | string | 否 | 空态文案 key | 可为空 |
| `refresh_strategy` | string | 是 | 刷新策略 | 仅支持 `manual` / `scheduled` / `event_driven` |
| `max_items` | integer | 否 | 列表型卡片最大项数 | 1 到 20 |
| `allowed_actions` | array | 否 | 允许动作类型 | 仅支持白名单动作 |

规则：

- 不允许声明自定义前端资源路径
- 不允许声明任意脚本表达式
- 只允许声明系统支持的模板和动作

#### 3.2.2 `plugin_dashboard_card_snapshots`

这张表保存插件卡片的最新展示结果。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | uuid | 是 | 主键 | 系统生成 |
| `household_id` | uuid | 是 | 家庭 id | 外键 |
| `plugin_id` | string | 是 | 插件 id | 必须能解析到注册插件 |
| `card_key` | string | 是 | 卡片键 | 必须能匹配 manifest 声明 |
| `placement` | string | 是 | 卡片位置 | 第一版固定 `home` |
| `payload_json` | jsonb/text | 是 | 模板数据 | 必须符合模板 schema |
| `state` | string | 是 | 当前状态 | `ready` / `stale` / `invalid` / `error` |
| `error_code` | string | 否 | 错误码 | 失败时可为空或有值 |
| `error_message` | text | 否 | 错误说明 | 便于排查 |
| `generated_at` | datetime | 否 | 最近生成时间 | 成功生成时必填 |
| `expires_at` | datetime | 否 | 过期时间 | 可为空 |
| `created_at` | datetime | 是 | 创建时间 | 系统生成 |
| `updated_at` | datetime | 是 | 更新时间 | 系统生成 |

唯一键建议：

- `household_id + plugin_id + placement + card_key`

#### 3.2.3 `member_dashboard_layouts`

这张表保存成员首页布局。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | uuid | 是 | 主键 | 系统生成 |
| `member_id` | uuid | 是 | 成员 id | 外键 |
| `placement` | string | 是 | 布局位置 | 第一版固定 `home` |
| `layout_json` | jsonb/text | 是 | 布局定义 | 只保存标准结构 |
| `created_at` | datetime | 是 | 创建时间 | 系统生成 |
| `updated_at` | datetime | 是 | 更新时间 | 系统生成 |

`layout_json` 第一版结构：

```json
{
  "items": [
    {
      "card_ref": "builtin:weather",
      "visible": true,
      "order": 10,
      "size": "half"
    },
    {
      "card_ref": "plugin:channel-telegram:home:summary",
      "visible": true,
      "order": 20,
      "size": "full"
    }
  ]
}
```

#### 3.2.4 `HomeDashboardRead`

这是首页接口真正返回给前端的读模型。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `household_id` | string | 是 | 当前家庭 |
| `member_id` | string | 是 | 当前成员 |
| `layout_version` | integer | 是 | 当前布局版本 |
| `cards` | array | 是 | 最终可展示卡片列表 |
| `warnings` | array | 否 | 非阻断级警告 |

`cards[]` 的统一字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `card_ref` | string | 是 | 统一卡片引用 |
| `source_type` | string | 是 | `builtin` / `plugin` |
| `template_type` | string | 是 | 官方模板 |
| `size` | string | 是 | `half` / `full` |
| `state` | string | 是 | `ready` / `empty` / `stale` / `error` |
| `title` | string | 是 | 已翻译标题 |
| `subtitle` | string | 否 | 已翻译副标题 |
| `payload` | object | 是 | 模板数据 |
| `actions` | array | 否 | 受控动作列表 |

### 3.3 接口契约

覆盖需求：1、2、3、4、5

#### 3.3.1 首页聚合读取接口

- 类型：HTTP
- 路径或标识：`GET /dashboard/home`
- 输入：当前成员会话、当前家庭上下文
- 输出：`HomeDashboardRead`
- 校验：必须能解析当前成员和家庭；只返回当前成员可见的卡片
- 错误：认证失败、家庭不可见、聚合异常时返回结构化错误；单卡异常不得升级成整页错误

#### 3.3.2 成员首页布局保存接口

- 类型：HTTP
- 路径或标识：`PUT /dashboard/home/layout`
- 输入：卡片顺序、显隐、尺寸
- 输出：标准化后的布局结果
- 校验：
  - `card_ref` 不能重复
  - 只能提交当前成员可见卡片
  - 尺寸必须符合卡片定义允许范围
- 错误：布局项重复、引用无效卡片、字段非法时返回结构化错误

#### 3.3.3 插件卡片快照写入入口

- 类型：Function / Service
- 路径或标识：`PluginDashboardCardService.upsert_snapshot(...)`
- 输入：`household_id`、`plugin_id`、`card_key`、`payload`、`expires_at`
- 输出：快照写入结果
- 校验：
  - 插件必须声明该卡片
  - `payload` 必须符合模板字段限制
  - 动作必须属于白名单
  - 大小、条目数、文本长度必须受限
- 错误：未声明卡片、模板不匹配、payload 非法、插件不可见

## 4. 数据与状态模型

### 4.1 数据关系

- 插件注册表负责回答“这个插件声明了哪些卡片”
- 卡片快照表负责回答“这张卡片现在展示什么”
- 成员布局表负责回答“这个成员想把哪些卡片摆成什么顺序”
- 首页聚合结果负责回答“当前这个成员最终会看到什么”

说成人话：

1. manifest 定义卡片身份和边界  
2. snapshot 提供卡片内容  
3. layout 决定卡片怎么摆  
4. 首页接口只做合并，不直接猜业务细节

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `ready` | 快照可正常展示 | 最新快照校验通过且未过期 | 快照过期、被覆盖或校验失败 |
| `stale` | 可展示但已过期 | 快照过期但仍允许保守展示 | 新快照生成成功或卡片被移除 |
| `invalid` | 快照结构非法 | 写入时或读取时校验失败 | 插件重新写入合法快照 |
| `error` | 插件生成或读取失败 | 生成异常或依赖异常 | 新快照生成成功或卡片被移除 |

关键规则：

- `invalid` 和 `error` 只影响该卡片
- 首页聚合读取必须能识别并隔离坏卡片
- 被禁用或不可见的插件卡片不进入最终读模型

## 5. 错误处理

### 5.1 错误类型

- `plugin_dashboard_card_spec_invalid`：manifest 里的卡片声明非法
- `plugin_dashboard_card_not_declared`：插件写入了未声明卡片
- `plugin_dashboard_card_payload_invalid`：卡片 payload 不符合模板要求
- `member_dashboard_layout_invalid`：布局请求结构非法
- `member_dashboard_card_not_visible`：布局提交了当前不可见卡片

### 5.2 错误响应格式

```json
{
  "detail": "卡片 payload 不符合模板要求",
  "error_code": "plugin_dashboard_card_payload_invalid",
  "field": "payload.items[0].title",
  "timestamp": "2026-03-16T00:00:00Z"
}
```

### 5.3 处理策略

1. 输入验证错误：拒绝写入，返回字段级错误
2. 业务规则错误：拒绝该卡片或该布局请求，不影响其他卡片
3. 外部依赖错误：将卡片标记为 `error` 或 `stale`，首页继续返回其他卡片
4. 重试、降级或补偿：
   - 快照刷新走后台任务或事件驱动
   - 读取优先已有快照
   - 卡片坏了就降级，不在首页请求里补跑插件

## 6. 正确性属性

### 6.1 属性 1：首页不直接执行第三方插件

*对于任何* 首页读取请求，系统都应该满足：首页以读取聚合结果和卡片快照为主，不把第三方插件执行放进首屏同步路径。

**验证需求：** `requirements.md` 需求 2、需求 5

### 6.2 属性 2：第三方插件不能注入任意前端执行

*对于任何* 第三方插件卡片，系统都应该满足：插件只能声明受控模板和受控动作，不能把任意前端代码直接放进首页。

**验证需求：** `requirements.md` 需求 1、需求 3

### 6.3 属性 3：坏卡片不会拖垮整页

*对于任何* 单张插件卡片失败、超时或结构非法的情况，系统都应该满足：首页仍能返回其他可用卡片，且问题可被定位到具体卡片。

**验证需求：** `requirements.md` 需求 2、需求 5

## 7. 测试策略

### 7.1 单元测试

- manifest 卡片声明校验
- 卡片 payload 模板校验
- 布局标准化与无效卡片清理
- 聚合层对禁用、失效、过期卡片的过滤逻辑

### 7.2 集成测试

- 插件声明卡片后生成快照并进入首页聚合结果
- 插件禁用后卡片从首页移除
- 成员保存布局后首页顺序正确
- 坏快照存在时首页仍能返回其他卡片

### 7.3 端到端测试

- `user-app` 首页展示内置卡片和插件卡片
- 用户拖动或隐藏卡片后刷新页面仍保持结果
- 插件卡片报错时首页展示降级结果而不是整页崩溃

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.3.1、§3.2.1、§3.3.3 | manifest 校验测试、插件声明集成测试 |
| `requirements.md` 需求 2 | `design.md` §2.3.3、§3.2.4、§4.2 | 首页聚合接口测试、首页人工回归 |
| `requirements.md` 需求 3 | `design.md` §3.2.1、§3.3.3、§6.2 | 模板/动作白名单测试 |
| `requirements.md` 需求 4 | `design.md` §2.3.4、§3.2.3、§3.3.2 | 布局保存接口测试、前端回归 |
| `requirements.md` 需求 5 | `design.md` §4.2、§5.3、§6.3 | 降级与故障隔离测试 |

## 8. 风险与待确认项

### 8.1 风险

- 现有首页卡片仍是前端硬编码，迁到统一模型时容易把内置卡片和插件卡片逻辑搅在一起
- 如果模板字段定义收得不够紧，后面容易被插件 payload 反向绑架前端实现
- 成员布局从本地缓存迁到后端后，需要处理旧数据兼容和多端同步

### 8.2 待确认项

- 第一版是否需要把现有全部内置卡片都纳入统一后端布局，还是先允许“内置卡片 + 插件卡片”双轨过渡
- 插件卡片快照的刷新触发，优先走计划任务、事件驱动还是人工刷新
- 首页接口是否与现有 `context/overview` 聚合到同一入口，还是拆成独立 `dashboard/home`
