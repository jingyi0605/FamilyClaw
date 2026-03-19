---
title: manifest字段规范
version: 2.0.0
updated_at: 2026-03-19
version_history:
  - version: 2.0.0
    date: 2026-03-19
    note: 补充插件配置动态选项源、字段联动依赖和普通字段 clear_fields 语义。
---

# 03-manifest字段规范

这份文档只写稳定边界，不重复抄代码实现细节。

代码事实来源仍然是：

- `apps/api-server/app/modules/plugin/schemas.py`

## 1. 最小 manifest 该有什么

每个插件至少要声明：

- `id`
- `name`
- `version`
- `api_version`
- `types`
- `permissions`
- `entrypoints`
- `capabilities`

如果插件需要配置，再加：

- `config_specs`
- `locales`

## 2. `config_specs` 现在能声明什么

配置字段仍然分成两层：

- `config_schema`：数据语义
- `ui_schema`：展示提示

当前正式作用域：

- `plugin`
- `integration_instance`
- `device`
- `channel_account`

## 3. 枚举字段不再只有静态选项

以前 `enum` / `multi_enum` 只能写死 `enum_options`。

现在正式支持两种写法，二选一：

### 3.1 静态选项

```json
{
  "key": "mode",
  "type": "enum",
  "enum_options": [
    { "label": "严格", "value": "strict" },
    { "label": "宽松", "value": "loose" }
  ]
}
```

### 3.2 动态选项源

```json
{
  "key": "provider_code",
  "type": "enum",
  "option_source": {
    "source": "region_provider_list",
    "country_code": "CN"
  }
}
```

死规矩：

- `enum_options` 和 `option_source` 不能同时写
- 只有 `enum` / `multi_enum` 能写 `option_source`

## 4. 动态选项源规范

### 4.1 `region_provider_list`

用途：列出当前家庭可用的地区 provider。

字段：

- `source`: 固定为 `region_provider_list`
- `country_code`: 目标国家，例如 `CN`

### 4.2 `region_catalog_children`

用途：按 provider 和父级地区拉子级目录。

字段：

- `source`: 固定为 `region_catalog_children`
- `country_code`: 目标国家
- `provider_code` 或 `provider_field`: 二选一
- `parent_field`: 当级联到 `city` / `district` 时必填
- `admin_level`: `province` / `city` / `district`

示例：

```json
{
  "key": "city_code",
  "type": "enum",
  "depends_on": ["provider_code", "province_code"],
  "clear_on_dependency_change": true,
  "option_source": {
    "source": "region_catalog_children",
    "country_code": "CN",
    "provider_field": "provider_code",
    "parent_field": "province_code",
    "admin_level": "city"
  }
}
```

## 5. 字段联动怎么声明

如果一个字段依赖别的字段，正式用下面两个字段表达：

- `depends_on`
- `clear_on_dependency_change`

例子：

```json
{
  "key": "district_code",
  "type": "enum",
  "depends_on": ["provider_code", "province_code", "city_code"],
  "clear_on_dependency_change": true,
  "option_source": {
    "source": "region_catalog_children",
    "country_code": "CN",
    "provider_field": "provider_code",
    "parent_field": "city_code",
    "admin_level": "district"
  }
}
```

含义很直接：

- 上游字段一变，宿主要重新解析这个字段的可选项
- 如果当前值已经不在新候选里，宿主应该把它清掉

## 6. 文案字段怎么写

插件配置表单允许“原文 + 词典 key”并存。

当前正式支持的 key 字段包括：

- `config_specs[].title_key`
- `config_specs[].description_key`
- `config_specs[].config_schema.fields[].label_key`
- `config_specs[].config_schema.fields[].description_key`
- `config_specs[].config_schema.fields[].enum_options[].label_key`
- `config_specs[].ui_schema.sections[].title_key`
- `config_specs[].ui_schema.sections[].description_key`
- `config_specs[].ui_schema.widgets[].placeholder_key`
- `config_specs[].ui_schema.widgets[].help_text_key`
- `config_specs[].ui_schema.submit_text_key`

推荐做法：

- 给用户看的原文一定要有，别只塞 key
- 有多语言时再补 key
- 宿主先走 key，没命中再退回原文

## 7. 天气插件该怎么写

天气插件现在的正确写法不是把省市区整包塞进 manifest。

正确路线是：

1. `provider_code` 走 `region_provider_list`
2. `province_code` 走 `region_catalog_children(province)`
3. `city_code` 依赖 `provider_code + province_code`
4. `district_code` 依赖 `provider_code + city_code`

这样后续装了新的地区 provider，宿主就能直接把它列出来，天气插件不用再改代码。
