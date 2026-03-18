# 设计文档 - 官方天气插件

状态：Draft

## 1. 概述

### 1.1 目标

- 做一个默认可用的官方天气插件，优先服务家庭本地部署场景
- 通过统一经纬度输入查询天气，不再依赖城市名猜测
- 复用现有插件、设备、实体和仪表盘卡片体系

### 1.2 覆盖需求

- `requirements.md` 需求 1：默认家庭天气可用
- `requirements.md` 需求 2：天气源可插拔
- `requirements.md` 需求 3：多地区设备
- `requirements.md` 需求 4：天气实体
- `requirements.md` 需求 5：仪表盘卡片
- `requirements.md` 需求 6：刷新、缓存和降级

### 1.3 技术约束

- 默认天气源选用 `MET Norway`
- 插件必须依赖 `001.3.1` 提供的统一坐标解析结果
- 插件内所有地区设备都通过经纬度查询，不走 `city` 文本主链路
- 第一版实体只覆盖默认天气源稳定可返回的数据
- 插件启停、设备暴露、卡片接入必须遵守现有插件统一规则

## 2. 架构

### 2.1 系统结构

插件由四层组成：

1. 天气源适配层：负责把不同供应商接口转成统一天气结果
2. 设备编排层：负责默认设备和附加设备的创建、绑定和刷新
3. 实体映射层：负责把统一天气结果映射成设备实体
4. 卡片消费层：负责从指定天气设备读取展示快照

主链路如下：

1. 插件启动后读取插件配置，确定当前天气源
2. 默认天气设备从家庭地区上下文解析器拿到经纬度
3. 附加天气设备从地区绑定或手动录入的坐标上下文拿到经纬度
4. 设备刷新任务调用天气源适配器取数
5. 统一结果映射为天气实体，并更新卡片读取快照

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| WeatherProviderAdapter | 封装第三方天气 API | 坐标、源配置 | 统一天气结果 |
| WeatherPluginConfig | 保存天气源选择与 key 配置 | 用户配置 | 插件运行参数 |
| WeatherDeviceManager | 创建默认设备和附加设备 | 家庭上下文、设备设置 | 天气设备 |
| WeatherEntityMapper | 把统一结果写成实体 | 统一天气结果 | 设备实体集 |
| WeatherDashboardCard | 为卡片提供展示快照 | 指定天气设备 | 卡片展示数据 |

### 2.3 关键流程

#### 2.3.1 默认家庭天气设备刷新

1. 读取默认天气设备对应的家庭 `household_id`
2. 调用家庭地区上下文解析器获取最终坐标
3. 如果无坐标，记录设备状态为待补全并停止请求天气源
4. 如果有坐标，调用当前天气源适配器查询
5. 统一结果映射为设备实体和最近一次成功快照

#### 2.3.2 手动添加附加地区设备

1. 用户在插件中选择一个地区节点，或明确录入一个自定义坐标
2. 系统校验该地区或坐标是否可解析
3. 创建新的天气设备，并保存设备级绑定信息
4. 设备进入独立刷新和独立状态管理

#### 2.3.3 切换天气源

1. 用户修改插件配置中的天气源类型
2. 如果新来源需要 key，系统先校验 key 是否存在
3. 插件刷新逻辑改用新的适配器
4. 实体模型保持不变，只更新字段映射和数据来源

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5、6

- `MetNorwayAdapter`：默认天气源适配器
- `OpenWeatherAdapter`：用户自带 key 的增强天气源
- `WeatherApiAdapter`：用户自带 key 的增强天气源
- `WeatherDeviceBinding`：天气设备和地区/坐标的绑定关系
- `WeatherEntityMapper`：统一天气结果到设备实体的映射器
- `WeatherCardSnapshotBuilder`：天气卡片展示快照生成器

### 3.2 数据结构

覆盖需求：2、3、4、6

#### 3.2.1 插件配置模型

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `provider_type` | `string` | 是 | `met_norway` / `openweather` / `weatherapi` | 枚举值 |
| `api_key` | `string` | 否 | key 型来源所需密钥 | `met_norway` 时为空 |
| `refresh_interval_minutes` | `int` | 否 | 主动刷新间隔 | 设定合理最小值 |
| `request_timeout_seconds` | `int` | 否 | 外部请求超时 | 设定上限 |
| `user_agent` | `string` | 否 | 对外请求标识 | 默认插件值 |

