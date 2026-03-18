# Plugin Developer Docs

## Document Metadata

- Purpose: serve as the English entry point for plugin developer documentation, organized around stable rules first and fast-changing references later.
- Current version: v1.4
- Related documents: `docs/开发者文档/插件开发/README.md`, `docs/开发者文档/插件开发/zh-CN/README.md`
- Change log:
  - `2026-03-13`: created the English entry.
  - `2026-03-13`: switched to numbered reading order and added document metadata.
  - `2026-03-14`: added the scheduled-task API and OpenAPI guide.
  - `2026-03-16`: reorganized the reading order into stable rules and fast-changing references, and added plugin configuration integration guidance.
  - `2026-03-18`: added household region-coordinate boundaries, including the `region-provider` coordinate contract and the unified `coordinate` runtime result.

This directory stores the English plugin developer documentation.

## 2026-03-17 Current boundary

The formal plugin type set is now 9 types:

- `connector`
- `memory-ingestor`
- `action`
- `agent-skill`
- `channel`
- `locale-pack`
- `region-provider`
- `theme-pack`
- `ai-provider`

`theme-pack` and `ai-provider` are no longer side systems. They now belong to the same general plugin system.

If you are changing plugin enable/disable rules, read:

- `docs/开发设计规范/20260317-插件启用禁用统一规则.md`

If you are changing version-governance boundaries, read:

- `specs/004.5-插件能力统一接入与版本治理/docs/20260317-插件版本治理现状与最小能力说明.md`

These docs are now organized around the target third-party model: same-container subprocess runners.

Keep one boundary in mind:

- the repository already implements built-in same-process plugins
- the recommended target path for third-party plugins is `main service + same-container subprocess runner + plugin-owned venv`
- the public execution path already moved to “create a background job first, then let workers execute plugins”

If your change touches either of these areas, read `03` and `05` first before touching code:

- `region-provider` node payloads
- `household_region_context` consumption

Since `2026-03-18`, household region context now carries a formal unified `coordinate` result. Upper-layer plugins should consume that object directly instead of guessing coordinates from `city` text.

## What To Read First

### Stable rules first

- `00-how-to-use-and-maintain-these-docs.md`
- `01-plugin-development-overview.md`
- `03-manifest-spec.md`
- `04-plugin-directory-structure.md`
- `08-plugin-registry-pr-submission.md`
- `11-plugin-configuration-integration.md`

### Practical guides when needed

- `02-plugin-dev-environment-and-local-debug.md`
- `06-build-a-runnable-plugin-walkthrough.md`
- `07-plugin-testing-and-in-project-validation.md`

### Fast-changing references, not long-term rules

- `05-plugin-integration-guide.md`
- `10-scheduled-task-api-and-openapi-guide.md`
- `specs/004.2.3-插件配置协议与动态表单/docs/`
- `apps/api-server/app/modules/plugin/schemas.py`
- `apps/api-server/app/api/v1/endpoints/ai_config.py`

## Maintenance rules

- Put all future plugin developer docs here
- When you update a Chinese doc, update the matching English doc at the same time
- Keep both language trees aligned
- Stable docs should not duplicate API examples that already have a more volatile source of truth
