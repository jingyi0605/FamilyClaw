#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
API_DIR="${PROJECT_ROOT}/apps/api-server"
VENV_DIR="${API_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
DEPS_HASH_FILE="${VENV_DIR}/.deps.sha256"

log() {
  printf '[api-seed] %s\n' "$1"
}

fail() {
  printf '[api-seed] ERROR: %s\n' "$1" >&2
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

ensure_database() {
  log "执行数据库迁移到最新版本"
  alembic upgrade head
}

seed_database() {
  log "写入演示与联调用模拟数据"
  python -m app.seed
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
  seed_database
}

main "$@"
