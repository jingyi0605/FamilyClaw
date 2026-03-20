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

如果插件准备进入插件市场，还必须再补一条：

- `compatibility.min_app_version`

最小示例：

```json
{
  "id": "demo-plugin",
  "name": "示例插件",
  "version": "0.1.0",
  "api_version": 1,
  "types": ["integration"],
  "permissions": ["device.read"],
  "entrypoints": {
    "integration": "demo_plugin.integration.sync"
  },
  "capabilities": {
    "integration": {
      "domains": ["demo"]
    }
  },
  "compatibility": {
    "min_app_version": "0.1.0"
  }
}
```

这不是装饰字段。插件市场会把它写进 `versions[].min_app_version`，宿主安装前就靠它判断“当前宿主版本能不能装这个插件”。

如果你不写，市场会把兼容性判定成“未知”，安装按钮会直接禁用。

## 2. `config_specs` 现在能声明什么

配置字段仍然分成两层：

- `config_schema`：数据语义
- `ui_schema`：展示提示

当前正式作用域：

- `plugin`
- `integration_instance`
- `device`
- `channel_account`

## 2.1 `compatibility.min_app_version` 应该怎么写

用途很直接：

- 告诉 FamilyClaw 这个插件最低支持哪个宿主版本
- 让插件市场在安装和升级前就能做兼容性判断

当前推荐写法：

```json
{
  "compatibility": {
    "min_app_version": "0.1.0"
  }
}
```

兼容旧写法时，市场机器人也会读取 top-level `min_app_version`，但新插件不要继续写旧格式。

死规矩：

- 这是宿主最低版本，不是插件自己的版本号说明栏
- 字段缺失时，官方市场收录流程会直接失败
- 市场条目里的每个版本都必须带这个值，不再接受“兼容性未知但先收录”

## 2.2 如果要让市场保留多个版本，你还要准备什么

别把“多版本”理解成在 Issue 里多写几行说明。官方市场真正认的是仓库事实。

现在的正式规则是：

1. 单个插件的所有版本都收敛到同一个 `plugins/<plugin_id>/entry.json` 的 `versions[]`
2. 每个版本都要有自己的 `version`、`git_ref`、`artifact_type` 和 `min_app_version`
3. 正式多版本发布必须来自 tag，`git_ref` 统一写成 `refs/tags/<tag>`
4. 想让旧版本继续可回滚，就保留对应 tag，不要只留最新分支
5. `latest_version` 必须指向 `versions[]` 里的当前最高版本

推荐仓库发布习惯：

- tag 用 `v1.0.0`、`v0.9.0` 这种格式
- 推荐同时发 GitHub Release
- 如果是 `release_asset`，要能提供稳定的 `artifact_url`
- 如果是 `source_archive`，市场可以自己按 tag 推导归档地址

一句话：`manifest.json` 解决“这个版本最低支持哪个宿主”，tag / release 解决“市场里到底有哪些真实版本可装”。

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
