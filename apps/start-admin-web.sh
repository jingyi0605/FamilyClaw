#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WEB_DIR="${PROJECT_ROOT}/apps/admin-web"
HASH_FILE="${WEB_DIR}/node_modules/.deps.sha256"
PORT="${PORT:-5173}"
HOST="${HOST:-0.0.0.0}"

log() {
  printf '[admin-web] %s\n' "$1"
}

ensure_node() {
  command -v node >/dev/null 2>&1 || {
    printf '[admin-web] ERROR: node 未安装\n' >&2
    exit 1
  }
  command -v npm >/dev/null 2>&1 || {
    printf '[admin-web] ERROR: npm 未安装\n' >&2
    exit 1
  }
}

current_hash() {
  python3.11 - <<'PY'
from pathlib import Path
import hashlib

content = Path("package.json").read_bytes()
print(hashlib.sha256(content).hexdigest())
PY
}

ensure_dependencies() {
  local next_hash
  next_hash="$(current_hash)"
  if [[ ! -d node_modules ]] || [[ ! -f "${HASH_FILE}" ]] || [[ "$(<"${HASH_FILE}")" != "${next_hash}" ]]; then
    log "安装前端依赖"
    npm install
    mkdir -p "$(dirname "${HASH_FILE}")"
    printf '%s' "${next_hash}" > "${HASH_FILE}"
  else
    log "依赖未变化，复用 node_modules"
  fi
}

main() {
  ensure_node
  cd "${WEB_DIR}"
  ensure_dependencies
  log "启动管理台 http://${HOST}:${PORT}"
  exec npm run dev -- --host "${HOST}" --port "${PORT}"
}

main "$@"
