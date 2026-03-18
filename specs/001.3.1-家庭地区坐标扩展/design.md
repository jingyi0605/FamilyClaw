# 设计文档 - 家庭地区坐标扩展

状态：Draft

## 1. 概述

### 1.1 目标

- 在不破坏现有家庭地区绑定的前提下，给地区体系补充经纬度能力
- 明确区分地区代表坐标和家庭精确坐标，消除语义混乱
- 给天气等插件提供统一、稳定、可复用的坐标解析结果

### 1.2 覆盖需求

- `requirements.md` 需求 1：地区节点代表坐标
- `requirements.md` 需求 2：家庭精确坐标覆盖
- `requirements.md` 需求 3：统一坐标解析结果
- `requirements.md` 需求 4：外挂地区包兼容接入

### 1.3 技术约束

- 后端继续复用现有家庭地区模型和 Region Provider 机制，不自造第二套绑定体系
- 数据库结构修改必须通过 Alembic migration 完成
- 浏览器/应用定位只能作为候选输入，不能自动写入家庭正式数据
- 对外能力优先提供统一结果对象，不让每个插件各写一套优先级判断

## 2. 架构

### 2.1 系统结构

这次不重做地区系统，只是在现有链路上补两个点：

1. Region Provider 在地区节点层输出代表坐标
2. Household 在家庭层保存可选的精确坐标覆盖

插件读取时不直接碰底层字段，而是统一走“家庭地区上下文解析器”。

数据流如下：

1. 家庭继续绑定 `provider_code + region_code`
2. Region Provider 根据节点返回地区名称、层级和代表坐标
3. Household 可选保存精确坐标及其来源
4. 上层插件调用统一解析器，拿到最终坐标结果

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| Region Provider | 提供地区节点和可选代表坐标 | provider 配置、地区目录数据 | 统一地区节点模型 |
| Household 地区绑定 | 保存家庭地区绑定和家庭精确坐标 | 家庭设置、用户确认的定位结果 | 家庭地区记录 |
| 地区上下文解析器 | 统一计算最终查询坐标 | household、region node | 坐标解析结果 |
| 上层插件 | 消费最终坐标结果 | 坐标解析结果 | 天气等业务结果 |

### 2.3 关键流程

#### 2.3.1 解析家庭最终坐标

1. 读取家庭绑定的 `provider_code` 与 `region_code`
2. 从 Region Provider 拉取对应节点及其代表坐标
3. 检查家庭是否保存了精确坐标
4. 如果家庭有精确坐标，返回家庭精确坐标
5. 否则如果地区节点有代表坐标，返回地区代表坐标
6. 否则返回无坐标状态，并附上家庭地区上下文

#### 2.3.2 用户确认家庭精确坐标

1. 浏览器或应用获取当前位置，作为候选值展示
2. 用户手动确认“将此位置保存为家庭位置”
3. 系统写入家庭精确坐标及来源信息
4. 后续插件读取时自动优先使用该精确坐标

#### 2.3.3 外挂地区包接入坐标

1. 外挂 provider 按统一节点契约补充坐标字段
2. 系统装载 provider 时按统一结构读入
3. 无坐标的旧 provider 保持兼容，只是在解析结果里标记为 unavailable

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4

- `RegionNodeCoordinate`：地区节点上的代表坐标信息
- `HouseholdCoordinateOverride`：家庭精确坐标覆盖信息
- `ResolvedHouseholdCoordinate`：统一对外暴露的解析结果
- `HouseholdRegionContextService`：封装坐标解析与上下文输出

### 3.2 数据结构

覆盖需求：1、2、3、4

#### 3.2.1 Region Node 坐标扩展

建议在统一地区节点模型上增加以下可选字段：

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `latitude` | `float` | 否 | 地区代表点纬度 | 范围 `-90 ~ 90` |
| `longitude` | `float` | 否 | 地区代表点经度 | 范围 `-180 ~ 180` |
| `coordinate_precision` | `string` | 否 | 精度，如 `country` / `province` / `city` / `district` / `point` | 枚举值 |
| `coordinate_source` | `string` | 否 | 坐标来源，如 `provider_builtin` / `provider_external` | 枚举值 |
| `coordinate_updated_at` | `datetime` | 否 | provider 坐标更新时间 | UTC 时间 |

设计选择：

- 不单独再造一张“地区坐标表”，先把问题做简单
- 坐标跟着地区节点走，谁提供地区节点，谁对代表点负责

#### 3.2.2 Household 精确坐标扩展

建议在家庭表或其等价家庭资料模型上增加以下字段：

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `latitude` | `float` | 否 | 家庭精确纬度 | 范围 `-90 ~ 90` |
| `longitude` | `float` | 否 | 家庭精确经度 | 范围 `-180 ~ 180` |
| `coordinate_source` | `string` | 否 | 来源，如 `manual_browser` / `manual_app` / `manual_admin` | 枚举值 |
| `coordinate_precision` | `string` | 否 | 精度，固定表达为 `point` 或更细分值 | 枚举值 |
| `coordinate_updated_at` | `datetime` | 否 | 最后确认时间 | UTC 时间 |

设计选择：

- 不把家庭精确坐标塞进地区绑定记录里，因为那会把“行政归属”和“真实位置”搅在一起
- 只保留一份当前生效的家庭精确坐标，不在第一版做坐标历史

