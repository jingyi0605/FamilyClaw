# 05 Plugin Integration Guide

## Document Metadata

- Purpose: explain how a plugin actually integrates with FamilyClaw, including invocation, input/output, sync flow, and current API entries.
- Current version: v1.2
- Related documents: `docs/开发者文档/插件开发/en/01-plugin-development-overview.md`, `docs/开发者文档/插件开发/en/02-plugin-dev-environment-and-local-debug.md`, `docs/开发者文档/插件开发/en/03-manifest-spec.md`, `docs/开发者文档/插件开发/en/04-plugin-directory-structure.md`, `apps/api-server/app/modules/plugin/service.py`, `apps/api-server/app/modules/plugin/agent_bridge.py`
- Change log:
  - `2026-03-13`: added the integration guide to cover invocation flow, APIs, inputs/outputs, and sync paths.
  - `2026-03-13`: renamed by reading order and added document metadata.
  - `2026-03-13`: added plugin function signature rules, a full `connector` return example, an Observation field table, and a complete sync request/response example.
  - `2026-03-13`: added the `connector records` raw-record field table.

This document answers the core question: how does a plugin actually integrate with FamilyClaw?

Directory layout and `manifest` fields are only the shell. What developers really need is this:

1. how the system calls a plugin
2. what input a plugin receives
3. what output a plugin should return
4. how plugin data enters the system, becomes memory, and is then used by the Agent

One important truth comes first:

- the external main path is no longer “an API call synchronously executes the plugin”
- the accurate model now is “an API or Agent entry creates a background job first, then a worker executes the plugin”
- `execute_plugin()` and `run_plugin_sync_pipeline()` still exist, but they are now internal execution-layer and testing tools more than public integration semantics

## 1. Say The Plain Truth First

Two states must be separated here:

- already implemented: built-in same-process plugins
- target third-party mode: same-container subprocess runners

So from the third-party point of view, this guide now describes the runner direction.

The main service and a third-party plugin should split responsibilities like this:

- the main service handles registry loading, manifest validation, permissions, audit, memory writes, and Agent bridges
- the runner process handles Python environment setup, entrypoint loading, and plugin execution
- the plugin itself handles payload processing and JSON-serializable output only

In plain words: third-party plugins should move out of the main process and into runners.

## 2. The 3 Main Integration Paths Supported Today

### 2.1 Data Sync Pipeline

This is the most complete path, and the closest thing to the main plugin integration route.

Flow:

1. the caller creates a `plugin_job`
2. a worker claims the job and invokes the `connector`
3. the plugin returns raw `records`
4. the system stores those `records` in `plugin_raw_records`
5. a `memory-ingestor` plugin converts raw records into normalized Observation objects
6. the system writes those Observations into family memory
7. the system updates task status, attempts, and notifications
8. the Agent reads them later from memory

Relevant code:

- orchestration: `apps/api-server/app/modules/plugin/service.py:303`
- raw record persistence: `apps/api-server/app/modules/plugin/service.py:190`
- raw-to-memory conversion: `apps/api-server/app/modules/plugin/service.py:247`
- Observation write: `apps/api-server/app/modules/memory/service.py:756`

### 2.2 Direct Agent Invocation

This path lets the Agent invoke plugin capabilities directly.

Only two plugin types are currently allowed:

- `connector`
- `agent-skill`

Relevant code:

- `apps/api-server/app/modules/plugin/agent_bridge.py:29`
- constraint: `apps/api-server/app/modules/plugin/agent_bridge.py:103`

The point is simple: the Agent cannot call every plugin type directly. Only controlled read capabilities and skill capabilities are allowed now, and the current return semantics are task-oriented rather than synchronous final-result oriented.

### 2.3 Action Execution Path

Action plugins also go through a unified path, but with stricter limits.

Flow:

1. request an action plugin
2. the system verifies that the plugin declares `action`
3. the system verifies that the plugin declares the required permission
4. the system verifies that the current member is allowed to execute the action
5. if the plugin risk level is `high`, manual confirmation is required first
6. after that, a background job is created
7. the worker executes the plugin later

Relevant code:

- action entry: `apps/api-server/app/modules/plugin/agent_bridge.py:130`
- permission check: `apps/api-server/app/modules/plugin/agent_bridge.py:223`
- high-risk confirmation: `apps/api-server/app/modules/plugin/agent_bridge.py:282`

