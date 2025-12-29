#!/usr/bin/env bash
# run-frontend-integration.sh
# Purpose: Start the backend (optional), then run frontend unit tests + smoke integration checks.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FRONTEND_DIR="${REPO_ROOT}/tldw-frontend"

: "${TLDW_BACKEND_HOST:=127.0.0.1}"
: "${TLDW_BACKEND_PORT:=8000}"
: "${TLDW_API_URL:=http://${TLDW_BACKEND_HOST}:${TLDW_BACKEND_PORT}}"
: "${TLDW_API_VERSION:=v1}"
: "${TLDW_AUTH_MODE:=single_user}"
: "${TLDW_BACKEND_WAIT_SECS:=120}"

KEEP_BACKEND=0
SKIP_BACKEND=0
RUN_BACKEND_TESTS=1
USE_DOCKER=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --skip-backend     Do not start/stop the backend (assume already running)
  --keep-backend     Keep the backend running after tests complete
  --backend-tests    Run backend integration tests (default)
  --no-backend-tests Skip backend integration tests
  --backend-docker   Start backend via Docker Compose
  --backend-uvicorn  Start backend via uvicorn (default)
  -h, --help         Show this help

Environment overrides:
  TLDW_BACKEND_HOST  (default: 127.0.0.1)
  TLDW_BACKEND_PORT  (default: 8000)
  TLDW_API_URL       (default: http://HOST:PORT)
  TLDW_API_VERSION   (default: v1)
  TLDW_AUTH_MODE     (default: single_user)
  TLDW_X_API_KEY     (optional; used for smoke tests in single_user mode)
  TLDW_API_BEARER    (optional; used for smoke tests in multi_user mode)
  TLDW_BACKEND_WAIT_SECS   (default: 120)
  TLDW_DOCKER_COMPOSE       (optional; compose file override)
  TLDW_DOCKER_COMPOSE_DEV=1 (optional; include docker-compose.dev.yml)
  TLDW_DOCKER_BUILD=1       (optional; build images, default: 1)

Examples:
  $(basename "$0")
  TLDW_X_API_KEY=dev-key $(basename "$0")
  TLDW_AUTH_MODE=multi_user TLDW_API_BEARER=... $(basename "$0")
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-backend)
      SKIP_BACKEND=1
      shift
      ;;
    --keep-backend)
      KEEP_BACKEND=1
      shift
      ;;
    --backend-tests)
      RUN_BACKEND_TESTS=1
      shift
      ;;
    --no-backend-tests)
      RUN_BACKEND_TESTS=0
      shift
      ;;
    --backend-docker)
      USE_DOCKER=1
      shift
      ;;
    --backend-uvicorn)
      USE_DOCKER=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-${TLDW_API_URL}}"
export NEXT_PUBLIC_API_VERSION="${NEXT_PUBLIC_API_VERSION:-${TLDW_API_VERSION}}"
export NEXT_PUBLIC_API_BEARER="${NEXT_PUBLIC_API_BEARER:-${TLDW_API_BEARER:-}}"

AUTH_MODE="${AUTH_MODE:-${TLDW_AUTH_MODE}}"
export AUTH_MODE

