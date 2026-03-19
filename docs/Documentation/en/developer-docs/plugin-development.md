---
title: Plugin Development
docId: en-4.3
version: v0.1
status: active
order: 430
outline: deep
---

# Plugin Development

Plugin development is not "adding a patch point into the host." It is the current official extension model in FamilyClaw.

If you do not remember the full rule set yet, remember these four lines first:

1. The host only keeps platform rules and unified standards.
2. Third-party integration, field mapping, and provider-specific behavior should go into plugins first.
3. Plugin output must already be standardized. The host should not need patch-style repair logic afterward.
4. Whether a plugin can execute is determined only by the unified enabled/disabled state, not by page-specific guesses.

## Read these pages first

Recommended order:

1. Read [Plugin Specification](./plugin-specification.md) first so you understand the host-plugin boundary.
2. Then read [Field Specification](./plugin-fields.md) so you write `manifest.json` and config schemas correctly.
3. Then read [Integration Flow](./plugin-integration.md) so you understand execution flow and integration endpoints.
4. Then read [Example Plugin](./plugin-example.md) and compare against real built-in plugins.
5. Finally, read [Plugin Submission](./plugin-submission.md) and use it as your delivery checklist.

These pages together form the current plugin development handbook inside the official docs site. You do not need to leave `docs/Documentation` to piece the rules together.

## Current official plugin types

Based on `apps/api-server/app/modules/plugin/schemas.py`, the current official types are:

- `integration`
- `action`
- `agent-skill`
- `channel`
- `locale-pack`
- `region-provider`
- `theme-pack`
- `ai-provider`

Exclusive slots:

- `memory_engine`
- `memory_provider`
- `context_engine`

## What should become a plugin

### Good plugin candidates

- third-party API integrations
- third-party device protocol adapters
- model provider integrations
- communication platform channels
- theme resources and locale resources
- region catalogs and region parsing

### What should not become a plugin

- host-owned data such as families, members, rooms, and permissions
- host-wide audit
- host-wide scheduling
- host-wide standard entity, card, and action semantics

## What already exists in the repository

Built-in plugins live under:

- `apps/api-server/app/plugins/builtin/`

Current examples include:

- AI providers such as `ai_provider_chatgpt`, `ai_provider_claude`, and `ai_provider_qwen`
- channels such as `channel_feishu`, `channel_discord`, and `channel_telegram`
- the `health_basic` integration
- theme packs such as `theme_chun_he_jing_ming_pack`
- locale packs such as `locale_zh_tw_pack`

These are not conceptual examples. They already exist in the repository now.

## Minimal development flow

### 1. Decide the type before you write code

Decide whether it is:

- `integration`
- `action`
- `channel`
- `ai-provider`
- or another official type

If the type is wrong, the manifest, execution path, and config scope all go wrong with it.

### 2. Write `manifest.json` first

The host reads the manifest first and decides how your plugin is loaded.

At minimum, write:

- `id`
- `name`
- `version`
- `api_version`
- `types`
- `permissions`
- `risk_level`
- `entrypoints`
- `capabilities`

### 3. Then implement the entry code

Examples:

- an `integration` entry
- a `channel` entry
- an `ai_provider` entry

The code path must match the `manifest.json` declaration exactly.

### 4. Then connect configuration

If the plugin needs user-provided values, add:

- `config_specs`

Do not hide the config contract in code and expect the frontend to guess your fields.

### 5. Validate it inside the host

At minimum, confirm:

- the plugin can be discovered
- the plugin state is visible
- configuration can be saved
- the execution entry really runs
- disable state blocks execution consistently

## What the host currently owns

- plugin registration and mounting
- enable/disable governance
- config value storage
- permissions, audit, and scheduling
- standard entity, card, and action semantics
- plugin marketplace and version governance

## What the plugin currently owns

- third-party platform integration
- mapping third-party fields into host-standard data
- plugin-local cache, deduplication, rate limiting, and vendor-specific logic
- producing final standardized DTOs

## Common mistakes during development

### 1. Putting host-owned data into a plugin

That is not faster implementation. That is a broken boundary.

### 2. Making the host patch plugin output at read time

If the host still needs `if plugin_type == ...` just to understand the result, your plugin output was never standardized.

### 3. Inventing your own scheduler

Scheduled tasks, background jobs, and retry policy belong to the host.

Plugins should declare capability, not register their own private cron layer.

### 4. Ignoring disable semantics

After a plugin is disabled:

- it cannot be newly used
- it cannot continue executing
- but it can still be viewed and configured

That rule must match the whole system.

## Built-in plugins worth studying

- `apps/api-server/app/plugins/builtin/health_basic/manifest.json`
  Good for the smallest `integration` example and dashboard card declaration.
- `apps/api-server/app/plugins/builtin/ai_provider_chatgpt/manifest.json`
  Good for `ai-provider` schema and compatibility fields.
- `apps/api-server/app/plugins/builtin/channel_feishu/manifest.json`
  Good for channel config, UI schema, and binding capability.
- `apps/api-server/app/plugins/builtin/theme_chun_he_jing_ming_pack/manifest.json`
  Good for `theme-pack` resource declaration.

## When you should stop and rethink

If you notice yourself preparing to:

- add another domain-specific host service
- add another set of exceptions for one plugin type
- make the frontend or backend each add their own compatibility patch

stop first. The problem is probably not missing logic. The problem is that the boundary is already starting to rot.
