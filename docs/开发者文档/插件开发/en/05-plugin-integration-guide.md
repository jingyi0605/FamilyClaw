# 05 Plugin Integration Guide

Stable execution paths:

- `integration.refresh` for stateful plugins
- `action` entrypoints for controlled actions
- `entrypoints.ai_provider` for AI provider drivers
- exclusive slot contracts for memory plugins

Plugins return JSON-serializable payloads only.

For region-aware plugins, the canonical coordinate entry is:

- `_system_context.region.household_context.coordinate`

Do not rebuild the main lookup chain from free-text city names.

For plugin-managed integrations, the host currently exposes a small runtime context:

- `_system_context.integration_runtime.database_url`
- `_system_context.integration_runtime.db_session` for builtin same-process sync only

Treat `database_url` as the portable fallback.
Do not assume `db_session` exists unless you are writing a builtin plugin that runs in the same host process.

Stateful integrations should return standard refresh results and may include:

- `instance_status`
- `devices`
- `entities`
- `discoveries`
- `actions`
- `diagnostics`
- `dashboard_snapshots`
- `records`
- `observations`
- `message`
- `summary`
- `items`
- `sync_scope`

Use `dashboard_snapshots` as the plugin-facing card snapshot field.
If you still see `card_snapshots` in internal host code, treat it as transitional internal naming rather than the contract for new plugins.

AI provider plugins are different from `integration` plugins:

- the host resolves the plugin through the provider profile
- the host loads `entrypoints.ai_provider`
- the host calls `invoke`, `ainvoke`, or `stream`

The host owns persistence, validation, dedupe, status updates, memory writes, routing, secrets, and governance.

Hard rules for V1:

- `entities` must already be final standardized entities before handoff. The host must not keep weather-, power-, or health-specific read-time normalization.
- plugin-private tables, caches, provider bindings, and cursors stay inside the plugin boundary. The host must not import, register, or directly query plugin-private ORM models, and the host core Alembic migrations must not create, upgrade, or drop those tables.
- `capabilities` means manifest-declared capability metadata, not runtime entity-state storage. Do not treat it as a domain-specific runtime protocol.
- `official` and `third_party` plugins are runtime-mounted plugins. They do not belong in the final host image, and the host must not statically import them during module import.
