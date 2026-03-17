# 设计文档 - 小爱音箱插件界面与声纹管理迁移

状态：Draft

## 1. 概述

### 1.1 目标

- 把小爱专属“语音接管”从宿主硬编码里拆出来，挂到正式插件页签
- 把“声纹管理”定义成平台通用页签，而不是小爱专属逻辑
- 给插件体系补齐设备详情扩展点和设备级配置落点
- 用兼容迁移方式完成收口，不砸现有语音主链

### 1.2 覆盖需求

- `requirements.md` 需求 1
- `requirements.md` 需求 2
- `requirements.md` 需求 3
- `requirements.md` 需求 4
- `requirements.md` 需求 5
- `requirements.md` 需求 6
- `requirements.md` 需求 7

### 1.3 技术约束

- 后端：`apps/api-server`
- 前端：`apps/user-app`
- 数据存储：PostgreSQL + Alembic
- 插件配置协议现状：正式只支持 `plugin`、`channel_account`
- 现有小爱语音接管与声纹能力仍有旧 `Device` 字段依赖，不能直接硬砍
- 这次不做插件前端 bundle 动态加载

## 2. 架构

### 2.1 系统结构

这次只动设备详情入口，不动语音执行主链。

目标结构分三层：

1. 宿主设备详情容器
   - 负责加载设备基础信息
   - 负责根据能力和插件声明组合页签
   - 负责渲染统一标签页 UI

2. 插件专属页签层
   - 只承载插件私有配置
   - 首版只支持“按正式配置协议渲染动态表单”
   - 不负责执行动作，不负责声纹业务

3. 平台通用页签层
   - 负责所有语音终端通用能力
   - 首版这里只有“声纹管理”
   - 由平台现有 `voiceprint` 接口和设备能力判断驱动

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `plugin manifest / registry` | 声明插件是否提供设备详情页签、页签适用条件、配置 schema | 插件 manifest | 设备页签声明 |
| `plugin config service` | 提供设备级插件配置读写能力 | `device_id`、`plugin_id`、配置值 | 配置表单、校验结果 |
| `device detail service` | 聚合设备详情、设备能力、插件页签和通用页签 | `device_id` | 设备详情视图模型 |
| `user-app 设备详情容器` | 按统一规则渲染标签页 | 设备详情视图模型 | UI 标签页 |
| `voiceprint service` | 提供通用声纹 summary、建档和更新能力 | `terminal_id`、`household_id` | 通用声纹页签数据 |

### 2.3 关键流程

#### 2.3.1 打开设备详情

1. 前端请求设备详情视图模型。
2. 后端返回设备基础信息、设备能力标记、可见的插件页签声明、可见的通用页签声明。
3. 宿主前端按统一标签页组件渲染，不再按插件 id 手写分支。
4. 默认打开首个可见页签。

#### 2.3.2 打开小爱语音接管页签

1. 宿主根据插件页签声明识别该页签属于 `open-xiaoai-speaker`。
2. 宿主请求设备级插件配置表单。
3. 宿主用统一动态表单 renderer 渲染 `voice_auto_takeover_enabled`、`voice_takeover_prefixes`。
4. 保存时写入正式设备级插件配置，并同步兼容字段。

#### 2.3.3 打开声纹管理页签

1. 宿主根据设备能力判断设备是否具备 `voice_terminal` / `voiceprint_supported` 能力。
2. 如果具备，则渲染平台通用“声纹管理”页签。
3. 页签继续调用平台现有 `voiceprints` summary、建档和更新接口。
4. 该页签不关心设备来自哪个插件，只关心设备能力和 `terminal_id`。

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5、7

- `PluginManifestDeviceDetailTabSpec`
  - 插件在 manifest 里声明的设备详情页签定义
- `DevicePluginConfigFormRead`
  - 设备级插件配置表单读取结果
- `DeviceDetailViewRead`
  - 设备详情聚合返回模型
- `DevicePluginTabRenderer`
  - 前端宿主里按统一配置协议渲染插件页签的组件
- `VoiceTerminalCapabilityResolver`
  - 从设备绑定、能力快照或聚合视图里判断设备是否支持语音终端能力的服务

### 3.2 数据结构

覆盖需求：2、3、5、6

#### 3.2.1 `PluginManifestDeviceDetailTabSpec`

建议新增到插件 manifest 的能力声明里，首版挂在 `capabilities.admin_ui.device_detail_tabs` 或等价正式位置。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `tab_id` | `string` | 是 | 页签唯一标识 | 同一插件内唯一 |
| `title` | `string` | 是 | 页签标题 | 1-50 字 |
| `render_mode` | `enum` | 是 | 首版固定为 `config_form` | 不支持自定义 bundle |
| `scope_type` | `enum` | 是 | 首版固定为 `device` | 对应设备级配置 |
| `match` | `object` | 是 | 页签适用条件 | 至少包含一条条件 |
| `order` | `integer` | 否 | 页签排序 | 默认 100 |

`match` 建议支持：

- `device_type`
- `vendor`
- `adapter_type`
- `plugin_id`
- `capability_tags`

首版小爱页签可以简单声明：

