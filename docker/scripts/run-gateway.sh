#!/usr/bin/env bash

set -euo pipefail

source /opt/familyclaw/docker/scripts/common.sh

main() {
  if ! is_truthy "${FAMILYCLAW_ENABLE_GATEWAY}"; then
    log "Gateway disabled by FAMILYCLAW_ENABLE_GATEWAY=${FAMILYCLAW_ENABLE_GATEWAY}"
    exit 0
  fi

  wait_for_api
  log "Starting open-xiaoai-gateway on 0.0.0.0:${FAMILYCLAW_GATEWAY_PORT}"
  cd /opt/familyclaw/apps/open-xiaoai-gateway
  exec python -m open_xiaoai_gateway.main
}

main "$@"
