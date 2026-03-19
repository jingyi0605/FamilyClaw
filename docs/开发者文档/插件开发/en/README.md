# Plugin Development Docs (EN)

This handbook documents the current Plugin System V1 rules.

Primary references:

- `specs/004.8-插件系统V1定稿与全量迁移/`
- `specs/004.8.1-AI供应商彻底插件化迁移/`

Official plugin types:

- `integration`
- `action`
- `agent-skill`
- `channel`
- `region-provider`
- `ai-provider`
- `locale-pack`
- `theme-pack`

Exclusive slots:

- `memory_engine`
- `memory_provider`
- `context_engine`

Current AI provider boundary:

- the host keeps the unified AI gateway, routing, permissions, audit, secrets, plugin-state checks, and fallback
- `ai-provider` plugins own provider declaration, field schema, driver entrypoint, protocol adaptation, streaming, and vendor-specific behavior

Important:

- this is the current rule, not a future target model
- historical specs and dated reports are background only
- use `004.8.1` as the single primary spec for AI provider work
- `official` and `third_party` plugins are runtime-mounted plugins, not host image dependencies
- plugin-private tables must not be registered in the host core ORM
- plugins must emit final standardized entities; the host must not keep domain-specific read-time repair logic
