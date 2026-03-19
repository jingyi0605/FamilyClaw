# 设计文档 - 插件配置协议与动态表单

状态：Active

## 更新记录

- 2026-03-19
  - 配置协议新增动态选项源 `option_source`。
  - 配置字段新增 `depends_on`、`clear_on_dependency_change`。
  - 配置保存新增 `clear_fields`。
  - 配置 API 新增 `POST /ai-config/{household_id}/plugins/{plugin_id}/config/resolve`。
  - 官方天气插件改为“动态地区 provider + 省市区级联”。

## 1. 概述

### 1.1 这次到底修什么

不是再给天气插件补一层页面逻辑，而是把宿主配置系统补到“能处理联动”的程度。

核心问题只有三个：

1. schema 只能写静态枚举
2. 字段变化后没有正式的重算入口
3. 普通字段没有清空语义，脏值删不掉

这三个问题不解决，任何级联表单最后都会退化成特判。

### 1.2 设计目标

- 宿主正式支持动态选项源
- 前端字段变化后能向后端请求重解析
- 失效的下游值能被清理并真正持久化删除
- 天气插件通过通用能力完成地区联动，不再依赖巨型静态枚举

## 2. 数据结构

### 2.1 `PluginManifestConfigField`

在现有字段定义上补三块能力：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `option_source` | object | 动态选项源声明，和 `enum_options` 二选一 |
| `depends_on` | string[] | 这个字段依赖哪些父字段 |
| `clear_on_dependency_change` | boolean | 父字段变化后，这个字段的旧值是否应该被视为可清理 |

规则：

- 只有 `enum` / `multi_enum` 能声明 `option_source`
- `enum_options` 和 `option_source` 不能同时出现
- `clear_on_dependency_change = true` 时必须显式写出 `depends_on`

### 2.2 `option_source`

第一版只支持两个动态源，先解决真实需求，不玩虚的。

#### 2.2.1 `region_provider_list`

用途：列出当前家庭可用的地区 provider。

字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `source` | 是 | 固定为 `region_provider_list` |
| `country_code` | 是 | 当前需要的国家，比如 `CN` |

#### 2.2.2 `region_catalog_children`

用途：按 provider 和父级地区拉子目录。

字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `source` | 是 | 固定为 `region_catalog_children` |
| `country_code` | 是 | 当前国家 |
| `provider_code` / `provider_field` | 二选一 | 固定 provider 或从别的字段读取 provider |
| `parent_field` | 条件必填 | `city` / `district` 级联时必须提供 |
| `admin_level` | 是 | `province` / `city` / `district` |

### 2.3 配置写入请求

`PluginConfigUpdateRequest` 在原来基础上补一个字段：

| 字段 | 说明 |
| --- | --- |
| `clear_fields` | 需要显式删除的普通字段 key 列表 |

现在写入语义固定成下面这样：

- `values` 里出现的字段：写新值
- `clear_fields` 里出现的普通字段：删除旧值
- `clear_secret_fields` 里出现的 secret 字段：删除旧值
- 同一字段不能同时出现在“写新值”和“清空”两边

### 2.4 配置草稿解析请求

新增 `PluginConfigResolveRequest`：

| 字段 | 说明 |
| --- | --- |
| `scope_type` | 配置作用域 |
| `scope_key` | 可选。编辑现有实例时传，创建草稿时可不传 |
| `values` | 当前草稿值 |

返回仍然复用 `PluginConfigFormRead`，区别只是：

- `config_spec` 已按当前草稿值动态解析过
- `view.values` 反映当前草稿与默认值合并后的结果
- 不会落库

## 3. 服务层设计

### 3.1 统一入口

`config_service` 统一走同一条链：

1. 读取当前已存值
2. 合并本次草稿值或写入值
3. 根据当前有效值解析动态选项
4. 再做字段校验
5. 返回已解析的 `config_spec` 和 `view`

这条链会同时服务三种场景：

- `GET config`
- `POST config/resolve`
- `PUT config`

### 3.2 动态选项解析

后端新增 `_resolve_dynamic_config_spec(...)`，专门做运行时 `enum_options` 生成。

#### `region_provider_list`

- 调用 `RegionProviderRegistry.list(household_id=...)`
- 按 `country_code` 过滤
- 生成 `{ label, value }` 列表

#### `region_catalog_children`

