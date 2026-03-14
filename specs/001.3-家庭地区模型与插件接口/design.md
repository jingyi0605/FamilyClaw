# 设计文档 - 家庭地区模型与插件接口

状态：Draft

## 1. 概述

### 1.1 目标

- 把家庭地区从单一 `city` 文本升级为正式的结构化绑定
- 第一版只落中国大陆地区目录，并细化到区县
- 给天气、地区问答等插件提供统一地区上下文
- 保留 `city` 兼容输出，避免破坏现有接口和页面
- 让未来新增其他国家和地区时，只需要增加地区提供方，而不是推翻主模型

### 1.2 覆盖需求

- `requirements.md` 需求 1：家庭必须绑定结构化地区，最细支持到区县
- `requirements.md` 需求 2：第一版只支持中国大陆地区目录，但要用稳定编码而不是自由文本
- `requirements.md` 需求 3：现有家庭和现有接口必须有兼容路径
- `requirements.md` 需求 4：地区能力必须通过统一接口提供给业务模块和插件
- `requirements.md` 需求 5：其他国家和地区必须能通过插件扩展接入

### 1.3 技术约束

- 后端：`FastAPI` + `SQLAlchemy`
- 前端：`apps/user-web` React 页面和状态层
- 数据存储：现阶段主库仍为 `SQLite`，表结构变更必须走 Alembic
- 兼容约束：现有 `households.city` 字段不能直接删除
- 范围约束：第一版只内置中国大陆目录，不导入海外地区
- 权限约束：地区目录查询接口默认面向已登录用户开放；家庭地区上下文仍受家庭访问权限约束

## 2. 架构

### 2.1 系统结构

这次只加三层，别做成地理平台。

1. **地区目录层**：保存标准地区节点，第一版内置中国大陆省 / 市 / 区县目录。
2. **家庭地区绑定层**：把家庭和某个正式地区节点关联起来，同时保留一份快照给兼容输出和降级读取。
3. **地区服务与插件桥接层**：给家庭接口、初始化向导、天气插件、地区问答插件提供统一查询入口。

数据流向如下：

1. 前端查询地区目录，完成省 / 市 / 区县选择
2. 家庭接口提交结构化地区选择
3. 后端校验目录节点和层级关系
4. 系统写入家庭地区绑定，并同步兼容 `city` 展示值
5. 业务模块或插件按 `household_id` 读取标准地区上下文

### 2.2 模块职责

| 模块 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `region` 模块 | 管理地区目录、搜索、上下文拼装 | 地区编码、关键字、父节点 | 地区节点、地区上下文 |
| `household` 模块 | 保存家庭地区绑定和兼容字段 | 家庭资料、地区选择 | 家庭详情、家庭地区绑定 |
| `plugin` 桥接层 | 向插件暴露标准地区查询能力 | `household_id`、查询条件 | 插件可用地区上下文 / 目录结果 |
| `user-web` 家庭页面与向导 | 地区选择和展示 | 目录接口、家庭接口 | 区县级家庭地区配置 |

### 2.3 关键流程

#### 2.3.1 新建或更新家庭地区

1. 前端先查省列表，再按父节点查市列表和区县列表。
2. 用户选定区县后，提交 `provider_code + country_code + region_code`。
3. 后端在地区目录中校验该节点存在，且层级为 `district`，并能回溯出上级市、省。
4. 后端写入家庭地区绑定快照，并把 `households.city` 更新为兼容展示值。
5. 家庭详情接口返回结构化地区对象和 `city` 字段。

#### 2.3.2 旧家庭兼容读取

1. 如果家庭已存在正式地区绑定，直接按绑定返回结构化地区。
2. 如果只有旧 `city`，接口继续返回 `city`，同时 `region` 字段返回 `status=unconfigured` 的标准对象。
3. 初始化向导和设置页看到未配置状态时，提示用户补齐区县级地区。
4. 在旧客户端完成迁移前，`city` 仍保持可用展示值。

补一条硬规则：

- **新家庭初始化** 是否完成，要看 `region.status == configured`，不能再只看 `city` 有没有值。
- **旧家庭兼容访问** 可以继续依赖 `city` 展示，但天气、地区问答这类强依赖地区的功能必须明确提示“请先补录正式地区”。

#### 2.3.3 插件读取家庭地区上下文

