#!/usr/bin/env bash

set -euo pipefail

: "${FAMILYCLAW_APP_ROOT:=/opt/familyclaw}"
: "${FAMILYCLAW_DATA_DIR:=/data}"
: "${FAMILYCLAW_PGDATA:=${FAMILYCLAW_DATA_DIR}/postgres}"
: "${FAMILYCLAW_BACKUP_DIR:=${FAMILYCLAW_DATA_DIR}/backups}"
: "${FAMILYCLAW_LOG_DIR:=${FAMILYCLAW_DATA_DIR}/logs}"
: "${FAMILYCLAW_RUNTIME_DIR:=${FAMILYCLAW_DATA_DIR}/runtime}"
: "${FAMILYCLAW_PLUGIN_DATA_DIR:=${FAMILYCLAW_DATA_DIR}/plugins}"
: "${FAMILYCLAW_VOICE_ARTIFACTS_DIR:=${FAMILYCLAW_DATA_DIR}/voice-runtime-artifacts}"
: "${FAMILYCLAW_SECRET_DIR:=${FAMILYCLAW_RUNTIME_DIR}/secrets}"
: "${FAMILYCLAW_DB_PASSWORD_FILE:=${FAMILYCLAW_SECRET_DIR}/db-password}"
: "${FAMILYCLAW_VOICE_GATEWAY_TOKEN_FILE:=${FAMILYCLAW_SECRET_DIR}/voice-gateway-token}"
: "${FAMILYCLAW_DB_HOST:=127.0.0.1}"
: "${FAMILYCLAW_DB_PORT:=5432}"
: "${FAMILYCLAW_DB_NAME:=familyclaw}"
: "${FAMILYCLAW_DB_USER:=familyclaw}"
: "${FAMILYCLAW_API_PORT:=8000}"
: "${FAMILYCLAW_GATEWAY_PORT:=4399}"
: "${FAMILYCLAW_NGINX_PORT:=8080}"
: "${FAMILYCLAW_ENABLE_GATEWAY:=1}"
: "${FAMILYCLAW_RELEASE_MANIFEST_PATH:=${FAMILYCLAW_APP_ROOT}/release-manifest.json}"
: "${FAMILYCLAW_LOG_PREFIX:=familyclaw-container}"

log() {
  printf '[%s] %s\n' "${FAMILYCLAW_LOG_PREFIX}" "$1"
}

read_password_from_database_url() {
  python - <<'PY'
from __future__ import annotations

import os
from urllib.parse import urlsplit, unquote

database_url = os.environ.get("FAMILYCLAW_DATABASE_URL", "").strip()
if not database_url:
    raise SystemExit(0)

password = urlsplit(database_url).password
if password:
    print(unquote(password))
PY
}

canonicalize_database_url() {
  python - <<'PY'
from __future__ import annotations

import os
from urllib.parse import quote, urlsplit, urlunsplit

database_url = os.environ.get("FAMILYCLAW_DATABASE_URL", "").strip()
password = os.environ["FAMILYCLAW_DB_PASSWORD"]

if not database_url:
    user = quote(os.environ.get("FAMILYCLAW_DB_USER", "familyclaw"), safe="")
    host = os.environ.get("FAMILYCLAW_DB_HOST", "127.0.0.1")
    port = os.environ.get("FAMILYCLAW_DB_PORT", "5432")
    database_name = quote(os.environ.get("FAMILYCLAW_DB_NAME", "familyclaw"), safe="/")
    encoded_password = quote(password, safe="")
    print(f"postgresql+psycopg://{user}:{encoded_password}@{host}:{port}/{database_name}")
    raise SystemExit(0)

parts = urlsplit(database_url)
scheme = parts.scheme or "postgresql+psycopg"
username = parts.username or os.environ.get("FAMILYCLAW_DB_USER", "familyclaw")
hostname = parts.hostname or os.environ.get("FAMILYCLAW_DB_HOST", "127.0.0.1")
port = parts.port
path = parts.path or f"/{quote(os.environ.get('FAMILYCLAW_DB_NAME', 'familyclaw'), safe='')}"

userinfo = quote(username, safe="")
if password:
    userinfo = f"{userinfo}:{quote(password, safe='')}"

hostpart = hostname
if ":" in hostname and not hostname.startswith("["):
    hostpart = f"[{hostname}]"

netloc = f"{userinfo}@{hostpart}"
if port is not None:
    netloc = f"{netloc}:{port}"

print(urlunsplit((scheme, netloc, path, parts.query, parts.fragment)))
PY
}

