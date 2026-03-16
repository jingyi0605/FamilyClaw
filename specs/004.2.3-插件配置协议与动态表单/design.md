# 设计文档 - 插件配置协议与动态表单

状态：Draft

## 1. 概述

### 1.1 目标

- 给插件系统补一层正式的配置协议
- 给后端补一层正式的配置实例持久化
- 给前端补一套通用动态表单渲染能力
- 先把 `channel` 迁进来，验证这套设计不是纸上谈兵

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4
- `requirements.md` 需求 5

### 1.3 技术约束

- 后端继续复用现有插件 manifest、注册中心和家庭上下文，不推翻插件系统
- 第一版**不引入完整 JSON Schema 标准**，只支持项目当前真正需要的字段子集
- 第一版配置作用域只支持 `plugin` 和 `channel_account`
- 涉及数据库表结构变更必须走 Alembic migration
- secret 字段必须走统一加密存储，不允许在数据库中明文落地
- 不能因为新增配置协议破坏现有插件启停、挂载和运行链路

## 2. 架构

### 2.1 系统结构

这次改造的核心不是多一个设置页，而是把插件配置收成一条清楚的数据链。

整体结构分四层：

1. **协议声明层**
   - 插件在 manifest 里声明 `config_schema` 和 `ui_schema`
   - 描述字段、默认值、校验和 UI 提示
2. **配置实例层**
   - 按家庭、插件、作用域保存真正的配置值
   - 把普通字段和 secret 字段分开存
3. **配置服务层**
   - 负责 schema 解析、默认值合并、后端校验、secret 处理和读写接口
4. **前端渲染层**
   - 根据协议动态渲染表单
   - 统一展示错误、帮助说明、secret 状态和保存反馈

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| manifest 配置协议 | 定义插件可配置项 | 插件 manifest | 配置描述 |
| `PluginConfigRepository` | 保存和读取配置实例 | 家庭、插件、作用域、配置值 | 配置记录 |
| `PluginConfigService` | 统一校验、默认值合并、secret 处理 | 配置描述、提交值、已存值 | 可保存记录或字段错误 |
| 配置 API | 给前端提供 schema、当前值、保存入口 | 家庭上下文、插件 id、scope | JSON 响应 |
| `DynamicPluginConfigForm` | 动态渲染表单 | 配置描述、当前值、错误 | 用户可交互表单 |
| `ChannelConfigAdapter` | 把 `channel` 现有配置页接到新协议 | 通道插件、账号实体 | 统一插件配置读写 |

### 2.3 关键流程

#### 2.3.1 打开插件配置页

1. 前端请求插件可用的配置作用域列表。
2. 后端从 manifest 解析出该插件的配置描述。
3. 后端读取当前家庭、当前作用域下的配置实例。
4. 后端返回 schema、UI schema、当前值、secret 状态和配置状态。
5. 前端 renderer 按协议生成表单。

#### 2.3.2 保存插件配置

1. 用户在表单里修改字段并提交。
2. 前端把普通字段值和显式清空的 secret 字段一起提交。
3. 后端按 manifest 配置协议统一校验。
4. 校验通过后，普通字段写入 `data_json`，secret 字段写入加密存储。
5. 后端返回最新配置视图，前端刷新表单状态。

#### 2.3.3 `channel` 配置迁移到通用协议

1. 通道插件 manifest 补上正式 `config_schema` 和 `ui_schema`。
2. `SettingsChannelAccessPage` 不再维护平台字段常量，而是请求通道插件配置协议。
3. 原有通道账号配置写入通用配置实例表，`scope_type` 使用 `channel_account`。
4. 页面保留现有业务语义，但字段定义和渲染逻辑改为统一协议驱动。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5

- `PluginManifestConfigSpec`：插件 manifest 中的配置定义
- `PluginConfigField`：单个配置字段定义
- `PluginUiSchema`：表单布局和控件提示定义
- `PluginConfigInstance`：落库后的某份配置实例
- `PluginConfigView`：读接口返回给前端的配置视图
- `DynamicPluginConfigForm`：前端通用 renderer

### 3.2 数据结构

覆盖需求：1、2、3、4

#### 3.2.1 `PluginManifestConfigSpec`

每个插件可以声明零个或多个配置作用域。第一版只允许这两个：