1. 插件或业务模块通过统一服务传入 `household_id`。
2. 地区服务读取家庭地区绑定和目录快照。
3. 服务返回标准地区上下文，包括国家、提供方、当前节点、上级路径、兼容展示名。
4. 天气、地区问答等插件只消费这个上下文，不再自己读 `households.city` 做字符串猜测。

这轮再加一条落地规则：

- 插件必须在 `manifest.capabilities.context_reads.household_region_context=true` 后，才能拿到系统注入的地区上下文。
- 系统注入位置统一是 `payload._system_context.region.household_context`。
- 受控入口名统一叫 `region.resolve_household_context`。

#### 2.3.4 新地区提供方接入

1. 新提供方按统一 `RegionProvider` 接口声明 `provider_code`、支持国家和目录查询能力。
2. 提供方负责导入或实时提供对应国家的地区节点数据。
3. 核心家庭绑定仍只保存统一的 `provider_code / country_code / region_code / snapshot`。
4. 现有家庭接口和插件上下文读取逻辑不需要因为国家变化而重写。

这里再强调一次边界：

- 第一版先把 `RegionProvider` 作为后端内部扩展点收好
- 对外开放第三方地区提供方之前，必须先把 `specs/004.3-插件开发规范与注册表/` 里的 manifest 和注册规则补齐
- 这轮只把 manifest / schema / registry 的位置留好，不直接开放第三方地区 provider 运行

## 3. 组件和接口

### 3.1 核心组件

覆盖需求：1、2、3、4、5

- `RegionCatalogService`：按父节点查子节点、按关键字搜索节点、按编码解析路径。
- `HouseholdRegionService`：保存家庭地区绑定、生成兼容 `city`、拼装家庭返回对象。
- `RegionContextService`：给业务模块和插件提供标准地区上下文。
- `RegionProviderRegistry`：注册内置地区提供方和未来插件提供方。
- `CnMainlandRegionProvider`：第一版内置中国大陆提供方，实现省 / 市 / 区县目录查询。

### 3.2 数据结构

覆盖需求：1、2、3、5

#### 3.2.1 `RegionNode`

目录节点表，建议新建 `region_nodes`。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `id` | `text` | 是 | 主键 | UUID |
| `provider_code` | `varchar(50)` | 是 | 地区提供方编码 | 如 `builtin.cn-mainland` |
| `country_code` | `varchar(16)` | 是 | 国家 / 地区编码 | 第一版固定 `CN` |
| `region_code` | `varchar(32)` | 是 | 稳定地区编码 | 在同一提供方内唯一 |
| `parent_region_code` | `varchar(32)` | 否 | 上级节点编码 | 顶层为空 |
| `admin_level` | `varchar(16)` | 是 | 行政层级 | `province` / `city` / `district` |
| `name` | `varchar(100)` | 是 | 当前节点名称 | 非空 |
| `full_name` | `varchar(255)` | 是 | 完整路径展示名 | 非空 |
| `path_codes` | `text` | 是 | 从省到当前节点的编码路径 | JSON 数组或序列化文本 |
| `path_names` | `text` | 是 | 从省到当前节点的名称路径 | JSON 数组或序列化文本 |
| `timezone` | `varchar(64)` | 否 | 该节点默认时区 | 第一版默认 `Asia/Shanghai` |
| `source_version` | `varchar(64)` | 否 | 当前目录数据源版本 | 用于追踪编码来源 |
| `imported_at` | `text` | 否 | 最近导入时间 | ISO 时间 |
| `enabled` | `bool` | 是 | 是否可选 | 默认 `true` |
| `extra` | `text` | 否 | 扩展字段 | JSON 文本 |

关键约束：

- 唯一键：`(provider_code, region_code)`
- 索引：`(provider_code, parent_region_code)`、`(provider_code, admin_level)`
- 第一版只导入 `CN` + `province/city/district`
- 必须能看出当前节点来自哪一版目录数据

#### 3.2.2 `HouseholdRegionBinding`

