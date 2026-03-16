#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
API_DIR="${PROJECT_ROOT}/apps/api-server"
VENV_DIR="${API_DIR}/.venv"
# Windows 使用 Scripts 目录，Unix 使用 bin 目录
if [[ "${OSTYPE}" == "msys" || "${OSTYPE}" == "win32" ]]; then
  VENV_BIN_DIR="Scripts"
else
  VENV_BIN_DIR="bin"
fi
# 默认使用 python3.11，若不存在则回退到 python（兼容 Windows）
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="python3.11"
  else
    PYTHON_BIN="python"
  fi
fi
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
  if [[ ! -x "${VENV_DIR}/${VENV_BIN_DIR}/python" && ! -x "${VENV_DIR}/${VENV_BIN_DIR}/python.exe" ]]; then
    log "创建虚拟环境 ${VENV_DIR}"
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  fi
}

activate_venv() {
  # shellcheck disable=SC1091
  source "${VENV_DIR}/${VENV_BIN_DIR}/activate"
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

current_revision() {
  python - <<'PY'
import os
from sqlalchemy import create_engine, inspect, text

database_url = os.getenv("FAMILYCLAW_DATABASE_URL")
if not database_url:
    from app.core.config import settings
    database_url = settings.database_url

engine = create_engine(database_url, future=True)
try:
    with engine.connect() as conn:
        inspector = inspect(conn)
        if "alembic_version" not in inspector.get_table_names():
            print("unversioned")
        else:
            version = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
            print(version or "empty")
finally:
    engine.dispose()
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
  local db_file
  local current_rev
  local head_rev

  head_rev="$(head_revision)"
  current_rev="$(current_revision)"
  db_file="${FAMILYCLAW_DATABASE_URL:-postgresql-configured}"

  log "数据库连接: ${db_file}"

  if [[ "${current_rev}" == "${head_rev}" ]]; then
    log "数据库已是最新迁移版本 ${head_rev}"
    return
  fi

  case "${current_rev}" in
    unversioned|empty)
      log "数据库未初始化迁移版本，执行迁移"
      ;;
    *)
      log "数据库当前版本 ${current_rev}，目标版本 ${head_rev}，执行迁移"
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
