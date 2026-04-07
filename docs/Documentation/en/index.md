---
layout: home
title: FamilyClaw Docs
titleTemplate: FamilyClaw Docs
docId: en-home
version: v0.1.3
status: active
hero:
  name: FamilyClaw Docs
  text: Start installation, usage, and development from here
  tagline: This documentation only describes what already exists in the current product and repository. User-facing pages are written for first-time users. Developer pages are written from the real implementation and the real boundaries.
  actions:
    - theme: brand
      text: Start with Getting Started
      link: /en/getting-started/docs-overview
    - theme: alt
      text: Open Installation
      link: /en/installation-deployment/overview
    - theme: alt
      text: Open User Guide
      link: /en/user-guide/first-login-and-setup
    - theme: alt
      text: Open Developer Docs
      link: /en/developer-docs/environment-setup
    - theme: alt
      text: 中文文档
      link: /
features:
  - title: Friendly to first-time users
    details: Installation and user guides default to the perspective of someone touching FamilyClaw for the first time, so steps are intentionally explicit.
  - title: Real current state only
    details: Developer docs only describe the current repository, scripts, interfaces, and rules. Draft ideas and historical plans are not presented as current behavior.
  - title: Separate user and developer paths
    details: Users can stay in Getting Started, Installation, and User Guide. Developers can go directly to Developer Docs, plugin topics, and integration references.
---

## Which section to open first

- If this is your first time seeing FamilyClaw, start with [Getting Started](/en/getting-started/docs-overview).
- If your goal is to get FamilyClaw running quickly, open [Installation](/en/installation-deployment/overview).
- If FamilyClaw is already installed and you want to learn how the pages work, open the [User Guide](/en/user-guide/first-login-and-setup).
- If you need to change code, integrate APIs, or write plugins, open the [Developer Docs](/en/developer-docs/environment-setup).

## How these docs are written

- User-facing pages answer what to click next, what to fill in, and where people usually make mistakes.
- Developer pages answer where the real entry points are, where the boundaries are, and what should not be touched casually.
- If a feature, command, or deployment path does not exist in the repository, it does not belong in the official docs.
- English remains under `/en/`. The Chinese root path is the primary maintenance entry.

## Current documentation structure

- `Getting Started`: understand the product first, then choose installation, usage, or development.
- `Installation`: covers Docker, source, NAS, Ubuntu, and Windows paths.
- `User Guide`: covers first login, dashboard, family, assistant, memory, settings, and plugins.
- `Developer Docs`: covers development environment, backend boundaries, the plugin system, integration flow, and current rules.
- `Community`: keeps the official website and community entry points.
