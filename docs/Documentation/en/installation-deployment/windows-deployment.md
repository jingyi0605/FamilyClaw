---
title: Windows Deployment
docId: en-2.6
version: v0.1
status: draft
order: 260
outline: deep
---

# Windows Deployment

## Suitable for

- Local demos or lightweight testing on Windows 10 or 11.
- Development machines that need a quick way to open the web interface.

## Recommended path: Docker Desktop

1. Install Docker Desktop and enable the WSL2 backend.
2. Reserve a data directory such as `D:\familyclaw-data`.
3. Open PowerShell as Administrator and run:
   ```powershell
   docker run -d `
     --name familyclaw `
     -p 8080:8080 `
     -p 4399:4399 `
     -v D:/familyclaw-data:/data `
     jingyi0605/familyclaw:latest
   ```
   This guide uses `latest` by default. Only pin a concrete tag when you need precise rollback, issue reproduction, or a fixed release target.
   Use `/` in the mounted path on Windows. On first start, the generated database password and voice gateway token are written into `D:/familyclaw-data/runtime/secrets/`.
4. Open `http://localhost:8080` in a browser. If the login page appears, startup succeeded.

Placeholder for screenshot: Docker Desktop container list

## Source path, optional

- The recommended way is to use Ubuntu inside WSL2 and follow [Source Installation](./source-installation.md).
- Native Windows with Python 3.11 plus PostgreSQL is possible, but you must handle `psycopg`, Taro, and Node dependencies yourself. WSL is the safer default.

## Common issues

- The container does not start: confirm Docker Desktop is running and WSL2 is enabled.
- Port conflicts: change the mapping to something like `-p 18080:8080`.
- Mounted path errors: use a forward-slash path such as `D:/familyclaw-data:/data`.