- 先拿到当前 provider
- 再从当前草稿里取父级地区编码
- 调用 `list_region_catalog(...)`
- 把返回的地区节点转换成 `{ label: node.name, value: node.region_code }`

如果 provider 或父级值还没准备好，直接返回空数组。

### 3.3 旧配置兼容

天气插件老配置里已经存在：

- `provider_selector`
- `region_code`

运行时兼容策略：

- 新 UI 主路径只认 `provider_code` + `province_code` + `city_code` + `district_code`
- 老实例如果还保存 `provider_selector` 或直接保存 `region_code`，服务层仍然能解析
- 新 manifest 不再暴露 `provider_selector` 和手动省市区巨型枚举

## 4. 接口设计

### 4.1 读取配置表单

`GET /ai-config/{household_id}/plugins/{plugin_id}/config`

行为更新：

- 返回的 `config_spec` 已经是“按当前已存值解析后的版本”
- 不再把原始静态 manifest 直接丢给前端

### 4.2 解析配置草稿

`POST /ai-config/{household_id}/plugins/{plugin_id}/config/resolve`

请求示例：

```json
{
  "scope_type": "integration_instance",
  "values": {
    "binding_type": "region_node",
    "provider_code": "builtin.cn-mainland",
    "province_code": "310000"
  }
}
```

返回重点：

- `provider_code` 已拿到可选 provider
- `city_code` 已根据 `province_code` 重算选项
- `district_code` 如果还缺 `city_code`，就返回空选项

### 4.3 保存配置

`PUT /ai-config/{household_id}/plugins/{plugin_id}/config`

请求示例：

```json
{
  "scope_type": "integration_instance",
  "scope_key": "instance-001",
  "values": {
    "binding_type": "default_household"
  },
  "clear_fields": [
    "provider_code",
    "province_code",
    "city_code",
    "district_code"
  ],
  "clear_secret_fields": []
}
```

关键点：

- 切回默认家庭坐标时，旧的地区选择值必须通过 `clear_fields` 真正删除
- 不能靠“前端不提交”来赌后端自己理解

## 5. 前端设计

### 5.1 打开创建表单

创建新实例时还没有真实 `scope_key`，流程改成：

1. 前端先发 `config/resolve`
2. `scope_key` 允许为空
3. 后端返回基于默认值解析后的表单

### 5.2 字段变化后的联动

前端字段变化后：

1. 更新本地草稿
2. 如果这个字段被别的字段依赖，或者它影响 `visible_when`
3. 调用 `config/resolve`
4. 用新 `config_spec` 比对当前值
5. 把已经不在候选里的下游值删掉
6. 再次 resolve，直到结果稳定

这么做的原因很简单：

- 父级选项变了，子级旧值很可能已经非法
- 只刷新 UI 不清值，保存时照样会把脏数据带回后端

### 5.3 提交时的清理策略

提交集成实例配置时：

- 不可见字段进 `clear_fields`
- 当前为空的普通字段进 `clear_fields`
- 勾选清空的 secret 字段进 `clear_secret_fields`

这样才能保证“界面上已经删掉的值”在数据库里也真的删掉。

## 6. 天气插件落地方案

### 6.1 manifest 结构

天气插件的 `integration_instance` 配置改成：

1. `binding_type`
2. `provider_code`
3. `province_code`
4. `city_code`
5. `district_code`

其中：

- `provider_code` 走 `region_provider_list`
- `province_code` 走 `region_catalog_children(admin_level=province)`
- `city_code` 依赖 `provider_code + province_code`
- `district_code` 依赖 `provider_code + city_code`

### 6.2 运行时解析

天气服务保存和读取时：

- 新路径优先使用 `provider_code + district_code`
- 最终 `region_code` 由 `district_code` 映射
- 旧实例的 `provider_selector` 和直接 `region_code` 继续兼容

## 7. 风险与回归点

### 7.1 最大风险

最大风险不是接口多一个，而是“前端看起来清空了，数据库里其实还保留旧值”。

所以 `clear_fields` 不是可选优化，是这次联动能力必须一起落的基础件。

### 7.2 回归重点

- `GET config` 是否返回已解析的动态选项
- `POST resolve` 是否能在无 `scope_key` 的创建草稿上工作
- `PUT config` 是否真的删除 `clear_fields`
- 天气插件省 -> 市 -> 区是否逐级联动
- 旧天气实例是否还能继续读
