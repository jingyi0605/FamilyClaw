#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
GATEWAY_DIR="${PROJECT_ROOT}/apps/open-xiaoai-gateway"
VENV_DIR="${GATEWAY_DIR}/.venv"
ENV_FILE="${GATEWAY_DIR}/.env"
DEPS_HASH_FILE="${VENV_DIR}/.deps.sha256"
DRY_RUN="${DRY_RUN:-0}"
PYTHON_CMD=()
PYTHON_CMD_DESC=""

# Windows 使用 Scripts 目录，Unix 使用 bin 目录。
if [[ "${OSTYPE}" == "msys" || "${OSTYPE}" == "win32" ]]; then
  VENV_BIN_DIR="Scripts"
else
  VENV_BIN_DIR="bin"
fi

log() {
  printf '[gateway-start] %s\n' "$1"
}

fail() {
  printf '[gateway-start] ERROR: %s\n' "$1" >&2
  exit 1
}

resolve_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
      fail "未找到 ${PYTHON_BIN}，请先安装 Python 3.11，或通过 PYTHON_BIN 指定可执行文件路径。"
    fi

    PYTHON_CMD=("${PYTHON_BIN}")
    PYTHON_CMD_DESC="${PYTHON_BIN}"
    return
  fi

  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_CMD=("python3.11")
    PYTHON_CMD_DESC="python3.11"
    return
  fi

  if command -v python >/dev/null 2>&1; then
    PYTHON_CMD=("python")
    PYTHON_CMD_DESC="python"
    return
  fi

  # Windows Git Bash 经常只有 py，没有 python/python3.11。
  if command -v py >/dev/null 2>&1; then
    if py -3.11 -c "import sys" >/dev/null 2>&1; then
      PYTHON_CMD=("py" "-3.11")
      PYTHON_CMD_DESC="py -3.11"
      return
    fi

    PYTHON_CMD=("py")
    PYTHON_CMD_DESC="py"
    return
  fi

  PYTHON_CMD=()
  PYTHON_CMD_DESC=""
}

run_python() {
  "${PYTHON_CMD[@]}" "$@"
}

ensure_python() {
  resolve_python
  if [[ ${#PYTHON_CMD[@]} -eq 0 ]]; then
    fail "未找到 Python 解释器，请先安装 Python 3.11，或通过 PYTHON_BIN 指定可执行文件路径。"
  fi

  log "使用 Python 解释器: ${PYTHON_CMD_DESC}"
}

ensure_env_file() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    fail "未找到 ${ENV_FILE}。先把网关参数补齐，再启动。"
  fi
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

  if ! python -c "import open_xiaoai_gateway" >/dev/null 2>&1; then
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

validate_settings() {
  python - <<'PY'
from open_xiaoai_gateway.settings import settings

print(f"listen={settings.listen_host}:{settings.listen_port}")
print(f"api_server_http_url={settings.api_server_http_url}")
print(f"api_server_ws_url={settings.api_server_ws_url}")
print(f"invocation_mode={settings.invocation_mode}")
print(f"log_level={settings.log_level}")
PY
}

start_gateway() {
  log "启动 open-xiaoai-gateway"
  exec python -m open_xiaoai_gateway.main
}

main() {
  ensure_python
  ensure_env_file
  ensure_venv
  activate_venv
  cd "${GATEWAY_DIR}"

  local dep_hash=""
  if dep_hash="$(dependencies_need_install)"; then
    install_dependencies "${dep_hash}"
  else
    log "依赖未变化，复用现有虚拟环境"
  fi

  log "校验网关配置"
  validate_settings

  if [[ "${DRY_RUN}" == "1" ]]; then
    log "DRY_RUN=1，仅完成初始化与配置校验，不启动网关"
    return 0
  fi

  start_gateway
}

main "$@"
