---
title: Integration Flow
docId: en-4.7
version: v0.1
status: draft
order: 470
outline: deep
---

# Integration Flow

## Current main flows

### integration

1. The host reads the manifest.
2. It validates the type, entry points, and capability declaration.
3. It injects runtime context and formal configuration.
4. It calls `integration.refresh`.
5. The plugin returns standard results.
6. The host validates, deduplicates, stores, and updates status.

### action

1. The host checks that the plugin is enabled.
2. It checks permissions and risk level.
3. It requests confirmation when required.
4. It calls the action entry point.

### ai-provider

1. The host locates the matching plugin.
2. It loads `entrypoints.ai_provider`.
3. It calls the unified driver interface.
4. The host owns permission, audit, secret, and result handling.

## Hard boundaries

- Entry points should consume JSON-serializable payloads.
- Do not depend on request objects, ORM sessions, or non-serializable objects.
- Standard DTO output is mandatory.

## Completion standard

- Plugin authors understand how the host calls them and what shape the output must have.
