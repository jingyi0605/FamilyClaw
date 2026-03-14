# 04 Plugin Directory Structure Specification

## Document Metadata

- Purpose: define how a plugin directory should be organized, where each entrypoint file should live, and what the minimum maintainable layout looks like.
- Current version: v1.1
- Related documents: `docs/开发者文档/插件开发/en/01-plugin-development-overview.md`, `docs/开发者文档/插件开发/en/02-plugin-dev-environment-and-local-debug.md`, `docs/开发者文档/插件开发/en/03-manifest-spec.md`
- Change log:
  - `2026-03-13`: created the first plugin directory structure specification.
  - `2026-03-13`: renamed by reading order and added document metadata.

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
  plugin/
    __init__.py
    connector.py
    ingestor.py
    executor.py
    skill.py
  tests/
    test_manifest.md
```

This does not mean every file must exist. It means:

- `manifest.json`: required
- `requirements.txt`: strongly recommended for third-party plugin dependencies
- `README.md`: strongly recommended for reviewers and future maintainers
- `plugin/`: recommended as the real code directory instead of filling the repository root with code files
- `plugin/__init__.py`: strongly recommended, so the Python package path stays clear
- `plugin/connector.py` / `plugin/ingestor.py` / `plugin/executor.py` / `plugin/skill.py`: include only what matches declared plugin types
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

### `plugin/connector.py`

- stores the read-data entrypoint
- recommended function name: `sync`
- common return shape: a dict containing `records`

### `plugin/ingestor.py`

- stores the raw-record to normalized-memory entrypoint
- recommended function name: `transform`
- common return shape: a list of memory candidates

### `plugin/executor.py`

- stores the action execution entrypoint
- recommended function name: `run`
- handles the action itself, not permission bypassing

### `plugin/skill.py`

- stores the Agent skill entrypoint
- recommended function name: `run`
- exposes controlled capabilities only, not Agent flow overrides

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

If a plugin includes both `connector` and `memory-ingestor`, do not split it into two plugin directories.

The minimum workable layout is:

```text
health_basic/
  manifest.json
  __init__.py
  connector.py
  ingestor.py
```

This is also how `apps/api-server/app/plugins/builtin/health_basic/` is organized.

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

## 7. Directory Content That Is Not Recommended Yet

Do not add these in version one unless the Spec explicitly expands scope later:

- auto-install scripts
- remote downloaders
- sandbox configuration directories
- full signing certificate directories
- marketplace frontend asset bundles

The point is not that these are forbidden forever. The point is that they do not have a real landing place yet and would mislead third-party developers.

## 8. Reference Directories In The Current Repository

Useful real examples:

- `apps/api-server/app/plugins/builtin/health_basic/`
- `apps/api-server/app/plugins/builtin/homeassistant_device_sync/`
- `apps/api-server/app/plugins/builtin/homeassistant_device_action/`
- `apps/api-server/app/plugins/builtin/homeassistant_door_lock_action/`

If your structure looks very different from these, explain why. If you cannot explain it clearly, the design is probably drifting.
