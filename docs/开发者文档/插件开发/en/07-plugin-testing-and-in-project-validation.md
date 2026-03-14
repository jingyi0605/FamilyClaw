# 07 Plugin Testing and In-Project Validation

## Document Metadata

- Purpose: tell developers how to prove a plugin is not just “written,” but actually runnable inside the project.
- Current version: v1.0
- Related documents: `docs/开发者文档/插件开发/en/02-plugin-dev-environment-and-local-debug.md`, `docs/开发者文档/插件开发/en/05-plugin-integration-guide.md`, `docs/开发者文档/插件开发/en/06-build-a-runnable-plugin-walkthrough.md`, `apps/api-server/tests/test_plugin_manifest.py`, `apps/api-server/tests/test_plugin_runs.py`
- Change log:
  - `2026-03-13`: created the first plugin testing and in-project validation guide.

This document answers one question:

- how to prove your plugin works under the runner model and can still be accepted by the main project

Do not confuse “the code imports” with “the plugin is ready.” Those are not the same thing.

## 1. Minimum Validation Has 4 Layers

Use this order:

1. `manifest` validation
2. runner-side entry function validation
3. main-service protocol validation
4. in-project invocation validation

If one layer fails, do not rush into the next one.

## 2. Layer One: `manifest` Validation

This is the most basic layer.

At minimum, confirm:

1. `id`, `name`, `version`, `types`, `permissions`, `risk_level`, `triggers`, and `entrypoints` all exist
2. the `id` character rules are correct
3. `types` does not introduce unsupported plugin types
4. every declared type has a matching entrypoint

Existing references:

- `apps/api-server/tests/test_plugin_manifest.py:22`
- `apps/api-server/tests/test_plugin_manifest.py:31`

If this layer fails, nothing else matters.

## 3. Layer Two: Entry Function Validation

This layer ignores the database and focuses only on whether the plugin works inside its own venv / runner environment.

### 3.1 `connector`

At minimum, confirm:

- it returns a `dict`
- it contains `records`
- `records` is a `list`

### 3.2 `memory-ingestor`

At minimum, confirm:

- it returns a `list`
- every item is a `dict`
- every item contains at least `category`, `value`, and `source_record_ref`

### 3.3 `action`

At minimum, confirm:

- it returns a JSON-serializable `dict`
- the caller can understand whether the action succeeded

### 3.4 `agent-skill`

At minimum, confirm:

- it returns a JSON-serializable `dict`
- it does not secretly depend on hidden extra runtime context

## 4. Layer Three: Service-Layer Pipeline Validation

This is where you verify whether the main service will really accept the plugin output.

The runner and background-job path already exist now, so testing must stop pretending that one synchronous function call is the whole story.

### 4.1 Validate the basic execution entry

Use `execute_plugin()` to confirm:

- the plugin can be discovered by the registry
- the unified entry can call it
- the return structure has not drifted

Reference:

- `apps/api-server/tests/test_plugin_manifest.py:95`

### 4.2 Validate the full data sync pipeline

If this is a `connector + memory-ingestor` plugin, you should also validate:

- `run_plugin_sync_pipeline()`

That chain covers:

1. invoke `connector`
2. persist raw records
3. invoke `memory-ingestor`
4. write normalized memory
5. write audit logs

But keep the boundary clear:

- `run_plugin_sync_pipeline()` is an internal orchestration check
- the real public path now also needs background-job validation

At minimum, also validate:

- `POST /api/v1/plugin-jobs`
- worker execution reaches a terminal state
- `GET /api/v1/plugin-jobs/{job_id}` returns attempts and notifications

References:

- `apps/api-server/tests/test_plugin_runs.py:48`
- `apps/api-server/tests/test_plugin_runs.py:116`
- `apps/api-server/tests/test_plugin_runs.py:192`

### 4.3 Validate the Agent bridge

If the plugin is meant for direct Agent use, validate:

- `invoke_agent_plugin()`

