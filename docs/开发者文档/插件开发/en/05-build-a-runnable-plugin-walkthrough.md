# 05 Build A Runnable Plugin Walkthrough

## Document Metadata

- Purpose: give developers one complete path from `manifest` to API invocation so they can assemble a runnable plugin under the current architecture.
- Current version: v1.0
- Related documents: `docs/开发者文档/插件开发/en/01-plugin-development-overview.md`, `docs/开发者文档/插件开发/en/02-plugin-integration-guide.md`, `docs/开发者文档/插件开发/en/03-manifest-spec.md`, `docs/开发者文档/插件开发/en/04-plugin-directory-structure.md`
- Change log:
  - `2026-03-13`: created the first walkthrough, covering the full path from `manifest` and code files to API invocation.

This is not a rules document. This is a practical path.

The goal is simple:

- build one plugin from scratch that the current repository can recognize, run, and use to sync data into memory

## 1. Start With The Simplest Useful Goal

Do not begin with an action plugin. Do not begin with high-risk control.

This walkthrough uses:

- a minimal health data sync plugin
- plugin types: `connector + memory-ingestor`
- result: one sync API call writes steps and heart-rate data into system memory

The plugin id will be:

- `health-demo-sync`

## 2. Step One: Put It In The Right Directory

The current version does not support remote plugin installation, so the code must live in a backend-loadable path first.

Following the current repository style, create:

```text
apps/api-server/app/plugins/builtin/health_demo_sync/
  __init__.py
  manifest.json
  connector.py
  ingestor.py
```

Use underscores for the directory name and hyphens for `manifest.id`. That matches the current built-in plugin style.

## 3. Step Two: Write `manifest.json`

Start with the minimum runnable version:

```json
{
  "id": "health-demo-sync",
  "name": "Health Demo Sync Plugin",
  "version": "0.1.0",
  "types": ["connector", "memory-ingestor"],
  "permissions": [
    "health.read",
    "memory.write.observation"
  ],
  "risk_level": "low",
  "triggers": ["manual", "agent-checkpoint"],
  "entrypoints": {
    "connector": "app.plugins.builtin.health_demo_sync.connector.sync",
    "memory_ingestor": "app.plugins.builtin.health_demo_sync.ingestor.transform"
  },
  "description": "Reads demo health data and writes it as Observation memory.",
  "vendor": {
    "name": "FamilyClaw Demo",
    "contact": "internal-demo"
  }
}
```

The most common mistakes here are:

- using underscores in `id`
- letting `entrypoints` disagree with the real directory path
- declaring `memory-ingestor` without a `memory_ingestor` entrypoint

## 4. Step Three: Write `connector.py`

This plugin will return two raw records first: steps and heart rate.

```python
from __future__ import annotations


def sync(payload: dict | None = None) -> dict:
    normalized_payload = payload or {}
    member_id = normalized_payload.get("member_id", "demo-member")
    captured_at = normalized_payload.get("captured_at", "2026-03-13T07:30:00Z")

    return {
        "source": "health-demo-sync",
        "mode": "connector",
        "received_payload": normalized_payload,
        "records": [
            {
                "record_type": "steps",
                "external_member_id": member_id,
                "member_id": member_id,
                "value": 9032,
                "unit": "count",
                "captured_at": captured_at
            },
            {
                "record_type": "heart_rate",
                "external_member_id": member_id,
                "member_id": member_id,
                "value": 68,
                "unit": "bpm",
                "captured_at": captured_at
            }
        ]
    }
```

This satisfies the current runtime requirements:

- it returns `records`
- each record has `record_type`
- each record has `value`
- each record has `captured_at`

## 5. Step Four: Write `ingestor.py`

Now convert the raw records into Observation items.