家庭地区绑定表，建议新建 `household_regions`。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `household_id` | `text` | 是 | 家庭 ID | 与 `households.id` 一对一 |
| `provider_code` | `varchar(50)` | 是 | 绑定来源 | 非空 |
| `country_code` | `varchar(16)` | 是 | 国家 / 地区编码 | 非空 |
| `region_code` | `varchar(32)` | 是 | 当前绑定节点编码 | 必须指向区县级节点 |
| `admin_level` | `varchar(16)` | 是 | 当前绑定层级 | 第一版固定 `district` |
| `province_code` | `varchar(32)` | 是 | 冗余保存省编码 | 非空 |
| `province_name` | `varchar(100)` | 是 | 冗余保存省名称 | 非空 |
| `city_code` | `varchar(32)` | 是 | 冗余保存市编码 | 非空 |
| `city_name` | `varchar(100)` | 是 | 冗余保存市名称 | 非空 |
| `district_code` | `varchar(32)` | 是 | 冗余保存区县编码 | 与 `region_code` 保持一致 |
| `district_name` | `varchar(100)` | 是 | 冗余保存区县名称 | 非空 |
| `display_name` | `varchar(255)` | 是 | 默认展示名 | 例如 `北京市 朝阳区` |
| `snapshot` | `text` | 是 | 绑定时的完整地区快照 | JSON 文本 |
| `source` | `varchar(32)` | 是 | 来源 | `setup` / `settings` / `migration` |
| `created_at` | `text` | 是 | 创建时间 | ISO 时间 |
| `updated_at` | `text` | 是 | 更新时间 | ISO 时间 |

为什么要存快照：

- 读取插件上下文时不必每次重算整条路径
- 即使未来提供方插件临时不可用，家庭已有地区仍然可读
- 兼容输出 `city` 时不必反查旧逻辑

#### 3.2.3 `HouseholdRegionContext`

给接口和插件统一返回的 DTO。

| 字段 | 类型 | 必填 | 说明 | 约束 |
| --- | --- | --- | --- | --- |
| `status` | `string` | 是 | `configured` / `unconfigured` / `provider_unavailable` | 非空 |
| `provider_code` | `string` | 否 | 地区提供方 | 未配置时可空 |
| `country_code` | `string` | 否 | 国家 / 地区编码 | 未配置时可空 |
| `region_code` | `string` | 否 | 当前区县编码 | 未配置时可空 |
| `admin_level` | `string` | 否 | 当前层级 | 第一版为 `district` |
| `province` | `object` | 否 | 省节点摘要 | 包含 `code`、`name` |
| `city` | `object` | 否 | 市节点摘要 | 包含 `code`、`name` |
| `district` | `object` | 否 | 区县节点摘要 | 包含 `code`、`name` |
| `display_name` | `string` | 否 | 展示名称 | 未配置时可空 |
| `timezone` | `string` | 否 | 默认时区 | 可从快照带出 |

### 3.3 接口契约

覆盖需求：1、2、3、4、5

#### 3.3.1 `GET /regions/catalog`

- 类型：HTTP
- 路径或标识：`/regions/catalog`
- 输入：`provider_code`、`country_code`、`parent_region_code`、`admin_level`
- 输出：地区节点摘要列表
- 校验：第一版仅允许 `provider_code=builtin.cn-mainland` 且 `country_code=CN`
- 权限：已登录用户可调用；不要求管理员，但匿名请求直接拒绝
- 错误：提供方不存在、国家不支持、父节点不存在

用途：前端级联选择器按父节点查子节点，不返回整棵树，避免一次性灌大列表。

#### 3.3.2 `GET /regions/search`

- 类型：HTTP
- 路径或标识：`/regions/search`
- 输入：`provider_code`、`country_code`、`keyword`、`admin_level?`、`parent_region_code?`
- 输出：按关键字匹配的地区节点列表
- 校验：`keyword` 不能为空；第一版只搜索中国大陆目录
- 权限：已登录用户可调用；匿名请求直接拒绝
- 错误：关键字为空、提供方不存在、搜索范围非法

用途：给设置页或后续高级选择入口做快速搜索。

#### 3.3.3 `POST /households` 与 `PATCH /households/{household_id}` 扩展

- 类型：HTTP
- 路径或标识：`/households`、`/households/{household_id}`
- 输入：保留现有 `name / city / timezone / locale`，新增 `region_selection`
- 输出：家庭详情，包含 `region` 和兼容 `city`
- 校验：
  - 如果带 `region_selection`，必须能解析到区县节点
  - 如果只带旧 `city`，允许通过，但 `region` 视为未配置
  - `timezone` 和 `locale` 继续按原规则校验
- 错误：地区编码不存在、层级不是区县、路径不完整、家庭不存在

建议请求体新增结构：

```json
{
  "name": "三口之家",
  "timezone": "Asia/Shanghai",
  "locale": "zh-CN",
  "region_selection": {
    "provider_code": "builtin.cn-mainland",
    "country_code": "CN",
    "region_code": "110105"
  }
}
```

