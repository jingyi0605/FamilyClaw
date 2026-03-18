#!/usr/bin/env bash

set -euo pipefail

export FAMILYCLAW_LOG_PREFIX="nginx"
source /opt/familyclaw/docker/scripts/common.sh

main() {
  setup_service_logging "nginx"
  wait_for_api
  log "Starting nginx on 0.0.0.0:${FAMILYCLAW_NGINX_PORT}"
  exec nginx -g 'daemon off;'
}

main "$@"
