# 01 Plugin Development Overview

Host responsibilities:

- standards, permissions, audit, runtime, device/entity/card contracts
- memory ownership and fallback
- unified AI gateway, routing, secrets, plugin-state checks, and fallback

Plugin responsibilities:

- external integration and mapping
- refresh, execution, snapshots
- for `ai-provider`: provider declaration, field schema, driver entrypoint, protocol adaptation, streaming, and vendor-specific behavior

Hard boundaries:

- `official` and `third_party` plugins are runtime-mounted plugins, not host image dependencies, and the host must not statically import them at import time.
- plugin-private tables, caches, provider bindings, and cursors stay inside the plugin boundary and must not be registered in the host core ORM.
- plugins must emit final standardized entities before handoff; the host must not keep weather-, power-, or health-specific read-time normalization.

Official plugin types:

- `integration`
- `action`
- `agent-skill`
- `channel`
- `region-provider`
- `ai-provider`
- `locale-pack`
- `theme-pack`

Exclusive memory slots:

- `memory_engine`
- `memory_provider`
- `context_engine`

For AI provider work, use `specs/004.8.1-AI供应商彻底插件化迁移/` as the primary spec.
