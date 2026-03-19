---
title: Integration Flow
docId: en-4.7
version: v0.1
status: active
order: 470
outline: deep
---

# Integration Flow

This page explains how the host actually calls plugins and which endpoints matter most during integration and debugging.

## General rule

Plugin execution entries should only accept serializable input and should only return standardized results.

Do not pass any of the following directly into plugin execution:

- FastAPI request objects
- SQLAlchemy sessions
- Python objects that cannot be serialized

## Typical execution paths

### `integration`

1. the host reads the plugin manifest
2. it validates plugin type, state, and declared capabilities
3. it injects configuration and runtime context
4. it calls the `integration` entry
5. the plugin returns standardized entities, cards, and action descriptions
6. the host persists and updates state in a unified way

### `action`

1. validate that the plugin is enabled
2. validate permissions and risk level
3. run a confirmation flow if required
4. execute the action entry
5. let the host unify the execution result

### `ai-provider`

1. the host chooses the provider plugin through routing strategy
2. it loads provider profile and secret references
3. it calls `entrypoints.ai_provider`
4. the host handles timeout, retry, fallback, and audit in a unified way

### `channel`

1. the host stores channel accounts and binding relations
2. incoming channel events are parsed by the channel plugin
3. the host decides conversation ownership, member binding, and later dispatch
4. replies or notifications are sent back through the channel plugin

### `theme-pack` and `locale-pack`

These resource plugins do not go through heavy execution flows. The real flow is:

1. the host registers the plugin
2. the frontend reads the available resource list
3. the frontend loads theme tokens or locale resources by resource path

## Endpoint groups used most often during integration

### Auth and bootstrap

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/households/{household_id}/setup-status`

### Dashboard and memory

- `GET /api/v1/dashboard/home`
- `GET /api/v1/dashboard/home/layout`
- `PUT /api/v1/dashboard/home/layout`
- `GET /api/v1/memories/cards`
- `GET /api/v1/memories/cards/{memory_id}/revisions`
- `POST /api/v1/memories/cards/{memory_id}/corrections`

### AI config and plugin mounts

- `GET /api/v1/ai-config/provider-adapters`
- `GET /api/v1/ai-config/{household_id}/provider-profiles`
- `POST /api/v1/ai-config/{household_id}/provider-profiles`
- `GET /api/v1/ai-config/{household_id}/plugins`
- `PUT /api/v1/ai-config/{household_id}/plugins/{plugin_id}/state`
- `GET /api/v1/ai-config/{household_id}/plugin-mounts`
- `POST /api/v1/ai-config/{household_id}/plugin-mounts`

### Plugin marketplace

- `GET /api/v1/plugin-marketplace/sources`
- `POST /api/v1/plugin-marketplace/sources`
- `POST /api/v1/plugin-marketplace/sources/{source_id}/sync`
- `GET /api/v1/plugin-marketplace/catalog`
- `POST /api/v1/plugin-marketplace/install-tasks`

### Integrations and channels

- `GET /api/v1/integrations/catalog`
- `GET /api/v1/integrations/instances`
- `POST /api/v1/integrations/instances`
- `POST /api/v1/integrations/instances/{instance_id}/actions`
- `GET /api/v1/ai-config/{household_id}/channel-accounts`
- `POST /api/v1/ai-config/{household_id}/channel-accounts`
- `POST /api/v1/ai-config/{household_id}/channel-accounts/{account_id}/probe`

### Scheduled tasks and background execution

- `POST /api/v1/scheduled-tasks`
- `GET /api/v1/scheduled-tasks`
- `GET /api/v1/scheduled-task-runs`
- `POST /api/v1/scheduled-task-drafts/from-conversation`
- `POST /api/v1/scheduled-task-drafts/{draft_id}/confirm`

## How to use OpenAPI

After the backend is running, the most direct entries are:

- `/docs`
- `/redoc`
- `/openapi.json`

Do not treat OpenAPI as a design document. It tells you what fields exist, not why the boundaries were designed that way. For boundaries, read the rules and the code.

## WebSocket integration

Current real-time entries:

- `/api/v1/realtime/voice`
- `/api/v1/realtime/agent-bootstrap`
- `/api/v1/realtime/conversation`

During debugging, pay attention to:

- whether authentication succeeded
- whether `household_id` and `session_id` match the expected context
- whether event types match the backend definitions

## Most reliable fact sources

If you only read one layer before changing code, at least read these:

- `apps/api-server/app/api/v1/router.py`
- `apps/api-server/app/api/v1/endpoints/`
- `packages/user-core/src/api/create-api-client.ts`

The first two are the real backend entry points. The last one is the current contract the frontend is actively calling.

## Final reminder

Do not confuse "integration works" with "design is correct."

If a new plugin only integrates successfully because the host and frontend each need three layers of patch logic, the problem is not that integration is hard. The problem is that the integration design itself is already wrong.
