---
title: Field Specification
docId: en-4.6
version: v0.1
status: active
order: 460
outline: deep
---

# Field Specification

This page only covers the fields that are easiest to get wrong in plugin manifests and config schemas.

Fact sources:

- `apps/api-server/app/modules/plugin/schemas.py`
- built-in plugin `manifest.json` files in the repository
- [Plugin Specification](./plugin-specification.md)
- [Example Plugin](./plugin-example.md)

## Core manifest fields

| Field | Required | Description |
| --- | --- | --- |
| `id` | yes | Unique plugin identifier. The backend and scheduled tasks both use it to locate the plugin. |
| `name` | yes | Display name |
| `version` | yes | Plugin version |
| `api_version` | required for most types | Plugin protocol version |
| `types` | yes | Array of plugin types |
| `permissions` | yes | Declared permissions |
| `risk_level` | yes | `low` / `medium` / `high` |
| `triggers` | yes | Allowed trigger modes such as `manual` or `schedule` |
| `entrypoints` | depends on type | Entry function paths |
| `capabilities` | yes | Capability declarations for the declared types |

## How to write `entrypoints`

An entry must be:

- Python module path plus function name

For example:

```json
"entrypoints": {
  "integration": "app.plugins.builtin.health_basic.integration.sync"
}
```

Wrong examples include:

- only a module name with no function
- an empty string
- a path that does not match the real code

## `types` and `entrypoints` must match

Examples:

- If `types` includes `integration`, you should have `entrypoints.integration`.
- If `types` includes `channel`, you should have `entrypoints.channel`.
- `theme-pack`, `locale-pack`, and some `ai-provider` cases do not always need executable entrypoints, but their capability declarations still need to be complete.

## What `config_specs` is for

If a plugin needs user-provided configuration, use `config_specs`.

Do not scatter the config contract across README text and code comments.

A typical structure:

```json
{
  "scope_type": "channel_account",
  "title": "Feishu account configuration",
  "schema_version": 1,
  "config_schema": {
    "fields": []
  },
  "ui_schema": {
    "sections": [],
    "field_order": [],
    "widgets": {}
  }
}
```

## Common config field types

Current common types:

- `string`
- `text`
- `integer`
- `number`
- `boolean`
- `enum`
- `multi_enum`
- `secret`
- `json`

Current common widgets:

- `input`
- `password`
- `textarea`
- `switch`
- `select`
- `multi_select`
- `json_editor`

## Dynamic option fields

If a field's options are not hardcoded, use:

- `option_source`

Current officially supported dynamic option sources:

- `region_provider_list`
- `region_catalog_children`

Important notes:

- do not misuse `enum_options` and `option_source` together
- configure `depends_on` correctly when a field depends on another
- use `clear_on_dependency_change` when an old value must be cleared after dependency changes

## Extra points by plugin type

### `integration`

Pay special attention to:

- `capabilities.integration.domains`
- `instance_model`
- `refresh_mode`
- `supports_discovery`
- `supports_actions`
- `supports_cards`

### `channel`

Pay special attention to:

- `capabilities.channel.platform_code`
- `inbound_modes`
- `delivery_modes`
- `supports_member_binding`
- `config_specs.scope_type = channel_account`

### `ai-provider`

Pay special attention to:

- `capabilities.ai_provider.adapter_code`
- `field_schema`
- `supported_model_types`
- `runtime_capability`

### `theme-pack`

Pay special attention to:

- `theme_id`
- `display_name`
- `tokens_resource` or `entry_resource`
- `resource_source`
- `resource_version`
- `platform_targets`

## Mistakes people make most often

- changing `id` but forgetting to update README references, scheduled task references, or existing config records
- declaring `schedule` in `triggers` without implementing the corresponding ability
- making `field_schema` different from the fields read at runtime
- hardcoding user-facing text in code instead of using config and i18n resources

If the field design is vague, debugging becomes more painful than writing the code.
