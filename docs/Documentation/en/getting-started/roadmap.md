---
title: Roadmap
docId: en-1.15
version: v0.1
status: draft
order: 115
outline: deep
---

# Roadmap

This page does one thing only: it states the actual project status as of March 22, 2026.

Do not treat it like marketing copy. It is split directly into what is already finished, what is still under active development, and what is only planned next.

## How to read this page

| Status | Decision rule | What it means |
| --- | --- | --- |
| Implemented | The feature is already truly usable or already delivered as a real product capability | Use it now instead of pretending it is still “in progress” |
| In Progress | The direction is confirmed and the work is still being implemented, integrated, or optimized | The target is real, but it is not fully closed yet |
| Planned | The direction is clear, but it is not yet in the current delivery path | Know that it is coming, but do not read it as already available |

## Implemented

| Area | What is already shipped | What you can do now | Docs |
| --- | --- | --- | --- |
| Installation and deployment | Docker, source, NAS, Ubuntu, and Windows paths | Deploy the system without inventing your own process | [Installation Overview](../installation-deployment/overview.md) |
| Dashboard and family management | Home cards, quick entry points, family, room, and member organization | Land on a usable home page first, then manage family basics | [Dashboard](../user-guide/dashboard.md), [Family](../user-guide/households.md) |
| Conversations and assistants | Multi-session chat, assistant switching, streaming replies, suggested prompts, proposals, action records, and quick jumps | Start chatting from the `Personal` tab and handle proposals or actions inline | [Conversations](../user-guide/conversations.md) |
| Memory management | Memory list, filters, search, detail view, correction, invalidation, and deletion | Review what the system remembers and fix bad memories manually | [Memory](../user-guide/memory.md) |
| Settings and AI connectivity | Theme, language, timezone, device and integration settings, AI provider plugins, and local model access | Configure `Ollama`, `LM Studio`, `LocalAI`, and common cloud providers | [Settings](../user-guide/settings.md) |
| Plugin system and marketplace | Plugin browsing, detail pages, enable/disable, marketplace actions, and visible dev-vs-installed variants | Install, upgrade, roll back, uninstall, and switch plugin variants | [Plugins](../user-guide/plugins.md) |
| Xiaomi speaker integration | `open-xiaoai` client access, gateway discovery, device sync, and wake-prefix configuration | Bring a flashed Xiaomi speaker into the household workflow | [Xiaomi Speaker Integration](../user-guide/xiaomi-speaker-integration.md) |
| Cross-platform onboarding guide | Post-setup guide trigger, restore, skip, and reopen flow | New users already have a real onboarding path instead of a paper-only design | [First Login & Setup](../user-guide/first-login-and-setup.md) |
| Family memory center | Household memory viewing, correction, invalidation, and revision history management | The family memory center itself is already done and should not stay in a future bucket | [Memory](../user-guide/memory.md) |
| Unified device and integration capability | Device access, integration instances, sync, and one configuration entry | Devices and integrations are already a real product capability, not just an unfinished refactor | [Settings](../user-guide/settings.md), [Xiaomi Speaker Integration](../user-guide/xiaomi-speaker-integration.md) |
| Chat and task action mainline | Session management, proposal confirmation, action history, and schedule-related action entry points | The chat mainline already handles real actions instead of being only a demo conversation page | [Conversations](../user-guide/conversations.md) |
| Plugin execution foundation | Dynamic config, plugin lifecycle control, installation and upgrade flow, and task capability entry points | Plugins already carry real extensibility instead of being a passive catalog | [Plugins](../user-guide/plugins.md), [Plugin Development](../developer-docs/plugin-development.md) |
| Multi-platform product shell | The current user-app shell, navigation, and core high-frequency flows across platforms | The base multi-platform product shell is already running; the remaining work is mobile polish, not a greenfield build | [Dashboard](../user-guide/dashboard.md), [Settings](../user-guide/settings.md) |
| Plugin development baseline | Plugin rules, directory structure, field rules, integration flow, example plugin, and submission guide | Developers already have a workable plugin development path | [Plugin Development](../developer-docs/plugin-development.md) |

## In Progress

| Area | Current state | What this work is closing | Source |
| --- | --- | --- | --- |
| Layered long-term memory and recall | In development | Push memory beyond basic storage into layered recall, ranking, and real prompt injection | This is still an active mainline effort |
| Persona-based Agent assistant | In development | The family memory center is already done; the current work is the persona system, role config, and member awareness around the Agent | The unfinished part is the Agent persona itself |
| Voiceprint recognition optimization | In development | Continue improving capture quality, recognition accuracy, and device-side experience | The voice chain is still being tuned |
| Multi-channel communication access | In development | Focus on real channels such as WeCom and QQ so the product is not limited to the web entry | Current focus is WeCom and QQ |
| Mobile clients | In development | Keep tightening Android and iOS into full product-grade mobile clients instead of stopping at the existing cross-platform shell | Current focus is Android and iOS |
| Xiaomi camera face recognition and visual analysis | In development | Add face recognition, visual analysis, and related household scenarios around Xiaomi cameras | This is an explicitly active vision track |

## Planned

| Area | Planned work | Why it matters | Source |
| --- | --- | --- | --- |
| Photo and album foundation | Build the base for photo access, organization, retrieval, and later expansion | This is the lower layer for future visual and family-memory scenarios | Confirmed as a next-phase capability |
| Family feed | Create a shared family stream for content, interaction, and long-term household activity | This is how family information becomes family interaction | Confirmed as a future product direction |
| Public chat | Add a shared household chat space beyond private conversations | It gives family members one shared conversational context for common matters | Confirmed as a future product direction |
| Presence recognition through Bluetooth devices | Identify who is present through Bluetooth devices | This is useful for household automation and contextual awareness | Confirmed as a future recognition direction |
| Centralized plugin marketplace | Further centralize plugin discovery, distribution, and governance | Plugin capability already exists; the next step is to make the market more unified and easier to manage | Confirmed as a future platform direction |
| Community hub | Build an official community entry and a long-term communication space | This is required if plugins, feedback, and project collaboration are going to scale | Confirmed as a future community direction |

## How to use this page

- If you need to deploy or use the product now, start from the Implemented section.
- If you need to decide whether something can be promised externally, check whether it is Implemented or only In Progress / Planned.
- If you want to contribute code, this page is only the index; the real source of truth is the related official docs and Specs.

## Bottom line

FamilyClaw is already well past the empty-shell stage. Installation, dashboard, family management, conversations, memory, settings, plugins, device access, and the base multi-platform product shell are already finished and should not keep pretending to live in the “in progress” bucket.

The real active work now is narrower: layered memory recall, a persona-based Agent, voiceprint optimization, multi-channel communication access, mobile clients, and Xiaomi-camera-based face recognition and visual analysis. That boundary is the whole reason this roadmap exists.
