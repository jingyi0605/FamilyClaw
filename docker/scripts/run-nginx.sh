#!/usr/bin/env bash

set -euo pipefail

source /opt/familyclaw/docker/scripts/common.sh

main() {
  wait_for_api
  log "Starting nginx on 0.0.0.0:${FAMILYCLAW_NGINX_PORT}"
  exec nginx -g 'daemon off;'
}

main "$@"
