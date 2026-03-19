---
title: Core Features
docId: en-1.4
version: v0.1
status: draft
order: 140
outline: deep
---

# Core Features

## Current core modules

- Dashboard: family overview, reminders, weather and health cards, plus quick entry points.
- Family: manages family data, members, rooms, and permissions. This is the root of everything else.
- Conversations: the text conversation entry is available, and the voice gateway is optional on port `4399`.
- Memory: long-term memory for events, preferences, and relationships, with query and revision support.
- Settings: one place for AI providers, themes, plugins, accounts, timezone, and language.
- Plugins: AI providers, channels, theme packs, and more are managed as plugins, with enable, disable, and configuration support.

![fc-doc-20260319T231506.webp](../../快速开始/assets/fc-doc-20260319T231506.webp)
Placeholder for screenshot: main product interface overview

![fc-doc-20260319T231556.webp](../../快速开始/assets/fc-doc-20260319T231556.webp)

## Capability boundary

- Host system: rules, permissions, scheduling, standard data models, logs, and auditing.
- Plugins: connect to third-party APIs, devices, and models, then produce standardized entities, cards, and action results.

## Recommended follow-up reading

- If you want click-by-click guidance, read the [User Guide](../user-guide/dashboard.md).
- If you want it running, read [Installation](../installation-deployment/overview.md).
- If you want to customize it, read the [Developer Docs](../developer-docs/environment-setup.md) and the plugin topics.
