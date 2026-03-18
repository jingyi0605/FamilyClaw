# 05 Plugin Integration Guide

## Document Metadata

- Purpose: explain how plugins integrate with FamilyClaw today, with the focus on stable runtime paths and clear boundaries instead of copied API details.
- Current version: v1.6
- Related documents: `docs/开发者文档/插件开发/en/03-manifest-spec.md`, `docs/开发者文档/插件开发/en/11-plugin-configuration-integration.md`, `specs/004.2.3-插件配置协议与动态表单/docs/README.md`, `apps/api-server/app/modules/plugin/service.py`
- Change log:
  - `2026-03-13`: added the first plugin integration guide.
  - `2026-03-14`: added `locale-pack`, region-context, and scheduled-task boundaries.
  - `2026-03-16`: added formal plugin configuration integration rules and switched to the “stable rules + referenced facts” structure.
  - `2026-03-18`: added the unified household coordinate structure, the `region-provider` representative-coordinate contract, and the household exact-coordinate write boundary.

This document answers four questions:

1. how the system calls plugins
2. what input plugins receive
3. what output plugins should return
4. how formal configuration is integrated

## 1. The Plain Truth First

The external main path is no longer “call an API and synchronously finish the plugin”.

The accurate model now is:

1. the caller submits a plugin request
2. the system creates a `plugin_job`
3. a worker executes the plugin in the background
4. the caller follows the result through task status, notifications, or later queries

`execute_plugin()` and `run_plugin_sync_pipeline()` still exist, but they are internal execution-layer and test-layer tools now. They should not be documented as the default public model anymore.

## 2. The Main Runtime Paths

### 2.1 Data Sync Pipeline

This is the most complete and stable path:

1. create a `plugin_job`
2. the worker invokes `connector`
3. the plugin returns `records`
4. the system stores raw records in `plugin_raw_records`
5. `memory-ingestor` converts raw records into Observations
6. the system writes Observations into family memory

This path fits:

- health data
- smart-home state
- other cases where external data should be persisted first and then normalized into memory

### 2.2 Direct Agent Invocation

Only two types are currently open here:

- `connector`
- `agent-skill`

The point is not “can the Agent call plugins”. The point is “the Agent can call only controlled capabilities, not arbitrary plugin code”.

### 2.3 Action Execution

Action plugins use the same unified entry, but with extra permission and risk controls:

1. verify that the plugin declares `action`
2. verify that the required permission is declared
3. verify that the current member is allowed to execute it
4. if the risk level is `high`, require manual confirmation first
5. only then create the background job

### 2.4 Scheduled Task Triggering

Scheduled tasks are now also a formal path, but do not invert the order:

1. create a task definition in the scheduled-task system
2. when due, create `scheduled_task_run`
3. convert that run into a standard `plugin_job`
4. let the existing plugin worker execute it

If `manifest.triggers` includes `schedule`, that means only “this plugin may be called by the scheduled-task system”. It does not mean “the plugin registers its own timers”.

## 3. How Plugins Are Called

The system calls plugins through `manifest.entrypoints`, not by hardcoded file names.

Types that currently take part in execution:

- `connector`
- `memory-ingestor`
- `action`
- `agent-skill`
- `channel`
- `region-provider`

Type that does not enter the execution chain:

- `locale-pack`

That means `locale-pack` registers resources, while `channel` and `region-provider` are formal extension types. They should not be treated as page-level exceptions anymore.

## 4. What Input Plugins Receive

The unified entry passes a `dict payload`.

Recommended function shapes are still simple:

```python
def sync(payload: dict | None = None) -> dict:
    ...


def transform(payload: dict | None = None) -> list[dict]:
    ...


def run(payload: dict | None = None) -> dict:
    ...
```

The boundary is strict:

- plugins should not receive database sessions directly
- plugins should not depend on request objects
- plugins should not return non-serializable objects

If the plugin declares household region-context reads, the system injects controlled context into:

- `_system_context.region.household_context`

If the invocation comes from scheduled tasks, source-tracing fields are also included. They exist for tracing and idempotency support, not for mutating scheduler state.

### 4.1 How To Read `household_context.coordinate`

From this round on, `_system_context.region.household_context` includes a formal unified coordinate result. Upper-layer plugins should not rebuild priority rules by hand anymore.

The structure looks roughly like this:

```json
{
  "status": "configured",
  "provider_code": "builtin.cn-mainland",
  "region_code": "110105",
  "display_name": "Beijing Chaoyang District",
  "coordinate": {
    "available": true,
    "latitude": 39.9219,
    "longitude": 116.4436,
    "source_type": "household_exact",
    "precision": "point",
    "provider_code": "builtin.cn-mainland",
    "region_code": "110105",
    "region_path": ["Beijing", "Beijing", "Chaoyang District"],
    "updated_at": "2026-03-18T09:00:00Z"
  }
}
```

