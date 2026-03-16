# 03 Manifest Specification

## Document Metadata

- Purpose: explain which `manifest.json` fields are formal entry points, which rules are stable, and which changing details should be referenced instead of copied.
- Current version: v1.4
- Related documents: `docs/开发者文档/插件开发/en/00-how-to-use-and-maintain-these-docs.md`, `docs/开发者文档/插件开发/en/11-plugin-configuration-integration.md`, `specs/004.2.3-插件配置协议与动态表单/docs/README.md`, `apps/api-server/app/modules/plugin/schemas.py`
- Change log:
  - `2026-03-13`: created the first manifest specification.
  - `2026-03-14`: added `locale-pack`, region-context, and `schedule_templates` rules.
  - `2026-03-16`: added `channel`, `region-provider`, the formal configuration protocol entry, and the new “stable rules + referenced facts” structure.

This document keeps only stable rules. It does not copy large tables that will change often.

For exact field shapes, current runnable examples, and API payloads, read these sources directly:

- `apps/api-server/app/modules/plugin/schemas.py`
- `specs/004.2.3-插件配置协议与动态表单/docs/20260316-manifest-示例.md`
- `specs/004.2.3-插件配置协议与动态表单/docs/20260316-api-示例.md`

## 1. Boundary First

`manifest.json` is responsible for three things:

- what the plugin is
- which formal entrypoints it exposes
- which runtime declarations it makes

It is not responsible for:

- replacing the background job model
- replacing page implementations
- replacing configuration-instance persistence

External execution now creates a `plugin_job` first. Writing an entrypoint does not mean a public API will synchronously run the whole plugin.

## 2. Minimum Example

```json
{
  "id": "health-basic-reader",
  "name": "Health Basic Data Plugin",
  "version": "0.1.0",
  "types": ["connector", "memory-ingestor"],
  "permissions": [
    "health.read",
    "memory.write.observation"
  ],
  "risk_level": "low",
  "triggers": ["manual", "schedule"],
  "entrypoints": {
    "connector": "app.plugins.builtin.health_basic.connector.sync",
    "memory_ingestor": "app.plugins.builtin.health_basic.ingestor.transform"
  },
  "description": "Reads raw health data and converts it into normalized Observation records.",
  "vendor": {
    "name": "FamilyClaw official example",
    "contact": "https://github.com/FamilyClaw"
  }
}
```

If the plugin needs formal configuration, add `config_specs`. If it needs household region context, add `capabilities.context_reads.household_region_context=true`.

## 3. Field Rules

### `id`

- Required
- Type: `string`
- Rule: lowercase letters, digits, and hyphens only
- Recommendation: use it as the base for directory names, registry keys, and repository slugs

### `name`

- Required
- Type: `string`
- Rule: cannot be empty after trimming spaces
- Recommendation: use a human-readable display name, not an internal code name

### `version`

- Required
- Type: `string`
- Rule: cannot be empty after trimming spaces
- Recommendation: use semver such as `0.1.0`

### `types`

- Required
- Type: `string[]`
- Rule: at least one value, no duplicates, only currently supported formal types

The types that are already part of the formal system are:

- `connector`
- `memory-ingestor`
- `action`
- `agent-skill`
- `locale-pack`
- `channel`
- `region-provider`

Do not keep writing “only 4 types” or “only 5 types”. That is already outdated.

Keep the boundary clear:

- `locale-pack` registers language resources and does not run in workers
- `channel` handles communication-platform inbound and outbound flows
- `region-provider` is a formal region-directory extension, not a renamed sync plugin

### `permissions`

- Required
- Type: `string[]`
- Rule: empty arrays are allowed; empty strings and duplicates are not
- Recommendation: declare only the minimum permissions the plugin really needs

### `risk_level`

- Required
- Type: `string`
- Allowed values: `low` / `medium` / `high`

### `triggers`

- Required
- Type: `string[]`
- Rule: empty arrays are allowed; empty strings and duplicates are not
- Common first-version values: `manual`, `schedule`, `agent`

`schedule` only means “this plugin may be called by the scheduled-task system”. It does not mean the plugin owns scheduling.

### `schedule_templates`

- Optional
- Type: `object[]`
- Purpose: recommended templates for scheduled-task setup, not auto-created tasks

Once `schedule_templates` is declared, `triggers` must include `schedule`.

### `entrypoints`

- Required for executable plugins
- Type: `object`
- Rule: each value must be `module_path.function_name` and really importable
- Rule: every declared executable type must have a matching entrypoint

Current common keys:

