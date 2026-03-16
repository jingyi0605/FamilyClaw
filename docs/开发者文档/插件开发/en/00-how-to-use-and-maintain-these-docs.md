# 00 How To Use And Maintain These Docs

## Document Metadata

- Purpose: explain how plugin developer docs should be read and maintained, so small plugin-system changes do not force large documentation rewrites.
- Current version: v1.0
- Related documents: `docs/开发者文档/插件开发/en/README.md`, `docs/开发者文档/插件开发/en/03-manifest-spec.md`, `docs/开发者文档/插件开发/en/05-plugin-integration-guide.md`, `docs/开发者文档/插件开发/en/11-plugin-configuration-integration.md`
- Change log:
  - `2026-03-16`: created the first version of the doc usage and maintenance rules.

This document answers one question:

- which docs should stay stable
- which details should be referenced instead of copied everywhere

## 1. Split The Docs Into Two Layers

Plugin developer docs should now be split into two layers by default.

### A. Stable rule docs

These should change as little as possible.

They explain:

- conceptual boundaries
- data-structure rules
- what not to do
- integration order
- which document is the real source of truth

Typical examples:

- `01-plugin-development-overview.md`
- `03-manifest-spec.md`
- `04-plugin-directory-structure.md`
- `08-plugin-registry-pr-submission.md`
- `11-plugin-configuration-integration.md`

### B. Fast-changing reference docs

These can change more often, but the same field matrix should not be duplicated across five documents.

They carry:

- current API paths
- current request/response examples
- current UI component names
- currently supported field types, widgets, and routes
- current code file locations

Typical examples:

- `05-plugin-integration-guide.md`
- `10-scheduled-task-api-and-openapi-guide.md`
- `specs/004.2.3-插件配置协议与动态表单/docs/`
- `apps/api-server/app/modules/plugin/schemas.py`
- `apps/api-server/app/api/v1/endpoints/ai_config.py`

## 2. One Hard Rule: Do Not Copy Fast-Changing Details

Use this rule from now on:

- stable docs explain the why and the boundary
- fast-changing API and example details should have a single source of truth

For plugin configuration, for example:

- why `config_specs` exists in `manifest` is a stable rule
- which field types, widgets, and API shapes are supported right now is a fast-changing implementation detail

The first belongs in the developer handbook.

The second should point to:

- `specs/004.2.3-插件配置协议与动态表单/docs/20260316-manifest-示例.md`
- `specs/004.2.3-插件配置协议与动态表单/docs/20260316-api-示例.md`
- `apps/api-server/app/modules/plugin/schemas.py`

Do not copy that content into every handbook page.

## 3. Update Order

When the plugin system changes, update docs in this order:

1. update the source-of-truth code first
2. update the matching Spec or example docs second
3. update stable handbook pages only if the rule itself changed

If only API paths, examples, or support ranges changed:

- do not start by rewriting the high-level overview
- update the source-of-truth and reference docs first

If only UI component names, file paths, or request examples changed:

- update only the fast-changing reference docs
- keep the stable rule docs mostly unchanged

## 4. Source-Of-Truth Priority

For plugin development topics, use this order:

1. code-level schemas, services, and endpoints
2. matching Spec docs and implementation examples
3. the developer handbook

If the handbook conflicts with the code:

- follow the code and the current Spec
- then go back and fix the handbook

Do not force the implementation backwards just because an older handbook page says so.

## 5. What This Structure Is Trying To Prevent

This structure is not about making docs look elegant. It is about stopping two practical failures:

1. one plugin-system change makes a large set of docs stale at once
2. developers follow old docs and keep spreading field definitions across host pages and business code

So the goal is simple:

- keep stable rules tight
- centralize changing details
- keep one source of truth
