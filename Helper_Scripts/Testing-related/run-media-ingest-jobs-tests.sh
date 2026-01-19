#!/usr/bin/env bash
# run-media-ingest-jobs-tests.sh
# Purpose: Run the media ingest jobs test suite and related trace-context check.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

FULL_TRACE_CONTEXT=0
PYTEST_ARGS=()

usage() {
  cat <<EOF
Usage: $(basename "$0") [--full-trace-context] [-- pytest-args...]

Options:
  --full-trace-context   Run the full test_trace_context.py file
  --help                 Show this help

Examples:
  $(basename "$0")
  $(basename "$0") -v
  $(basename "$0") --full-trace-context
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --full-trace-context)
      FULL_TRACE_CONTEXT=1
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

export TEST_MODE="${TEST_MODE:-1}"
export MINIMAL_TEST_APP="${MINIMAL_TEST_APP:-1}"
export OTEL_SDK_DISABLED="${OTEL_SDK_DISABLED:-true}"

cd "${REPO_ROOT}"

if [[ ${#PYTEST_ARGS[@]} -gt 0 ]]; then
  python -m pytest -q \
    tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_endpoint.py \
    tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py \
    tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_cancellation.py \
    tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_ingest_jobs.py \
    "${PYTEST_ARGS[@]}"
else
  python -m pytest -q \
    tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_endpoint.py \
    tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_jobs_worker.py \
    tldw_Server_API/tests/MediaIngestion_NEW/unit/test_media_ingest_cancellation.py \
    tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_ingest_jobs.py
fi

if [[ ${FULL_TRACE_CONTEXT} -eq 1 ]]; then
  if [[ ${#PYTEST_ARGS[@]} -gt 0 ]]; then
    python -m pytest -q \
      tldw_Server_API/tests/Logging/test_trace_context.py \
      "${PYTEST_ARGS[@]}"
  else
    python -m pytest -q \
      tldw_Server_API/tests/Logging/test_trace_context.py
  fi
else
  if [[ ${#PYTEST_ARGS[@]} -gt 0 ]]; then
    python -m pytest -q \
      tldw_Server_API/tests/Logging/test_trace_context.py \
      -k "media_ingest_jobs_submit_propagates_request_id" \
      "${PYTEST_ARGS[@]}"
  else
    python -m pytest -q \
      tldw_Server_API/tests/Logging/test_trace_context.py \
      -k "media_ingest_jobs_submit_propagates_request_id"
  fi
fi
