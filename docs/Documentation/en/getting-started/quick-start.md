---
title: Quick Start
docId: en-1.3
version: v0.1
status: draft
order: 130
outline: deep
---

# Quick Start

## What this page solves

- It gives a first-time reader the shortest path to a usable web experience.
- It tells a new user what to do first, which command to run, and what success should look like.

## Choose your path

1. If you just want it running as fast as possible, use [Docker Installation](../installation-deployment/docker-installation.md). One `docker run` command is enough.
2. If you need local development or code changes, follow [Source Installation](../installation-deployment/source-installation.md) and bring up backend plus frontend.
3. If you only want to inspect the UI first, open the [Dashboard](../user-guide/dashboard.md) page and check the screenshots.

## Shortest runnable path: Docker

1. Prepare a machine that can run Docker, with at least 2 GB of memory, plus port `8080` for the web app and optionally `4399` for the voice gateway.
2. Run this command:

```bash
docker run -d \
  --name familyclaw \
  -p 8080:8080 \
  -p 4399:4399 \
  -v /srv/familyclaw-data:/data \
  jingyi0605/familyclaw:0.1.0
```

3. On first start, the container generates a random database password and voice gateway token, then stores them under `/srv/familyclaw-data/runtime/secrets/`. About one minute later, open `http://<server-ip>:8080` in a browser. If the login page appears, the system is up.
4. The initial account is `user` / `user`. After login, follow the setup flow to change the account and password.

Placeholder for screenshot: login page after Docker startup

## First thing to do after startup

- Open Settings and complete timezone, language, and the default AI provider.
- Open Family settings and make sure at least one member exists. If not, complete the setup wizard.

## Completion standard

- You can open the web home page in a browser and log in successfully.
- You have either completed family setup once or reached the state that says setup is already complete.
