#!/usr/bin/env bash

set -euo pipefail

export FAMILYCLAW_LOG_PREFIX="api-server"
source /opt/familyclaw/docker/scripts/common.sh

current_revision() {
  python - <<'PY'
import os
from sqlalchemy import create_engine, inspect, text

engine = create_engine(os.environ["FAMILYCLAW_DATABASE_URL"], future=True)
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

config = Config("/opt/familyclaw/apps/api-server/alembic.ini")
script = ScriptDirectory.from_config(config)
print(",".join(script.get_heads()))
PY
}

run_migrations() {
  local current_rev
  local head_rev

  current_rev="$(current_revision)"
  head_rev="$(head_revision)"

  if [[ "${current_rev}" == "${head_rev}" ]]; then
    log "Schema already at head ${head_rev}"
    return 0
  fi

  if [[ "${current_rev}" != "unversioned" && "${current_rev}" != "empty" ]]; then
    log "Schema change detected (${current_rev} -> ${head_rev}), creating backup first"
    /opt/familyclaw/docker/scripts/familyclawctl.sh backup "pre-migrate-${current_rev}-to-${head_rev}"
  else
    log "Fresh database detected, skipping pre-migration backup"
  fi

  log "Running alembic upgrade head"
  (
    cd /opt/familyclaw/apps/api-server
    alembic upgrade head
  )
}

main() {
  setup_service_logging "api-server"
  ensure_runtime_layout
  wait_for_postgres
  run_migrations
  write_runtime_state
  log "Starting api-server on 0.0.0.0:${FAMILYCLAW_API_PORT}"
  cd /opt/familyclaw/apps/api-server
  exec uvicorn app.main:app --host 0.0.0.0 --port "${FAMILYCLAW_API_PORT}"
}

main "$@"
