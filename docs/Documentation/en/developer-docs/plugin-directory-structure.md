---
title: Directory Structure
docId: en-4.5
version: v0.1
status: draft
order: 450
outline: deep
---

# Directory Structure

## Minimal template

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
```

## Hard rules

- One plugin directory, one `manifest.json`
- One `manifest.json`, one plugin identity
- Directory naming and `manifest.id` should be easy to map at a glance

## Completion standard

- Plugin authors know where files belong instead of inventing their own layout.
