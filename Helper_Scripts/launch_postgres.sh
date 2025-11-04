#!/usr/bin/env bash
set -euo pipefail

# Simple launcher/provisioner for a local Postgres instance via Docker.
# - Reuses an existing container if present; starts it if stopped; creates it if missing.
# - Waits for readiness and ensures the expected databases exist.
# - Prints convenient DSNs to export for the app/tests.
#
# Defaults can be overridden via env vars:
#   PG_CONTAINER   (default: tldw_postgres_dev)
#   PG_IMAGE       (default: postgres:18)
#   PG_PORT        (default: 55432)
#   PG_USER        (default: tldw)
#   PG_PASSWORD    (default: tldw)
#   PG_DB_PRIMARY  (default: tldw_content)  # Jobs/outbox default
#   PG_DB_AUTHNZ   (default: tldw_users)    # AuthNZ default
#
# Example:
#   PG_PORT=55432 PG_USER=tldw PG_PASSWORD=tldw ./Helper_Scripts/launch_postgres.sh

PG_CONTAINER=${PG_CONTAINER:-tldw_postgres_dev}
PG_IMAGE=${PG_IMAGE:-postgres:18}
PG_PORT=${PG_PORT:-55432}
PG_USER=${PG_USER:-tldw}
PG_PASSWORD=${PG_PASSWORD:-tldw}
PG_DB_PRIMARY=${PG_DB_PRIMARY:-tldw_content}
PG_DB_AUTHNZ=${PG_DB_AUTHNZ:-tldw_users}

command -v docker >/dev/null 2>&1 || {
  echo "Error: docker is required but not found in PATH" >&2
  exit 1
}

container_exists() {
  docker ps -a --format '{{.Names}}' | grep -qx "${PG_CONTAINER}"
}

container_running() {
  docker ps --format '{{.Names}}' | grep -qx "${PG_CONTAINER}"
}

start_container() {
  if container_exists; then
    if container_running; then
      echo "Postgres container '${PG_CONTAINER}' already running on port ${PG_PORT}."
      return 0
    fi
    echo "Starting existing Postgres container '${PG_CONTAINER}'..."
    docker start "${PG_CONTAINER}" >/dev/null
  else
    echo "Creating Postgres container '${PG_CONTAINER}' (image=${PG_IMAGE}) on port ${PG_PORT}..."
    docker run -d --name "${PG_CONTAINER}" \
      -e POSTGRES_USER="${PG_USER}" \
      -e POSTGRES_PASSWORD="${PG_PASSWORD}" \
      -e POSTGRES_DB="${PG_DB_PRIMARY}" \
      -p "${PG_PORT}:5432" \
      "${PG_IMAGE}" >/dev/null
  fi
}

wait_for_ready() {
  echo "Waiting for Postgres to become ready..."
  for i in {1..60}; do
    if docker exec "${PG_CONTAINER}" pg_isready -U "${PG_USER}" >/dev/null 2>&1; then
      echo "Postgres is ready."
      return 0
    fi
    sleep 1
  done
  echo "Error: Postgres did not become ready in time" >&2
  exit 1
}

ensure_database() {
  local db_name="$1"
  # Check if DB exists; if not, create it as the current user (owner will be PG_USER)
  if docker exec -e PGPASSWORD="${PG_PASSWORD}" "${PG_CONTAINER}" \
      psql -U "${PG_USER}" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${db_name}'" | grep -q 1; then
    echo "Database '${db_name}' already exists."
  else
    echo "Creating database '${db_name}'..."
    docker exec -e PGPASSWORD="${PG_PASSWORD}" "${PG_CONTAINER}" \
      psql -U "${PG_USER}" -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"${db_name}\";" >/dev/null
    echo "Database '${db_name}' created."
  fi
}

print_dsn_help() {
  local host="127.0.0.1"
  local jobs_dsn="postgresql://${PG_USER}:${PG_PASSWORD}@${host}:${PG_PORT}/${PG_DB_PRIMARY}"
  local authnz_dsn="postgresql://${PG_USER}:${PG_PASSWORD}@${host}:${PG_PORT}/${PG_DB_AUTHNZ}"
  cat <<EOF

Ready.

Suggested environment exports:
  export JOBS_DB_URL=${jobs_dsn}
  export DATABASE_URL=${authnz_dsn}

Quick checks:
  docker logs -f ${PG_CONTAINER}
  docker exec -it ${PG_CONTAINER} psql -U ${PG_USER} -d ${PG_DB_PRIMARY} -c 'SELECT now();'

To stop/remove:
  docker stop ${PG_CONTAINER}
  docker rm ${PG_CONTAINER}
EOF
}

# ---- main ----
start_container
wait_for_ready
# Ensure both primary (jobs/outbox) and AuthNZ databases exist
ensure_database "${PG_DB_PRIMARY}"
ensure_database "${PG_DB_AUTHNZ}"
print_dsn_help
