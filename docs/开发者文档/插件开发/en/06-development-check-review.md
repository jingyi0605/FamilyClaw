# 06 Development Check Review

## Document Metadata

- Purpose: record whether the current developer docs really cover the minimum plugin development path instead of only looking complete on paper.
- Current version: v1.1
- Related documents: `docs/开发者文档/插件开发/en/01-plugin-development-overview.md`, `docs/开发者文档/插件开发/en/02-plugin-integration-guide.md`, `docs/开发者文档/插件开发/en/03-manifest-spec.md`, `docs/开发者文档/插件开发/en/04-plugin-directory-structure.md`
- Change log:
  - `2026-03-13`: created the first development check review.
  - `2026-03-13`: added integration coverage checks.
  - `2026-03-13`: renamed by reading order and added document metadata.
  - `2026-03-13`: moved to `06` so the runnable walkthrough can use `05`.

This review answers one question: are the phase 1 documents good enough for a third-party developer to build a plugin by following the rules?

Short answer: yes. They are enough for a minimum version-one plugin, without forcing people to dig through backend code just to guess the rules.

## 1. What Was Reviewed

Document review scope:

- `specs/004.3-插件开发规范与注册表/README.md`
- `specs/004.3-插件开发规范与注册表/design.md`
- `docs/开发者文档/插件开发/en/01-plugin-development-overview.md`
- `docs/开发者文档/插件开发/en/03-manifest-spec.md`
- `docs/开发者文档/插件开发/en/04-plugin-directory-structure.md`
- `docs/开发者文档/插件开发/en/02-plugin-integration-guide.md`

Code review scope:

- `apps/api-server/app/modules/plugin/schemas.py`
- `apps/api-server/app/modules/plugin/service.py`
- `apps/api-server/app/modules/plugin/agent_bridge.py`
- `apps/api-server/app/plugins/builtin/health_basic/`
- `apps/api-server/app/plugins/builtin/homeassistant_device_sync/`
- `apps/api-server/app/plugins/builtin/homeassistant_device_action/`
- `apps/api-server/app/plugins/builtin/homeassistant_door_lock_action/`

## 2. What This Review Confirms

### The entry path is clear

A new developer can now tell:

- what document to read first
- which 4 plugin types are supported
- what the minimum development flow looks like
- what is explicitly out of scope

### The `manifest` rules are usable

The docs now clearly explain:

- the minimum required fields for version one
- the character rules for `id`
- the allowed values for `types`
- the real format requirements for `entrypoints`
- the current boundaries for action plugins and Agent plugins

### The directory structure is usable

The docs now clearly explain:

- one plugin per directory
- where `manifest.json` must live
- which module files are recommended for each plugin type
- how to lay out multi-capability plugins
- how to lay out action plugins

### The integration path is now explicit

The docs now clearly explain:

- how the system resolves and invokes plugin entrypoints
- what input plugin functions receive
- what `connector`, `memory-ingestor`, and `action` should return
- how data moves into raw records, normalized memory, and Agent usage
- which HTTP entries exist today and which platform features do not exist yet

## 3. Results Against Existing Built-In Plugins

### `health_basic`

- matches the multi-capability plugin rules
- matches the `connector + memory-ingestor` directory template
- matches the recommended `connector.sync` and `ingestor.transform` entrypoints

### `homeassistant_device_sync`

- matches the read-data plus normalized-memory pipeline
- matches the low-risk, manual-or-scheduled trigger guidance

### `homeassistant_device_action`

- matches the action plugin directory template
- matches the `device.control` permission declaration
- matches the `medium` risk action boundary

### `homeassistant_door_lock_action`

- matches the high-risk action guidance
- matches the manual confirmation boundary

## 4. What Was Intentionally Not Done Yet

These items are still intentionally deferred. They were not forgotten:

- detailed registry schema
- GitHub PR submission flow
- official vs third-party registry coexistence details
- automated review scripts
- marketplace frontend pages

These belong to later phases and should not be silently injected into phase 1.

## 5. Can Phase 1 Be Considered Done?

Yes.

Why:

1. Third-party developers can already tell what to read first and what to do next.
2. The `manifest` and directory rules map directly to existing plugin implementations.
3. The docs clearly keep the version-one boundary intact and do not sneak remote install, sandboxing, or signing systems back into scope.

Phase 2 can now move on to registry schema work and the GitHub PR process.
