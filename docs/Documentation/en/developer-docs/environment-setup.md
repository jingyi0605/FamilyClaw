---
title: Environment Setup
docId: en-4.1
version: v0.1
status: active
order: 410
outline: deep
---

# Environment Setup

This page solves one specific problem: when a developer touches this repository for the first time, they should know what to install locally, what to run first, and which commands are actually used in the current repo.

## Local requirements

- Operating system: macOS, Linux, and Windows are all supported.
- Python: `3.11`. Both the backend and the gateway run on this version.
- Node.js: `20+`. The root docs site and `apps/user-app` both depend on it.
- PostgreSQL: `15+`. Development and testing both use PostgreSQL. There is no SQLite fallback.
- Git plus Bash: the backend and gateway startup scripts in the repository are Bash scripts. On Windows, Git Bash is the recommended option.

## Repository directories you should actually care about

```text
FamilyClaw/
├── apps/
│   ├── api-server/               # FastAPI + SQLAlchemy + Alembic
│   ├── user-app/                 # Taro + React + TypeScript
│   ├── open-xiaoai-gateway/      # Voice gateway
│   ├── start-api-server.sh       # Backend development startup script
│   └── start-open-xiaoai-gateway.sh
├── packages/
│   ├── user-core/                # Frontend shared API and types
│   ├── user-platform/            # Platform adapters
│   └── user-ui/                  # UI components and theme capabilities
├── docs/Documentation/           # Official VitePress documentation source
├── docs/开发设计规范/            # Supplementary repo materials that still exist
├── docs/开发者文档/              # Supplementary repo materials that still exist
├── docker/                       # Runtime scripts plus nginx and supervisor config
└── specs/                        # Specifications and design records
```

## Correct order for first-time setup

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd FamilyClaw
```

### 2. Install root dependencies

The root dependencies mainly support the docs site and workspace package linking:

```bash
npm install --legacy-peer-deps
```

### 3. Install frontend dependencies

`apps/user-app` is not the kind of directory that becomes runnable just because the root workspace finished installing. It has its own dependency set:

```bash
npm --prefix ./apps/user-app install --legacy-peer-deps
```

### 4. Prepare PostgreSQL

You need at least one local PostgreSQL database. A typical default setup looks like this:

- database: `familyclaw`
- user: `familyclaw`
- password: `change-me`

If you change the username, password, or port, update `.env` to match. Do not expect the code to guess correctly.

### 5. Prepare backend environment variables

```bash
cp apps/api-server/.env.example apps/api-server/.env
```

The most important keys are:

- `FAMILYCLAW_DATABASE_URL`
- `FAMILYCLAW_TEST_DATABASE_URL`
- `FAMILYCLAW_BOOTSTRAP_ADMIN_USERNAME`
- `FAMILYCLAW_BOOTSTRAP_ADMIN_PASSWORD`
- `FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_USERNAME`
- `FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_PASSWORD`
- `FAMILYCLAW_AI_PROVIDER_CONFIGS`
- `OPENAI_API_KEY` if you use an OpenAI-compatible provider

### 5.1 Sync project version metadata

Version handling now follows two simple rules:

- The backend development runtime reads the repository root `VERSION` file by default. Do not keep another handwritten formal version in backend config.
- Files such as `pyproject.toml`, `package.json`, `package-lock.json`, and `Dockerfile` cannot read `VERSION` on their own, so they must be synchronized by script.

Common commands:

```bash
# Windows
py -3.11 apps/scripts/sync_versions.py
py -3.11 apps/scripts/sync_versions.py --check

# macOS / Linux
python3 apps/scripts/sync_versions.py
python3 apps/scripts/sync_versions.py --check
```

Recommended habit:

- After changing the root `VERSION`, run the sync script once.
- Before committing release-related changes, run `--check` to make sure version drift is gone.

### 6. Start the backend

The repository already provides the official development script. Do not improvise your own startup command:

```bash
bash apps/start-api-server.sh
```

This script will:

- create `apps/api-server/.venv` automatically
- install Python dependencies automatically
- check the Alembic state and run `alembic upgrade head`
- start `uvicorn app.main:app` with hot reload

Default addresses:

- API: `http://127.0.0.1:8000`
- health check: `http://127.0.0.1:8000/api/v1/healthz`
- OpenAPI: `http://127.0.0.1:8000/docs`

### 7. Start the H5 frontend

```bash
npm run dev:user-app:h5
```

The H5 development environment proxies `/api` to `http://127.0.0.1:8000`. Use the URL shown in the terminal instead of memorizing a hardcoded port.

### 8. Start the docs site

```bash
npm run docs:dev
```

Again, use the address printed by the terminal.

## Minimal verification checklist

For a first working setup, confirm at least these items:

- `bash apps/start-api-server.sh` completes without migration failure.
- `GET /api/v1/healthz` returns success.
- The H5 page opens and `/api` requests are not returning `404`.
- The login page appears and the initialization flow can start.
- `npm run docs:build` succeeds.

## Required reading

During development, use the current official developer docs inside this documentation site as your baseline. Do not build your understanding on materials outside `docs/Documentation`.

Recommended order:

1. Read [Directory Structure](./plugin-directory-structure.md) first so you know which directories are the real work areas.
2. Before changing backend code, read [Backend Development](./backend-development.md). It already covers migrations, event loop boundaries, workers, API entry points, and the recommended change order.
3. Before changing plugins, read [Plugin Development](./plugin-development.md), [Plugin Specification](./plugin-specification.md), [Field Specification](./plugin-fields.md), and [Integration Flow](./plugin-integration.md).
4. When you are ready to deliver a plugin, read [Example Plugin](./plugin-example.md) and [Plugin Submission](./plugin-submission.md).

The hard rules to remember are:

- Database structure changes must go through Alembic migrations. Do not hide `create_all()` or `drop_all()` in business code.
- Any blocking or long-running synchronous work must stay out of `async` entry points and be pushed down to workers or the blocking runtime.
- Plugin enable, disable, and execution boundaries must stay unified. One page must not block what a background task still keeps running.
- Plugins handle third-party adaptation. The host handles unified permissions, unified standards, and unified scheduling.

## Windows notes

- Running `apps/start-api-server.sh` through Git Bash is recommended.
- If you force PowerShell for everything, you own the path differences, activation script quirks, and line-ending problems.
- `apps/user-app` H5 development can still run in PowerShell, but when you mix frontend and backend work, Git Bash is the least painful option.

## Things not to do

- Do not use `create_all()` or `drop_all()` in business code to force schema changes.
- Do not invent another backend startup command to replace `apps/start-api-server.sh`.
- Do not hardcode user-facing frontend text into components. New pages must use the shared i18n pipeline.
- Do not edit build artifacts under `docs/Documentation/.vitepress/dist`.
