---
title: Plugin Specification
docId: en-4.4
version: v0.1
status: active
order: 440
outline: deep
---

# Plugin Specification

This page fixes the boundary between the host and plugins so people stop treating plugins as a trash can for random logic.

## What this page is for

This page is the current baseline for plugin boundaries inside the official docs site.

If supplementary repo materials disagree with this page, start from this page and the current code facts, then verify against the code. Do not force readers to piece the rule set together outside `docs/Documentation`.

Current direct fact sources include:

- `apps/api-server/app/modules/plugin/schemas.py`
- `apps/api-server/app/modules/plugin/`
- `apps/api-server/app/plugins/builtin/`

## What the host does and what plugins do

| Capability | Host owns it | Plugin owns it |
| --- | --- | --- |
| Household, member, room, and permission data | yes | no |
| Plugin registration, mount, enable, disable | yes | no |
| Config value and secret storage | yes | no |
| Scheduling, retry, audit | yes | no |
| Third-party APIs, devices, and platforms | no | yes |
| Third-party field mapping | no | yes |
| Standard entities, cards, and action semantics | yes | no |
| Plugin-local cache and provider-specific handling | no | yes |

One sentence version:

The host is the platform kernel. Plugins are the domain integration layer.

## Current official plugin types

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

## Boundaries for plugin-private state

Plugins may have their own:

- private tables
- private cache
- refresh cursors
- raw snapshots

But the host core should not:

- import plugin-private ORM models directly
- register plugin-private models into the host global model aggregation
- query plugin-private tables directly with SQL

The host should only consume standardized DTOs, standard state tables, and public interfaces.

## Enable and disable semantics

The final state should be determined only by:

- `PluginRegistryItem.enabled`
- `PluginRegistryItem.disabled_reason`

Correct disable semantics mean:

- it cannot be newly used
- it cannot continue executing
- it cannot continue automatic triggering
- but it can still be viewed
- and it can still be configured

Execution paths must apply one consistent validation rule. One page is not allowed to block a plugin while a background worker still runs it anyway.

If you are changing this logic, read the plugin enable/disable section in [Backend Development](./backend-development.md) as well. Do not patch only one endpoint.

## Configuration dependency rules

Dynamic configuration dependency is a host capability. Plugins do not get to invent their own private protocol for this.

Current official dynamic option sources:

- `region_provider_list`
- `region_catalog_children`

Plugins declare:

- field dependencies
- `option_source`
- which fields must be cleared when a dependency changes

The host handles:

- dependency parsing
- dynamic option recalculation
- config draft persistence

## Boundaries for theme and locale plugins

### `theme-pack`

It must declare:

- `theme_id`
- `display_name`
- `tokens_resource` or `entry_resource`
- `resource_source`
- `resource_version`
- `theme_schema_version`
- `platform_targets`

The host and frontend runtime now only rely on plugin resources. They no longer rely on hidden static theme tables inside the host.

### `locale-pack`

This type provides a full language resource pack.

Normal plugins may also declare their own `locales`, but only for their own text. They cannot pretend to be the full system language pack.

## Boundary for AI provider plugins

`ai-provider` plugins own:

- provider field schemas
- adapter capability declarations
- driver entry points
- provider protocol adaptation

The host owns:

- AI routing
- permissions
- secret references
- audit
- downgrade and fallback

## Most important evaluation rule

If a capability goes live and the host still needs a pile of domain-specific branches just for that one plugin, then the plugin failed to absorb the complexity. The design is not good enough.
