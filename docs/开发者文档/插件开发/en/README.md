# Plugin Developer Docs

## Document Metadata

- Purpose: serve as the English entry point for plugin developer documentation, organized around stable rules first and fast-changing references later.
- Current version: v1.3
- Related documents: `docs/开发者文档/插件开发/README.md`, `docs/开发者文档/插件开发/zh-CN/README.md`
- Change log:
  - `2026-03-13`: created the English entry.
  - `2026-03-13`: switched to numbered reading order and added document metadata.
  - `2026-03-14`: added the scheduled-task API and OpenAPI guide.
  - `2026-03-16`: reorganized the reading order into stable rules and fast-changing references, and added plugin configuration integration guidance.

This directory stores the English plugin developer documentation.

These docs are now organized around the target third-party model: same-container subprocess runners.

Keep one boundary in mind:

- the repository already implements built-in same-process plugins
- the recommended target path for third-party plugins is `main service + same-container subprocess runner + plugin-owned venv`
- the public execution path already moved to “create a background job first, then let workers execute plugins”

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
