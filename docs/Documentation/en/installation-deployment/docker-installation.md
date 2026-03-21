---
title: Docker Installation
docId: en-2.2
version: v0.1
status: draft
order: 220
outline: deep
---

# Docker Installation

## Suitable for

- You want the fastest startup path and do not plan to change code right away.
- You only have one machine with Docker support, such as a server, NAS, or personal computer.
- You accept using the PostgreSQL and Nginx that come inside the container setup.

## Prerequisites

- Docker is already installed on Linux, Windows, or macOS.
- Reserve port `8080` for the web app and optionally `4399` for the voice gateway.
- Reserve a data directory such as `/srv/familyclaw-data`, which will be mounted to `/data` inside the container.
- At least 2 GB of memory.

## Start it with one command

```bash
docker run -d \
  --name familyclaw \
  -p 8080:8080 \
  -p 4399:4399 \
  -v /srv/familyclaw-data:/data \
  jingyi0605/familyclaw:latest
```

The default install path uses `latest`. Only replace it with a concrete tag when you need precise rollback, issue reproduction, or a fixed release target.

Parameter notes, based on the repository Dockerfile and scripts:

- `8080`: Nginx reverse-proxies both the H5 frontend and backend API.
- `4399`: voice gateway, `open-xiaoai-gateway`. Remove this mapping if you do not need voice.
- `-v /srv/familyclaw-data:/data`: persists database files, plugins, logs, and related data.

On first start, the container auto-generates a random database password and a random voice gateway token, then stores them in:
- `/data/runtime/secrets/db-password`
- `/data/runtime/secrets/voice-gateway-token`

If you want to take over either value yourself, you can still pass `FAMILYCLAW_DB_PASSWORD` or `FAMILYCLAW_VOICE_GATEWAY_TOKEN`. The container will use your value and sync it back into the same secrets files.

## Verify after startup

1. Wait about 60 seconds, then run `docker ps`. The container status should be `Up`.
2. Open `http://<server-ip>:8080` in a browser. If the login page appears, startup succeeded.
   Placeholder for screenshot: login page
3. The initial account is `user` / `user`. Change it immediately after login.
4. If you want a quick health check, run `docker logs familyclaw | tail -n 50` and confirm the API server started without errors.

## Common issues

- Cannot reach port 8080: check your firewall or whether another service already uses the port.
- The container does not start: make sure the image pulled successfully, or remove the old container first with `docker rm -f familyclaw`.
- Login shows database errors: confirm `/data/runtime/secrets/db-password` was created and the mounted data volume is writable.
- Voice-related errors while you do not use voice: you can skip the `4399` port mapping and ignore voice gateway logs.

## Uninstall

```bash
docker rm -f familyclaw
rm -rf /srv/familyclaw-data   # Only run this if you also want to delete all persisted data
```