#### 3.2.2 天气设备绑定模型

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `device_id` | `uuid` | 是 | 设备主键 | 无 |
| `household_id` | `uuid` | 是 | 所属家庭 | 无 |
| `binding_type` | `string` | 是 | `default_household` / `region_node` / `custom_coordinate` | 枚举值 |
| `provider_code` | `string` | 否 | 地区 provider | `region_node` 时必填 |
| `region_code` | `string` | 否 | 地区节点编码 | `region_node` 时必填 |
| `latitude` | `float` | 否 | 自定义纬度 | `custom_coordinate` 时必填 |
| `longitude` | `float` | 否 | 自定义经度 | `custom_coordinate` 时必填 |
| `display_name` | `string` | 是 | 设备显示名 | 默认自动生成，可修改 |
| `last_success_at` | `datetime` | 否 | 最近成功刷新时间 | UTC 时间 |
| `last_error_code` | `string` | 否 | 最近失败原因 | 无 |

设计选择：

- 默认家庭天气和附加地区天气都落到同一种设备模型
- 附加设备第一版允许“地区节点”或“自定义坐标”两种绑定方式
- 不允许自由文本城市名直接成为主绑定类型

#### 3.2.3 统一天气结果模型

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `condition_code` | `string` | 是 | 统一天气状态码 | 适配器映射结果 |
| `condition_text` | `string` | 是 | 用户可读天气摘要 | 统一文本 |
| `temperature` | `float` | 是 | 当前气温 | 摄氏度 |
| `humidity` | `float` | 否 | 相对湿度 | 百分比 |
| `wind_speed` | `float` | 否 | 风速 | m/s |
| `wind_direction` | `float` | 否 | 风向角度 | 0-360 |
| `pressure` | `float` | 否 | 海平面气压 | hPa |
| `cloud_cover` | `float` | 否 | 云量 | 百分比 |
| `precipitation_next_1h` | `float` | 否 | 未来 1 小时降水量 | mm |
| `forecast_6h_min_temp` | `float` | 否 | 未来 6 小时最低温 | 摄氏度 |
| `forecast_6h_max_temp` | `float` | 否 | 未来 6 小时最高温 | 摄氏度 |
| `forecast_6h_condition_code` | `string` | 否 | 未来 6 小时摘要码 | 无 |
| `updated_at` | `datetime` | 是 | 数据更新时间 | UTC 时间 |
| `is_stale` | `bool` | 是 | 是否为过期快照 | 无 |

为什么第一版只定这些：

- 这些字段已经通过 `MET Norway` 实测能稳定拿到
- 体感温度、AQI、预警、日出日落目前不适合作为默认必备字段

#### 3.2.4 设备实体集合

第一版天气设备固定暴露以下核心实体：

| 实体 ID | 值来源 | 说明 |
| --- | --- | --- |
| `weather.condition` | `condition_text` | 当前天气摘要 |
| `weather.temperature` | `temperature` | 当前温度 |
| `weather.humidity` | `humidity` | 相对湿度 |
| `weather.wind_speed` | `wind_speed` | 风速 |
| `weather.wind_direction` | `wind_direction` | 风向 |
| `weather.pressure` | `pressure` | 海平面气压 |
| `weather.cloud_cover` | `cloud_cover` | 云量 |
| `weather.precipitation_next_1h` | `precipitation_next_1h` | 未来 1 小时降水 |
| `weather.forecast_6h` | 6 小时摘要字段组合 | 未来 6 小时摘要 |
| `weather.updated_at` | `updated_at` | 更新时间 |

### 3.3 接口契约

覆盖需求：1、2、3、5、6

#### 3.3.1 天气源适配器接口

- 类型：Function / Interface
- 标识：`fetch_weather(coordinate, provider_config)`
- 输入：纬度、经度、天气源配置
- 输出：统一天气结果模型
- 校验：坐标必须存在；key 型来源必须有 key
- 错误：无坐标、缺 key、外部接口超时、响应结构不合法

#### 3.3.2 创建附加天气设备

- 类型：HTTP / Function
- 标识：`POST /plugins/weather/devices`
- 输入：`binding_type`、地区节点或自定义坐标、设备显示名
- 输出：新建天气设备信息
- 校验：地区节点或坐标必须可解析；禁止重复创建完全相同绑定的设备
- 错误：无坐标、参数非法、重复设备

#### 3.3.3 查询天气卡片快照

- 类型：HTTP / Function
- 标识：`GET /plugins/weather/cards/{card_id}/snapshot`
- 输入：卡片绑定的天气设备 ID
- 输出：地区名、天气图标、天气摘要、温度、更新时间、异常状态
- 校验：设备必须存在且属于当前家庭
- 错误：设备不存在、设备无数据、天气源配置错误

## 4. 数据与状态模型

### 4.1 数据关系

核心关系只有四个对象：

