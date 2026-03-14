# 10 Scheduled Task API And OpenAPI Guide

## Document Metadata

- Purpose: explain the current scheduled-task APIs for plugin developers and integration engineers, where to view OpenAPI, and what matters when plugins are used by scheduled tasks.
- Current version: v1.0
- Related documents: `docs/开发者文档/插件开发/en/03-manifest-spec.md`, `docs/开发者文档/插件开发/en/05-plugin-integration-guide.md`, `apps/api-server/app/api/v1/endpoints/scheduled_tasks.py`
- Change log:
  - `2026-03-14`: created the first version with scheduled-task APIs, OpenAPI access points, and plugin integration boundaries.

This document answers 3 things:

1. which scheduled-task APIs are formally available now
2. where to read the generated OpenAPI docs
3. what plugin developers can configure, and what they must not fake

## 1. Lock The Boundary First

- Right now the only real target developers can configure is the plugin path, which means `target_type=plugin_job`
- `target_ref_id` is not an arbitrary string; it is the plugin `id`
- The plugin must declare `schedule` inside `manifest.triggers`, otherwise the scheduled-task API rejects it
- A plugin does not own cron registration just because it declares `schedule`; scheduling, ownership, permissions, and idempotency all belong to the scheduled-task system
- Scheduled tasks now support 2 ownership scopes:
  - `household`: family-shared task
  - `member`: member-private task

## 2. Where To View OpenAPI

If the backend service is running, you can usually open these directly:

- `GET /openapi.json`: full OpenAPI JSON
- `GET /docs`: Swagger UI
- `GET /redoc`: ReDoc

The difference is simple:

- `openapi.json` is for tools, or for importing into Postman or Insomnia
- `/docs` is the fastest place to try requests during integration
- `/redoc` is easier to read when you mainly want schema details

Do not confuse scope here:

- OpenAPI tells you what the fields look like
- it does not fully explain business boundaries such as “family-shared vs member-private tasks” or “what happens after a plugin is disabled”
- those boundaries still belong in this guide and the related design docs

## 3. Current Formal APIs

Code entry: `apps/api-server/app/api/v1/endpoints/scheduled_tasks.py`

### 3.1 Create A Scheduled Task

- Method: `POST /api/v1/scheduled-tasks`
- Purpose: create one task definition
- Auth: requires a logged-in actor bound to a household member

Minimum example:

```json
{
  "household_id": "household-demo",
  "owner_scope": "household",
  "code": "daily-health-sync",
  "name": "Daily Health Sync",
  "trigger_type": "schedule",
  "schedule_type": "daily",
  "schedule_expr": "09:00",
  "target_type": "plugin_job",
  "target_ref_id": "health-basic-reader"
}
```

Key fields:

- `owner_scope`
  - `household`: family-shared task, admin only
  - `member`: member-private task, and a normal member can only create one for self
- `trigger_type`
  - `schedule`: fixed-time trigger
  - `heartbeat`: heartbeat inspection trigger
- `schedule_type`
  - currently supported: `daily`, `interval`, `cron`
- `target_type`
  - currently stable: `plugin_job`
- `target_ref_id`
  - currently this is simply the plugin `id`

Common failure reasons:

- the plugin does not declare `schedule`
- the plugin is disabled
- a normal member tries to create a family-shared task
- a normal member tries to create a member-private task for someone else

### 3.2 List Task Definitions

- Method: `GET /api/v1/scheduled-tasks`
- Purpose: filter task definitions by household, ownership, and status

Common query parameters:

- `household_id`: required
- `owner_scope`
- `owner_member_id`
- `enabled`
- `trigger_type`
- `target_type`
- `status`

Permission boundary:

- family-shared tasks are visible to household members
- member-private tasks are visible to admins for all members, but a normal member only sees their own

### 3.3 Get Task Detail

- Method: `GET /api/v1/scheduled-tasks/{task_id}`
- Purpose: read one task definition

Important note:

- if you are not allowed to see a member-private task, the API behaves as “not found” instead of exposing someone else’s task

### 3.4 Update A Task Definition

- Method: `PATCH /api/v1/scheduled-tasks/{task_id}`
- Purpose: update name, description, ownership, timing config, target plugin, enabled status, and more

Common use cases:

- change the schedule
- move the task between private and family-shared scopes
- switch the target plugin

Important note:

- when you change the target plugin, the backend validates again that the plugin exists, is enabled, and supports `schedule`

### 3.5 Enable / Disable A Task

- Method: `POST /api/v1/scheduled-tasks/{task_id}/enable`
- Method: `POST /api/v1/scheduled-tasks/{task_id}/disable`
- Purpose: toggle task execution on or off

The difference is plain:

- `enable` puts the task back into future scheduler scans
- `disable` pauses it so no new runs are produced

### 3.6 List Run Records

- Method: `GET /api/v1/scheduled-task-runs`
- Purpose: query execution history for one household

Common query parameters:

- `household_id`: required
- `task_definition_id`
- `owner_scope`
- `owner_member_id`
- `status`
- `created_from`
- `created_to`
- `limit`

This API mainly answers 2 questions:

1. did the task actually run when it became due
2. did that run later turn into a `plugin_job`

## 4. How To Trace One Full Chain

To inspect the chain “scheduled task -> plugin_job -> queryable result”, use this order:

1. use `GET /api/v1/scheduled-tasks` to find the task definition
2. use `GET /api/v1/scheduled-task-runs?task_definition_id=...` to find run records
3. read `target_run_id` from the run record
4. query `GET /api/v1/plugin-jobs/{job_id}`

Key tracing fields:

- `scheduled_task_run.target_run_id`: maps to `plugin_job.id`
- `plugin_job.source_task_definition_id`: source task-definition id
- `plugin_job.source_task_run_id`: source task-run id

In plain words: scheduled tasks and plugin background jobs are no longer disconnected logs. They can now be traced across the whole chain.

## 5. What Plugin Developers Can Configure Today

At this stage, the formal plugin-side configuration related to scheduled tasks is limited to these parts:

### 5.1 `manifest.triggers`

- if the plugin should be callable by scheduled tasks, it must include `schedule`
- without that, the plugin is not eligible for the scheduled-task system

### 5.2 `manifest.schedule_templates`

- this is a recommendation surface, not an auto-create mechanism
- use it to tell later UIs or config flows what a sensible scheduled-task template looks like

### 5.3 Plugin Mount Enabled State

- after a plugin is disabled at the household mount layer, new task creation is rejected
- already queued-but-not-yet-dispatched runs also fail at dispatch time

## 6. What Is Not Open To Plugin Authors Yet

Do not write or assume these yet:

- plugins registering their own cron or heartbeat timers
- plugins mutating scheduler state by themselves
- templates auto-persisting into real scheduled tasks
- scheduled tasks bypassing `plugin_job` and synchronously executing plugins directly
- marketplace one-click full scheduled-task setup

## 7. Practical Integration Flow

The fastest way to test this path is:

1. open `/docs` and inspect the request models
2. call `POST /api/v1/scheduled-tasks` to create a task targeting your plugin
3. call `GET /api/v1/scheduled-task-runs` to verify that a run record exists
4. call `GET /api/v1/plugin-jobs/{job_id}` to confirm the run actually entered the plugin background-job chain

If step 2 already fails, check these first:

- did you use the correct plugin id
- is the plugin enabled
- does `manifest.triggers` include `schedule`
- are you crossing an ownership boundary you are not allowed to cross
