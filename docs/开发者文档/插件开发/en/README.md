# Plugin Developer Docs

## Document Metadata

- Purpose: serve as the English entry point for plugin developer documentation, organized in reading order.
- Current version: v1.1
- Related documents: `docs/开发者文档/插件开发/README.md`, `docs/开发者文档/插件开发/zh-CN/README.md`
- Change log:
  - `2026-03-13`: created the English entry.
  - `2026-03-13`: switched to numbered reading order and added document metadata.

This directory stores the English plugin developer documentation.

These docs are now organized around the target third-party model: same-container subprocess runners.

Keep one boundary in mind:

- the repository already implements built-in same-process plugins
- the recommended target path for third-party plugins is `main service + same-container subprocess runner + plugin-owned venv`
- the public execution path already moved to “create a background job first, then let workers execute plugins”

## Current documents

- `01-plugin-development-overview.md`
- `02-plugin-dev-environment-and-local-debug.md`
- `03-manifest-spec.md`
- `04-plugin-directory-structure.md`
- `05-plugin-integration-guide.md`
- `06-build-a-runnable-plugin-walkthrough.md`
- `07-plugin-testing-and-in-project-validation.md`
- `08-plugin-registry-pr-submission.md`
- `09-development-check-review.md`

## Maintenance rules

- Put all future plugin developer docs here
- When you update a Chinese doc, update the matching English doc at the same time
- Keep both language trees aligned
