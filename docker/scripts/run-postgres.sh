#!/usr/bin/env bash

set -euo pipefail

export FAMILYCLAW_LOG_PREFIX="postgres"
source /opt/familyclaw/docker/scripts/common.sh

initialize_database() {
  if [[ -s "${FAMILYCLAW_PGDATA}/PG_VERSION" ]]; then
    return 0
  fi

  log "Initializing PostgreSQL cluster in ${FAMILYCLAW_PGDATA}"
  ensure_runtime_layout

  runuser -u postgres -- initdb -D "${FAMILYCLAW_PGDATA}" --username=postgres --auth-local=trust --auth-host=scram-sha-256

  runuser -u postgres -- pg_ctl -D "${FAMILYCLAW_PGDATA}" -w start -o "-c listen_addresses='' -k /var/run/postgresql -p ${FAMILYCLAW_DB_PORT}"

  runuser -u postgres -- psql \
    --username postgres \
    --host /var/run/postgresql \
    --port "${FAMILYCLAW_DB_PORT}" \
    --set=ON_ERROR_STOP=1 \
    --set=db_user="${FAMILYCLAW_DB_USER}" \
    --set=db_password="${FAMILYCLAW_DB_PASSWORD}" \
    --set=db_name="${FAMILYCLAW_DB_NAME}" <<'SQL'
DO $do$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'db_user') THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password');
  ELSE
    EXECUTE format('ALTER ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password');
  END IF;
END
$do$;
SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name') \gexec
SQL

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
