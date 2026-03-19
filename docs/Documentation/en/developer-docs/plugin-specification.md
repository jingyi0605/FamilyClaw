---
title: Plugin Specification
docId: en-4.4
version: v0.1
status: draft
order: 440
outline: deep
---

# Plugin Specification

## What this page solves

- It explains the boundary between the host and plugins in plain language.

## Current stable position

- The host owns rules, entry points, permissions, audit, scheduling, and standard data semantics.
- Plugins own third-party integration, mapping, and capability extension.
- Devices, entities, cards, and actions returned by plugins must already match the host standard shape.

## Current official plugin types

- `integration`
- `action`
- `agent-skill`
- `channel`
- `region-provider`
- `ai-provider`
- `locale-pack`
- `theme-pack`

## Exclusive slots

- `memory_engine`
- `memory_provider`
- `context_engine`

## Completion standard

- Plugin authors know what belongs in the host and what must stay inside plugins.