## 3. How The System Calls A Plugin

The system does not hardcode file names. It uses `entrypoints` from `manifest.json`.

Example:

```json
{
  "entrypoints": {
    "connector": "app.plugins.builtin.health_basic.connector.sync",
    "memory_ingestor": "app.plugins.builtin.health_basic.ingestor.transform"
  }
}
```

In the current built-in mode, the system does two things:

1. split the string into module path and function name
2. load the module with `import_module()` and invoke the target function

Relevant code:

- entrypoint loading: `apps/api-server/app/modules/plugin/service.py:431`
- plugin-type to entrypoint-key mapping: `apps/api-server/app/modules/plugin/service.py:416`

In the runner mode, the runner must do the same two things, except the import happens inside the child process.

So the real responsibility of the plugin author is:

- keep `entrypoints` correct
- make sure the Python module actually exists
- make sure the target function is callable

Do not confuse that with public runtime semantics:

- a callable entrypoint does not mean the system will synchronously finish the plugin before returning to the caller
- the public path now persists a `plugin_job` first

## 4. What Input A Plugin Receives

The unified runtime entry passes a `dict payload` into the plugin function.

At the lower service layer, the execution request contains:

- `plugin_id`
- `plugin_type`
- `payload`
- `trigger`

Relevant structure: `apps/api-server/app/modules/plugin/schemas.py:154`

But the plugin function itself typically receives this shape:

```python
def sync(payload: dict | None = None) -> dict:
    ...
```

That means the plugin does not directly receive a database session, request object, or heavy runtime context.

What you can depend on today is:

- the caller-provided `payload`
- your own plugin logic and configuration

Simple, but clear.

What the caller should depend on is now split into two layers:

- task fields like `job_id`, `job_status`, and `queued`
- the later execution result obtained through job queries, notifications, or responses

## 4.1 Plugin Function Signature Rules

The current plugin entry model is simple. Just implement a normal Python callable.

Recommended signatures:

```python
def sync(payload: dict | None = None) -> dict:
    ...


def transform(payload: dict | None = None) -> list[dict]:
    ...


def run(payload: dict | None = None) -> dict:
    ...
```

By plugin type:

| Plugin type | Recommended function | Recommended signature | Return type |
| --- | --- | --- | --- |
| `connector` | `sync` | `def sync(payload: dict | None = None) -> dict` | `dict` |
| `memory-ingestor` | `transform` | `def transform(payload: dict | None = None) -> list[dict]` | `list[dict]` |
| `action` | `run` | `def run(payload: dict | None = None) -> dict` | `dict` |
| `agent-skill` | `run` | `def run(payload: dict | None = None) -> dict` | `dict` |

There are 4 hard rules here:

1. the entrypoint must resolve to a callable function
2. it must accept at least one `payload` parameter positionally or compatibly
3. the return value must be JSON-serializable basic data, not database objects, sessions, or custom class instances
4. `memory-ingestor` must return a list, not a dict and not a generator

Do not do this kind of junk:

- signatures that only work with hidden extra runtime context
- logic that depends on `*args` / `**kwargs` ambiguity
- returning custom class instances
- touching database transactions directly inside the entrypoint

## 5. What Output A Plugin Should Return

### 5.1 What A `connector` Should Return

It should return a `dict`, usually with at least:

- `records`: `list[dict]`

Current example: `apps/api-server/app/plugins/builtin/health_basic/connector.py:4`

Minimum example:

```python
return {
    "source": "health-basic-reader",
    "mode": "connector",
    "records": [
        {
            "record_type": "steps",
            "member_id": "demo-member",
            "value": 8421,
            "unit": "count",
            "captured_at": "2026-03-12T07:00:00Z"
        }
    ]
}
```

The system mainly treats `records` as the raw record input.

#### Full `connector` return example

This example is closer to a real integration case instead of a toy payload:

