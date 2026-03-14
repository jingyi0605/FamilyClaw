# 03 Manifest Specification

## Document Metadata

- Purpose: define `manifest.json` fields, hard constraints, recommended usage, and current implementation boundaries so developers do not need to guess.
- Current version: v1.3
- Related documents: `docs/开发者文档/插件开发/en/01-plugin-development-overview.md`, `docs/开发者文档/插件开发/en/02-plugin-dev-environment-and-local-debug.md`, `docs/开发者文档/插件开发/en/04-plugin-directory-structure.md`, `apps/api-server/app/modules/plugin/schemas.py`
- Change log:
  - `2026-03-13`: created the first manifest specification.
  - `2026-03-13`: renamed by reading order and added document metadata.
  - `2026-03-14`: added `locale-pack` and `locales` field rules.
  - `2026-03-14`: added schedule eligibility rules and `schedule_templates` field rules.

This document explains `manifest.json` clearly so developers do not need to guess.

The rules here follow the validation logic that already exists in the repository, mainly from:

- `apps/api-server/app/modules/plugin/schemas.py`
- The built-in plugin examples under `apps/api-server/app/plugins/builtin/`

One boundary must stay explicit:

- `manifest.json` declares what the plugin is, where entrypoints live, and how risky it is
- it does not replace the background-job model
- external execution now creates a `plugin_job` first instead of using `manifest` as a reason to synchronously finish the whole plugin call

## 1. Minimum Example For Version One

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

Note: `description` and `vendor` are currently recommended fields in the spec. They are not hard runtime validation fields yet. You should still include them because later registry and marketplace work will depend on them.

## 2. Field-by-Field Rules

### `id`

- Required
- Type: `string`
- Rule: lowercase letters, digits, and hyphens only
- Recommendation: use it as the base for directory names, registry keys, and repository slugs

Valid examples:

- `health-basic-reader`
- `homeassistant-device-sync`

Invalid examples:

- `HealthBasicReader`
- `health_basic_reader`
- `健康插件`

### `name`

- Required
- Type: `string`
- Rule: cannot be empty after trimming spaces
- Recommendation: use a display name humans can understand, not an internal code name

### `version`

- Required
- Type: `string`
- Rule: cannot be empty after trimming spaces
- Recommendation: use semver such as `0.1.0`

### `types`

- Required
- Type: `string[]`
- Rule: at least one value; no duplicates; only these 5 values are allowed:
  - `connector`
  - `memory-ingestor`
  - `action`
  - `agent-skill`
  - `locale-pack`

The first 4 are executable plugin types. `locale-pack` is for language-pack plugins.

Keep the boundary clear:

- `locale-pack` does not run in workers
- it does not create execution jobs
- it only registers locale metadata and translation resources such as Traditional Chinese UI text

Scheduled-task integration adds one more boundary:

- declaring a normal executable type is still not enough
- if the plugin should be callable by scheduled tasks, `triggers` must explicitly include `schedule`
- otherwise the scheduler rejects it as a target

### `permissions`

- Required
- Type: `string[]`
- Rule: empty arrays are allowed; empty strings are not; duplicates are not allowed
- Recommendation: declare only the minimum permissions the plugin actually needs

Examples visible in current plugins:

- `health.read`
- `device.read`
- `device.control`
- `memory.write.device`
- `memory.write.observation`

### `risk_level`

- Required
- Type: `string`
- Allowed values: `low` / `medium` / `high`

Current behavior boundaries:

- `low`: common for read-only plugins
- `medium`: common for normal device action plugins
- `high`: high-risk actions such as door locks go through a manual confirmation entry

### `triggers`

- Required
- Type: `string[]`
- Rule: empty arrays are allowed; empty strings are not; duplicates are not allowed
- Recommended values for version one: `manual`, `schedule`, `agent`

Keep triggers controlled. Do not invent automatic trigger semantics the system does not support yet.

The schedule boundary must stay explicit:

- only plugins that explicitly include `schedule` in `triggers` may be referenced by the scheduled-task system
- if `schedule` is missing, the backend rejects that plugin as a scheduled-task target
- plugin authors cannot use `manifest` to secretly register timers by themselves; the formal entry still goes through scheduled tasks and `plugin_job`
- if the plugin is disabled at the registry or household mount layer, new scheduled-task dispatches must stop using it

