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

One hard rule:

- Channel account forms now rely only on the plugin's own `config_specs` and `ui_schema`.
- Do not expect the host frontend to hardcode vendor-specific fields, placeholders, or help text for you.
- If a channel plugin needs configuration but does not declare a proper `channel_account` config spec, that is a plugin bug.

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

## Multi-step setup forms

For multi-section forms in devices and integrations, the frontend now renders `ui_schema.sections` as staged steps:

- section order becomes the step order
- section title and description are reused as the step label and helper text
- if `section.mode = "advanced"`, that section is hidden behind an optional advanced step so regular users can finish the basic flow first
- if you keep everything in one section, the UI can only render one long form

If your setup flow needs real side effects such as:

- logging in to a third-party account
- loading live device candidates
- surfacing secondary verification or risk-control steps

do not abuse `config/resolve`.

The recommended pattern is:

- declare `entrypoints.config_preview` in the manifest
- let the UI explicitly call `POST /plugins/{plugin_id}/config/preview`
- keep returning the standard `PluginConfigFormRead`
- put temporary runtime output in `view.runtime_state`

If the preview flow includes third-party verification callbacks, do not invent a plugin-private callback endpoint. The host now provides a unified auth-session runtime object through `view.runtime_state.auth_session`.

The plugin side should treat it as a generic contract:

- read `auth_session.callback_url` and use it as the provider callback target
- write provider resume data into `auth_session.payload`
- wait for the host to move the session into `callback_received`
- consume `auth_session.callback_payload` on the next preview run and continue the flow
- mark the session `completed` or `failed` when the staged setup is done

That keeps the saved config schema clean while still allowing staged setup flows with real login, verification links, and live device lists.

## How `ui_schema.actions` and `runtime_sections` work now

If a plugin setup flow needs a staged step such as "click a button, wait for real login, then pick a device", do not hardcode that in the host. Declare it in the manifest:

- `ui_schema.actions`: preview actions the host can render inside a config section
- `ui_schema.runtime_sections`: runtime-only output the host can render after an action finishes

The normal handshake is:

1. gate the button with `depends_on_fields`
2. let the host call `config_preview` with the matching `action_key`
3. return login state, verification links, candidate devices, or other temporary data through `runtime_state`
4. render them with `status_badge`, `text`, `link`, or `candidate_select` items
5. if the user picks a candidate, the host only writes the selected value back to `target_field`; it does not understand vendor-specific meaning

Keep the boundary strict:

- persisted values still belong in real config fields such as `device_selector`
- `runtime_state` is temporary output, not saved config
- the host renders a generic contract, not Xiaomi-specific or Weixin-specific setup logic

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
- `instance_display_name_placeholder`
- `instance_display_name_placeholder_key`

Those last two fields are only for the instance-name input placeholder during manual creation.

- They are hints, not saved defaults.
- The host should render them, not turn them into actual input values.

### `channel`

Pay special attention to:

- `capabilities.channel.platform_code`
- `inbound_modes`
- `delivery_modes`
- `supports_member_binding`
- `config_specs.scope_type = channel_account`

Also keep the unified outbound payload in mind:

- `delivery.text`: optional plain text
- `delivery.attachments`: optional platform-neutral attachment list
- `delivery.metadata`: optional plugin-specific context

Attachment items currently use these generic fields:

- `kind`
- `file_name`
- `content_type`
- `source_path` or `source_url`
- `size_bytes`
- `metadata`

Rules:

- Attachments are a host-wide generic capability, not a platform-specific escape hatch.
- The host does not perform vendor upload, transcoding, or auth for the plugin.
- Text-only plugins may ignore `attachments`. Media-capable plugins must explicitly handle the kinds they support.

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
