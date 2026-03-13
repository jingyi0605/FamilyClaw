# 03 Manifest Specification

## Document Metadata

- Purpose: define `manifest.json` fields, hard constraints, recommended usage, and current implementation boundaries so developers do not need to guess.
- Current version: v1.1
- Related documents: `docs/开发者文档/插件开发/en/01-plugin-development-overview.md`, `docs/开发者文档/插件开发/en/02-plugin-integration-guide.md`, `docs/开发者文档/插件开发/en/04-plugin-directory-structure.md`, `apps/api-server/app/modules/plugin/schemas.py`
- Change log:
  - `2026-03-13`: created the first manifest specification.
  - `2026-03-13`: renamed by reading order and added document metadata.

This document explains `manifest.json` clearly so developers do not need to guess.

The rules here follow the validation logic that already exists in the repository, mainly from:

- `apps/api-server/app/modules/plugin/schemas.py`
- The built-in plugin examples under `apps/api-server/app/plugins/builtin/`

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
- Rule: at least one value; no duplicates; only these 4 values are allowed:
  - `connector`
  - `memory-ingestor`
  - `action`
  - `agent-skill`

Do not add a new type. The repository does not support it.

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

### `entrypoints`

- Required
- Type: `object`
- Rule: each value must use the `module_path.function_name` format and be really importable
- Rule: every declared type in `types` must have a matching entrypoint here

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

## 4. Hard Constraints Tied To The Current Implementation

These are not suggestions. Breaking them will cause real problems:

1. `id` values must be unique. The plugin registry rejects duplicates.
2. The `manifest.json` top level must be an object, not an array.
3. Every `entrypoints` target must resolve to a callable function.
4. Every type in `types` must have a matching entrypoint.
5. The unified Agent entry currently allows only `connector` and `agent-skill`.
6. `action` plugins also go through permission checks, and high-risk actions require manual confirmation.

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
2. Does `types` use only the 4 supported values?
3. Can every entrypoint really be imported?
4. Are `permissions` minimized instead of bloated?
5. Does `risk_level` match the actual plugin risk?
6. If this is an `action` plugin, are risk and permission boundaries clearly declared?
7. Am I secretly depending on remote install, remote execution, sandboxing, or a signing platform?

If all of these pass, then prepare the registry submission material.