In plain words: `schedule` means "this plugin is allowed to be called by scheduled tasks", not "this plugin owns the scheduler".

### `schedule_templates`

- Optional
- Type: `object[]`
- Purpose: provide recommended templates for scheduled-task setup UIs or later conversation drafts; it does not create tasks by itself

Each item currently supports these fields:

- `code`: template code, unique inside the plugin
- `name`: display name
- `description`: human-readable explanation
- `default_definition`: default task-definition fragment such as `trigger_type`, `schedule_type`, or `schedule_expr`
- `enabled_by_default`: whether the template should be suggested as enabled by default

Minimum example:

```json
{
  "triggers": ["manual", "schedule"],
  "schedule_templates": [
    {
      "code": "daily-check",
      "name": "Daily Check",
      "description": "Run one basic sync every morning",
      "default_definition": {
        "trigger_type": "schedule",
        "schedule_type": "daily",
        "schedule_expr": "09:00"
      },
      "enabled_by_default": false
    }
  ]
}
```

Hard rules:

- once `schedule_templates` is declared, `triggers` must include `schedule`
- `schedule_templates` is only a recommendation surface; it never auto-creates tasks for any household
- template defaults are only suggestions; the final stored task still goes through scheduled-task validation for ownership, permissions, and target checks

The schedule boundary must stay explicit:

- only plugins that explicitly include `schedule` in `triggers` may be referenced by the scheduled-task system
- if `schedule` is missing, the backend rejects that plugin as a scheduled-task target
- plugin authors cannot use `manifest` to secretly register timers by themselves; the formal entry still goes through scheduled tasks and `plugin_job`
- if the plugin is disabled at the registry or household mount layer, new scheduled-task dispatches must stop using it

In plain words: `schedule` means "this plugin is allowed to be called by scheduled tasks", not "this plugin owns the scheduler".

### `schedule_templates`

- Optional
- Type: `object[]`
- Purpose: provide recommended templates for scheduled-task setup UIs or later conversation drafts; it does not create tasks by itself

Each item currently supports these fields:

- `code`: template code, unique inside the plugin
- `name`: display name
- `description`: human-readable explanation
- `default_definition`: default task-definition fragment such as `trigger_type`, `schedule_type`, or `schedule_expr`
- `enabled_by_default`: whether the template should be suggested as enabled by default

Minimum example:

```json
{
  "triggers": ["manual", "schedule"],
  "schedule_templates": [
    {
      "code": "daily-check",
      "name": "Daily Check",
      "description": "Run one basic sync every morning",
      "default_definition": {
        "trigger_type": "schedule",
        "schedule_type": "daily",
        "schedule_expr": "09:00"
      },
      "enabled_by_default": false
    }
  ]
}
```

Hard rules:

- once `schedule_templates` is declared, `triggers` must include `schedule`
- `schedule_templates` is only a recommendation surface; it never auto-creates tasks for any household
- template defaults are only suggestions; the final stored task still goes through scheduled-task validation for ownership, permissions, and target checks

### `entrypoints`

- Required for executable plugins; pure `locale-pack` plugins may use an empty object
- Type: `object`
- Rule: each value must use the `module_path.function_name` format and be really importable
- Rule: every declared executable type in `types` must have a matching entrypoint here

Supported keys:

- `connector`
- `memory_ingestor` or `memory-ingestor`
- `action`
- `agent_skill` or `agent-skill`

The docs recommend underscore keys because runtime normalization also ends up using underscores.

Valid example:

```json
{
  "connector": "app.plugins.builtin.health_basic.connector.sync",
  "memory_ingestor": "app.plugins.builtin.health_basic.ingestor.transform"
}
```

Invalid example:

```json
{
  "connector": "health_basic_connector",
  "memory_ingestor": "app.plugins.builtin.health_basic.ingestor"
}
```

The first one is missing a function name. The second one is also missing a function name.

### `locales`

- Only for `locale-pack` plugins
- Type: `object[]`
- Rule: if `locale-pack` is declared, at least one locale item must exist

