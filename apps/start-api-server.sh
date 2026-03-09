#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
API_DIR="${PROJECT_ROOT}/apps/api-server"
VENV_DIR="${API_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
RELOAD_DIR="${RELOAD_DIR:-app}"
DEPS_HASH_FILE="${VENV_DIR}/.deps.sha256"

log() {
  printf '[api-start] %s\n' "$1"
}

fail() {
  printf '[api-start] ERROR: %s\n' "$1" >&2
  exit 1
}

ensure_python() {
  if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    fail "未找到 ${PYTHON_BIN}，请先安装 Python 3.11，或通过 PYTHON_BIN 指定解释器。"
  fi
}

ensure_venv() {
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    log "创建虚拟环境 ${VENV_DIR}"
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  fi
}

activate_venv() {
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
}

current_dep_hash() {
  python - <<'PY'
from pathlib import Path
import hashlib

content = Path("pyproject.toml").read_bytes()
print(hashlib.sha256(content).hexdigest())
PY
}

dependencies_need_install() {
  local current_hash
  current_hash="$(current_dep_hash)"

  if [[ ! -f "${DEPS_HASH_FILE}" ]]; then
    echo "${current_hash}"
    return 0
  fi

  if [[ "$(<"${DEPS_HASH_FILE}")" != "${current_hash}" ]]; then
    echo "${current_hash}"
    return 0
  fi

  if ! python -c "import fastapi, uvicorn, sqlalchemy, alembic" >/dev/null 2>&1; then
    echo "${current_hash}"
    return 0
  fi

  return 1
}

install_dependencies() {
  local current_hash="$1"
  log "检测到新依赖或环境未初始化，正在安装依赖"
  python -m pip install --upgrade pip
  python -m pip install -e .
  printf '%s' "${current_hash}" > "${DEPS_HASH_FILE}"
}

database_file_path() {
  python - <<'PY'
import os
from pathlib import Path
from sqlalchemy.engine import make_url

database_url = os.getenv("FAMILYCLAW_DATABASE_URL")
if not database_url:
    from app.core.config import settings
    database_url = settings.database_url

url = make_url(database_url)
if url.get_backend_name() == "sqlite" and url.database:
    print(Path(url.database).resolve())
PY
}

database_status() {
  python - <<'PY'
import os
import sqlite3
from pathlib import Path
from sqlalchemy.engine import make_url

database_url = os.getenv("FAMILYCLAW_DATABASE_URL")
if not database_url:
    from app.core.config import settings
    database_url = settings.database_url

url = make_url(database_url)
if url.get_backend_name() != "sqlite" or not url.database:
    print("non-sqlite")
    raise SystemExit(0)

db_path = Path(url.database)
if not db_path.exists():
    print("missing")
    raise SystemExit(0)

conn = sqlite3.connect(db_path)
try:
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "alembic_version" not in tables:
        print("unversioned")
        raise SystemExit(0)

    version = conn.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
    print(version[0] if version else "empty")
finally:
    conn.close()
PY
}

head_revision() {
  python - <<'PY'
from alembic.config import Config
from alembic.script import ScriptDirectory

config = Config("alembic.ini")
script = ScriptDirectory.from_config(config)
print(",".join(script.get_heads()))
PY
}

ensure_database() {
  local db_status
  local db_file
  local head_rev

  head_rev="$(head_revision)"
  db_status="$(database_status)"
  db_file="$(database_file_path || true)"

  if [[ -n "${db_file}" ]]; then
    log "SQLite 数据库: ${db_file}"
  else
    log "数据库类型不是 SQLite，按 Alembic 状态检查"
  fi

  if [[ "${db_status}" == "${head_rev}" ]]; then
    log "数据库已是最新迁移版本 ${head_rev}"
    return
  fi

  case "${db_status}" in
    missing)
      log "数据库文件不存在，执行初始化迁移"
      ;;
    unversioned|empty)
      log "数据库未初始化迁移版本，执行迁移"
      ;;
    non-sqlite)
      log "检测 Alembic 头版本 ${head_rev}，执行迁移校准"
      ;;
    *)
      log "数据库当前版本 ${db_status}，目标版本 ${head_rev}，执行迁移"
      ;;
  esac

  alembic upgrade head
}

start_server() {
  log "启动开发服务器 http://${HOST}:${PORT}，开启热重载"
  exec uvicorn app.main:app --host "${HOST}" --port "${PORT}" --reload --reload-dir "${RELOAD_DIR}" "$@"
}

main() {
  ensure_python
  ensure_venv
  activate_venv
  cd "${API_DIR}"

  local dep_hash=""
  if dep_hash="$(dependencies_need_install)"; then
    install_dependencies "${dep_hash}"
  else
    log "依赖未变化，复用现有虚拟环境"
  fi

  ensure_database
  start_server "$@"
}

main "$@"