- `plugin`：当前家庭下，这个插件只有一份配置
- `channel_account`：当前家庭下，这个通道插件的某个账号实例有一份配置

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `scope_type` | string | 是 | 配置作用域 | 仅支持 `plugin` / `channel_account` |
| `title` | string | 是 | 页面标题 | 给前端直接展示 |
| `description` | string | 否 | 页面说明 | 人能看懂的话 |
| `schema_version` | integer | 是 | schema 版本 | 从 `1` 开始递增 |
| `config_schema` | object | 是 | 数据字段定义 | 结构见下文 |
| `ui_schema` | object | 是 | UI 展示定义 | 结构见下文 |

说明：

- 一个插件没有 `PluginManifestConfigSpec`，就表示“这个插件没有可配置项”
- 不支持插件在运行时动态拼接任意 schema
- 不支持用任意 JS 表达式控制表单行为

#### 3.2.2 `PluginConfigField`

第一版支持的字段类型只保留实际要用到的最小集合：

- `string`
- `text`
- `integer`
- `number`
- `boolean`
- `enum`
- `multi_enum`
- `secret`
- `json`

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `key` | string | 是 | 字段唯一键 | 同一 spec 内唯一 |
| `label` | string | 是 | 字段标题 | 给前端展示 |
| `type` | string | 是 | 字段类型 | 只能是支持集合之一 |
| `required` | boolean | 是 | 是否必填 | 默认 `false` |
| `description` | string | 否 | 字段说明 | 给用户看 |
| `default` | any | 否 | 默认值 | 必须符合字段类型 |
| `enum_options` | array | 否 | 枚举选项 | `enum` / `multi_enum` 使用 |
| `min_length` | integer | 否 | 最小长度 | 仅字符串类字段 |
| `max_length` | integer | 否 | 最大长度 | 仅字符串类字段 |
| `minimum` | number | 否 | 最小值 | 数值类字段 |
| `maximum` | number | 否 | 最大值 | 数值类字段 |
| `pattern` | string | 否 | 正则校验 | 仅字符串类字段 |
| `nullable` | boolean | 否 | 是否允许空值 | 默认 `false` |

规则定死：

- `secret` 是数据语义，不是 UI widget 名称
- `enum_options` 只支持静态选项，第一版不做远程异步拉取
- `json` 字段按 JSON 对象或数组整体校验，不支持子路径级联表单

#### 3.2.3 `PluginUiSchema`

`ui_schema` 只负责“怎么展示”，不负责“什么数据合法”。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `sections` | array | 是 | 表单分组 | 至少一组 |
| `field_order` | array | 否 | 全局字段顺序 | 不写则按 schema 顺序 |
| `submit_text` | string | 否 | 提交按钮文案 | 默认“保存配置” |

`sections` 中的每一项包含：

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | 分组 id | 同一 spec 内唯一 |
| `title` | string | 是 | 分组标题 | 给前端展示 |
| `description` | string | 否 | 分组说明 | 可为空 |
| `fields` | array | 是 | 字段 key 列表 | 必须全部出现在 schema 中 |

字段级 UI 提示统一放在 `widgets` 里：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `widget` | string | 否 | `input` / `password` / `textarea` / `switch` / `select` / `multi_select` / `json_editor` |
| `placeholder` | string | 否 | 占位文本 |
| `help_text` | string | 否 | 补充说明 |
| `visible_when` | array | 否 | 简单显示条件 |

`visible_when` 第一版只支持简单比较：

- `equals`
- `not_equals`
- `in`
- `truthy`

不支持任意脚本表达式。

#### 3.2.4 `plugin_config_instances`

这张表是配置持久化的核心。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | uuid | 是 | 主键 | 系统生成 |
| `household_id` | uuid | 是 | 家庭 id | 外键 |
| `plugin_id` | string | 是 | 插件稳定 id | 必须可解析到插件注册项 |
| `scope_type` | string | 是 | 配置作用域 | `plugin` / `channel_account` |
| `scope_key` | string | 是 | 作用域实例键 | `plugin` 作用域固定为 `default` |
| `schema_version` | integer | 是 | 保存时使用的 schema 版本 | 必须大于 0 |
| `data_json` | jsonb | 是 | 非 secret 字段值 | 只存用户显式保存的值 |
| `secret_data_encrypted` | text | 否 | 加密后的 secret JSON | 不允许明文 |
| `updated_by` | uuid | 否 | 最近操作人 | 用于排查 |
| `created_at` | datetime | 是 | 创建时间 | 系统生成 |
| `updated_at` | datetime | 是 | 更新时间 | 系统生成 |

