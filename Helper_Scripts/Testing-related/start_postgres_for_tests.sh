#!/usr/bin/env bash
set -euo pipefail

# Start a local PostgreSQL container for running integration tests.
# Default credentials match the test fixtures.

PG_USER=${PG_USER:-tldw_user}
PG_PASSWORD=${PG_PASSWORD:-TestPassword123!}
PG_DB=${PG_DB:-tldw_test}
PG_PORT=${PG_PORT:-5432}
CONTAINER_NAME=${CONTAINER_NAME:-tldw_postgres_test}

echo "Starting Postgres container '${CONTAINER_NAME}' on port ${PG_PORT}..."
docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
docker run -d --name "${CONTAINER_NAME}" \
  -e POSTGRES_USER="${PG_USER}" \
  -e POSTGRES_PASSWORD="${PG_PASSWORD}" \
  -e POSTGRES_DB="${PG_DB}" \
  -p "${PG_PORT}:5432" \
  postgres:18

echo "Waiting for Postgres to become ready..."
for i in {1..30}; do
  if docker exec "${CONTAINER_NAME}" pg_isready -U "${PG_USER}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "Postgres ready. Example env to run tests:"
echo "  export TEST_DATABASE_URL=postgresql://${PG_USER}:${PG_PASSWORD}@localhost:${PG_PORT}/${PG_DB}"
echo "  python -m pytest -m 'integration' -v"