#### 3.3.4 `GET /households/{household_id}` 扩展返回

- 类型：HTTP
- 路径或标识：`/households/{household_id}`
- 输入：`household_id`
- 输出：原有家庭字段 + `region`
- 校验：访问权限沿用现有 household 规则
- 错误：家庭不存在、无访问权限

返回示意：

```json
{
  "id": "household-1",
  "name": "三口之家",
  "city": "北京市 朝阳区",
  "timezone": "Asia/Shanghai",
  "locale": "zh-CN",
  "region": {
    "status": "configured",
    "provider_code": "builtin.cn-mainland",
    "country_code": "CN",
    "region_code": "110105",
    "admin_level": "district",
    "province": { "code": "110000", "name": "北京市" },
    "city": { "code": "110100", "name": "北京市" },
    "district": { "code": "110105", "name": "朝阳区" },
    "display_name": "北京市 朝阳区",
    "timezone": "Asia/Shanghai"
  }
}
```

#### 3.3.5 插件运行时接口：`region.resolve_household_context`

- 类型：Function / Service
- 路径或标识：`region.resolve_household_context(household_id)`
- 输入：`household_id`
- 输出：`HouseholdRegionContext`
- 校验：必须先校验家庭存在和调用方权限范围
- 错误：家庭不存在、无权限、未配置地区、提供方不可用

用途：天气插件、地区问答插件统一通过它获取地区上下文。

补一条死规则：

- 地区相关插件只能从这里或它的等价服务入口拿地区信息
- 不允许再直接读取 `households.city` 做正式地区推断

#### 3.3.6 地区提供方接口：`RegionProvider`

- 类型：内部协议 / 插件扩展点
- 路径或标识：`RegionProvider`
- 输入：目录查询条件、地区编码、关键字
- 输出：标准 `RegionNode` 列表或解析结果
- 校验：每个提供方必须声明 `provider_code`、支持国家、支持的层级和查询能力
- 错误：提供方未注册、目录不可用、返回结构非法

建议最小方法：

- `list_children(parent_region_code)`
- `search(keyword, parent_region_code=None)`
- `resolve(region_code)`
- `build_snapshot(region_code)`

## 4. 数据与状态模型

### 4.1 数据关系

- 一个 `Household` 最多只有一条 `HouseholdRegionBinding`
- 一条 `HouseholdRegionBinding` 指向一个正式 `RegionNode`
- 一个 `RegionNode` 通过 `parent_region_code` 形成目录树
- `Household.city` 仍保留，但只是兼容展示投影，不再是正式地区来源

推荐关系：

- `households`：继续保存基础资料和兼容 `city`
- `household_regions`：保存正式绑定和快照
- `region_nodes`：保存目录节点

### 4.2 状态流转

家庭地区本身不需要复杂状态机，只要明确读取状态即可。

| 状态 | 含义 | 进入条件 | 退出条件 |
| --- | --- | --- | --- |
| `unconfigured` | 还没有正式地区绑定 | 旧家庭仅有 `city`，或新家庭未提交地区选择 | 成功写入 `household_regions` |
| `configured` | 已有正式地区绑定 | `household_regions` 写入成功且快照完整 | 绑定被清空或损坏 |
| `provider_unavailable` | 绑定存在，但提供方当前不可用 | 读取绑定成功，但提供方查询失败 | 提供方恢复，或直接使用快照降级为 `configured` |

第一版的实用规则：

- 优先用快照返回已绑定地区
- 只有在快照损坏且提供方也不可读时，才进入明确异常
- 不为地区绑定单独设计审批流和历史版本系统
- 新家庭的 `family_profile` 完成判定依赖 `configured`，旧家庭只用于兼容读取时才允许停留在 `unconfigured`

## 5. 错误处理

### 5.1 错误类型

- `region_provider_not_found`：请求的地区提供方不存在
- `region_not_found`：地区编码不存在
- `region_level_invalid`：提交的节点不是区县级
- `region_parent_mismatch`：地区层级路径不成立
- `household_region_unconfigured`：家庭还没配置正式地区
- `region_provider_unavailable`：地区提供方暂时不可用

### 5.2 错误响应格式

```json
{
  "detail": "当前家庭还没有配置正式地区",
  "error_code": "household_region_unconfigured",
  "field": "region_selection.region_code",
  "timestamp": "2026-03-14T00:00:00Z"
}
```

### 5.3 处理策略

