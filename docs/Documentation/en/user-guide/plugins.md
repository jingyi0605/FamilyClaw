---
title: Plugins
docId: en-3.6
version: v0.1
status: draft
order: 360
outline: deep
---

# Plugins

## Page status

- **Status**: The H5 plugins page is available. The entry is `/pages/plugins/index`, and it requires login plus a valid family context.
- **Purpose**: install, enable, disable, and inspect plugins, then manage plugin marketplace sources.

![fc-doc-20260320T000611.webp](../../使用指南/assets/fc-doc-20260320T000611.webp)

## What you can do

- Browse the plugin registry. Built-in, official, and third-party plugins all show their source, risk level, version state, and availability.
- Switch between card view and list view.
- Manage installation sources:
  - View existing marketplace sources.
  - Add new sources from GitHub, GitLab, Gitee, or Gitea.
  - Run source synchronization.
- Work with plugins:
  - Install, enable, or disable them.
  - Review version governance states such as current version, upgrade available, or blocked.
  - Check configuration requirements and risk warnings.

## Typical workflow

1. Open the plugins page and confirm the selected family in the top-right corner is correct.
2. If you need a new plugin source, add the repository URL and branch in the marketplace source area, then click sync.
3. In the list, select the target plugin:
   - Review the detail panel and risk notes.
   - Click **Install** or **Enable**. If you disable a plugin, all later execution paths that depend on it are blocked.
4. If the plugin needs configuration, continue in the Settings page or the AI Settings page. For example, AI provider plugins still need secrets and provider fields to be filled in after installation.

## States and warnings

- **Risk level**: `low`, `medium`, or `high`. This is informational, but high-risk plugins should be enabled carefully.
- **Version status**: examples include `installed`, `upgrade available`, `blocked`, and source labels such as official or third-party.
- **Disable semantics**: after a plugin is disabled, it cannot be newly used and it cannot execute, but it can still be viewed and configured.

## Common issues

- **Enable failed**: check whether the plugin's required configuration is complete or whether the page shows a disable reason.
- **Marketplace source sync failed**: confirm the repository URL, branch, and network connectivity.
- **Theme or language pack stopped working**: if the related plugin is disabled or uninstalled, those resources stop applying. Switch to another available plugin resource.

## Completion standard

- You can browse, install, enable, disable, and inspect plugin versions from the plugins page.
- You understand which execution paths are blocked after a plugin is disabled, so you do not confuse disable behavior with a product bug.
