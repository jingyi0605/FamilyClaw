#!/usr/bin/env bash

set -euo pipefail

export FAMILYCLAW_LOG_PREFIX="postgres"
source /opt/familyclaw/docker/scripts/common.sh

initialize_database() {
  if [[ ! -s "${FAMILYCLAW_PGDATA}/PG_VERSION" ]]; then
    log "Initializing PostgreSQL cluster in ${FAMILYCLAW_PGDATA}"
    ensure_runtime_layout
    runuser -u postgres -- initdb -D "${FAMILYCLAW_PGDATA}" --username=postgres --auth-local=trust --auth-host=scram-sha-256
  fi

  runuser -u postgres -- pg_ctl -D "${FAMILYCLAW_PGDATA}" -w start -o "-c listen_addresses='' -k /var/run/postgresql -p ${FAMILYCLAW_DB_PORT}"

  # Sync the application role password with the persisted secret on every start.
  runuser -u postgres -- psql \
    --username postgres \
    --host /var/run/postgresql \
    --port "${FAMILYCLAW_DB_PORT}" \
    --set=ON_ERROR_STOP=1 \
    -c "DO \$\$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${FAMILYCLAW_DB_USER}') THEN
            CREATE ROLE \"${FAMILYCLAW_DB_USER}\" LOGIN PASSWORD '${FAMILYCLAW_DB_PASSWORD}';
          ELSE
            ALTER ROLE \"${FAMILYCLAW_DB_USER}\" LOGIN PASSWORD '${FAMILYCLAW_DB_PASSWORD}';
          END IF;
        END
        \$\$;"

  runuser -u postgres -- psql \
    --username postgres \
    --host /var/run/postgresql \
    --port "${FAMILYCLAW_DB_PORT}" \
    --set=ON_ERROR_STOP=1 \
    -c "SELECT 1 FROM pg_database WHERE datname = '${FAMILYCLAW_DB_NAME}'" | grep -q 1 || \
    runuser -u postgres -- createdb -O "${FAMILYCLAW_DB_USER}" "${FAMILYCLAW_DB_NAME}"

  runuser -u postgres -- pg_ctl -D "${FAMILYCLAW_PGDATA}" -m fast -w stop
}

main() {
  setup_service_logging "postgres"
  ensure_runtime_layout
  initialize_database
  log "Starting PostgreSQL on ${FAMILYCLAW_DB_HOST}:${FAMILYCLAW_DB_PORT}"
  exec runuser -u postgres -- postgres \
    -D "${FAMILYCLAW_PGDATA}" \
    -c "listen_addresses=${FAMILYCLAW_DB_HOST}" \
    -c "port=${FAMILYCLAW_DB_PORT}" \
    -c "unix_socket_directories=/var/run/postgresql"
}

main "$@"
