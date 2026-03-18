#!/usr/bin/env bash

set -euo pipefail

source /opt/familyclaw/docker/scripts/common.sh

pg_isready -h "${FAMILYCLAW_DB_HOST}" -p "${FAMILYCLAW_DB_PORT}" -U "${FAMILYCLAW_DB_USER}" -d "${FAMILYCLAW_DB_NAME}" >/dev/null
curl --fail --silent --show-error "http://127.0.0.1:${FAMILYCLAW_API_PORT}/api/v1/healthz" >/dev/null
curl --fail --silent --show-error "http://127.0.0.1:${FAMILYCLAW_NGINX_PORT}/" >/dev/null

if is_truthy "${FAMILYCLAW_ENABLE_GATEWAY}"; then
  python - <<'PY'
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
fi