```python
return {
    "source": "homeassistant-device-sync",
    "mode": "connector",
    "received_payload": {
        "room_id": "living-room",
        "sensor_id": "living-room-sensor",
        "light_id": "living-room-main-light"
    },
    "records": [
        {
            "record_type": "device_power_state",
            "external_device_id": "living-room-main-light",
            "device": "living-room-main-light",
            "room_id": "living-room",
            "value": "on",
            "unit": "state",
            "captured_at": "2026-03-12T08:30:00Z"
        },
        {
            "record_type": "temperature",
            "external_device_id": "living-room-sensor",
            "device": "living-room-sensor",
            "room_id": "living-room",
            "value": 23.5,
            "unit": "celsius",
            "captured_at": "2026-03-12T08:30:00Z"
        },
        {
            "record_type": "humidity",
            "external_device_id": "living-room-sensor",
            "device": "living-room-sensor",
            "room_id": "living-room",
            "value": 48.0,
            "unit": "percent",
            "captured_at": "2026-03-12T08:30:00Z"
        }
    ]
}
```

Current implementation reference: `apps/api-server/app/plugins/builtin/homeassistant_device_sync/connector.py:4`

Each item inside `records` should ideally include at least:

| Field | Required | Meaning |
| --- | --- | --- |
| `record_type` | yes | raw record type, later used by `memory-ingestor` for routing |
| `value` | yes | raw value |
| `captured_at` | strongly recommended | capture time |
| `unit` | strongly recommended | value unit |
| `external_device_id` / `external_member_id` | recommended | external system primary key |
| `device` / `member_id` | recommended | business object reference |
| other extension fields | optional | for example `room_id`, `source_name` |

#### `connector records` raw-record field table

When the system persists raw records, it does not store a connector item as-is. It maps each returned item into a normalized structure.

It is easier to understand this from two layers:

##### A. Recommended fields in each connector record item

| Field | Type | Required | Meaning | How the system uses it |
| --- | --- | --- | --- | --- |
| `record_type` | string | recommended | raw record category | preferred source for system `record_type` |
| `type` | string | optional | fallback category field | used if `record_type` is missing |
| `category` | string | optional | second fallback category field | used if the first two are missing |
| `source_ref` | string | optional | external object reference | preferred source for system `source_ref` |
| `external_member_id` | string | optional | external member id | candidate source for `source_ref` |
| `external_device_id` | string | optional | external device id | useful for device tracing |
| `device` | string | optional | business device reference | candidate source for `source_ref` |
| `member_id` | string | optional | business member reference | candidate source for `source_ref` |
| `captured_at` | string | optional | raw capture time | preferred record timestamp |
| `observed_at` | string | optional | fallback time field | used if `captured_at` is missing |
| `occurred_at` | string | optional | second fallback time field | used if needed |
| `date` | string | optional | final fallback time field | used as last fallback |
| `value` | any | recommended | raw value | stored in `payload` for ingestor conversion |
| `unit` | string | recommended | value unit | stored in `payload` for ingestor conversion |
| other extension fields | any | optional | for example `room_id`, `status`, `vendor_name` | preserved inside `payload` |

##### B. Normalized raw-record structure after persistence

The system maps each raw item into this normalized structure:

| Field | Type | Source | Meaning |
| --- | --- | --- | --- |
| `id` | string | generated by system | raw record id |
| `household_id` | string | invocation context | household id |
| `plugin_id` | string | invocation context | source plugin id |
| `run_id` | string | generated by system | plugin run id |
| `trigger` | string | invocation context | trigger type |
| `record_type` | string | inferred from `record_type` / `type` / `category` | raw record category |
| `source_ref` | string \| null | inferred from `source_ref` / `external_member_id` / `external_device_id` / `device` / `member_id` | object reference |
| `payload` | object | original returned item | the main source read later by `memory-ingestor` |
| `captured_at` | string | inferred from `captured_at` / `observed_at` / `occurred_at` / `date` | record timestamp |
| `created_at` | string | generated by system | insert time |

Relevant implementation:

- raw record persistence: `apps/api-server/app/modules/plugin/service.py:190`
- `record_type` inference: `apps/api-server/app/modules/plugin/service.py:476`
- `source_ref` inference: `apps/api-server/app/modules/plugin/service.py:484`
- `captured_at` inference: `apps/api-server/app/modules/plugin/service.py:492`

### 5.2 What A `memory-ingestor` Should Return

It must return `list[dict]`.

Each item represents one normalized Observation candidate.

Hard requirements:

- it must contain `source_record_ref`
- it must contain `category`
- it must contain `value`

Current example: `apps/api-server/app/plugins/builtin/health_basic/ingestor.py:4`

Relevant system checks:

- `apps/api-server/app/modules/plugin/service.py:280`
- `apps/api-server/app/modules/plugin/service.py:287`
- `apps/api-server/app/modules/memory/service.py:772`