Currently only these types are allowed:

- `connector`
- `agent-skill`

Reference:

- `apps/api-server/tests/test_agent_plugin_bridge.py:48`

### 4.4 Validate action permissions and high-risk confirmation

If the plugin is an `action` plugin, validate at least these two things:

1. it is rejected when the actor lacks permission
2. high-risk actions go through manual confirmation instead of direct execution

References:

- `apps/api-server/tests/test_action_plugin_permissions.py:50`
- `apps/api-server/tests/test_action_plugin_permissions.py:107`
- `apps/api-server/tests/test_action_plugin_permissions.py:164`

## 5. Recommended Test Commands

Until the runner lands, inside `apps/api-server/`, the minimum useful commands are:

```bash
python -m unittest tests.test_plugin_manifest
python -m unittest tests.test_plugin_runs
python -m unittest tests.test_agent_plugin_bridge
python -m unittest tests.test_action_plugin_permissions
```

If you are only building a read-data plugin, the first two are the most important starting point.

## 6. How To Tell That The Plugin Really Runs In-Project

Do not stop at “the tests passed.”

Third-party plugins should later add one more runner-side check:

- execute entrypoints inside the plugin-owned venv
- confirm dependencies stay in the plugin environment instead of the main API environment

You should see outcomes that match your plugin type.

### 6.1 `connector + memory-ingestor`

At minimum, confirm:

- plugin execution succeeds
- raw record count is greater than 0
- normalized memory write count is greater than 0
- audit logs exist

### 6.2 `connector` for direct Agent use

At minimum, confirm:

- `invoke_agent_plugin()` succeeds
- the returned output matches expectations
- matching audit logs exist

### 6.3 `action`

At minimum, confirm:

- it is denied without permission
- it succeeds with permission
- high-risk actions return `confirmation_required` first

## 7. If You Need HTTP Integration Later

The current project entries are:

- `POST /api/v1/plugin-jobs`
- `GET /api/v1/plugin-jobs/{job_id}`
- `GET /api/v1/plugin-jobs`
- `POST /api/v1/plugin-jobs/{job_id}/responses`
- `POST /api/v1/ai-config/{household_id}/agents/{agent_id}/plugin-invocations`
- `POST /api/v1/ai-config/{household_id}/agents/{agent_id}/plugin-memory-checkpoint`
- `POST /api/v1/ai-config/{household_id}/agents/{agent_id}/action-plugin-invocations`
- `POST /api/v1/ai-config/{household_id}/agents/{agent_id}/action-plugin-confirmations/{confirmation_request_id}/confirm`

Relevant code:

- `apps/api-server/app/api/v1/endpoints/ai_config.py:505`
- `apps/api-server/app/api/v1/endpoints/ai_config.py:550`
- `apps/api-server/app/api/v1/endpoints/ai_config.py:576`
- `apps/api-server/app/api/v1/endpoints/ai_config.py:603`

But again:

- validate the service layer first
- then move on to HTTP integration

Otherwise you will not know whether the failure comes from the API layer, permissions, database setup, or the plugin itself.

## 8. Minimum Pre-Submission Self-Check

Before opening a registration PR, at least pass these 8 checks:

1. `manifest` passes validation
2. all entrypoints are importable
3. returned structures match the declared plugin type
4. if this is a data plugin, the internal pipeline is at least verified with `run_plugin_sync_pipeline()`
5. at least one full `create job -> worker execute -> query result` flow works
6. if this is for Agent use, confirm the return shape is now job-oriented instead of pretending to be a synchronous final result
7. if this is an action plugin, permission denial, high-risk confirmation, and job response flow were all tested
8. the README explains the minimum verification flow

## 9. One-Line Summary

Do not fake plugin testing in this version.

The minimum delivery bar is:

- valid `manifest`
- callable entrypoints
- working project service pipeline
- no bypass of permissions, audit, or confirmation logic

Once you have that, the plugin is actually runnable inside the project.