- `plugin_id = open-xiaoai-speaker`
- `device_type = speaker`
- `adapter_type = open_xiaoai`

#### 3.2.2 `DevicePluginConfigInstance`

推荐方案：直接把正式配置作用域扩成 `device`。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `uuid/text` | 是 | 配置实例主键 | 唯一 |
| `household_id` | `text` | 是 | 家庭 id | 外键 |
| `plugin_id` | `text` | 是 | 插件 id | 索引 |
| `device_id` | `text` | 是 | 设备 id | 外键、索引 |
| `scope_type` | `enum` | 是 | 固定 `device` | 正式作用域 |
| `scope_key` | `text` | 是 | 固定等于 `device_id` | 与设备一一对应 |
| `schema_version` | `int` | 是 | schema 版本 | >=1 |
| `data_json` | `json/text` | 是 | 普通字段 | 默认 `{}` |
| `secret_data_encrypted` | `text` | 是 | secret 字段 | 默认空 |
| `updated_by` | `text` | 否 | 更新人 | 可空 |
| `created_at` | `text` | 是 | 创建时间 | ISO |
| `updated_at` | `text` | 是 | 更新时间 | ISO |

为什么选 `device` 而不是继续偷用 `plugin`：

- 当前 `plugin` 作用域在正式接口里代表家庭默认配置
- 集成实例已经在偷偷拿 `plugin` 映射成 `integration_instance_id`
- 如果设备级再继续偷用 `plugin`，这套作用域就彻底烂了

所以这次应该把作用域说清楚，而不是继续把脏东西埋起来。

#### 3.2.3 `DeviceDetailViewRead`

设备详情聚合视图建议补下面两个块：

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `device` | `DeviceRead` | 是 | 设备基础信息 | 现有结构 |
| `capabilities` | `object` | 是 | 设备详情能力快照 | 新增 |
| `plugin_tabs` | `list` | 是 | 插件专属页签列表 | 新增 |
| `builtin_tabs` | `list` | 是 | 平台通用页签列表 | 新增 |

`capabilities` 建议首版最少提供：

- `supports_voice_terminal: boolean`
- `supports_voiceprint: boolean`
- `adapter_type: string | null`
- `plugin_id: string | null`
- `capability_tags: string[]`

这样前端就不必再靠 `device_type == "speaker"` 瞎猜。

### 3.3 接口契约

覆盖需求：2、3、4、5、6、7

#### 3.3.1 获取设备详情聚合视图

- 类型：HTTP
- 路径或标识：`GET /api/v1/devices/{device_id}/detail-view`
- 输入：`device_id`
- 输出：
  - 设备基础信息
  - 设备能力快照
  - 插件专属页签列表
  - 平台通用页签列表
- 校验：
  - 设备必须存在
  - 只返回当前用户有权看到的页签
- 错误：
  - `404 device_not_found`

#### 3.3.2 获取设备级插件配置表单

- 类型：HTTP
- 路径或标识：`GET /api/v1/ai-config/{household_id}/plugins/{plugin_id}/device-config`
- 输入：
  - `device_id`
  - 可选 `tab_id`
- 输出：
  - `PluginConfigFormRead` 的设备级版本
- 校验：
  - 设备必须存在且属于当前家庭
  - 设备必须匹配该插件页签的适用条件
- 错误：
  - `404 device_not_found`
  - `404 plugin_tab_not_found`
  - `409 plugin_disabled`

#### 3.3.3 保存设备级插件配置表单

- 类型：HTTP
- 路径或标识：`PUT /api/v1/ai-config/{household_id}/plugins/{plugin_id}/device-config`
- 输入：
  - `device_id`
  - `values`
  - `clear_secret_fields`
- 输出：
  - 保存后的设备级配置表单视图
- 校验：
  - 沿用正式插件配置协议字段校验
  - 设备与插件页签适配关系必须成立
- 错误：
  - `400 plugin_config_validation_failed`
  - `404 plugin_tab_not_found`
  - `409 plugin_disabled`

#### 3.3.4 声纹管理通用接口

首版继续复用现有接口：

- `GET /api/v1/voiceprints/households/{household_id}/summary?terminal_id=...`
- `POST /api/v1/voiceprints/enrollments`
- `GET /api/v1/voiceprints/enrollments/{enrollment_id}`
- `POST /api/v1/voiceprints/enrollments/{enrollment_id}/cancel`

这轮不改协议，只改“谁来决定显示入口”。

## 4. 数据与状态模型

### 4.1 数据关系

目标关系如下：

```text
Plugin manifest
  -> 声明 device_detail_tabs
  -> 宿主按声明组合设备详情页签

Device
  -> 基础设备信息
  -> 通过 DeviceBinding / capabilities 判断是否支持 voice_terminal

DevicePluginConfigInstance
  -> 保存某插件在某设备上的专属配置

Voiceprint summary / enrollment
  -> 继续挂在平台通用 terminal_id 上
```

最重要的边界：

- 小爱语音接管属于 `plugin + device` 维度
- 声纹管理属于 `platform + voice_terminal` 维度
- 两者都挂在同一个设备详情容器里，但不再共用同一层职责

