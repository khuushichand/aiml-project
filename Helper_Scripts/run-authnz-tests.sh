#!/usr/bin/env bash
# run-authnz-tests.sh
# Purpose: Spin up a local PostgreSQL via Docker and run all AuthNZ tests.
# Keeps DB infra separate from the app for reliable, repeatable testing.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/tldw_Server_API/Dockerfiles/docker-compose.postgres.yml"

# Defaults aligned with tests
: "${TEST_DB_HOST:=localhost}"
: "${TEST_DB_PORT:=5432}"
: "${TEST_DB_USER:=tldw_user}"
: "${TEST_DB_PASSWORD:=TestPassword123!}"

KEEP_DB=0
PYTEST_ARGS=()

usage() {
  cat <<EOF
Usage: $(basename "$0") [--keep-db] [-- pytest-args...]

Options:
  --keep-db        Do not stop/remove the postgres container after tests
  --help           Show this help

Environment (overrides):
  TEST_DB_HOST           (default: localhost)
  TEST_DB_PORT           (default: 5432)
  TEST_DB_USER           (default: tldw_user)
  TEST_DB_PASSWORD       (default: TestPassword123!)
  POSTGRES_DB            (default: tldw_users in compose)

Examples:
  $(basename "$0")
  $(basename "$0") -m integration -k "AuthNZ"
  $(basename "$0") --keep-db -q
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep-db)
      KEEP_DB=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      PYTEST_ARGS+=("$@")
      break
      ;;
    *)
      PYTEST_ARGS+=("$1")
      shift
      ;;
  esac
done

# Resolve docker compose command (plugin or standalone)
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  DCMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DCMD=(docker-compose)
else
  echo "ERROR: Docker and docker compose not found. Install Docker Desktop or docker-compose." >&2
  exit 1
fi

echo "[+] Using compose file: ${COMPOSE_FILE}"

echo "[+] Starting PostgreSQL container..."
"${DCMD[@]}" -f "${COMPOSE_FILE}" up -d

echo "[+] Waiting for PostgreSQL to become healthy..."
CID=$("${DCMD[@]}" -f "${COMPOSE_FILE}" ps -q postgres)
if [[ -z "${CID}" ]]; then
  echo "ERROR: Could not find postgres container id." >&2
  exit 1
fi

# Wait on health status
for i in {1..30}; do
  STATUS=$(docker inspect -f '{{.State.Health.Status}}' "${CID}" 2>/dev/null || echo "unknown")
  if [[ "${STATUS}" == "healthy" ]]; then
    echo "[+] Postgres is healthy."
    break
  fi
  if [[ "$i" -eq 30 ]]; then
    echo "ERROR: Postgres did not become healthy in time (status=${STATUS})." >&2
    docker logs "${CID}" || true
    exit 1
  fi
  sleep 2
done

# Create common test DB used by some tests (others create per-test DBs)
echo "[+] Ensuring database tldw_test exists..."
docker exec -i "${CID}" bash -lc "psql -U ${TEST_DB_USER} -d postgres -tc \"SELECT 1 FROM pg_database WHERE datname='tldw_test'\" | grep -q 1 || createdb -U ${TEST_DB_USER} tldw_test"

# Export env used by tests and app
export TEST_DB_HOST
export TEST_DB_PORT
export TEST_DB_USER
export TEST_DB_PASSWORD
export DATABASE_URL="postgresql://${TEST_DB_USER}:${TEST_DB_PASSWORD}@${TEST_DB_HOST}:${TEST_DB_PORT}/${POSTGRES_DB:-tldw_users}"
export TEST_DATABASE_URL="postgresql://${TEST_DB_USER}:${TEST_DB_PASSWORD}@${TEST_DB_HOST}:${TEST_DB_PORT}/tldw_test"

echo "[+] Environment configured:"
echo "    DATABASE_URL=${DATABASE_URL}"
echo "    TEST_DATABASE_URL=${TEST_DATABASE_URL}"

cd "${REPO_ROOT}"

echo "[+] Running AuthNZ tests..."
# Run the full AuthNZ suite and backend tests explicitly
python -m pytest -v \
  tldw_Server_API/tests/AuthNZ \
  tldw_Server_API/tests/test_authnz_backends.py \
  tldw_Server_API/tests/test_authnz_backends_improved.py \
  "${PYTEST_ARGS[@]}"

EXIT_CODE=$?

if [[ ${KEEP_DB} -eq 0 ]]; then
  echo "[+] Stopping PostgreSQL container..."
  "${DCMD[@]}" -f "${COMPOSE_FILE}" down -v
else
  echo "[i] Keeping PostgreSQL container running as requested (--keep-db)."
fi

exit ${EXIT_CODE}
