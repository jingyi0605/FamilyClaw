---
title: Backend Development
docId: en-4.2
version: v0.1
status: active
order: 420
outline: deep
---

# Backend Development

The FamilyClaw backend is not a giant utility drawer. It is a host kernel with explicit boundaries.

Keep this sentence in mind before you touch backend code:

The host owns unified rules, unified data, unified permissions, and unified scheduling. Domain-specific exceptions belong in plugins, not as new special cases inside the host.

## Current stack

- Web framework: FastAPI
- ORM: SQLAlchemy 2.x
- Migration tool: Alembic
- Database: PostgreSQL
- Real-time transport: WebSocket
- Runtime entry: `apps/api-server/app/main.py`

## Real startup chain

When the application starts, `lifespan` currently does these things:

1. initialize logging
2. ensure the bootstrap admin account and pending bootstrap account exist
3. synchronize persisted plugin state
4. start `PluginJobWorker`
5. start `ScheduledTaskWorker`
6. start `ChannelPollingWorker`

So the backend is not just an HTTP service. It also carries background workers. If you shove blocking logic into the main event loop, you are slowing down API, WebSocket, and workers at the same time.

## Key directories

```text
apps/api-server/
├── app/
│   ├── api/v1/                 # HTTP and WebSocket endpoints
│   ├── core/                   # config, logging, blocking runtime, worker runtime
│   ├── db/                     # sessions and model aggregation
│   ├── modules/                # business modules
│   └── plugins/builtin/        # built-in plugins
├── migrations/                 # Alembic migrations
├── alembic.ini
└── .env.example
```

Current major modules under `app/modules/` include:

- `account`
- `agent`
- `ai_gateway`
- `channel`
- `context`
- `conversation`
- `device`, `device_action`, `device_integration`
- `household`
- `integration`
- `memory`
- `plugin`, `plugin_marketplace`
- `reminder`, `scheduler`
- `voice`, `voiceprint`
- `weather`

## Hard rules you do not get to ignore

### 1. Database structure must be changed through Alembic

Hard requirements:

- New tables, fields, indexes, and constraints must come with a migration.
- Do not sneak `create_all()` or `drop_all()` into app startup, scripts, or tests.
- If the database is dirty, verify the structure first and then use `alembic stamp`. Do not rely on luck.

### 2. Blocking logic cannot sit in the main event loop

This is not a suggestion. It is a red line.

Examples that must be pushed down:

- synchronous database work
- synchronous HTTP or SDK calls
- synchronous plugin execution
- long CPU-heavy computation
- `while True + sleep` polling loops

High-frequency fact sources:

- `apps/api-server/app/core/blocking.py`
- `apps/api-server/app/core/worker_runtime.py`

The practical reading is simple:

- `async` entry points should receive requests, do lightweight orchestration, and return results.
- Anything that blocks threads, blocks the event loop, or blocks WebSocket traffic must be moved down explicitly.
- Long-running background logic should use the existing worker system instead of ad-hoc loops.

### 3. Plugin enable/disable semantics must stay unified

Key points:

- Use `get_household_plugin(...)` for view and configuration flows.
- Use `require_available_household_plugin(...)` for any path that actually executes a plugin.
- Disabled plugin behavior should consistently return `409` plus `plugin_disabled`.

If you bypass this logic in one endpoint, the result is usually ugly:

- the UI looks like the plugin is disabled
- but a worker still executes it
- or the conversation flow still calls it anyway

That is not a small bug. That is a broken boundary.

### 4. The host must stop absorbing domain exceptions

If you catch yourself writing any of the following, you are going in the wrong direction:

- another host-only aggregation service just for weather, electricity, health, or steps
- a new set of host-specific special handling for one provider
- plugin code that writes directly into host core tables

The current official direction is explicit:

- the host maintains unified models, unified permissions, unified scheduling, and unified audit
- plugins absorb third-party differences, provider-specific edge cases, and integration details
- the host consumes standardized results, not third-party raw structures

