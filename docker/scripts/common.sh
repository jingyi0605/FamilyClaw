#!/usr/bin/env bash

set -euo pipefail

: "${FAMILYCLAW_APP_ROOT:=/opt/familyclaw}"
: "${FAMILYCLAW_DATA_DIR:=/data}"
: "${FAMILYCLAW_PGDATA:=${FAMILYCLAW_DATA_DIR}/postgres}"
: "${FAMILYCLAW_BACKUP_DIR:=${FAMILYCLAW_DATA_DIR}/backups}"
: "${FAMILYCLAW_RUNTIME_DIR:=${FAMILYCLAW_DATA_DIR}/runtime}"
: "${FAMILYCLAW_PLUGIN_DATA_DIR:=${FAMILYCLAW_DATA_DIR}/plugins}"
: "${FAMILYCLAW_VOICE_ARTIFACTS_DIR:=${FAMILYCLAW_DATA_DIR}/voice-runtime-artifacts}"
: "${FAMILYCLAW_DB_HOST:=127.0.0.1}"
: "${FAMILYCLAW_DB_PORT:=5432}"
: "${FAMILYCLAW_DB_NAME:=familyclaw}"
: "${FAMILYCLAW_DB_USER:=familyclaw}"
: "${FAMILYCLAW_DB_PASSWORD:=change-me}"
: "${FAMILYCLAW_API_PORT:=8000}"
: "${FAMILYCLAW_GATEWAY_PORT:=4399}"
: "${FAMILYCLAW_NGINX_PORT:=8080}"
: "${FAMILYCLAW_ENABLE_GATEWAY:=1}"
: "${FAMILYCLAW_RELEASE_MANIFEST_PATH:=${FAMILYCLAW_APP_ROOT}/release-manifest.json}"

export FAMILYCLAW_DATABASE_URL="${FAMILYCLAW_DATABASE_URL:-postgresql+psycopg://${FAMILYCLAW_DB_USER}:${FAMILYCLAW_DB_PASSWORD}@${FAMILYCLAW_DB_HOST}:${FAMILYCLAW_DB_PORT}/${FAMILYCLAW_DB_NAME}}"
export FAMILYCLAW_PLUGIN_STORAGE_ROOT="${FAMILYCLAW_PLUGIN_STORAGE_ROOT:-${FAMILYCLAW_PLUGIN_DATA_DIR}}"
export FAMILYCLAW_PLUGIN_MARKETPLACE_INSTALL_ROOT="${FAMILYCLAW_PLUGIN_MARKETPLACE_INSTALL_ROOT:-${FAMILYCLAW_PLUGIN_DATA_DIR}}"
export FAMILYCLAW_VOICE_RUNTIME_ARTIFACTS_ROOT="${FAMILYCLAW_VOICE_RUNTIME_ARTIFACTS_ROOT:-${FAMILYCLAW_VOICE_ARTIFACTS_DIR}}"
export FAMILYCLAW_RELEASE_MANIFEST_PATH
export FAMILYCLAW_RUNTIME_DIR
export FAMILYCLAW_ENVIRONMENT="${FAMILYCLAW_ENVIRONMENT:-production}"
export FAMILYCLAW_BUILD_CHANNEL="${FAMILYCLAW_BUILD_CHANNEL:-development}"
export FAMILYCLAW_VOICE_GATEWAY_TOKEN="${FAMILYCLAW_VOICE_GATEWAY_TOKEN:-dev-voice-gateway-token}"
export FAMILYCLAW_OPEN_XIAOAI_GATEWAY_API_SERVER_HTTP_URL="${FAMILYCLAW_OPEN_XIAOAI_GATEWAY_API_SERVER_HTTP_URL:-http://127.0.0.1:${FAMILYCLAW_API_PORT}/api/v1}"
export FAMILYCLAW_OPEN_XIAOAI_GATEWAY_API_SERVER_WS_URL="${FAMILYCLAW_OPEN_XIAOAI_GATEWAY_API_SERVER_WS_URL:-ws://127.0.0.1:${FAMILYCLAW_API_PORT}/api/v1/realtime/voice}"
export FAMILYCLAW_OPEN_XIAOAI_GATEWAY_LISTEN_HOST="${FAMILYCLAW_OPEN_XIAOAI_GATEWAY_LISTEN_HOST:-0.0.0.0}"
export FAMILYCLAW_OPEN_XIAOAI_GATEWAY_LISTEN_PORT="${FAMILYCLAW_OPEN_XIAOAI_GATEWAY_LISTEN_PORT:-${FAMILYCLAW_GATEWAY_PORT}}"
export FAMILYCLAW_OPEN_XIAOAI_GATEWAY_VOICE_GATEWAY_TOKEN="${FAMILYCLAW_OPEN_XIAOAI_GATEWAY_VOICE_GATEWAY_TOKEN:-${FAMILYCLAW_VOICE_GATEWAY_TOKEN}}"
export PGPASSWORD="${PGPASSWORD:-${FAMILYCLAW_DB_PASSWORD}}"

log() {
  printf '[familyclaw-container] %s\n' "$1"
}

is_truthy() {
  case "${1,,}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

ensure_runtime_layout() {
  mkdir -p \
    "${FAMILYCLAW_PGDATA}" \
    "${FAMILYCLAW_BACKUP_DIR}" \
    "${FAMILYCLAW_RUNTIME_DIR}" \
    "${FAMILYCLAW_PLUGIN_DATA_DIR}" \
    "${FAMILYCLAW_VOICE_ARTIFACTS_DIR}" \
    /var/run/postgresql
  chown -R postgres:postgres "${FAMILYCLAW_PGDATA}" /var/run/postgresql
  chmod 700 "${FAMILYCLAW_PGDATA}"
}

wait_for_postgres() {
  local attempts="${1:-60}"
  local i=0
  until pg_isready -h "${FAMILYCLAW_DB_HOST}" -p "${FAMILYCLAW_DB_PORT}" -U "${FAMILYCLAW_DB_USER}" -d "${FAMILYCLAW_DB_NAME}" >/dev/null 2>&1; do
    i=$((i + 1))
    if [[ "${i}" -ge "${attempts}" ]]; then
      log "PostgreSQL did not become ready in time"
      return 1
    fi
    sleep 1
  done
}

wait_for_api() {
  local attempts="${1:-60}"
  local i=0
  until curl --fail --silent --show-error "http://127.0.0.1:${FAMILYCLAW_API_PORT}/api/v1/healthz" >/dev/null; do
    i=$((i + 1))
    if [[ "${i}" -ge "${attempts}" ]]; then
      log "api-server did not become ready in time"
      return 1
    fi
    sleep 1
  done
}

write_runtime_state() {
  python - <<'PY'
from __future__ import annotations

import json
from pathlib import Path
import os

manifest_path = Path(os.environ["FAMILYCLAW_RELEASE_MANIFEST_PATH"])
runtime_path = Path(os.environ["FAMILYCLAW_RUNTIME_DIR"]) / "installed-version.json"

payload = {
    "app_version": os.environ.get("FAMILYCLAW_APP_VERSION"),
    "build_channel": os.environ.get("FAMILYCLAW_BUILD_CHANNEL", "development"),
}

if manifest_path.exists():
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = {}
    payload = {
        "app_version": manifest.get("app_version"),
        "git_tag": manifest.get("git_tag"),
        "git_sha": manifest.get("git_sha"),
        "built_at": manifest.get("built_at"),
        "schema_heads": manifest.get("schema_heads", []),
        "build_channel": manifest.get("build_channel"),
    }

runtime_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}
