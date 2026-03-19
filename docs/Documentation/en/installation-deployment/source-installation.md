---
title: Source Installation
docId: en-2.3
version: v0.1
status: draft
order: 230
outline: deep
---

# Source Installation

## Suitable for

- You need to modify code, debug, or run your own branch.
- Your machine or server already has Python 3.11, Node.js 20, and an external PostgreSQL instance.

## Environment requirements

- Python 3.11+
- Node.js 20+ with npm
- PostgreSQL 15+, with a `familyclaw` database and a `familyclaw` user. Choose your own password.
- macOS, Linux, WSL, or Windows

## Step 1: clone the repository

```bash
git clone https://github.com/jingyi0605/FamilyClaw.git
cd familyclaw
```

## Step 2: prepare backend configuration

```bash
cp apps/api-server/.env.example apps/api-server/.env
```

At minimum, update these values for your local database:

- `FAMILYCLAW_DATABASE_URL`, for example `postgresql+psycopg://familyclaw:<password>@127.0.0.1:5432/familyclaw`
- `FAMILYCLAW_TEST_DATABASE_URL` for the test database
- `OPENAI_API_KEY` only if you plan to call OpenAI

## Step 3: start the backend API

```bash
bash apps/start-api-server.sh
```

This script will:

- verify Python 3.11 and create `apps/api-server/.venv`
- install dependencies from `pyproject.toml`
- run Alembic migrations automatically
- start the Uvicorn development server, defaulting to `0.0.0.0:8000`, unless `HOST` or `PORT` overrides it

Verification: open `http://127.0.0.1:8000/api/v1/healthz` in a browser or with curl. It should return `{"status":"ok"}`.

## Step 4: start the H5 frontend

```bash
npm install --legacy-peer-deps
npm --prefix ./apps/user-app install --legacy-peer-deps
npm run dev:user-app:h5
```

- `apps/user-app/config/platform/h5.ts` already proxies `/api` to `http://127.0.0.1:8000`.
- Use the actual H5 address printed by the terminal instead of hardcoding a port from memory.

Verification: open the H5 address from the terminal. If the login page appears, the frontend is up.

## Log in after startup

- The initial account is `user` / `user`. Change the password after login.
- If the setup wizard appears, complete the required family information.

## Common issues

- Backend cannot connect to PostgreSQL: verify the server is running, credentials are correct, and the port is available.
- Frontend address does not open: inspect the terminal logs and make sure the Taro dev server did not fail.
- CORS or 404 on API calls: confirm the frontend still proxies to `http://127.0.0.1:8000` and the backend is running.
- Migration errors: start from an empty database when possible. If necessary, reset the database and rerun `bash apps/start-api-server.sh`.

## Completion standard

- The H5 development address allows login and can fetch API data.
- Local code changes take effect immediately through frontend hot reload and backend hot reload.