generate_secret() {
  local token_bytes="${1:-32}"
  python - "${token_bytes}" <<'PY'
from __future__ import annotations

import secrets
import sys

token_bytes = int(sys.argv[1])
print(secrets.token_urlsafe(token_bytes))
PY
}

write_secret_file() {
  local secret_file="$1"
  local secret_value="$2"
  local secret_dir
  secret_dir="$(dirname "${secret_file}")"

  mkdir -p "${secret_dir}"
  chmod 700 "${secret_dir}"
  (
    umask 077
    printf '%s\n' "${secret_value}" > "${secret_file}"
  )
  chmod 600 "${secret_file}"
}

acquire_secret_lock() {
  local lock_dir="$1"
  local max_attempts="${2:-300}"
  local attempt=0
  local lock_parent

  lock_parent="$(dirname "${lock_dir}")"
  mkdir -p "${lock_parent}"

  while ! mkdir "${lock_dir}" 2>/dev/null; do
    attempt=$((attempt + 1))
    if [[ "${attempt}" -ge "${max_attempts}" ]]; then
      log "Timed out waiting for secret lock ${lock_dir}"
      return 1
    fi
    sleep 0.1
  done
}

release_secret_lock() {
  local lock_dir="$1"
  rmdir "${lock_dir}" 2>/dev/null || true
}

load_or_create_secret() {
  local var_name="$1"
  local secret_file="$2"
  local secret_label="$3"
  local token_bytes="${4:-32}"
  local current_value="${!var_name:-}"
  local lock_dir="${secret_file}.lock"

  # 首次启动时多个服务会并发 source 本脚本，这里必须串行化 secret 初始化。
  acquire_secret_lock "${lock_dir}"

  if [[ -n "${current_value}" ]]; then
    write_secret_file "${secret_file}" "${current_value}"
    log "Using ${secret_label} from environment and syncing it to ${secret_file}"
  elif [[ -s "${secret_file}" ]]; then
    current_value="$(tr -d '\r\n' < "${secret_file}")"
  else
    current_value="$(generate_secret "${token_bytes}")"
    write_secret_file "${secret_file}" "${current_value}"
    log "Generated and persisted ${secret_label} at ${secret_file}"
  fi

  release_secret_lock "${lock_dir}"

  printf -v "${var_name}" '%s' "${current_value}"
  export "${var_name}"
}