#### 3.2.3 统一坐标解析结果

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `available` | `bool` | 是 | 是否成功得到坐标 | 无 |
| `latitude` | `float` | 否 | 最终纬度 | `available=true` 时必有 |
| `longitude` | `float` | 否 | 最终经度 | `available=true` 时必有 |
| `source_type` | `string` | 是 | `household_exact` / `region_representative` / `unavailable` | 枚举值 |
| `precision` | `string` | 否 | 最终坐标精度 | 枚举值 |
| `provider_code` | `string` | 否 | 地区 provider | 无 |
| `region_code` | `string` | 否 | 地区节点编码 | 无 |
| `region_path` | `array[string]` | 否 | 省市区展示链路 | 无 |
| `updated_at` | `datetime` | 否 | 最终坐标更新时间 | UTC 时间 |

### 3.3 接口契约

覆盖需求：2、3、4

#### 3.3.1 读取家庭地区上下文

- 类型：Function / Service
- 标识：`resolve_household_region_context(household_id)`
- 输入：`household_id`
- 输出：地区绑定信息 + 统一坐标解析结果
- 校验：家庭必须存在；无地区绑定时返回显式空状态
- 错误：家庭不存在、provider 不可用、地区节点不存在

#### 3.3.2 保存家庭精确坐标

- 类型：HTTP / Function
- 标识：`PATCH /households/{id}/coordinate`
- 输入：`latitude`、`longitude`、`coordinate_source`、确认标记
- 输出：保存后的家庭坐标信息
- 校验：必须由用户主动确认；经纬度范围合法
- 错误：未确认、参数非法、家庭不存在

#### 3.3.3 Region Provider 节点契约扩展

- 类型：Data Contract
- 标识：`RegionNode`
- 输入：provider 自身地区数据
- 输出：标准化节点对象，含可选坐标字段
- 校验：坐标字段可选，但如果出现则必须完整且合法
- 错误：非法坐标将被拒绝装载或记录校验告警

## 4. 数据与状态模型

### 4.1 数据关系

核心关系只有三层：

1. Household 继续拥有一个地区绑定
2. Region Node 可选拥有一个代表坐标
3. Household 可选拥有一个精确坐标覆盖

最终对外结果不是简单拼字段，而是解析器生成的统一视图。

### 4.2 状态流转

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `region_only` | 只有地区绑定，无任何坐标 | 家庭绑定地区但没有精确坐标，节点无坐标或未解析 | provider 补坐标或家庭保存精确坐标 |
| `region_coordinate_ready` | 可用地区代表坐标 | 地区节点存在代表坐标，家庭无精确坐标 | 家庭保存精确坐标或地区坐标失效 |
| `household_coordinate_ready` | 可用家庭精确坐标 | 家庭保存并确认精确坐标 | 用户清空或替换家庭精确坐标 |

## 5. 错误处理

### 5.1 错误类型

- `coordinate_not_available`：家庭和地区节点都没有坐标
- `coordinate_invalid`：经纬度格式或范围非法
- `coordinate_unconfirmed`：候选定位结果未经用户确认就尝试保存
- `region_provider_unavailable`：provider 无法装载或读取节点失败

### 5.2 错误响应格式

```json
{
  "detail": "当前家庭已绑定地区，但该地区还没有可用坐标，请补充地区坐标或手动确认家庭位置。",
  "error_code": "coordinate_not_available",
  "field": "latitude",
  "timestamp": "2026-03-18T00:00:00Z"
}
```

### 5.3 处理策略

1. 输入校验错误：直接拒绝保存，返回明确字段错误
2. 业务规则错误：例如未确认就保存定位，直接拒绝并提示用户确认
3. 外挂 provider 无坐标：允许降级，不影响地区绑定主功能
4. 最终无坐标：统一向上层返回 unavailable，不允许偷偷退回 `city` 文本猜测

## 6. 正确性属性

### 6.1 坐标优先级单一且稳定

*对于任何* 已绑定地区的家庭，系统都应该满足：

- 有家庭精确坐标时，最终结果必须优先使用家庭精确坐标
- 没有家庭精确坐标时，才允许回退到地区代表坐标

**验证需求：** `requirements.md` 需求 2、需求 3

### 6.2 地区绑定与家庭位置分离

*对于任何* 家庭，系统都应该满足：

- 保存、更新、删除家庭精确坐标时，不会改写 `provider_code` 和 `region_code`

**验证需求：** `requirements.md` 需求 2

## 7. 测试策略

### 7.1 单元测试

- 坐标优先级解析测试
- 坐标字段校验与来源枚举测试
- 无坐标 provider 的兼容测试

### 7.2 集成测试

- 家庭绑定地区后读取统一上下文，能拿到地区代表坐标
- 家庭写入精确坐标后，再读取上下文时结果切换为家庭精确坐标
- 外挂 provider 节点含坐标时能被统一解析

### 7.3 端到端测试

- 用户通过地区绑定完成家庭设置后，天气插件能读取到统一坐标
- 用户确认浏览器或应用位置后，天气插件查询点切换为家庭精确坐标

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` 3.2.1、3.3.3 | provider 数据装载测试、人工抽查节点 |
| `requirements.md` 需求 2 | `design.md` 3.2.2、3.3.2、6.2 | API 测试、迁移后字段校验 |
| `requirements.md` 需求 3 | `design.md` 2.3.1、3.2.3、6.1 | 单元测试、集成测试 |
| `requirements.md` 需求 4 | `design.md` 2.3.3、3.3.3 | 外挂 provider 兼容测试 |

## 8. 风险与待确认项

### 8.1 风险

- 部分外挂地区包可能短期内补不齐区县坐标，天气插件需要处理 unavailable 状态
- 如果把家庭精确坐标和地区代表坐标写到同一层接口但不带来源字段，后面一定会排障困难

### 8.2 待确认项

- 家庭精确坐标是否允许前端地图手动微调，还是第一版只允许确认浏览器/应用提供的点
- 对于没有地区节点坐标的外挂包，是否要在插件市场或管理页显式标记“天气不可用”
