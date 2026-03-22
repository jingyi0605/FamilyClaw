---
title: Directory Structure
docId: en-4.5
version: v0.1
status: active
order: 450
outline: deep
---

# Directory Structure

This page skips fluff and only explains the directories that are actually worth remembering in the current repository.

## Project-level directories

```text
FamilyClaw/
├── apps/
│   ├── api-server/
│   ├── user-app/
│   ├── open-xiaoai-gateway/
│   ├── start-api-server.sh
│   └── start-open-xiaoai-gateway.sh
├── packages/
│   ├── user-core/
│   ├── user-platform/
│   └── user-ui/
├── docs/
│   ├── Documentation/
│   ├── 开发设计规范/
│   └── 开发者文档/
├── docker/
├── specs/
├── package.json
└── Dockerfile
```

## What each directory is for

### `apps/api-server`

The main backend service.

Look at:

- `app/main.py`
- `app/api/v1/`
- `app/modules/`
- `app/core/`
- `migrations/`

### `apps/user-app`

The main frontend application, built with Taro.

Look at:

- `src/app.config.ts`
- `src/pages/`
- `src/runtime/`
- `config/platform/h5.ts`

### `apps/open-xiaoai-gateway`

The voice gateway.

Look at:

- `open_xiaoai_gateway/settings.py`
- `apps/start-open-xiaoai-gateway.sh`

### `packages/user-core`

Frontend shared types and the API client fact source.

Look at:

- `src/domain/types.ts`
- `src/api/create-api-client.ts`
- `src/services/`

### `packages/user-platform`

The platform capability adapter layer, such as storage and real-time support.

### `packages/user-ui`

UI components and theme normalization.

### `docs/Documentation`

The official docs site source. If you change user-visible behavior, installation flow, or API semantics, this doc tree must be updated in the same change.

### `docs/开发设计规范`

This supplementary repo directory still exists, but it is not the main reading path for the official docs site.

If you are reading through VitePress and want the maintained rule set, start with these pages inside the current site:

- [Environment Setup](./environment-setup.md)
- [Backend Development](./backend-development.md)
- [Plugin Specification](./plugin-specification.md)
- [Field Specification](./plugin-fields.md)
- [Integration Flow](./plugin-integration.md)

### `docs/开发者文档`

This supplementary topic directory also still exists in the repository, but the maintained official developer handbook is now concentrated under `docs/Documentation/en/developer-docs/`.

If you need a stable, navigable, maintained developer handbook, stay inside the current documentation tree instead of depending on those external directories.

## What plugin directories look like

Built-in plugins live under:

- `apps/api-server/app/plugins/builtin/`

A typical built-in plugin:

```text
apps/api-server/app/plugins/builtin/health_basic/
├── __init__.py
├── integration.py
├── ingestor.py
└── manifest.json
```

Another example with channel configuration:

```text
apps/api-server/app/plugins/builtin/channel_feishu/
├── __init__.py
├── channel.py
└── manifest.json
```

A theme plugin example:

```text
apps/api-server/app/plugins/builtin/theme_chun_he_jing_ming_pack/
├── manifest.json
└── themes/
```

## Do not mix two different standards

This is the part that was easy to misunderstand before.

### 1. In-repo development directory standard

This rule only answers where plugin source should live inside the FamilyClaw repository:

```text
apps/api-server/plugins-dev/<plugin>/
```

That is the development location rule.

### 2. External plugin repository / marketplace submission standard

This rule answers how an independently maintained plugin repository can organize its own files.

The layout used by `official_weather` is valid and has already passed marketplace update and installation verification:

```text
your_plugin_repo/
  README.md
  requirements.txt
  <plugin_package>/
    __init__.py
    manifest.json
    integration.py / driver.py / channel.py
    resources/
```

In short:

- `plugins-dev/<plugin>/` defines where development source lives in the host repo
- the `official_weather` style defines how an external plugin repo may organize itself internally

If you mount an independently maintained plugin repository under `plugins-dev/`, it is acceptable to keep that repository's own internal structure.

## Minimal in-repo development template

```text
your_plugin/
├── manifest.json
├── __init__.py
├── README.md
├── requirements.txt          # only if you really need extra dependencies
├── integration.py            # only for integration plugins
├── action.py                 # only for action plugins
├── channel.py                # only for channel plugins
├── locales/                  # only if the plugin adds text resources
└── tests/                    # strongly recommended
```

This template is good for quick in-repo development and small local experiments.

## Recommended external plugin repository / marketplace template

```text
your_plugin_repo/
  README.md
  requirements.txt
  your_plugin/
    __init__.py
    manifest.json
    integration.py / driver.py / channel.py
    resources/
```

This template is good for:

- independently maintained plugin repositories
- plugins that will later be submitted to the marketplace
- repositories that need root-level README and dependency files

`official_weather` is the real working example of this layout.

## Bad smells in directory design

If you see any of these, the structure is usually already going bad:

- multiple `manifest.json` files inside one plugin directory
- the plugin directory name and `manifest.id` do not match at all
- host business logic being written inside plugin directories
- plugin-private models being pushed back into the host global model entry

When the structure is unclear, all later documentation, debugging, and maintenance become unclear too.