1. 输入验证错误：地区编码不存在、层级不对、路径不完整时，直接拒绝写入。
2. 兼容读取错误：旧家庭没有正式地区绑定时，家庭详情继续可读，只把 `region.status` 标成 `unconfigured`。
3. 提供方错误：如果目录提供方短时不可用，但家庭已有快照，优先返回快照并附带降级状态。
4. 数据导入错误：导入中国大陆目录时如果发现重复编码或断裂路径，导入任务必须失败，不允许脏数据进入正式目录。
5. 目录升级错误：如果新目录版本里出现旧编码废弃或路径变化，必须保留映射或兼容记录，不能直接让已绑定家庭失联。

## 6. 正确性属性

### 6.1 属性 1：家庭正式地区必须唯一

*对于任何* 一个家庭，系统都应该满足：最多只有一条有效的正式地区绑定，不能同时绑定两个不同区县。

**验证需求：** `requirements.md` 需求 1、需求 3

### 6.2 属性 2：家庭地区绑定必须能回溯完整路径

*对于任何* 成功保存的家庭地区绑定，系统都应该满足：能够稳定得到对应的省、市、区县编码和名称路径。

**验证需求：** `requirements.md` 需求 1、需求 2、需求 4

### 6.3 属性 3：兼容 `city` 必须和正式地区快照一致

*对于任何* 已配置正式地区的家庭，系统都应该满足：返回的 `city` 兼容展示值来自正式地区快照，而不是另一套独立拼接逻辑。

**验证需求：** `requirements.md` 需求 3

### 6.4 属性 4：新增地区提供方不应破坏已有家庭绑定模型

*对于任何* 新接入的地区提供方，系统都应该满足：家庭绑定结构和插件读取接口保持不变，只新增提供方实现和目录数据。

**验证需求：** `requirements.md` 需求 5

## 7. 测试策略

### 7.1 单元测试

- 地区目录路径解析和层级校验
- 家庭地区绑定写入、覆盖更新和兼容 `city` 生成
- `RegionContextService` 在 `configured` / `unconfigured` / `provider_unavailable` 三种状态下的输出

### 7.2 集成测试

- Alembic migration 创建 `region_nodes`、`household_regions`
- 家庭创建 / 更新接口写入区县级地区绑定
- 地区目录接口按父节点查询和关键词搜索
- 插件桥接层读取家庭地区上下文

### 7.3 端到端测试

- 初始化向导完成省 / 市 / 区县选择并保存家庭资料
- 设置页修改家庭地区后，家庭详情和插件上下文同时更新
- 旧家庭只有 `city` 时，页面仍可进入并看到补录提示

### 7.4 验证映射

| 需求 | 设计章节 | 验证方式 |
| --- | --- | --- |
| `requirements.md` 需求 1 | `design.md` §2.3.1、§3.2.2、§6.1、§6.2 | API 集成测试 + 单元测试 |
| `requirements.md` 需求 2 | `design.md` §3.2.1、§3.3.1、§3.3.2、§5.3 | 目录导入校验测试 + API 测试 |
| `requirements.md` 需求 3 | `design.md` §2.3.2、§3.3.3、§3.3.4、§6.3 | 兼容回归测试 + 页面联调 |
| `requirements.md` 需求 4 | `design.md` §2.3.3、§3.3.5 | 插件桥接集成测试 |
| `requirements.md` 需求 5 | `design.md` §2.3.4、§3.3.6、§6.4 | 提供方契约测试 + 文档走查 |

## 8. 风险与待确认项

### 8.1 风险

- 中国大陆地区目录来源如果不稳定，后续导入和更新会很麻烦
- 旧页面和旧客户端如果长期只看 `city`，迁移期会被拖长
- 天气或问答插件如果继续偷偷读取 `city`，会形成新旧逻辑并存的垃圾状态
- 如果初始化完成判定没有同步切到正式地区绑定，系统会出现“看起来填完了，实际地区还是空的”这种假完成状态

### 8.2 待确认项

- 中国大陆目录采用哪一套正式编码源，需要在实现前定死
- 是否要在第一版就为地区节点预留经纬度字段，如果天气插件需要可直接从目录快照读取
- 初始化向导里是否把“地区”替换掉“城市”，还是先保留城市文案并在区县选择后自动回填
- `specs/004.3-插件开发规范与注册表/` 何时补地区提供方插件规则，需要和真正开放第三方扩展的时间点对齐