## API entry points

The unified route aggregation lives in:

- `apps/api-server/app/api/v1/router.py`

Base prefix:

- `/api/v1`

Common HTTP documentation entries:

- `/docs`
- `/redoc`
- `/openapi.json`

## Main endpoint groups

These are the groups developers touch most often right now:

| Group | Route prefix | Main purpose |
| --- | --- | --- |
| System health | `/api/v1/healthz` | Health check |
| Auth | `/api/v1/auth` | Login, logout, current identity |
| Households | `/api/v1/households` | Household details and setup state |
| Dashboard | `/api/v1/dashboard/home` | Home cards and layout |
| Conversations | `/api/v1/conversations` | Sessions, turns, proposal confirmation |
| Memory | `/api/v1/memories` | Memory cards, revisions, queries, corrections |
| AI config | `/api/v1/ai-config` | Providers, routes, agents, themes, plugin mounts |
| Integrations | `/api/v1/integrations` | Integration instances, resources, actions |
| Channel accounts | `/api/v1/ai-config/{household_id}/channel-accounts` | Channel accounts, binding, probe |
| Plugin marketplace | `/api/v1/plugin-marketplace` | Marketplace sources, catalogs, install tasks |
| Scheduled tasks | `/api/v1/scheduled-tasks` | Task definitions, start-stop, draft confirmation |
| Voiceprints | `/api/v1/voiceprints` | Enrollment, summary, deletion |

### Frequently used concrete endpoints

- `GET /api/v1/healthz`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/households/{household_id}/setup-status`
- `GET /api/v1/dashboard/home`
- `GET /api/v1/dashboard/home/layout`
- `PUT /api/v1/dashboard/home/layout`
- `POST /api/v1/conversations/sessions`
- `POST /api/v1/conversations/sessions/{session_id}/turns`
- `GET /api/v1/memories/cards`
- `GET /api/v1/memories/cards/{memory_id}/revisions`
- `POST /api/v1/memories/cards/{memory_id}/corrections`
- `GET /api/v1/ai-config/provider-adapters`
- `GET /api/v1/ai-config/{household_id}/provider-profiles`
- `GET /api/v1/ai-config/{household_id}/plugins`
- `GET /api/v1/plugin-marketplace/catalog`
- `POST /api/v1/scheduled-tasks`
- `GET /api/v1/scheduled-task-runs`

## WebSocket entries

Current real-time channels:

- `ws://<host>/api/v1/realtime/voice`
- `ws://<host>/api/v1/realtime/agent-bootstrap`
- `ws://<host>/api/v1/realtime/conversation`

They currently live under `apps/api-server/app/api/v1/endpoints/realtime.py`.

## Where the real contract with the frontend lives

If you want to know which APIs the frontend really depends on, do not guess. Look here:

- `packages/user-core/src/api/create-api-client.ts`

If you want to compare code facts with the official documentation, also read:

- [Integration Flow](./plugin-integration.md)
- [Plugin Specification](./plugin-specification.md)

That frontend API client file is the current fact source for endpoint names, request paths, and return types.

## Recommended order for changes

### Adding or changing backend functionality

1. check whether existing modules and data structures already fit the job
2. decide whether the change belongs in the host or a plugin
3. confirm the migration plan before touching models
4. check whether `packages/user-core` already has matching types before changing API contracts
5. think through blocking boundaries before you add any heavy runtime work
6. update docs and targeted verification last

### Adding a new endpoint

1. add the endpoint
2. add service or repository support
3. update `packages/user-core/src/domain/types.ts`
4. update `packages/user-core/src/api/create-api-client.ts`
5. update any affected user or developer docs

## Final hard truth

If one change only works because you pile up `if/else` blocks for plugin state, thread boundaries, migration versions, and compatibility, the problem is probably not that the code is too short. The problem is that the data model or execution boundary is wrong. Fix the structure first, then write the code.