Minimum Observation example:

```python
{
    "type": "Observation",
    "subject_type": "Person",
    "subject_id": "member-1",
    "category": "daily_steps",
    "value": 8421,
    "unit": "count",
    "observed_at": "2026-03-12T07:00:00Z",
    "source_plugin_id": "health-basic-reader",
    "source_record_ref": "raw-record-id"
}
```

#### Full Observation field table

Each item returned by `memory-ingestor` should ideally follow this structure:

| Field | Type | Required | Meaning | Current usage |
| --- | --- | --- | --- | --- |
| `type` | string | recommended | usually `Observation` | helps readability and later extension |
| `subject_type` | string | recommended | target type such as `Person` or `Device` | used for memory organization |
| `subject_id` | string | recommended | observed subject id | used to locate the subject |
| `category` | string | yes | observation category such as `daily_steps` or `room_temperature` | required for memory write |
| `value` | any | yes | observation value | required for memory write |
| `unit` | string | recommended | unit such as `count` or `celsius` | useful for summaries and display |
| `observed_at` | string | recommended | observation timestamp | becomes memory time data |
| `source_plugin_id` | string | recommended | source plugin id | helps source tracing |
| `source_record_ref` | string | yes | matching raw record id | required for dedupe and tracing |

Only 3 fields are hard-required today:

- `category`
- `value`
- `source_record_ref`

But if you omit everything else, it may still run while producing ugly downstream results for tracing, display, and summarization.

A more complete real example:

```python
{
    "type": "Observation",
    "subject_type": "Device",
    "subject_id": "living-room-sensor",
    "category": "room_temperature",
    "value": 23.5,
    "unit": "celsius",
    "observed_at": "2026-03-12T08:30:00Z",
    "source_plugin_id": "homeassistant-device-sync",
    "source_record_ref": "raw-record-123"
}
```

Current implementation reference: `apps/api-server/app/plugins/builtin/homeassistant_device_sync/ingestor.py:4`

### 5.3 What An `action` Plugin Should Return

An action plugin can currently return a normal `dict`.

Current example: `apps/api-server/app/plugins/builtin/homeassistant_device_action/executor.py:4`

Common fields:

- `source`
- `mode`
- `target_ref`
- `action_name`
- `executed`
- `received_payload`

The point is not pretty field design. The point is that the caller can understand the action result.

### 5.4 What An `agent-skill` Should Return

There is no built-in example yet, but the runtime model is similar to `connector`: return JSON-serializable data.

Keep the boundary clear:

- it exposes capability to the Agent
- it does not take over the Agent main flow

## 6. What HTTP Endpoints Exist Today

Do not over-imagine this part. The currently exposed HTTP entries are mainly Agent-side integration entries, not a full plugin platform API.

### 6.1 Agent Invokes A Normal Plugin

- path: `POST /api/v1/ai-config/{household_id}/agents/{agent_id}/plugin-invocations`
- code: `apps/api-server/app/api/v1/endpoints/ai_config.py:505`
- body: `AgentPluginInvokeRequest`
- currently allowed types: `connector`, `agent-skill`

Request example:

```json
{
  "plugin_id": "health-basic-reader",
  "plugin_type": "connector",
  "payload": {
    "member_id": "member-1"
  },
  "trigger": "agent"
}
```

#### Complete sync request / response example

This example uses the current API entry that is closest to a formal integration path:

- `POST /api/v1/ai-config/{household_id}/agents/{agent_id}/plugin-memory-checkpoint`

Request example:

```json
{
  "plugin_id": "homeassistant-device-sync",
  "payload": {
    "room_id": "living-room",
    "sensor_id": "living-room-sensor",
    "light_id": "living-room-main-light"
  },
  "trigger": "agent-checkpoint"
}
```

Successful response example:

```json
{
  "agent_id": "agent-001",
  "agent_name": "Family Butler",
  "household_id": "household-001",
  "plugin_id": "homeassistant-device-sync",
  "trigger": "agent-checkpoint",
  "pipeline_run_id": "run-001",
  "pipeline_success": true,
  "raw_record_count": 3,
  "memory_card_count": 3,
  "degraded": false,
  "insight": {
    "agent_id": "agent-001",
    "agent_name": "Family Butler",
    "household_id": "household-001",
    "summary": "Family Butler has read plugin-written family memory: living-room-sensor room_temperature observation / 23.5 / celsius; living-room-sensor room_humidity observation / 48.0 / percent.",
    "suggestions": [
      "Continue watching living room temperature changes",
      "Combine humidity records with environment reminders"
    ],
    "used_plugins": [
      "homeassistant-device-sync"
    ],
    "facts": [
      {
        "memory_id": "memory-001",
        "source_plugin_id": "homeassistant-device-sync",
        "category": "room_temperature",
        "summary": "living-room-sensor room_temperature observation / 23.5 / celsius",
        "observed_at": "2026-03-12T08:30:00Z"
      }
    ]
  }
}
```

The 4 result fields you should care about most are:

- `pipeline_success`: whether the full sync chain succeeded
- `raw_record_count`: how many raw records were saved
- `memory_card_count`: how many normalized memory cards were written
- `insight`: whether the Agent can immediately use the new memory

### 6.2 Agent Triggers A Memory Checkpoint Sync

- path: `POST /api/v1/ai-config/{household_id}/agents/{agent_id}/plugin-memory-checkpoint`
- code: `apps/api-server/app/api/v1/endpoints/ai_config.py:550`
- purpose: invoke a `connector`, save raw records, convert them into memory, then return refreshed memory insight

This is currently the closest public endpoint to “sync plugin data into the project.”

Request example:

```json
{
  "plugin_id": "health-basic-reader",
  "payload": {
    "member_id": "member-1"
  },
  "trigger": "agent-checkpoint"
}
```

### 6.3 Agent Invokes An Action Plugin

- path: `POST /api/v1/ai-config/{household_id}/agents/{agent_id}/action-plugin-invocations`
- code: `apps/api-server/app/api/v1/endpoints/ai_config.py:576`
- body: `AgentActionPluginInvokeRequest`

### 6.4 Confirm A High-Risk Action

- path: `POST /api/v1/ai-config/{household_id}/agents/{agent_id}/action-plugin-confirmations/{confirmation_request_id}/confirm`
- code: `apps/api-server/app/api/v1/endpoints/ai_config.py:603`

## 7. What System Information Is Available

Plugins do not directly receive the entire system context. They get controlled input and then rely on the platform pipeline.

### Directly available to the plugin at call time

- caller-provided `payload`
- the invocation type implied by the entrypoint being called

### What the system handles for you

- raw record persistence
- plugin run tracking
- normalized Observation memory generation
- audit logging
- Agent action permission checks
- manual confirmation for high-risk actions

### What is not directly exposed to plugins yet

- a general database SDK
- a plugin-specific HTTP SDK
- an automatic configuration injection protocol
- a remote plugin callback mechanism
- a sandboxed runtime environment

So do not design against a “third-party cloud plugin platform” model. That is not what exists today.

## 8. How Data Sync Actually Works Today

There is one stable and correct sync path today:

### Path A: sync through `connector + memory-ingestor`

Steps:

1. `connector` fetches external data
2. it returns `records`
3. the system stores them in `plugin_raw_records`
4. `memory-ingestor` converts raw records into Observation objects
5. the system writes them into `memory_cards`
6. the Agent and business modules read those memories

This is the main backend path that already exists.

### Path B: trigger sync through the Agent memory checkpoint

If you need a public API entry to trigger sync, the most ready-made one today is:

- `plugin-memory-checkpoint`

It is still Path A under the hood, just wrapped in an Agent scenario.

### Sync paths that are not supported now

- letting plugins write database tables directly
- letting remote repository plugins callback into the system to execute code
- downloading third-party plugins automatically and executing them on the server
- bypassing raw records and writing arbitrary memory types directly from plugins

## 9. What Counts As The Minimum Integration Bar

The minimum passing bar is simple:

1. `manifest.json` is valid and loadable
2. entrypoint functions are importable
3. `connector` returns valid `records`
4. if `memory-ingestor` is declared, it can convert raw records into valid Observation objects
5. if `action` is declared, permissions and risk level are clearly defined
6. the plugin does not depend on auto-install, remote execution, or sandboxing features that do not exist yet

## 10. One-Line Summary

The current integration model is not “just mount an external API and you are done.” It is:

- register a loadable plugin through `manifest`
- let the system invoke it through a unified entry
- store data as raw records first, then convert it into normalized memory
- bridge Agent and action capabilities through controlled paths

That is the real integration model that exists today.
