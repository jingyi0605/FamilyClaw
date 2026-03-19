---
title: Ubuntu Deployment
docId: en-2.5
version: v0.1
status: draft
order: 250
outline: deep
---

# Ubuntu Deployment

## Suitable for

- Ubuntu 20.04 or 22.04 servers and cloud hosts.
- Stable runtime use where Docker plus its bundled PostgreSQL is acceptable.

## Recommended path: run with Docker

1. Install Docker. Example with the official script:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER
   newgrp docker
   ```
2. Prepare the data directory:
   ```bash
   sudo mkdir -p /srv/familyclaw-data && sudo chown $USER:$USER /srv/familyclaw-data
   ```
3. Run the container:
   ```bash
   docker run -d \
     --name familyclaw \
     -p 8080:8080 \
     -p 4399:4399 \
     -e FAMILYCLAW_DB_PASSWORD='change-me' \
     -e FAMILYCLAW_VOICE_GATEWAY_TOKEN='replace-me' \
     -v /srv/familyclaw-data:/data \
     jingyi0605/familyclaw:0.1.0
   ```
4. Verify:
   - `docker ps` should show the container as `Up`.
   - Opening `http://<server-ip>:8080` should show the login page.

Placeholder for screenshot: Ubuntu terminal and login page

## Need automatic restart on boot?

Docker restart policy is not enabled by default. Add `--restart unless-stopped` if needed. If you prefer `systemd`, wrap the same `docker run` or `docker start` logic in a service on the host. This page does not duplicate a second management path.

## Source deployment

If you are doing active development on Ubuntu, follow [Source Installation](./source-installation.md). You can install dependencies with apt:

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv nodejs npm postgresql
```

The remaining steps are the same as the source installation page.

## Common issues

- Port 8080 is unreachable: check UFW or your cloud security group and allow 8080, plus optionally 4399.
- Permission errors: make sure `/srv/familyclaw-data` is writable by the runtime user.
- Slow image pulls: switch to a closer registry mirror and try again.
