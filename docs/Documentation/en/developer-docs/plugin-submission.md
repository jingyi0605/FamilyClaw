---
title: Plugin Submission
docId: en-4.9
version: v0.1
status: active
order: 490
outline: deep
---

# Plugin Submission

This page is about how to hand a plugin over once it is written, not how to push a PR full of “we will fix this later”.

## What to read before submitting

Before you submit a plugin, read at least:

- [Plugin Specification](./plugin-specification.md)
- [Field Specification](./plugin-fields.md)
- [Integration Flow](./plugin-integration.md)
- [Example Plugin](./plugin-example.md)

These pages already connect type choice, manifest fields, integration flow, examples, and review expectations into one path. You do not need to jump outside the current docs site.

## Minimum bar before submission

At minimum, make sure:

1. `manifest.json` passes the current validation rules
2. entry paths match the real code
3. the README explains purpose, config, permissions, risk, and validation method
4. plugin type, permissions, and risk level are not guesswork
5. if configuration is involved, `config_specs` matches what runtime code really reads
6. if private schema or database work is involved, the migration path is clear and repeatable
7. if the plugin changes official docs or user-visible behavior, the corresponding docs are updated too

## What the submission should include

- plugin source code
- `manifest.json`
- README
- minimum tests or validation notes
- version information
- if the plugin depends on an external platform, clear prerequisites and required account type

## What reviewers look at first

### 1. Was the type chosen correctly?

If something that should be an `integration` is forced into `action`, everything after that goes wrong.

### 2. Are permissions and risk levels honest?

If a high-risk plugin claims `low`, that is not convenience. That is planting a mine.

### 3. Can the README keep the next developer alive?

If the README only says “this is a powerful plugin”, it effectively says nothing.

At minimum, it should explain:

- what the plugin does
- what configuration it needs
- how to install it
- how to verify it
- what the known limits are

### 4. Does it break the host boundary?

If the implementation starts depending directly on host-private details or writing directly into host core tables, review should stop.

## Difference between built-in and third-party plugins

### Built-in plugins

- code usually lives under `apps/api-server/app/plugins/builtin/`
- maintained together with the main repository version
- docs, config, and frontend entry points often need synchronized updates

### Third-party plugins

- README, self-description, and isolation matter even more
- they cannot assume readers know private context
- they cannot require the host to carry a stack of special cases

## Self-checklist before submission

- [ ] `manifest.id` is stable and unique
- [ ] `entrypoints` match real function paths
- [ ] config fields match runtime read logic
- [ ] after disabling the plugin, the execution path is correctly blocked
- [ ] when scheduled tasks reference the plugin, `triggers` is declared correctly
- [ ] the README explains config, dependencies, and validation steps
- [ ] impacted docs have been updated

## One plain truth

The worst plugin submissions are not the ones with little code. They are the ones with incomplete information.

If other people cannot tell what your plugin needs, what it does, or how to verify it, then it does not belong in the formal system.