- `connector`
- `memory_ingestor` or `memory-ingestor`
- `action`
- `agent_skill` or `agent-skill`
- `channel`
- `region_provider` or `region-provider`

The docs recommend underscore keys because runtime normalization also ends up with underscores.

### `locales`

- Only for `locale-pack` plugins
- Type: `object[]`
- Rule: if `locale-pack` is declared, at least one locale item must exist

### `capabilities`

- Optional
- Type: `object`
- Purpose: declare which controlled context the plugin reads, or which formal extension capability it mounts

Capabilities formally available in this round:

- `context_reads.household_region_context`
- `region_provider.*`

For channel plugins, keep platform capability declarations in the formal channel plugin fields. Do not push those fields back into page-level constants.

### `config_specs`

- Optional
- Type: `object[]`
- Purpose: declare the formal plugin configuration protocol

Each item contains at least:

- `scope_type`
- `schema_version`
- `config_schema`
- `ui_schema`

This round supports only two formal scopes:

- `plugin`
- `channel_account`

This document intentionally does not copy the full field-type list, widget list, or condition list. Those change. Read them from:

- `docs/开发者文档/插件开发/en/11-plugin-configuration-integration.md`
- `specs/004.2.3-插件配置协议与动态表单/docs/README.md`
- `apps/api-server/app/modules/plugin/schemas.py`

The stable rules are short:

1. Field definitions live in one place only: the plugin manifest.
2. Older plugins without `config_specs` must still stay loadable, visible, and runnable.
3. Secret fields must never be echoed back in plaintext.

### `description`

- Optional, but strongly recommended
- Type: `string`
- Recommended content:
  - what problem the plugin solves
  - what data it reads, or what action it executes
  - what it explicitly does not do

### `vendor`

- Optional, but strongly recommended
- Type: `object`
- Recommended minimum: `name`, `contact`

## 4. Minimum Type-to-Entrypoint Mapping

| Type | Recommended module | Recommended function | Purpose |
| --- | --- | --- | --- |
| `connector` | `connector.py` | `sync` | Read raw external data |
| `memory-ingestor` | `ingestor.py` | `transform` | Convert raw records into normalized memory |
| `action` | `executor.py` | `run` | Execute actions |
| `agent-skill` | `skill.py` | `run` | Expose controlled capabilities to the Agent |
| `channel` | `channel.py` | `handle` | Handle communication-platform inbound and outbound flows |
| `region-provider` | `region_provider.py` | `handle` | Provide region-directory capability |
| `locale-pack` | `locales/*.json` | none | Register UI locale and translation resources |

## 5. Hard Constraints Tied To The Current Implementation

These are not suggestions:

1. `id` must be unique.
2. The top level of `manifest.json` must be an object.
3. Executable `entrypoints` must resolve to real callable functions.
4. Every executable type in `types` must have a matching entrypoint.
5. `locale-pack` must declare at least one `locales` item.
6. If a plugin should be usable by scheduled tasks, `triggers` must include `schedule`.
7. If `schedule_templates` is declared, `triggers` must also include `schedule`.
8. If a plugin reads household region context, it must explicitly declare `capabilities.context_reads.household_region_context=true`.
9. If a plugin runs as a region provider, it must declare `types=["region-provider"]` plus a full `capabilities.region_provider`.
10. If a plugin declares `config_specs`, the backend validates that formal protocol and rejects invalid manifests.
11. Older plugins without the configuration protocol must not become invalid just because `config_specs` now exists.

## 6. Things That Should Not Go Into Manifest Yet

These look fancy but only damage the boundary right now:

- remote installation URLs
- automatic downloader scripts
- sandbox strategy settings
- full signing-verification fields
- marketplace layout metadata
- frontend component names
- a duplicated copy of backend field tables

In short: keep the formal runtime declaration clear. Do not stuff future open-platform ideas into version one.

## 7. Self-Check Before Submission

1. Does `id` follow the character rules?
2. Does `types` use only currently supported formal types?
3. If this is executable, can every entrypoint really be imported?
4. Are `permissions` minimized instead of bloated?
5. Does `risk_level` match the actual plugin risk?
6. If you use `config_specs`, do field definitions live only in the manifest instead of being copied into page constants?
7. If you use secret fields, have you confirmed “no echo on read” and the formal clear semantics?
8. If this plugin should be used by scheduled tasks, did you explicitly declare `schedule`?
9. If this is a `channel` plugin, did you declare the `channel_account` scope through the formal configuration protocol instead of hardcoding fields in the page?
10. Are you secretly depending on remote install, remote execution, sandboxing, or a signing platform?

If these all pass, then prepare the registry and integration materials.