### 4.2 状态流转

#### 4.2.1 插件设备页签可见性

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `hidden` | 页签不显示 | 设备不匹配插件声明 | 设备匹配声明 |
| `visible_readonly` | 页签可见但只读 | 插件禁用或无管理权限 | 插件启用且有权限 |
| `visible_editable` | 页签可编辑 | 设备匹配且插件可配置 | 插件禁用、失配或无权限 |

#### 4.2.2 通用声纹页签可见性

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `hidden` | 页签不显示 | 设备不支持 `voice_terminal` | 设备支持该能力 |
| `visible` | 页签显示 | `supports_voice_terminal=true` | 设备能力变化或设备失效 |

## 5. 错误处理

### 5.1 错误类型

- 设备不匹配插件页签声明
- 设备级插件配置字段校验失败
- 插件已禁用
- 设备详情能力判断缺失或错误
- 新配置与兼容字段同步失败

### 5.2 错误响应格式

```json
{
  "detail": "当前设备不支持这个插件页签",
  "error_code": "plugin_tab_not_found",
  "field": "device_id",
  "timestamp": "2026-03-17T00:00:00Z"
}
```

### 5.3 处理策略

1. 输入验证错误：
   - 沿用正式插件配置协议的字段级错误返回。
2. 业务规则错误：
   - 设备不匹配插件页签时返回明确错误，不允许返回空表单蒙混过关。
3. 插件禁用：
   - 遵守统一插件禁用规则，配置可看可改，执行类动作不可混入。
4. 兼容同步失败：
   - 首版以“先保存正式配置，再同步兼容字段”为准。
   - 如果兼容同步失败，要记录错误并阻止出现“新旧状态分叉但前端假装成功”的情况。

## 6. 正确性属性

### 6.1 属性 1：插件私有配置不能再污染通用设备模型

*对于任何* 只属于单个插件的设备配置，系统都应该满足：该配置的正式来源是设备级插件配置实例，而不是继续新增通用 `Device` 字段。

**验证需求：** `requirements.md` 需求 3、需求 7

### 6.2 属性 2：通用声纹页签不能依赖单个插件存在

*对于任何* 具备语音终端能力的设备，系统都应该满足：声纹管理入口由平台能力和设备能力决定，而不是由“小爱插件页面”顺带提供。

**验证需求：** `requirements.md` 需求 1、需求 5

### 6.3 属性 3：迁移期间不能破坏现有运行链路

*对于任何* 已经存在的小爱设备，系统都应该满足：在新配置和旧字段并存阶段，语音接管和声纹相关链路继续可用。

**验证需求：** `requirements.md` 需求 6

## 7. 测试策略

### 7.1 单元测试

- manifest 页签声明校验
- 设备能力判断逻辑
- 设备级插件配置字段校验
- 前端设备详情页签组合逻辑

### 7.2 集成测试

- 小爱设备详情能显示插件专属“语音接管”页签
- 设备级插件配置可读可写
- 普通 `speaker` 但不支持语音终端的设备不显示“声纹管理”
- 支持语音终端的设备显示“声纹管理”并继续走现有 voiceprint 接口
- 新配置保存后兼容字段同步成功

### 7.3 端到端测试

- 从设备列表打开小爱设备详情
- 切换到插件“语音接管”页签并保存
- 切换到通用“声纹管理”页签并正常加载 summary
- 插件禁用后设备详情仍能查看配置，但不出现执行型伪入口

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.1、§4.1 | 设备详情聚合视图测试 + 前端标签页测试 |
| `requirements.md` 需求 2 | `design.md` §3.2.1、§3.3.1 | manifest 校验 + 详情页签渲染测试 |
| `requirements.md` 需求 3 | `design.md` §3.2.2、§3.3.2、§3.3.3 | 配置读写测试 + migration 测试 |
| `requirements.md` 需求 4 | `design.md` §2.3.2、§3.3.2、§5.3 | 小爱页签保存测试 |
| `requirements.md` 需求 5 | `design.md` §2.3.3、§3.2.3、§6.2 | 能力判断测试 + 声纹页签集成测试 |
| `requirements.md` 需求 6 | `design.md` §4.1、§5.3、§6.3 | 兼容迁移测试 |
| `requirements.md` 需求 7 | `design.md` §2.1、§3.1、§6.1 | grep 自检 + 前端分支清理测试 |

## 8. 风险与待确认项

### 8.1 风险

- 如果继续复用 `plugin` 作用域偷映射设备配置，这次虽然能跑，但以后还会烂。
- 如果前端继续按 `speaker` 类型判断声纹页签，普通音箱会被误伤。
- 如果新配置保存后旧字段同步策略没立住，迁移期会出现新旧状态分叉。

### 8.2 待确认项

- 设备详情页签声明最终挂在 manifest 的哪一级字段上，只要是正式能力声明即可。
- 设备级配置实例是直接扩展现有 `plugin_config_instances`，还是单独建表；如果现有表可平滑扩 scope，优先扩 scope。
- 设备详情聚合视图是新增独立接口，还是扩现有详情接口；首版以少改宿主调用栈为优先。
