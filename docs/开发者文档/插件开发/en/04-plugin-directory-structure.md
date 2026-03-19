# 04 Plugin Directory Structure Specification

## Document Metadata

- Purpose: define how a plugin directory should be organized, where each entrypoint file should live, and what the minimum maintainable layout looks like.
- Current version: v1.2
- Related documents: `docs/开发者文档/插件开发/en/01-plugin-development-overview.md`, `docs/开发者文档/插件开发/en/02-plugin-dev-environment-and-local-debug.md`, `docs/开发者文档/插件开发/en/03-manifest-spec.md`
- Change log:
  - `2026-03-13`: created the first plugin directory structure specification.
  - `2026-03-13`: renamed by reading order and added document metadata.
  - `2026-03-14`: added a `locale-pack` directory example.

This document answers one question only: how should a plugin directory be laid out?

Do not make version one complicated. Keep the structure close to what the current repository already runs.

Do not mix up directory layout with execution semantics:

- directory layout decides where plugin code lives, where dependencies are isolated, and how a runner can resolve entrypoints
- it does not change the public execution model
- public execution now still means “create a background job first, then let workers and runners handle it”

## 1. Minimum Directory Template

```text
your_plugin/
  manifest.json
  requirements.txt
  README.md
  __init__.py
  integration.py
  action.py
  channel.py
  agent_skill.py
  ai_provider.py
  memory_engine.py
  memory_provider.py
  context_engine.py
  locales/
  tests/
    test_manifest.md
```

This does not mean every file must exist. It means:

- `manifest.json`: required
- `requirements.txt`: strongly recommended for third-party plugin dependencies
- `README.md`: strongly recommended for reviewers and future maintainers
- `__init__.py`: strongly recommended, so the Python package path stays clear
- `integration.py` / `action.py` / `channel.py` / `agent_skill.py` / `ai_provider.py` / `memory_*.py`: include only what matches declared V1 plugin types or exclusive slots
- `locales/`: translation resources for `locale-pack` plugins or plugin-owned dictionaries
- `tests/`: strongly recommended, even if it starts with a simple self-check note

## 2. One Plugin Per Directory

This is a hard rule:

- one plugin directory contains only one `manifest.json`
- one `manifest.json` describes only one plugin
- do not pack multiple plugin capability groups into one directory and split them with scripts

The reason is simple:

- the plugin registry scans plugins through `manifest.json`
- one directory for one plugin makes debugging, review, and registration much simpler

## 3. How To Name The Directory

Version one should keep the directory name close to the `manifest.json` `id`, ideally easy to match at a glance.

Valid examples:

- directory: `health_basic`
- `id`: `health-basic-reader`

- directory: `homeassistant_device_action`
- `id`: `homeassistant-device-action`

They do not need to be exactly identical because Python modules usually use underscores, but humans should be able to match them immediately.

## 4. Recommended File Responsibilities

### `manifest.json`

- stores plugin declarations
- does not store runtime code
- does not include a bunch of fields that only future versions may use

### `requirements.txt`

- stores plugin-owned Python dependencies
- should not assume automatic platform installation
- should use explicit version ranges
- should be consumed by the plugin-owned environment, not by the main API environment as a fallback

### `integration.py`

- stores the formal `integration` entrypoint
- exports refresh, discovery, or sync functions declared in the manifest
- emits standard devices, standard entities, standard card snapshots, and standard action outputs only

### `action.py`

- stores the formal `action` entrypoint
- executes the action itself, not permission bypassing

### `agent_skill.py`

- stores the formal `agent-skill` entrypoint
- exposes controlled capabilities only, not Agent flow overrides

### `ai_provider.py`

- stores the `ai-provider` driver entrypoint
- implements driver methods such as `invoke`, `ainvoke`, or `stream`

### `memory_engine.py` / `memory_provider.py` / `context_engine.py`

- store exclusive-slot plugin entrypoints
- must follow the host slot contract instead of the old `memory-ingestor` semantics