约束：

- 唯一键：`household_id + plugin_id + scope_type + scope_key`
- `scope_type = plugin` 时，`scope_key` 固定为 `default`
- `secret_data_encrypted` 的明文结构只允许在应用内解密，不允许在接口层原样回传

#### 3.2.5 `PluginConfigView`

这是前端真正消费的读模型。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `scope_type` | string | 是 | 当前作用域 |
| `scope_key` | string | 是 | 当前作用域实例键 |
| `schema_version` | integer | 是 | 当前协议版本 |
| `state` | string | 是 | `unconfigured` / `configured` / `invalid` |
| `values` | object | 是 | 非 secret 当前值，加上默认值填充后的结果 |
| `secret_fields` | object | 是 | 每个 secret 字段的 `has_value` / `masked` 状态 |
| `field_errors` | object | 否 | 当前协议下未通过校验的字段错误 |

### 3.3 接口契约

覆盖需求：2、3、4、5

#### 3.3.1 获取插件可配置作用域

- 类型：HTTP
- 路径或标识：`GET /ai-config/{household_id}/plugins/{plugin_id}/config-scopes`
- 输入：`household_id`、`plugin_id`
- 输出：当前插件声明了哪些 `scope_type`，以及每个 scope 的标题、说明和可用实例提示
- 校验：插件必须存在，且当前家庭可见
- 错误：插件不存在或 manifest 配置协议非法时返回明确错误

说明：

- 这个接口用于告诉前端“这个插件有没有配置、配置放在哪些入口”
- 没有 scope 并不代表插件坏了，只代表它没有配置项

#### 3.3.2 读取某个作用域的配置表单

- 类型：HTTP
- 路径或标识：`GET /ai-config/{household_id}/plugins/{plugin_id}/config`
- 输入：`household_id`、`plugin_id`、`scope_type`、`scope_key`
- 输出：`PluginManifestConfigSpec` + `PluginConfigView`
- 校验：`scope_type` 必须被该插件声明；`scope_key` 必须匹配当前家庭下合法实例
- 错误：scope 不存在、实例不存在、schema 解析失败时返回明确错误

说明：

- 这是前端动态表单的主读取接口
- 对 `plugin` 作用域，前端固定传 `scope_key=default`

#### 3.3.3 保存某个作用域的配置

- 类型：HTTP
- 路径或标识：`PUT /ai-config/{household_id}/plugins/{plugin_id}/config`
- 输入：
  - `scope_type`
  - `scope_key`
  - `values`
  - `clear_secret_fields`
- 输出：最新 `PluginConfigView`
- 校验：后端按 manifest schema 统一校验
- 错误：字段校验失败、scope 非法、权限不足时返回字段级错误和结构化错误码

说明：

- secret 字段如果未出现在 `values` 中，表示“保持原值”
- secret 字段如果出现在 `clear_secret_fields` 中，表示“显式清空”
- 这条语义要统一，前端和后端都不允许自己发明另一套约定

## 4. 数据与状态模型

### 4.1 数据关系

- 插件注册表负责说明插件“是什么”
- 配置协议负责说明插件“需要配什么”
- 配置实例表负责说明当前家庭“实际配了什么”
- 前端 renderer 和业务页面只消费配置读模型，不直接猜数据库结构

说成人话：

1. manifest 管字段定义。
2. 配置表管具体值。
3. 页面只管展示和提交。

不要再让某个页面自己维护一份平台字段常量，然后后端再偷偷维护另一份。

### 4.2 配置状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `unconfigured` | 当前作用域没有保存记录 | 初始状态或迁移前 | 首次保存成功 |
| `configured` | 当前配置存在且通过当前 schema 校验 | 保存成功或兼容读取成功 | schema 校验失败或被删除 |
| `invalid` | 当前配置记录存在，但不符合当前 schema | schema 升级后旧值不合法，或脏数据写入 | 用户修正并重新保存 |

关键规则：

- `invalid` 不是 silent fallback，前端必须能看见
- `configured` 的 secret 字段也不能回显明文
- schema 升级后如果旧值还能兼容，系统应继续按 `configured` 读取，不强行打成 `invalid`

## 5. 错误处理