is_truthy() {
  case "${1,,}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

if [[ -z "${FAMILYCLAW_DB_PASSWORD:-}" && -n "${FAMILYCLAW_DATABASE_URL:-}" ]]; then
  parsed_db_password="$(read_password_from_database_url || true)"
  if [[ -n "${parsed_db_password}" ]]; then
    export FAMILYCLAW_DB_PASSWORD="${parsed_db_password}"
    log "Using database password parsed from FAMILYCLAW_DATABASE_URL"
  fi
fi

load_or_create_secret FAMILYCLAW_DB_PASSWORD "${FAMILYCLAW_DB_PASSWORD_FILE}" "database password" 24
load_or_create_secret FAMILYCLAW_VOICE_GATEWAY_TOKEN "${FAMILYCLAW_VOICE_GATEWAY_TOKEN_FILE}" "voice gateway token" 32

export FAMILYCLAW_DATABASE_URL="$(canonicalize_database_url)"
export FAMILYCLAW_PLUGIN_STORAGE_ROOT="${FAMILYCLAW_PLUGIN_STORAGE_ROOT:-${FAMILYCLAW_PLUGIN_DATA_DIR}}"
export FAMILYCLAW_PLUGIN_MARKETPLACE_INSTALL_ROOT="${FAMILYCLAW_PLUGIN_MARKETPLACE_INSTALL_ROOT:-${FAMILYCLAW_PLUGIN_DATA_DIR}}"
export FAMILYCLAW_VOICE_RUNTIME_ARTIFACTS_ROOT="${FAMILYCLAW_VOICE_RUNTIME_ARTIFACTS_ROOT:-${FAMILYCLAW_VOICE_ARTIFACTS_DIR}}"
export FAMILYCLAW_RELEASE_MANIFEST_PATH
export FAMILYCLAW_RUNTIME_DIR
export FAMILYCLAW_LOG_DIR
export FAMILYCLAW_ENVIRONMENT="${FAMILYCLAW_ENVIRONMENT:-production}"
export FAMILYCLAW_BUILD_CHANNEL="${FAMILYCLAW_BUILD_CHANNEL:-development}"
export FAMILYCLAW_OPEN_XIAOAI_GATEWAY_API_SERVER_HTTP_URL="${FAMILYCLAW_OPEN_XIAOAI_GATEWAY_API_SERVER_HTTP_URL:-http://127.0.0.1:${FAMILYCLAW_API_PORT}/api/v1}"
export FAMILYCLAW_OPEN_XIAOAI_GATEWAY_API_SERVER_WS_URL="${FAMILYCLAW_OPEN_XIAOAI_GATEWAY_API_SERVER_WS_URL:-ws://127.0.0.1:${FAMILYCLAW_API_PORT}/api/v1/realtime/voice}"
export FAMILYCLAW_OPEN_XIAOAI_GATEWAY_LISTEN_HOST="${FAMILYCLAW_OPEN_XIAOAI_GATEWAY_LISTEN_HOST:-0.0.0.0}"
export FAMILYCLAW_OPEN_XIAOAI_GATEWAY_LISTEN_PORT="${FAMILYCLAW_OPEN_XIAOAI_GATEWAY_LISTEN_PORT:-${FAMILYCLAW_GATEWAY_PORT}}"
export FAMILYCLAW_OPEN_XIAOAI_GATEWAY_VOICE_GATEWAY_TOKEN="${FAMILYCLAW_OPEN_XIAOAI_GATEWAY_VOICE_GATEWAY_TOKEN:-${FAMILYCLAW_VOICE_GATEWAY_TOKEN}}"
export PGPASSWORD="${PGPASSWORD:-${FAMILYCLAW_DB_PASSWORD}}"

ensure_runtime_layout() {
  mkdir -p \
    "${FAMILYCLAW_PGDATA}" \
    "${FAMILYCLAW_BACKUP_DIR}" \
    "${FAMILYCLAW_LOG_DIR}" \
    "${FAMILYCLAW_LOG_DIR}/api-server" \
    "${FAMILYCLAW_LOG_DIR}/gateway" \
    "${FAMILYCLAW_LOG_DIR}/postgres" \
    "${FAMILYCLAW_LOG_DIR}/nginx" \
    "${FAMILYCLAW_RUNTIME_DIR}" \
    "${FAMILYCLAW_SECRET_DIR}" \
    "${FAMILYCLAW_PLUGIN_DATA_DIR}" \
    "${FAMILYCLAW_VOICE_ARTIFACTS_DIR}" \
    /var/run/postgresql
  chmod 700 "${FAMILYCLAW_SECRET_DIR}"
  chown -R postgres:postgres "${FAMILYCLAW_PGDATA}" /var/run/postgresql
  chmod 700 "${FAMILYCLAW_PGDATA}"
}

setup_service_logging() {
  local service_name="$1"
  local service_log_dir="${FAMILYCLAW_LOG_DIR}/${service_name}"
  local service_log_file="${service_log_dir}/current.log"

  mkdir -p "${service_log_dir}"
  touch "${service_log_file}"

  exec > >(tee -a "${service_log_file}") 2>&1
}

wait_for_postgres() {
  local attempts="${1:-60}"
  local silent_until="${2:-60}"
  local i=0
  until pg_isready -h "${FAMILYCLAW_DB_HOST}" -p "${FAMILYCLAW_DB_PORT}" -U "${FAMILYCLAW_DB_USER}" -d "${FAMILYCLAW_DB_NAME}" >/dev/null 2>&1; do
    i=$((i + 1))
    if [[ "${i}" -ge "${attempts}" ]]; then
      log "PostgreSQL did not become ready in time"
      return 1
    fi
    if [[ "${i}" -ge "${silent_until}" ]] && [[ $((i % 5)) -eq 0 ]]; then
      log "Waiting for PostgreSQL... (${i}/${attempts})"
    fi
    sleep 1
  done
}

wait_for_api() {
  local attempts="${1:-120}"
  local silent_until="${2:-60}"
  local i=0
  until curl --fail --silent "http://127.0.0.1:${FAMILYCLAW_API_PORT}/api/v1/healthz" >/dev/null 2>&1; do
    i=$((i + 1))
    if [[ "${i}" -ge "${attempts}" ]]; then
      log "api-server did not become ready in time"
      return 1
    fi
    if [[ "${i}" -ge "${silent_until}" ]] && [[ $((i % 5)) -eq 0 ]]; then
      log "Waiting for api-server... (${i}/${attempts})"
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