### `locales/`

- stores translation resource files for `locale-pack` plugins or plugin-owned dictionaries
- recommend one file per locale, such as `locales/zh-TW.json`
- keep data as plain key-value translations, not executable code
- every `manifest.locales[].resource` must point to a real file here

This is an explicit rule now:

- `locale-pack` is the plugin type for full locale bundles
- normal plugins may also declare `locales`
- normal plugin locales are only for that plugin's own labels, config copy, card titles, and action text
- the host merges same-`locale_id` messages by key instead of replacing the whole locale bundle

### `README.md`

It should at least explain:

1. what the plugin does
2. what permissions it uses
3. what external configuration it needs
4. how to do minimum verification
5. what it explicitly does not do

### `tests/`

Version one does not force a large automation suite, but it should at least explain:

- whether `manifest` was self-checked
- whether the entrypoints can be imported
- whether core sample payloads were exercised

## 5. How To Lay Out Multi-Capability Plugins

If a plugin includes both `integration` and `action`, do not split it into two plugin directories.

The minimum workable layout is:

```text
health_basic/
  manifest.json
  __init__.py
  integration.py
  action.py
```

One plugin directory still maps to one plugin id, but that plugin may expose multiple formal entrypoints.

Why this works well:

- one plugin id maps to one capability set
- one development pass, one review pass, one registration pass
- the data pipeline from the same source stays together

## 6. How To Lay Out Action Plugins

Action plugins are usually simpler:

```text
homeassistant_device_action/
  manifest.json
  __init__.py
  executor.py
  README.md
```

If an action is high risk, such as a door lock, the directory structure does not need a special case. Risk is expressed through:

- `risk_level` in `manifest.json`
- permission declarations
- later registry risk notes

Do not invent a special directory hierarchy just for high-risk actions. That would only create junk complexity.

## 7. How To Lay Out Locale-Pack Plugins

`locale-pack` is not an executable plugin. It does not need `plugin/connector.py` or other runtime entry files.

The minimum workable layout is:

```text
locale_zh_tw_pack/
  manifest.json
  README.md
  locales/
    zh-TW.json
```

What actually matters is simple:

- `manifest.json` declares `types: ["locale-pack"]`
- the translation resource file really exists
- `manifest.locales[].resource` and the real file path match exactly

If one plugin provides multiple locales, keep it as one plugin directory and add more files under `locales/`.

## 8. Directory Content That Is Not Recommended Yet

Do not add these in version one unless the Spec explicitly expands scope later:

- auto-install scripts
- remote downloaders
- sandbox configuration directories
- full signing certificate directories
- marketplace frontend asset bundles

The point is not that these are forbidden forever. The point is that they do not have a real landing place yet and would mislead third-party developers.

## 9. Official Plugins And Image Packaging Boundary

This rule is now explicit:

- `builtin` plugins live in `apps/api-server/app/plugins/builtin/`
- `official` plugins live in `apps/api-server/data/plugins/official/`
- `third_party` plugins live in the host data directory or marketplace install directory

The packaging rule must match that boundary:

- the final Docker runtime image should contain only the host and `builtin` plugins
- `official` and `third_party` plugins should not be baked into the final image; they should be mounted, installed, or synchronized into the host data directory
- `.dockerignore` should exclude `apps/api-server/data/plugins/official/`
- host core code must not statically import `official` or `third_party` plugin modules during import time, or the host will fail to boot when those plugin files are absent

The short version:

official plugins may be trusted plugins, but they must not become host compile-time dependencies.

## 10. Reference Directories In The Current Repository

Useful real examples:

- `apps/api-server/app/plugins/builtin/health_basic/`
- `apps/api-server/app/plugins/builtin/homeassistant_device_sync/`
- `apps/api-server/app/plugins/builtin/homeassistant_device_action/`
- `apps/api-server/app/plugins/builtin/homeassistant_door_lock_action/`

If your structure looks very different from these, explain why. If you cannot explain it clearly, the design is probably drifting.
