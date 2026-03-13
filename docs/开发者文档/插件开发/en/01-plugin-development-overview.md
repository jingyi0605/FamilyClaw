# 01 Plugin Development Overview

## Document Metadata

- Purpose: give first-time FamilyClaw plugin developers a clean starting point so they can understand the boundary, supported plugin types, and minimum development flow.
- Current version: v1.1
- Related documents: `docs/开发者文档/插件开发/en/02-plugin-integration-guide.md`, `docs/开发者文档/插件开发/en/03-manifest-spec.md`, `docs/开发者文档/插件开发/en/04-plugin-directory-structure.md`, `specs/004.3-插件开发规范与注册表/design.md`
- Change log:
  - `2026-03-13`: created the first development guide.
  - `2026-03-13`: renamed by reading order and added document metadata.

This guide answers the first questions a third-party plugin developer will ask:

1. What plugin types are supported right now?
2. What is the minimum shape of a plugin?
3. How do I know I did not go off the rails?

If this is your first time working on this project, read this first, then move on to the detailed `manifest`, integration, and registry docs.

## 1. Scope First

`004.2` already built the runtime foundation, but version one is not an open platform.

What is supported now is simple: develop plugins following repository rules, then expose plugin metadata through the registry.

These items are explicitly out of scope now:

- Automatic download and installation of third-party code
- Remote execution of plugin code from external repositories
- A full signing system
- Runtime sandboxing
- Plugin marketplace frontend pages

If your plan depends on any of those, stop. That is not what this Spec is solving right now.

## 2. Supported Plugin Types

The backend currently recognizes only 4 plugin types. Do not invent a fifth one.

### `connector`

- Purpose: read raw data from external systems
- Typical cases: health data, device state
- Common output: a `records` list for raw record storage

### `memory-ingestor`

- Purpose: convert raw records into normalized memory items
- Typical cases: convert steps, heart rate, temperature, and humidity into Observation records
- Common output: a list of normalized memory candidates

### `action`

- Purpose: execute external actions
- Typical case: device control
- Extra limits: permission checks are required; high-risk actions also require manual confirmation

### `agent-skill`

- Purpose: expose extra tools or rules to the Agent
- Typical case: let the Agent call a controlled tool through a unified path
- Extra limits: a plugin can provide capabilities, but cannot rewrite the Agent main flow

## 3. Minimum Development Flow

Do it in this order. Do not start with fancy extras.

1. Confirm which of the 4 supported types your plugin belongs to.
2. Create a dedicated plugin directory and start with `manifest.json`.
3. Declare entrypoints, permissions, risk level, and triggers in the `manifest`.
4. Add the code files so each entrypoint resolves to a real Python module path.
5. Compare with existing built-in plugins to make sure your fields and layout are aligned.
6. Add minimal tests and self-check notes, then prepare later registry submission material.

In one sentence: version one is about clear declaration, runnable entrypoints, and staying inside the boundary.

## 4. Minimum Plugin Shape

Based on the current repository, a minimal plugin directory should contain at least:

```text
your_plugin/
  manifest.json
  __init__.py
  connector.py or ingestor.py or executor.py or skill.py
```

Not every file is mandatory, but every declared type must map to a real code file through an entrypoint.

Examples:

- `connector`: usually `connector.py`
- `memory-ingestor`: usually `ingestor.py`
- `action`: usually `executor.py`
- `agent-skill`: usually `skill.py` or another clearly named module

The file name itself is not hardcoded, but the entrypoint must be importable. That is a hard rule.

## 5. Existing Examples to Follow

The repository already has built-in examples you can use as references:

- `apps/api-server/app/plugins/builtin/health_basic/`: read health data and write normalized memory
- `apps/api-server/app/plugins/builtin/homeassistant_device_sync/`: read device and environment data
- `apps/api-server/app/plugins/builtin/homeassistant_device_action/`: normal device action plugin
- `apps/api-server/app/plugins/builtin/homeassistant_door_lock_action/`: high-risk action plugin

If you still feel unsure after reading the docs, align your layout and `manifest.json` with these examples instead of inventing a new style.

## 5.1 Read The Integration Doc Before Writing Real Code

If your real question is “how does a plugin actually connect to the project,” read this next:

- `docs/开发者文档/插件开发/en/02-plugin-integration-guide.md`

That document explains:

- how the system invokes plugins
- what input a plugin receives
- what output it should return
- how data moves into raw records, normalized memory, and Agent usage

## 6. Runtime Boundaries That Already Exist

These are not suggestions. They come directly from the current codebase:

- The unified Agent entry currently allows only `connector` and `agent-skill`
- `action` plugins must pass permission checks first
- `risk_level=high` action plugins go through manual confirmation instead of direct execution
- `manifest.json` `id` values may contain only lowercase letters, digits, and hyphens
- `entrypoints` must use the `module_path.function_name` format

If the docs ever disagree with the code, keep the simpler option that does not break the current implementation. Do not document features the repository does not actually support.

## 7. What Not To Do In Version One

These choices are not acceptable right now:

- Telling developers to depend on remote installation
- Allowing plugins to auto-run high-risk actions by default
- Requiring a signing platform that does not exist yet
- Introducing a new plugin type that breaks the current 4-type model
- Letting plugins bypass the Agent flow or permission control

In plain words: do not turn version one into an unbounded remote execution platform.

## 8. Self-Check List

Before you go deeper, check these 8 items:

1. Did I use only the 4 supported plugin types?
2. Did I miss any entrypoint, permission, or risk level in `manifest.json`?
3. Can each entrypoint be imported for real?
4. Are my triggers limited to currently controlled cases?
5. If this is an action plugin, are permissions and risk clearly declared?
6. If the plugin is for the Agent, does it still go through the unified entry?
7. Am I secretly depending on remote execution, auto install, or sandbox features that do not exist yet?
8. Can someone start from my plugin by reading only docs and examples, without reading source code first?

If these 8 checks fail, do not rush into a PR.
