---
title: Dashboard
docId: en-3.1
version: v0.1
status: draft
order: 310
outline: deep
---

# Dashboard

## Page status

- **Status**: The H5 dashboard is available. You must log in and complete the initialization wizard first.
- **Entry**: after login, the app redirects to `/pages/home/index`. If you are not logged in, Guard redirects you to login or the setup wizard.

## What you can see

- Family welcome area: shows the current family and member nickname.
- Card area: built-in cards such as weather, family statistics, rooms, members, events, and quick actions. Some cards come from plugins or integrations.
- Card states: `normal`, `empty`, `stale`, and `error`. When a card fails, the page shows the reason.
- Quick actions: jump to conversations, memory, settings, family, and other core pages.

![fc-doc-20260319T234836.webp](../../使用指南/assets/fc-doc-20260319T234836.webp)

## How to use it

1. After opening the dashboard, first confirm the selected family and member in the upper-right corner so you know you are in the correct context.
2. Review the cards:
   - Weather card: powered by the weather plugin. It shows current conditions and temperature or humidity. If it looks wrong, check the plugin state and region settings first.
   - Statistics card: shows counts such as members, rooms, devices, and reminders. The data comes from the backend `/dashboard/home`.
   - Event or reminder cards: show recent to-dos or schedules.
   - Quick action cards: jump directly to conversations, memory, settings, and similar entries.
3. Adjust the layout:
   - Drag the six-dot handle in the upper-left corner of a card to reorder it.
   - Drag the lower-right corner to switch between half width or full width and compact, regular, or tall heights.
   - Layout changes are saved automatically for the current member.

> Screenshot placeholder: dragging cards to change width and height

## Common issues

- **A card stays on loading or error for a long time**: check the network and confirm the current family context is correct, then verify the related plugin or integration is enabled.
- **Weather card has no data**: confirm the region was selected during initialization or later in Settings, and make sure an available weather plugin is installed.
- **Layout was not saved**: the browser must allow local storage, and the previous layout should also be restored from the server after login.

## Completion standard

- A first-time user can understand what each dashboard card is for.
- The user knows how to drag cards, resize them, and recognize that the layout is saved automatically.
