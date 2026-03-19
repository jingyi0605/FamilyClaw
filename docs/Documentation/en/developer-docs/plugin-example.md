---
title: Example Plugin
docId: en-4.8
version: v0.1
status: draft
order: 480
outline: deep
---

# Example Plugin

## What this page solves

- It gives first-time plugin authors a minimal development path they can copy.

## Recommended example path

1. Pick a very small plugin target first.
2. Write `manifest.json` before business logic.
3. Implement the formal entry point file.
4. Run static checks before API validation.

## Example skeleton

```text
health-demo-sync/
  manifest.json
  requirements.txt
  README.md
  plugin/
    __init__.py
    connector.py
    ingestor.py
```

## Completion standard

- A new author knows how to build a first runnable plugin without over-design.
