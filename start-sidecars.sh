#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

if [[ -n "${TLDW_ENV_FILE:-}" && -f "${TLDW_ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "${TLDW_ENV_FILE}"
  set +a
fi

PYTHON_BIN="${PYTHON_BIN:-python}"
UVICORN_HOST="${UVICORN_HOST:-127.0.0.1}"
UVICORN_PORT="${UVICORN_PORT:-8000}"
UVICORN_WORKERS="${UVICORN_WORKERS:-1}"
UVICORN_RELOAD="${UVICORN_RELOAD:-false}"
UVICORN_EXTRA_ARGS="${UVICORN_EXTRA_ARGS:-}"
SIDECAR_PROFILE="${TLDW_SIDECAR_PROFILE:-full}"
SIDECAR_DRY_RUN="${TLDW_SIDECAR_DRY_RUN:-false}"
WAIT_FOR_SERVER_HEALTH="${TLDW_WAIT_FOR_SERVER_HEALTH:-true}"
SERVER_HEALTH_URL="${TLDW_SERVER_HEALTH_URL:-http://${UVICORN_HOST}:${UVICORN_PORT}/healthz}"
SERVER_HEALTH_RETRIES="${TLDW_SERVER_HEALTH_RETRIES:-60}"
SERVER_HEALTH_INTERVAL="${TLDW_SERVER_HEALTH_INTERVAL:-1}"

LOG_DIR="${TLDW_LOG_DIR:-${ROOT_DIR}/.logs/sidecars}"
mkdir -p "${LOG_DIR}"

export TLDW_WORKERS_SIDECAR_MODE="${TLDW_WORKERS_SIDECAR_MODE:-true}"

MANIFEST_PATH="${TLDW_WORKERS_MANIFEST:-${ROOT_DIR}/Docs/Deployment/sidecar_workers_manifest.json}"
if [[ ! -f "${MANIFEST_PATH}" ]]; then
  printf 'Manifest not found: %s\n' "${MANIFEST_PATH}" >&2
  exit 1
fi
MANIFEST_OUTPUT="$("${PYTHON_BIN}" - "${MANIFEST_PATH}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text())
default_workers = data.get("default_workers", [])
workers = data.get("workers", [])

print("DEFAULT_WORKERS=" + ",".join(default_workers))
for worker in workers:
    key = worker.get("key", "")
    slug = worker.get("slug", "")
    module = worker.get("module", "")
    print(f"{key}|{slug}|{module}")
PY
)"

DEFAULT_WORKERS=""
WORKER_KEYS=()
WORKER_SLUGS=()
WORKER_MODULES=()

while IFS= read -r line; do
  if [[ -z "${DEFAULT_WORKERS}" ]]; then
    DEFAULT_WORKERS="${line#DEFAULT_WORKERS=}"
    continue
  fi
  IFS='|' read -r key slug module <<< "${line}"
  if [[ -n "${key}" && -n "${module}" ]]; then
    WORKER_KEYS+=( "${key}" )
    WORKER_SLUGS+=( "${slug}" )
    WORKER_MODULES+=( "${module}" )
  fi
done <<< "${MANIFEST_OUTPUT}"

WORKERS_CSV="$("${PYTHON_BIN}" - "${SIDECAR_PROFILE}" "${TLDW_SIDECAR_WORKERS:-}" "${DEFAULT_WORKERS}" <<'PY'
import sys

from Helper_Scripts.common.sidecar_profiles import resolve_workers

profile, explicit_workers_csv, default_workers_csv = sys.argv[1], sys.argv[2], sys.argv[3]
workers = resolve_workers(
    profile=profile,
    explicit_workers_csv=explicit_workers_csv or None,
    default_workers_csv=default_workers_csv,
)
print(",".join(workers))
PY
)"

declare -a PIDS=()
declare -a NAMES=()

start_proc() {
  local name="$1"
  shift
  local log="${LOG_DIR}/${name}.log"
  "$@" >"${log}" 2>&1 &
  local pid=$!
  PIDS+=("${pid}")
  NAMES+=("${name}")
  printf 'Started %s (pid=%s, log=%s)\n' "${name}" "${pid}" "${log}"
}

stop_all() {
  printf '\nStopping sidecar stack...\n'
  for pid in "${PIDS[@]-}"; do
    kill "${pid}" 2>/dev/null || true
  done
  wait || true
}

wait_for_server_health() {
  if [[ "${WAIT_FOR_SERVER_HEALTH}" != "true" ]]; then
    return 0
  fi
  if ! command -v curl >/dev/null 2>&1; then
    printf 'curl not available; skipping server health wait.\n'
    return 0
  fi

  local attempt=1
  while [[ "${attempt}" -le "${SERVER_HEALTH_RETRIES}" ]]; do
    if curl -fsS "${SERVER_HEALTH_URL}" >/dev/null 2>&1; then
      printf 'Server healthy at %s\n' "${SERVER_HEALTH_URL}"
      return 0
    fi
    sleep "${SERVER_HEALTH_INTERVAL}"
    attempt=$((attempt + 1))
  done
  return 1
}

trap stop_all INT TERM EXIT

server_cmd=( "${PYTHON_BIN}" -m uvicorn tldw_Server_API.app.main:app --host "${UVICORN_HOST}" --port "${UVICORN_PORT}" )
if [[ -n "${UVICORN_WORKERS}" && "${UVICORN_WORKERS}" != "0" ]]; then
  server_cmd+=( --workers "${UVICORN_WORKERS}" )
fi
if [[ "${UVICORN_RELOAD}" == "true" ]]; then
  server_cmd+=( --reload )
fi
if [[ -n "${UVICORN_EXTRA_ARGS}" ]]; then
  # shellcheck disable=SC2206
  # Note: arguments containing spaces are not supported; split into separate args.
  extra_args=( ${UVICORN_EXTRA_ARGS} )
  server_cmd+=( "${extra_args[@]}" )
fi

IFS=',' read -r -a WORKER_LIST <<< "${WORKERS_CSV}"

if [[ "${SIDECAR_DRY_RUN}" == "true" ]]; then
  printf 'Dry run enabled. Profile=%s selected_workers=%s\n' "${SIDECAR_PROFILE}" "${WORKERS_CSV}"
  printf 'Server command: %s\n' "${server_cmd[*]}"
  for worker in "${WORKER_LIST[@]}"; do
    [[ -z "${worker}" ]] && continue
    printf 'Worker key: %s\n' "${worker}"
  done
  exit 0
fi

start_proc "server" "${server_cmd[@]}"
SERVER_PID="${PIDS[$(( ${#PIDS[@]} - 1 ))]}"

if ! wait_for_server_health; then
  printf 'Server failed health check at %s\n' "${SERVER_HEALTH_URL}" >&2
  exit 1
fi

for worker in "${WORKER_LIST[@]}"; do
  if [[ -z "${worker}" ]]; then
    continue
  fi
  module=""
  slug=""
  for i in "${!WORKER_KEYS[@]}"; do
    if [[ "${WORKER_KEYS[$i]}" == "${worker}" ]]; then
      module="${WORKER_MODULES[$i]}"
      slug="${WORKER_SLUGS[$i]}"
      break
    fi
  done
  if [[ -z "${module}" ]]; then
    printf 'Unknown worker: %s (skipping)\n' "${worker}"
    continue
  fi
  if [[ -z "${slug}" ]]; then
    slug="${worker}"
  fi
  start_proc "${slug}-worker" "${PYTHON_BIN}" -m "${module}"
done

printf 'Sidecar stack running. Logs: %s\n' "${LOG_DIR}"
wait "${SERVER_PID}"