Four hard rules apply:

1. Coordinate priority is already resolved by the system:
   - household exact coordinate
   - region representative coordinate
   - `unavailable`
2. `coordinate.source_type` has only three formal values:
   - `household_exact`
   - `region_representative`
   - `unavailable`
3. If `coordinate.available=false`, treat it as no coordinate. Do not geocode from `city` or `display_name`.
4. If the provider is temporarily unavailable but the binding snapshot already contains a representative coordinate, the system may still return `region_representative`. That is expected.

### 4.2 Browser Or App Location Does Not Auto-Override Household Coordinates

Browser or app location is only a candidate input.

A formal household exact coordinate requires all three:

- explicit user confirmation
- `PATCH /households/{id}/coordinate`
- `confirmed=true`

Before that save happens, plugins still see the currently effective `household_context.coordinate`. Candidate location data does not silently override it.

## 5. What Output Plugins Should Return

### `connector`

- returns `dict`
- must include at least `records: list[dict]`

### `memory-ingestor`

- returns `list[dict]`
- each item must include at least:
  - `category`
  - `value`
  - `source_record_ref`

### `action`

- returns a normal `dict`
- the main requirement is that the caller can understand the result

### `agent-skill`

- returns JSON-serializable data
- it exposes capability to the Agent, not control over the Agent main flow

### `channel`

- follows the formal channel protocol for normalized inbound and outbound messages
- platform-specific details belong in channel plugin implementations and channel modules, not in page constants

### `region-provider`

- follows the formal region-provider protocol and returns JSON results
- it is now a formal extension point, not a temporary experiment

If the result is a standard region node, the node may now optionally include five representative-coordinate fields:

- `latitude`
- `longitude`
- `coordinate_precision`
- `coordinate_source`
- `coordinate_updated_at`

Keep the rules clean:

- older providers stay compatible without coordinates
- once latitude and longitude are present, precision and source must also be present
- upper-layer plugins should ultimately consume unified `household_context.coordinate`, not guess coordinates from node names

## 6. How Formal Plugin Configuration Is Integrated

This is the most important new boundary in this round.

Whenever a plugin needs user-managed parameters, it should use the formal configuration protocol. Do not go back to these old patterns:

- page-level hardcoded field constants
- a random business table storing one JSON blob as the only source of truth
- reading secret values back like plain strings

The formal manifest entry is:

- `config_specs`

Each config scope contains at least:

- `scope_type`
- `schema_version`
- `config_schema`
- `ui_schema`

This round supports only two formal scopes:

- `plugin`
- `channel_account`

The stable rules are short:

1. Field definitions live only in the plugin manifest.
2. Host pages only read the protocol, render the form, and submit config data.
3. Secret fields must never be echoed back in plaintext.
4. If a secret field is omitted during save, the old value is preserved.
5. To clear a secret value, the client must explicitly use `clear_secret_fields`.

Do not copy more details into this handbook. Read them from:

- `docs/开发者文档/插件开发/en/11-plugin-configuration-integration.md`
- `specs/004.2.3-插件配置协议与动态表单/docs/20260316-manifest-示例.md`
- `specs/004.2.3-插件配置协议与动态表单/docs/20260316-api-示例.md`
- `apps/api-server/app/modules/plugin/schemas.py`

## 7. Why Channel Plugins Need An Explicit Warning

Because channel plugins are the first migration batch, and this is the easiest place to accidentally revive the old source-of-truth mess.

The rule set now is:

- the formal field source is the channel plugin’s own `manifest.config_specs`
- the `channel_account` scope is read and saved through the unified plugin configuration APIs
- `channel_plugin_accounts.config_json` is only a compatibility runtime copy, not the only source of truth anymore
- `SettingsChannelAccessPage` should now be driven by the protocol and the dynamic form renderer
- `PluginDetailDrawer` already has a unified plugin-level configuration entry

If future docs keep documenting channel field lists as page-level truth, that is just rebuilding the same bug on purpose.

## 8. Which HTTP Entries Matter

This guide does not repeat long payload samples. It keeps only the stable categories:

- Agent invokes normal plugins
- Agent triggers memory checkpoints
- Agent invokes action plugins
- high-risk action confirmation
- unified plugin configuration scope / form / save APIs
- household exact-coordinate save API: `PATCH /households/{id}/coordinate`

For concrete request and response examples, read:

- `specs/004.2.3-插件配置协议与动态表单/docs/20260316-api-示例.md`
- `apps/api-server/app/api/v1/endpoints/ai_config.py`

## 9. One-Line Summary

Integrating a plugin into FamilyClaw is not “mount an external API and you are done”. It is:

- declare formal capabilities and the formal configuration protocol through `manifest`
- let the system invoke the plugin through the unified task pipeline
- persist raw records first, then convert them into normalized memory
- drive configuration UIs from the protocol instead of hardcoded plugin-specific page fields
