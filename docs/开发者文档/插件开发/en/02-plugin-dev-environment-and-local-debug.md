# 02 Plugin Development Environment and Local Debugging

## Document Metadata

- Purpose: tell third-party developers how to prepare the plugin development environment, where plugin code should live, and how to do minimum local debugging without digging through the codebase first.
- Current version: v1.0
- Related documents: `docs/开发者文档/插件开发/en/01-plugin-development-overview.md`, `docs/开发者文档/插件开发/en/05-plugin-integration-guide.md`, `docs/开发者文档/插件开发/en/06-build-a-runnable-plugin-walkthrough.md`, `docs/开发者文档/插件开发/en/07-plugin-testing-and-in-project-validation.md`, `apps/api-server/pyproject.toml`
- Change log:
  - `2026-03-13`: created the first environment and local debugging guide.

This document answers 4 questions:

1. how to prepare the local environment before building a plugin
2. where plugin code should live right now
3. how to do minimum local debugging without starting a full stack immediately
4. where plugin-specific dependencies should be installed

## 1. Say The Real Boundary First

Two modes must be separated here:

- already implemented: built-in plugins run in the main process
- recommended target for third-party plugins: run inside same-container subprocess runners

For the target third-party mode, plugin code must satisfy two things:

- Python must be able to import the module path
- the entrypoints in `manifest.json` must point to real functions

So the safest third-party workflow is:

- build the plugin in its own repository layout
- give the plugin its own `requirements.txt`
- validate entrypoints inside the plugin-owned venv first
- integrate later through the runner protocol

Built-in plugins are still a maintainer concern; third-party developers should stop treating the main source tree as the default plugin location.

## 2. Minimum Local Requirements

Prepare these first:

1. Python `3.11+`
2. ability to create a virtual environment with `venv`
3. working `pip`
4. basic Git usage

The current backend dependencies are visible in `apps/api-server/pyproject.toml`, including:

- `fastapi`
- `uvicorn`
- `sqlalchemy`
- `alembic`
- `websockets`

## 3. Recommended Environment Setup

Run these steps inside `apps/api-server/`.

### 3.1 Create a virtual environment

```bash
python -m venv .venv
```

Activate on Windows:

```bash
.venv\Scripts\activate
```

Activate on macOS / Linux:

```bash
source .venv/bin/activate
```

### 3.2 Install backend dependencies

```bash
pip install -e .
```

This helps because:

- `app.*` module paths become directly importable
- you can change backend or plugin code without reinstalling the package every time

### 3.3 Create a separate plugin environment

Do not default to installing third-party plugin dependencies into the main backend environment.

Instead:

```bash
python -m venv .plugin-venv
```

Then install plugin dependencies:

```bash
.plugin-venv\Scripts\pip install -r requirements.txt
```

Or on macOS / Linux:

```bash
source .plugin-venv/bin/activate
pip install -r requirements.txt
```

That environment is what the runner should use later.

## 4. Where Plugin Code Should Live Right Now

For third-party developers, the recommended location is the plugin repository itself.

Suggested minimum layout:

```text
your-plugin/
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
```

If you are a project maintainer working on current built-in plugins, the existing location is still:

```text
apps/api-server/app/plugins/builtin/
```

For example:

```text
apps/api-server/app/plugins/builtin/your_plugin/
  __init__.py
  manifest.json
  connector.py
  ingestor.py
```

This is not because it must stay this way forever. It is because the runtime currently works from this loadable path.

If you place plugin code outside the loadable backend path, the module strings in `manifest.json` will simply stop resolving.

## 5. Minimum Files You Should Prepare First

A minimum debuggable plugin usually starts with:

1. `manifest.json`
2. `__init__.py`
3. one entry file for the declared capability, such as `connector.py`
4. if you need the full data pipeline, also add `ingestor.py`

Do not start with complicated logic.

First make these 3 things work:

- `manifest.json` passes validation
- the entrypoint module is importable
- the entry function returns the expected shape

## 6. What Order Should You Debug In

Do not start by running the whole system and reading logs blindly.

Use this order instead:

### Layer 1: static checks

Check these first:

1. required fields exist in `manifest.json`
2. `entrypoints` match the real file layout
3. function names are correct
4. declared `types` and entrypoints match one by one

### Layer 2: import and call the function directly

Use a Python shell or a small test to call the entrypoint directly.

Example:

```python
from app.plugins.builtin.health_basic.connector import sync

result = sync({"member_id": "demo-member"})
print(result)
```

The goal here is not full integration. The goal is to confirm:

- the module path is correct
- the function is callable
- the returned structure is roughly correct

### Layer 3: run the real project service functions

If this is a `connector + memory-ingestor` plugin, then move on to:

- `execute_plugin()`
- `run_plugin_sync_pipeline()`
- Agent bridge entries

There are already repository tests covering these flows.

## 7. Existing Debug References You Can Reuse

Do not guess. Use these real tests and files as references:

- `apps/api-server/tests/test_plugin_manifest.py`
- `apps/api-server/tests/test_plugin_runs.py`
- `apps/api-server/tests/test_agent_plugin_bridge.py`
- `apps/api-server/tests/test_action_plugin_permissions.py`

These already cover:

- manifest validation
- plugin enable/disable
- unified execution entry
- raw-record and memory-write pipeline
- Agent invocation bridge
- action permissions and high-risk confirmation

## 8. If You Really Need HTTP Integration Later

There are current HTTP entries that can validate plugin flows, such as:

- `POST /api/v1/ai-config/{household_id}/agents/{agent_id}/plugin-invocations`
- `POST /api/v1/ai-config/{household_id}/agents/{agent_id}/plugin-memory-checkpoint`
- `POST /api/v1/ai-config/{household_id}/agents/{agent_id}/action-plugin-invocations`

But this document does not require you to start the dev server right now.

The safer order is:

1. static checks first
2. service-layer validation next
3. HTTP integration only if needed later

That is much easier to debug.

## 9. Most Common Local Debugging Mistakes

### Wrong module path

Symptom: entrypoint loading fails.

Common causes:

- directory and module names do not match
- `manifest.json` still points to an old module path
- function names changed but the entrypoint string did not

### Plugin code in the wrong place

Symptom: `import_module()` cannot find the module.

Common causes:

- the plugin is outside the current loadable path
- missing `__init__.py`

### Starting full integration too early

Symptom: you get many errors and cannot tell whether the root cause is manifest, entrypoint, return shape, or database setup.

Fix:

- debug in layers: static check -> entry function -> service pipeline -> HTTP integration

## 10. One-Line Summary

The correct current development workflow is not “publish first.” It is:

- build the plugin under `apps/api-server/app/plugins/builtin/`
- validate it through existing service functions and tests
- then prepare the registration material later

That is the real workflow supported by the repository today.
