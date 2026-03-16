# 11 Plugin Configuration Integration

## Document Metadata

- Purpose: explain why plugin configuration must use a formal protocol, which rules are stable, and where fast-changing details should live.
- Current version: v1.0
- Related documents: `docs/开发者文档/插件开发/en/03-manifest-spec.md`, `docs/开发者文档/插件开发/en/05-plugin-integration-guide.md`, `specs/004.2.3-插件配置协议与动态表单/README.md`
- Change log:
  - `2026-03-16`: created the first plugin configuration integration guide.

This document does not duplicate large API examples. It explains only the stable rules.

## 1. The Short Version

If a plugin needs user-facing configuration in the management UI, it should use the formal configuration protocol.

Do not go back to these older patterns:

- host pages maintaining their own field constants
- a business table hiding one JSON blob as the only source of truth
- treating secrets like normal strings on reads

Those shortcuts turn into junk fast.

## 2. What The Formal Protocol Is

The formal entry lives in `manifest.json`:

- `config_specs`

Each config scope must declare at least:

- `scope_type`
- `schema_version`
- `config_schema`
- `ui_schema`

Two stable rules matter here:

1. field definitions must have one source of truth, which is the plugin manifest
2. host pages only read the protocol, render the form, and submit config data

## 3. Scope Types Supported In Version One

This version supports only two scopes:

- `plugin`
- `channel_account`

Use them like this:

- if the household has only one config instance, use `plugin`
- if each channel account has its own config, use `channel_account`

Do not invent third or fourth scope layers right now.

## 4. Hard Rules For Secret Fields

`secret` is not a normal string field.

Two rules are fixed:

1. reads must never return the plaintext value
2. if the client does not submit the field, the previous stored value is kept

If you want to clear the stored value, use:

- `clear_secret_fields`

This semantic is stable. It should not change from page to page.

## 5. Stored Configuration And Runtime Copies Are Not The Same Thing

Separate these two ideas:

- formal config instances: stored through the unified config protocol and config-instance table
- compatibility runtime copies: older paths may still keep a mirror so current behavior is not broken

For example, channel plugins may still mirror data into older `config_json` fields so the existing runtime path keeps working.

That does not make the old field the source of truth anymore.

The source of truth is now the formal protocol.

## 6. What Not To Freeze In This Doc

These details change faster and should not be duplicated here:

- the full current list of field types
- the full current list of widgets
- current request/response examples
- current page or component names

Use these sources instead:

- `specs/004.2.3-插件配置协议与动态表单/docs/20260316-manifest-示例.md`
- `specs/004.2.3-插件配置协议与动态表单/docs/20260316-api-示例.md`
- `apps/api-server/app/modules/plugin/schemas.py`
- `apps/user-web/src/lib/types.ts`

## 7. The Five Things Plugin Authors Must Remember

If you build a plugin, remember these five:

1. if the plugin needs configuration, declare `config_specs`
2. keep field definitions only in the manifest
3. choose between `plugin` and `channel_account` correctly
4. never echo secrets; clear them only through `clear_secret_fields`
5. host pages should not hardcode fields by plugin id anymore
