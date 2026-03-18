#!/usr/bin/env bash

set -euo pipefail

source /opt/familyclaw/docker/scripts/common.sh

backup_database() {
  local reason="${1:-manual}"
  local timestamp
  local output_path

  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  output_path="${FAMILYCLAW_BACKUP_DIR}/familyclaw-${timestamp}-${reason}.sql.gz"

  mkdir -p "${FAMILYCLAW_BACKUP_DIR}"
  pg_dump \
    --host "${FAMILYCLAW_DB_HOST}" \
    --port "${FAMILYCLAW_DB_PORT}" \
    --username "${FAMILYCLAW_DB_USER}" \
    --dbname "${FAMILYCLAW_DB_NAME}" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges | gzip -c > "${output_path}"

  printf '%s\n' "${output_path}"
}

restore_database() {
  local archive_path="${1:-}"
  if [[ -z "${archive_path}" || ! -f "${archive_path}" ]]; then
    printf 'Usage: familyclawctl restore <backup.sql.gz>\n' >&2
    exit 1
  fi

  gzip -dc "${archive_path}" | psql \
    --host "${FAMILYCLAW_DB_HOST}" \
    --port "${FAMILYCLAW_DB_PORT}" \
    --username "${FAMILYCLAW_DB_USER}" \
    --dbname "${FAMILYCLAW_DB_NAME}"
}

print_version() {
  python - <<'PY'
from pathlib import Path
import json
import os

manifest_path = Path(os.environ["FAMILYCLAW_RELEASE_MANIFEST_PATH"])
if not manifest_path.exists():
    print("{}")
    raise SystemExit(0)

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
print(json.dumps(manifest, ensure_ascii=False, indent=2))
PY
}

doctor() {
  local failures=0

  if pg_isready -h "${FAMILYCLAW_DB_HOST}" -p "${FAMILYCLAW_DB_PORT}" -U "${FAMILYCLAW_DB_USER}" -d "${FAMILYCLAW_DB_NAME}" >/dev/null 2>&1; then
    printf 'postgres: ok\n'
  else
    printf 'postgres: failed\n'
    failures=$((failures + 1))
  fi

  if curl --fail --silent "http://127.0.0.1:${FAMILYCLAW_API_PORT}/api/v1/healthz" >/dev/null 2>&1; then
    printf 'api-server: ok\n'
  else
    printf 'api-server: failed\n'
    failures=$((failures + 1))
  fi

  if curl --fail --silent "http://127.0.0.1:${FAMILYCLAW_NGINX_PORT}/" >/dev/null 2>&1; then
    printf 'nginx: ok\n'
  else
    printf 'nginx: failed\n'
    failures=$((failures + 1))
  fi

  if is_truthy "${FAMILYCLAW_ENABLE_GATEWAY}"; then
    if python - <<'PY'
import os
import socket
import sys

sock = socket.socket()
sock.settimeout(2)
try:
    sock.connect(("127.0.0.1", int(os.environ["FAMILYCLAW_GATEWAY_PORT"])))
except OSError:
    sys.exit(1)
finally:
    sock.close()
PY
    then
      printf 'gateway: ok\n'
    else
      printf 'gateway: failed\n'
      failures=$((failures + 1))
    fi
  else
    printf 'gateway: disabled\n'
  fi

  return "${failures}"
}

main() {
  ensure_runtime_layout

  case "${1:-}" in
    backup)
      shift
      backup_database "${1:-manual}"
      ;;
    restore)
      shift
      restore_database "${1:-}"
      ;;
    doctor)
      doctor
      ;;
    version)
      print_version
      ;;
    *)
      cat <<'EOF' >&2
Usage: familyclawctl <command>

Commands:
  backup [reason]   Create a PostgreSQL backup under /data/backups
  restore <file>    Restore a .sql.gz backup into the current database
  doctor            Run container health probes
  version           Print release-manifest.json
EOF
      exit 1
      ;;
  esac
}

main "$@"