if [[ "${AUTH_MODE}" == "single_user" ]]; then
  SINGLE_USER_API_KEY="${SINGLE_USER_API_KEY:-${TLDW_X_API_KEY:-${NEXT_PUBLIC_X_API_KEY:-}}}"
  if [[ -z "${SINGLE_USER_API_KEY}" || ${#SINGLE_USER_API_KEY} -lt 16 ]]; then
    GENERATED_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
    SINGLE_USER_API_KEY="${GENERATED_KEY}"
    echo "[i] Generated SINGLE_USER_API_KEY for this run (>=16 chars required)."
  fi
  export SINGLE_USER_API_KEY
  export NEXT_PUBLIC_X_API_KEY="${NEXT_PUBLIC_X_API_KEY:-${SINGLE_USER_API_KEY}}"
fi

if [[ "${AUTH_MODE}" == "multi_user" ]]; then
  JWT_SECRET_KEY="${JWT_SECRET_KEY:-${TLDW_JWT_SECRET_KEY:-}}"
  if [[ -z "${JWT_SECRET_KEY}" || ${#JWT_SECRET_KEY} -lt 32 ]]; then
    GENERATED_JWT=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
    JWT_SECRET_KEY="${GENERATED_JWT}"
    echo "[i] Generated JWT_SECRET_KEY for this run (>=32 chars required)."
  fi
  export JWT_SECRET_KEY
fi

BACKEND_PID=""
BACKEND_LOG="${REPO_ROOT}/tmp/frontend-backend.log"
BACKEND_CONTAINER="${BACKEND_CONTAINER:-tldw-app}"
DOCKER_STARTED=0
DCMD=""
COMPOSE_ARGS=()

resolve_docker_compose() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "docker compose"
    return 0
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
    return 0
  fi
  return 1
}

cleanup() {
  if [[ ${DOCKER_STARTED} -eq 1 && ${KEEP_BACKEND} -eq 0 ]]; then
    echo "[+] Stopping docker backend"
    "${DCMD[@]}" "${COMPOSE_ARGS[@]}" down -v || true
  fi
  if [[ -n "${BACKEND_PID}" && ${KEEP_BACKEND} -eq 0 ]]; then
    echo "[+] Stopping backend (pid=${BACKEND_PID})"
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

start_backend() {
  if [[ ${SKIP_BACKEND} -eq 1 ]]; then
    echo "[i] Skipping backend startup (--skip-backend)"
    return 0
  fi

  if [[ ${USE_DOCKER} -eq 1 ]]; then
    local compose_cmd
    if ! compose_cmd=$(resolve_docker_compose); then
      echo "ERROR: Docker and docker compose not found. Install Docker Desktop or docker-compose." >&2
      exit 1
    fi
    read -r -a DCMD <<< "${compose_cmd}"
    COMPOSE_ARGS=()
    if [[ -n "${TLDW_DOCKER_COMPOSE:-}" ]]; then
      COMPOSE_ARGS+=(-f "${TLDW_DOCKER_COMPOSE}")
    else
      COMPOSE_ARGS+=(-f "${REPO_ROOT}/Dockerfiles/docker-compose.yml")
    fi
    if [[ "${TLDW_DOCKER_COMPOSE_DEV:-0}" == "1" ]]; then
      if [[ -f "${REPO_ROOT}/Dockerfiles/docker-compose.dev.yml" ]]; then
        COMPOSE_ARGS+=(-f "${REPO_ROOT}/Dockerfiles/docker-compose.dev.yml")
      else
        echo "[i] docker-compose.dev.yml not found; skipping dev overlay."
      fi
    fi

    local build_args=("--build")
    if [[ "${TLDW_DOCKER_BUILD:-1}" == "0" ]]; then
      build_args=()
    fi

    echo "[+] Starting backend via Docker Compose"
    "${DCMD[@]}" "${COMPOSE_ARGS[@]}" up -d "${build_args[@]}"
    DOCKER_STARTED=1
    return 0
  fi

  mkdir -p "${REPO_ROOT}/tmp"
  echo "[+] Starting backend on ${TLDW_BACKEND_HOST}:${TLDW_BACKEND_PORT} (AUTH_MODE=${AUTH_MODE})"
  pushd "${REPO_ROOT}" >/dev/null
  python -m uvicorn tldw_Server_API.app.main:app \
    --host "${TLDW_BACKEND_HOST}" \
    --port "${TLDW_BACKEND_PORT}" \
    --log-level info \
    >"${BACKEND_LOG}" 2>&1 &
  popd >/dev/null
  BACKEND_PID=$!
}

wait_for_backend() {
  local ready_url="${NEXT_PUBLIC_API_URL}/ready"
  local url="${NEXT_PUBLIC_API_URL}/api/${NEXT_PUBLIC_API_VERSION}/llm/providers"
  local headers=()
  if [[ -n "${NEXT_PUBLIC_API_BEARER}" ]]; then
    headers+=( -H "Authorization: Bearer ${NEXT_PUBLIC_API_BEARER}" )
  fi
  if [[ -n "${NEXT_PUBLIC_X_API_KEY:-}" ]]; then
    headers+=( -H "X-API-KEY: ${NEXT_PUBLIC_X_API_KEY}" )
  fi

  echo "[+] Waiting for backend to be ready: ${ready_url}"
  for ((i=1; i<=TLDW_BACKEND_WAIT_SECS; i++)); do
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "${ready_url}" || true)
    if [[ "${code}" =~ ^2[0-9][0-9]$ ]]; then
      echo "[+] Backend responded with HTTP ${code}"
      return 0
    fi
    if [[ ${#headers[@]} -gt 0 ]]; then
      code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "${headers[@]}" "${url}" || true)
    else
      code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "${url}" || true)
    fi
    if [[ "${code}" =~ ^2[0-9][0-9]$ ]]; then
      echo "[+] Backend responded with HTTP ${code}"
      return 0
    fi
    sleep 1
  done

  if [[ ${USE_DOCKER} -eq 1 || ${BACKEND_DOCKER:-0} -eq 1 || ${TLDW_BACKEND_DOCKER:-0} -eq 1 ]]; then
    echo "ERROR: Backend did not respond in time. Check Docker container logs: docker logs ${BACKEND_CONTAINER}." >&2
  elif [[ -n "${BACKEND_LOG}" && -f "${BACKEND_LOG}" ]]; then
    echo "ERROR: Backend did not respond in time. Check ${BACKEND_LOG}." >&2
  else
    echo "ERROR: Backend did not respond in time. Check Docker logs or ${BACKEND_LOG}." >&2
  fi
  return 1
}

start_backend
wait_for_backend

if [[ ${RUN_BACKEND_TESTS} -eq 1 ]]; then
  echo "[+] Running backend integration tests"
  (cd "${REPO_ROOT}" && python -m pytest -m "integration" -v)
fi

echo "[+] Running frontend tests"
(cd "${FRONTEND_DIR}" && npm run test:run)

echo "[+] Running frontend smoke tests"
(cd "${FRONTEND_DIR}" && npm run smoke)

if [[ ${KEEP_BACKEND} -eq 1 ]]; then
  echo "[i] Keeping backend running as requested (--keep-backend)."
fi