### 5.1 错误类型

- `plugin_config_schema_invalid`：manifest 里的配置协议不合法
- `plugin_config_scope_invalid`：请求了插件未声明的 scope
- `plugin_config_instance_not_found`：请求的作用域实例不存在
- `plugin_config_validation_failed`：提交值不符合 schema
- `plugin_config_secret_invalid`：secret 字段语义错误，比如把清空和保留混用

### 5.2 错误响应格式

```json
{
  "detail": "字段 bot_token 不能为空。",
  "error_code": "plugin_config_validation_failed",
  "field_errors": {
    "bot_token": "请输入有效的机器人 token。"
  },
  "timestamp": "2026-03-16T00:00:00Z"
}
```

### 5.3 处理策略

1. manifest 协议错误：在插件加载阶段就报错，不把坏 schema 放进运行态。
2. 字段校验错误：按字段返回，前端直接定位到具体表单项。
3. secret 读接口：永远只返回 `has_value` 和 `masked`，不回显密文或明文。
4. 旧配置不兼容：标记为 `invalid`，让用户看到问题并修正，不要偷偷丢字段。

## 6. 正确性属性

### 6.1 属性 1：字段协议和表单渲染使用同一份定义

*对于任何* 有配置的插件，系统都应该满足：后端校验所用字段定义和前端渲染所用字段定义来自同一份 manifest 配置协议。

**验证需求：** 需求 1、需求 3、需求 4

### 6.2 属性 2：secret 字段不会在读接口泄漏

*对于任何* 被标记为 `secret` 的字段，系统都应该满足：读取配置时不会返回其明文值。

**验证需求：** 需求 4

### 6.3 属性 3：没有配置协议的插件不会被这次改造搞坏

*对于任何* 尚未声明配置协议的旧插件，系统都应该满足：列表展示、启停和执行逻辑保持现有行为。

**验证需求：** 需求 5、非功能需求 1

### 6.4 属性 4：`channel` 迁移后不再维护第二套字段定义

*对于任何* 首批迁移到新协议的通道插件，系统都应该满足：页面字段、后端校验和持久化结构都来自统一协议，而不是一半来自页面常量、一半来自后端特判。

**验证需求：** 需求 5

## 7. 测试策略

### 7.1 单元测试

- manifest 配置协议解析测试
- 字段类型、默认值和显示条件规则测试
- secret 保留、更新、清空语义测试
- `PluginConfigService` 校验与合并逻辑测试

### 7.2 集成测试

- 插件配置实例读写接口测试
- schema 版本升级后的兼容读取测试
- `channel_account` 作用域配置读写测试
- 没有配置协议的旧插件兼容测试

### 7.3 端到端测试

- 打开插件详情页，按协议渲染配置表单并保存成功
- 打开通道配置页，使用统一 renderer 完成账号配置
- secret 字段保存后刷新页面，不回显明文但能显示“已配置”
- 提交非法字段后页面准确显示字段级错误

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.1、§3.2.1、§3.2.2、§3.2.3 | 协议解析测试、manifest 走查 |
| `requirements.md` 需求 2 | `design.md` §2.3.2、§3.2.4、§3.3.2、§3.3.3 | 配置读写接口测试、migration 校验 |
| `requirements.md` 需求 3 | `design.md` §2.3.1、§3.2.3、§3.3.2 | 前端 renderer 测试、页面联调 |
| `requirements.md` 需求 4 | `design.md` §3.2.2、§3.2.4、§5.3、§6.2 | 校验测试、secret 读写测试 |
| `requirements.md` 需求 5 | `design.md` §2.3.3、§4.1、§6.3、§6.4 | `channel` 迁移联调、旧插件兼容测试 |

## 8. 风险与待确认项

### 8.1 风险

- 如果第一版协议贪大，试图直接兼容完整 JSON Schema，最后只会把实现拖死。
- 如果 secret 仍然落明文，这份设计就是假安全。
- 如果 `channel` 页面迁移时保留一套旧字段常量，这次改造就只是在外面套了一层皮。

### 8.2 待确认项

- 当前项目里是否已有统一加密工具可直接复用到 `secret_data_encrypted`
- `channel_account` 的 `scope_key` 最终使用数据库主键还是稳定业务键
- 后续是否需要在下一份 Spec 里补“配置历史版本与审计”，但这轮先不展开
