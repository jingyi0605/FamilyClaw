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

## 5. 版本字段和兼容字段怎么理解

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