1. 插件配置决定当前用哪个天气源
2. 一个家庭下可以有多个天气设备
3. 一个天气设备绑定一个地区上下文或一组自定义坐标
4. 一个天气设备刷新后输出一组天气实体和一份卡片快照

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `pending_coordinate` | 设备没有可用坐标 | 家庭或设备绑定无法解析坐标 | 坐标补齐后刷新成功 |
| `ready` | 设备配置完整，可正常刷新 | 已有可用坐标和合法天气源配置 | 刷新失败或配置失效 |
| `refreshing` | 正在拉取天气 | 触发设备刷新任务 | 返回成功或失败 |
| `stale` | 保留旧快照但已过期 | 外部天气源失败或超过有效期 | 下次刷新成功 |
| `error` | 配置或请求失败 | 缺 key、接口持续失败、数据无法映射 | 修正配置或刷新成功 |

## 5. 错误处理

### 5.1 错误类型

- `weather_coordinate_missing`：设备没有可用坐标
- `weather_provider_key_missing`：切到 key 型来源但没填 key
- `weather_provider_timeout`：天气源请求超时
- `weather_provider_response_invalid`：外部返回结构不符合映射要求
- `weather_snapshot_stale`：当前显示的是最近一次成功但已过期的结果

### 5.2 错误响应格式

```json
{
  "detail": "当前天气设备没有可用坐标，请补充地区坐标或手动填写经纬度。",
  "error_code": "weather_coordinate_missing",
  "field": "coordinate",
  "timestamp": "2026-03-18T00:00:00Z"
}
```

### 5.3 处理策略

1. 无坐标：设备进入 `pending_coordinate`，不发请求
2. 缺 key：阻止对应天气源启用，并保留原来源或设备旧快照
3. 短时失败：保留最近一次成功结果，标记 `is_stale=true`
4. 字段缺失：只丢弃缺失字段，不影响其他实体更新

## 6. 正确性属性

### 6.1 查询主键是坐标，不是城市名

*对于任何* 天气设备，系统都应该满足：

- 刷新时必须先得到经纬度，不能直接以城市名字作为主查询参数

**验证需求：** `requirements.md` 需求 1、需求 3、需求 6

### 6.2 设备模型统一

*对于任何* 当前家庭天气或附加地区天气，系统都应该满足：

- 都以同一设备模型和同一实体集合对外暴露，而不是各走一套专用结构

**验证需求：** `requirements.md` 需求 3、需求 4、需求 5

### 6.3 默认源可用但不锁死

*对于任何* 已启用天气插件的家庭，系统都应该满足：

- 默认不填 key 即可使用基础天气能力
- 切换天气源时不需要改设备或卡片结构

**验证需求：** `requirements.md` 需求 2、需求 5

## 7. 测试策略

### 7.1 单元测试

- 各天气源适配器字段映射测试
- 统一天气结果到实体映射测试
- 设备状态流转与缓存过期测试

### 7.2 集成测试

- 默认家庭天气设备基于家庭坐标成功查询
- 附加地区天气设备创建、刷新和删除
- 切换天气源后同一设备实体仍能正常输出

### 7.3 端到端测试

- 启用插件后自动出现默认天气设备，并能展示当前家庭天气
- 用户手动添加第二个地区设备后，仪表盘卡片可以切换显示
- 外部天气源失败时，设备与卡片展示过期快照和错误状态

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` 2.3.1、3.3.1 | 集成测试、真实坐标联调 |
| `requirements.md` 需求 2 | `design.md` 2.3.3、3.2.1、6.3 | 配置测试、适配器测试 |
| `requirements.md` 需求 3 | `design.md` 2.3.2、3.2.2、6.2 | 设备创建测试、设备管理回归 |
| `requirements.md` 需求 4 | `design.md` 3.2.3、3.2.4、6.2 | 实体映射测试 |
| `requirements.md` 需求 5 | `design.md` 3.3.3、4.1 | 卡片联调测试 |
| `requirements.md` 需求 6 | `design.md` 4.2、5.3 | 刷新与降级测试 |

## 8. 风险与待确认项

### 8.1 风险

- `MET Norway` 默认源在法务和使用边界上需要文档写清楚，不能写成“无限制官方兜底服务”
- 如果设备刷新频率设计得太激进，多地区场景会很快把免费天气源刷爆
- 如果第一版把 AQI、预警、日出日落也硬塞进必备字段，适配器会立刻变脏

### 8.2 待确认项

- 默认天气设备是否随家庭地区变更自动重绑，还是提示用户确认后重绑
- 附加天气设备是否允许同一地区创建多个不同展示名实例，还是要做唯一约束
