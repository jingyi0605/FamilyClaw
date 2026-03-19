# 12 V1 Plugin Types and Contracts

| Type | Purpose | Current contract |
| --- | --- | --- |
| `integration` | stateful integration | executable plugin |
| `action` | action execution | executable plugin |
| `agent-skill` | agent tool capability | executable plugin |
| `channel` | messaging channel | executable plugin |
| `region-provider` | region and coordinate resolving | executable plugin |
| `ai-provider` | AI provider plugin | provider declaration plus `entrypoints.ai_provider` driver |
| `locale-pack` | locale resources | resource plugin |
| `theme-pack` | theme resources | resource plugin |

Exclusive memory slots:

- `memory_engine`
- `memory_provider`
- `context_engine`

`integration` plugins currently expose a concrete refresh contract around:

- `instance_status`
- `devices`
- `entities`
- `discoveries`
- `actions`
- `diagnostics`
- `dashboard_snapshots`
- `records`
- `observations`

Optional action-facing fields:

- `message`
- `summary`
- `items`
- `sync_scope`

Key runtime context entries:

- `_system_context.region.household_context.coordinate`
- `_system_context.integration_runtime.database_url`
- `_system_context.integration_runtime.db_session` for builtin same-process sync only

Hard runtime boundaries:

- `capabilities` = manifest-declared capability metadata
- `entities` = runtime standardized entity state
- do not mix them, and do not rely on host read-time repair to make broken domain payloads displayable
- `official` and `third_party` plugins are runtime-mounted plugins and must not become host image or import-time dependencies
- plugin-private tables stay outside the host core ORM
- plugins must emit final standardized entities before handoff

AI provider rule:

- the host keeps the unified AI gateway, routing, permissions, audit, secrets, plugin-state checks, and fallback
- `ai-provider` plugins own declaration, field schema, driver entrypoint, protocol adaptation, streaming, and vendor-specific behavior

Use `specs/004.8.1-AI供应商彻底插件化迁移/` as the primary spec.
