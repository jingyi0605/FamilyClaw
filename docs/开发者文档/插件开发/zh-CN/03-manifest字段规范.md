# 03-manifest字段规范

这份文档只保留稳定规则，不复制一大坨容易漂移的字段大表。

精确字段形状看代码事实来源：

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

如果需要配置，再加：

- `config_specs`
- `locales`

### `config_specs` 的文案怎么写

插件配置表单现在允许“原文 + 词典 key”并存。

最小规则是：

- 保留可读原文作为兜底，比如 `title`、`label`、`help_text`
- 如果要接入插件自己的词典，再额外写对应 key

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

推荐做法很简单：

- 有多语言需求的官方插件和第三方插件，写原文和 key 两套
- 宿主优先用 key 走家庭级 plugin locales
- 没命中词典时，回退原文，不把 key 直接甩给用户

## 2. `types` 只能写什么

### 普通插件类型

- `integration`
- `action`
- `agent-skill`
- `channel`
- `region-provider`
- `ai-provider`
- `locale-pack`
- `theme-pack`

### 独占槽位

- `memory_engine`
- `memory_provider`
- `context_engine`

不要再写：

- `connector`
- `memory-ingestor`

## 3. `entrypoints` 怎么看

当前正式执行入口 key 主要有：

- `integration`
- `action`
- `agent_skill`
- `channel`
- `region_provider`
- `ai_provider`
- `memory_engine`
- `memory_provider`
- `context_engine`

### 对 `ai-provider` 的特殊说明

`ai-provider` 现在已经是“声明 + driver”的正式插件类型。

必须满足：

- 声明 `entrypoints.ai_provider`
- 在 `capabilities.ai_provider` 里写供应商声明
- builtin AI 供应商使用真实 manifest，不再使用虚拟条目

不要再把 `ai-provider` 设计成“只有静态元数据、没有执行边界”的类型。

## 4. `capabilities` 讲什么

`capabilities` 用来声明正式能力边界，比如：

- `integration.*`
- `channel.*`
- `region_provider.*`
- `ai_provider.*`

槽位型插件额外声明：

- `slot_name`
- `exclusive`
- `fallback_required`
- `input_contract_version`
- `output_contract_version`

### 对 `integration` 的补充提醒

现在已经落地、而且插件作者需要真的写出来的字段，不止 `domains` 和 `instance_model` 这几个老名字。

如果是持续状态型插件，至少把下面这些能力边界想清楚：

- `instance_model`
  - 当前常见模型是 `multi_instance`
- `refresh_mode`
- `supports_discovery`
- `supports_actions`
- `supports_cards`
- `entity_types`
- `default_cache_ttl_seconds`
- `max_stale_seconds`

如果插件启用后要自动帮当前家庭建一个默认实例，还应该声明：

- `auto_create_default_instance`
- `default_instance_display_name`
- `default_instance_config`

如果插件会为多台设备或多个实例动态产出卡片，`dashboard_cards` 里还应该声明：

- 固定卡片用 `card_key`
- 动态多卡片用 `card_key_prefix`

天气插件现在就是这个模式：

- 默认实例自动创建
- 同一个插件允许多地区实例
- 每个天气设备都可以产出自己的卡片快照

## 5. `locales` 现在怎么用

`locales` 不再是 `locale-pack` 独占字段。

现在统一规则是：

- `locale-pack` 必须至少声明一个 `locales`
- 普通插件也可以声明自己的 `locales`
- `manifest.locales[].resource` 必须指向插件目录内真实存在的资源文件

普通插件声明 `locales` 的目的很直接：

- 给自己的卡片标题、配置文案、错误提示补词典
- 不需要再单独拆一个语言包插件才能翻译自己

### 同一个 `locale_id` 怎么合并

宿主不会再对同一个 `locale_id` 整包二选一，而是按消息 key 合并。

冲突优先级是：

- `builtin`
- `official`
- `third_party`

如果多个插件都提供了同一个消息 key，按上面的优先级覆盖；同优先级再按插件 id 稳定排序。

`locale-pack` 还有一个特殊规则：

- locale 元信息的归属优先给 `locale-pack`
- 如果当前没有 `locale-pack` 提供该 `locale_id`，再退回到最高优先级的普通插件

## 6. 版本字段和兼容字段怎么理解

当前插件系统里，下面这些字段是正式边界：

- `version`
- `installed_version`
- `compatibility`
- `update_state`

其中：

- `version` 是插件声明版本
- `installed_version` 是当前实际安装版本
- `compatibility` 用于承载兼容性说明
- `update_state` 用于承载最小升级状态

不要再把版本治理理解成“只有一个 `version` 字符串”。
