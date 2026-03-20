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
  - Scan compact marketplace cards first, then open a detail dialog for the plugin summary, version status, provider, categories, and per-version actions.
  - Pick a specific version to install, upgrade to, or roll back to from the marketplace detail dialog.
  - Review version states such as current version, latest version, latest compatible version, or blocked.
  - See the minimum host version and published time for each available version.
  - Check risk warnings before you install or enable a plugin.

## Typical workflow

1. Open the plugins page and confirm the selected family in the top-right corner is correct.
2. When you open the marketplace, the page refreshes enabled sources once automatically.
3. If you need a new plugin source, add the repository URL and branch in the source settings dialog, then run sync.
4. In the marketplace list, open the target plugin detail dialog and review the plugin summary, risk notes, version status, and provider information there.
   The dialog separates the plugin introduction from version information. The version update status describes the relationship between the installed version and the marketplace version; if the plugin is not installed yet, the UI shows `Not installed`.
5. If you need a specific release, use the **Versions** section in the detail dialog.
   Each row tells you:
   - whether this is the current version, the latest version, or the latest compatible version
   - which FamilyClaw version it requires at minimum
   - whether the current action is install, upgrade, rollback, current, or unavailable
   - why the version is unavailable when it cannot be selected
6. Confirm the version action in the confirmation dialog, then install, upgrade, roll back, enable, or disable the plugin as needed.
7. If the plugin needs configuration, continue in the Settings page or the AI Settings page. For example, AI provider plugins still need secrets and provider fields to be filled in after installation.

## States and warnings

- **Risk level**: `low`, `medium`, or `high`. This is informational, but high-risk plugins should be enabled carefully.
- **Version status**: examples include `installed`, `upgrade available`, `blocked`, and source labels such as official or third-party.
- **Versions list**: sorted from highest to lowest version, with each row showing its own host requirement and allowed action.
- **Unavailable reason**: when a version cannot be installed or switched to, the dialog explains why instead of making you guess.
- **Disable semantics**: after a plugin is disabled, it cannot be newly used and it cannot execute, but it can still be viewed and configured.

## Common issues

- **Enable failed**: check whether the plugin's required configuration is complete or whether the page shows a disable reason.
- **An older version cannot be selected**: check the unavailable reason under that version. The most common causes are a host version that is too old or missing compatibility metadata for that release.
- **Marketplace source sync failed**: confirm the repository URL, branch, and network connectivity.
- **Marketplace list did not change**: source refresh is incremental now. If nothing changed upstream, the backend keeps the existing snapshot instead of re-fetching everything.
- **Theme or language pack stopped working**: if the related plugin is disabled or uninstalled, those resources stop applying. Switch to another available plugin resource.

## Completion standard

- You can browse, install, enable, disable, and inspect plugin versions from the plugins page.
- You understand which execution paths are blocked after a plugin is disabled, so you do not confuse disable behavior with a product bug.
