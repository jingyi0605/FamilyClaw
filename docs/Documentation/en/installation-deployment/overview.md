---
title: Overview
docId: en-2.1
version: v0.1
status: draft
order: 210
outline: deep
---

# Installation Overview

## What this page solves

- It helps you decide which installation or deployment path fits your situation.

## Path selection

- Fastest trial path, recommended: read [Docker Installation](./docker-installation.md). One command is enough.
- Development or debugging: read [Source Installation](./source-installation.md).
- NAS panel deployment: read [NAS Deployment](./nas-deployment.md).
- Pure Linux server: read [Ubuntu Deployment](./ubuntu-deployment.md).
- Local Windows demo: read [Windows Deployment](./windows-deployment.md).

## Selection rules

- If Docker works for you, use Docker first. Switch to source only when you actually need code changes.
- All paths use the same product logic: web on `8080`, voice gateway on `4399`, data directory at `/data`.
- If you only need web conversations, you can leave the voice gateway port closed.

## Completion standard

- The reader can decide which page to open instead of scanning every installation page.