Each item should include at least:

- `id`: locale id such as `zh-TW`
- `label`: generic display label such as `Traditional Chinese`
- `native_label`: user-facing native label such as `繁體中文`
- `resource`: relative resource path such as `locales/zh-TW.json`
- `fallback`: optional fallback locale such as `zh-CN`

Minimum example:

```json
{
  "types": ["locale-pack"],
  "entrypoints": {},
  "locales": [
    {
      "id": "zh-TW",
      "label": "Traditional Chinese",
      "native_label": "繁體中文",
      "resource": "locales/zh-TW.json",
      "fallback": "zh-CN"
    }
  ]
}
```

The conflict rule must also stay explicit:

- if multiple locale-pack plugins declare the same `locale id` in one household
- the system does not expose all of them to the frontend at once
- only one wins, with priority: `builtin > official > third_party`
- if the source level is the same, the smaller `plugin_id` in lexical order wins
- suppressed plugins are still visible through the API field `overridden_plugin_ids`

In plain words: a third-party plugin should not expect to override the built-in `zh-TW` locale. If you really need a different pack, use a different locale id or change the built-in pack on purpose.

### `description`

- Optional, but strongly recommended
- Type: `string`
- Purpose: for maintainers and later marketplace display

Recommended content:

- what problem the plugin solves
- what data it reads, or what action it executes
- what it explicitly does not do

### `vendor`

- Optional, but strongly recommended
- Type: `object`
- Recommended minimum fields: `name`, `contact`

Version one does not freeze the structure yet, but maintainers must be reachable.

## 3. Minimum Type-to-Entrypoint Mapping

| Type | Recommended module | Recommended function | Purpose |
| --- | --- | --- | --- |
| `connector` | `connector.py` | `sync` | Read raw external data |
| `memory-ingestor` | `ingestor.py` | `transform` | Convert raw records into normalized memory |
| `action` | `executor.py` | `run` | Execute actions |
| `agent-skill` | `skill.py` | `run` | Expose controlled capabilities to the Agent |
| `locale-pack` | `locales/*.json` | none | Register UI locales and translation resources |

## 4. Hard Constraints Tied To The Current Implementation

These are not suggestions. Breaking them will cause real problems:

1. `id` values must be unique. The plugin registry rejects duplicates.
2. The `manifest.json` top level must be an object, not an array.
3. Every executable `entrypoints` target must resolve to a callable function.
4. Every executable type in `types` must have a matching entrypoint; `locale-pack` does not need a Python entrypoint.
5. The unified Agent entry currently allows only `connector` and `agent-skill`.
6. `action` plugins also go through permission checks, and high-risk actions require manual confirmation.
7. `locale-pack` must declare at least one `locales` item, and each `resource` must stay inside the plugin directory.
8. If a plugin should be usable by scheduled tasks, `triggers` must explicitly include `schedule`.
9. If `schedule_templates` is declared, `triggers` must also include `schedule`.

## 5. Fields That Should Not Go Into Manifest Yet

These sound fancy but would only damage the boundary right now:

- remote installation URLs
- automatic downloader scripts
- sandbox strategy settings
- full signing verification fields
- marketplace frontend layout metadata

In short: keep the runtime declaration clear. Do not stuff future open-platform concepts into version one.

## 6. Pre-Submission Self-Check

1. Does `id` follow the character rules?
2. Does `types` use only the 5 supported values?
3. If this is executable, can every entrypoint really be imported?
4. Are `permissions` minimized instead of bloated?
5. Does `risk_level` match the actual plugin risk?
6. If this is an `action` plugin, are risk and permission boundaries clearly declared?
7. If this is a `locale-pack`, did I provide real `locales/*.json` files and a clear fallback locale?
8. If this plugin should be used by scheduled tasks, did I explicitly declare `schedule` in `triggers`?
9. If I declared `schedule_templates`, did I keep them as templates instead of pretending they auto-create tasks?
10. Am I secretly depending on remote install, remote execution, sandboxing, or a signing platform?

If the locale id already exists as a built-in locale, assume your third-party pack will probably not win.

If all of these pass, then prepare the registry submission material.
