#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
API_DIR="${PROJECT_ROOT}/apps/api-server"
VENV_DIR="${API_DIR}/.venv"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
RELOAD_DIR="${RELOAD_DIR:-app}"
DEPS_HASH_FILE="${VENV_DIR}/.deps.sha256"
PYTHON_CMD=()
PYTHON_CMD_DESC=""
PYTHON_CANDIDATE_VERSION=""

# Windows 使用 Scripts 目录，Unix 使用 bin 目录。
if [[ "${OSTYPE}" == "msys" || "${OSTYPE}" == "win32" ]]; then
  VENV_BIN_DIR="Scripts"
else
  VENV_BIN_DIR="bin"
fi

log() {
  printf '[api-start] %s\n' "$1"
}

fail() {
  printf '[api-start] ERROR: %s\n' "$1" >&2
  exit 1
}

python_supports_project() {
  local candidate="$1"
  if ! command -v "${candidate}" >/dev/null 2>&1; then
    return 1
  fi

  "${candidate}" - <<'PY' >/dev/null 2>&1
import sys

major, minor = sys.version_info[:2]
raise SystemExit(0 if (major, minor) >= (3, 11) else 1)
PY
}

resolve_python_executable() {
  local candidate="$1"
  local resolved=""

  if ! resolved="$(command -v "${candidate}" 2>/dev/null)"; then
    return 1
  fi

  if [[ -L "${resolved}" ]]; then
    resolved="$(realpath "${resolved}")"
  fi

  if [[ -n "${resolved}" && -x "${resolved}" ]]; then
    printf '%s\n' "${resolved}"
    return 0
  fi

  return 1
}

select_python_candidate() {
  local candidate="$1"
  local desc="${2:-$1}"
  local resolved_candidate=""

  if ! python_supports_project "${candidate}"; then
    return 1
  fi

  if ! resolved_candidate="$(resolve_python_executable "${candidate}")"; then
    return 1
  fi

  PYTHON_CMD=("${resolved_candidate}")
  PYTHON_CMD_DESC="${desc} -> ${resolved_candidate}"
  PYTHON_CANDIDATE_VERSION="$("${resolved_candidate}" - <<'PY'
import sys

print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
  return 0
}

resolve_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
      fail "未找到 ${PYTHON_BIN}，请先安装 Python 3.11 及以上版本，或通过 PYTHON_BIN 指定可执行文件路径。"
    fi

    if select_python_candidate "${PYTHON_BIN}" "${PYTHON_BIN}"; then
      return
    fi

    fail "${PYTHON_BIN} 不是可用的 Python 3.11+ 解释器。"
  fi

  local preferred_paths=(
    "/opt/homebrew/opt/python@3.13/bin/python3.13"
    "/opt/homebrew/opt/python@3.12/bin/python3.12"
    "/opt/homebrew/opt/python@3.11/bin/python3.11"
  )

  local preferred_path=""
  for preferred_path in "${preferred_paths[@]}"; do
    if [[ -x "${preferred_path}" ]] && select_python_candidate "${preferred_path}" "${preferred_path}"; then
      return
    fi
  done

  local candidates=(
    "python3.13"
    "python3.12"
    "python3.11"
    "python3"
    "python"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    if select_python_candidate "${candidate}" "${candidate}"; then
      return
    fi
  done

  # Windows Git Bash 经常只有 py，没有 python/python3.11。
  if command -v py >/dev/null 2>&1; then
    local py_candidates=("-3.13" "-3.12" "-3.11")
    local py_candidate=""
    for py_candidate in "${py_candidates[@]}"; do
      if py "${py_candidate}" -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)" >/dev/null 2>&1; then
        PYTHON_CMD=("py" "${py_candidate}")
        PYTHON_CMD_DESC="py ${py_candidate}"
        PYTHON_CANDIDATE_VERSION="${py_candidate#-}"
        return
      fi
    done
  fi

  PYTHON_CMD=()
  PYTHON_CMD_DESC=""
  PYTHON_CANDIDATE_VERSION=""
}

run_python() {
  "${PYTHON_CMD[@]}" "$@"
}

ensure_python() {
  resolve_python
  if [[ ${#PYTHON_CMD[@]} -eq 0 ]]; then
    fail "未找到 Python 3.11 及以上解释器，请先安装，或通过 PYTHON_BIN 指定可执行文件路径。"
  fi

  log "使用 Python 解释器: ${PYTHON_CMD_DESC}"
}

ensure_venv() {
  if [[ ! -x "${VENV_DIR}/${VENV_BIN_DIR}/python" && ! -x "${VENV_DIR}/${VENV_BIN_DIR}/python.exe" ]]; then
    log "创建虚拟环境 ${VENV_DIR}"
    run_python -m venv "${VENV_DIR}"
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
  log "检测到新依赖或虚拟环境未初始化，开始安装依赖"
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
      log "数据库还没有迁移版本，开始执行迁移"
      ;;
    *)
      log "数据库当前版本 ${current_rev}，目标版本 ${head_rev}，开始执行迁移"
      ;;
  esac

  alembic upgrade head
}

voice_runtime_mode() {
  python - <<'PY'
from app.core.config import settings

print(settings.resolved_voice_runtime_mode)
PY
}

start_server() {
  local runtime_mode
  runtime_mode="$(voice_runtime_mode)"
  log "语音 runtime 模式: ${runtime_mode}"
  if [[ "${runtime_mode}" == "embedded" ]]; then
    log "当前为本地默认模式，只需要启动 api-server"
  else
    log "当前为禁用模式，语音 runtime 将按现有降级语义处理"
  fi
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