```python
from __future__ import annotations


def transform(payload: dict | None = None) -> list[dict]:
    normalized_payload = payload or {}
    records = normalized_payload.get("records", [])
    observations: list[dict] = []

    for record in records:
        if not isinstance(record, dict):
            continue

        raw_id = record.get("id")
        payload_data = record.get("payload", {})
        if not isinstance(payload_data, dict):
            payload_data = {}

        record_type = record.get("record_type")
        subject_id = payload_data.get("member_id") or payload_data.get("external_member_id")
        observed_at = record.get("captured_at")

        if record_type == "steps":
            observations.append(
                {
                    "type": "Observation",
                    "subject_type": "Person",
                    "subject_id": subject_id,
                    "category": "daily_steps",
                    "value": payload_data.get("value"),
                    "unit": payload_data.get("unit", "count"),
                    "observed_at": observed_at,
                    "source_plugin_id": "health-demo-sync",
                    "source_record_ref": raw_id,
                }
            )
        elif record_type == "heart_rate":
            observations.append(
                {
                    "type": "Observation",
                    "subject_type": "Person",
                    "subject_id": subject_id,
                    "category": "heart_rate",
                    "value": payload_data.get("value"),
                    "unit": payload_data.get("unit", "bpm"),
                    "observed_at": observed_at,
                    "source_plugin_id": "health-demo-sync",
                    "source_record_ref": raw_id,
                }
            )

    return observations
```

The fields you absolutely cannot miss are:

- `category`
- `value`
- `source_record_ref`

Miss any of them and the backend pipeline will fail or produce unusable memory writes.

## 6. Step Five: Run Static Checks First

Do not jump into API calls immediately. First pass these 4 checks:

1. `manifest.json` entrypoint paths match the real files
2. `connector.py` contains `sync()`
3. `ingestor.py` contains `transform()`
4. `manifest.id`, directory name, and module path are easy to match at a glance

If these four checks fail, API testing is just wasted time.

## 7. Step Six: Run One Full Sync Call

The best current API entry for validating this kind of plugin is:

- `POST /api/v1/ai-config/{household_id}/agents/{agent_id}/plugin-memory-checkpoint`

Request example:

```json
{
  "plugin_id": "health-demo-sync",
  "payload": {
    "member_id": "member-001",
    "captured_at": "2026-03-13T07:30:00Z"
  },
  "trigger": "agent-checkpoint"
}
```

This one call will automatically do all of this:

1. invoke the `connector`
2. save raw records
3. invoke the `memory-ingestor`
4. write Observation memory
5. return fresh Agent memory insight

## 8. Step Seven: What You Should See

On success, you should at least see:

- `pipeline_success = true`
- `raw_record_count = 2`
- `memory_card_count = 2`
- `used_plugins` contains `health-demo-sync`

Response example:

```json
{
  "agent_id": "agent-001",
  "agent_name": "Family Butler",
  "household_id": "household-001",
  "plugin_id": "health-demo-sync",
  "trigger": "agent-checkpoint",
  "pipeline_run_id": "run-001",
  "pipeline_success": true,
  "raw_record_count": 2,
  "memory_card_count": 2,
  "degraded": false,
  "insight": {
    "agent_id": "agent-001",
    "agent_name": "Family Butler",
    "household_id": "household-001",
    "summary": "Family Butler has read plugin-written family memory: member-001 daily_steps observation / 9032 / count; member-001 heart_rate observation / 68 / bpm.",
    "suggestions": [
      "Keep tracking step changes for today",
      "Use heart-rate trends for health reminders"
    ],
    "used_plugins": [
      "health-demo-sync"
    ],
    "facts": [
      {
        "memory_id": "memory-001",
        "source_plugin_id": "health-demo-sync",
        "category": "daily_steps",
        "summary": "member-001 daily_steps observation / 9032 / count",
        "observed_at": "2026-03-13T07:30:00Z"
      },
      {
        "memory_id": "memory-002",
        "source_plugin_id": "health-demo-sync",
        "category": "heart_rate",
        "summary": "member-001 heart_rate observation / 68 / bpm",
        "observed_at": "2026-03-13T07:30:00Z"
      }
    ]
  }
}
```

## 9. If It Fails, Check Here First

The most common failure points are these:

### Wrong `manifest` path

Symptom: plugin entrypoint loading fails.

Check first:

- the `entrypoints` module path
- the directory and module names
- the function names

### Wrong `memory-ingestor` return shape

Symptom: sync runs, but memory is not written.

Check first:

- does it return a `list`
- is every item a `dict`
- does every item contain `source_record_ref`
- does every item contain `category` and `value`

### `plugin_id` mismatch

Symptom: the API says the plugin does not exist.

Check first:

- `plugin_id` in the request
- `id` inside `manifest.json`

## 10. What This Walkthrough Proves

If you can get through this walkthrough, then you already understand the core integration path in the current version:

- declare the plugin through `manifest`
- return raw records from a `connector`
- convert them into Observation records through `memory-ingestor`
- sync data into the project through the unified API path

That is the real plugin path that works today.
