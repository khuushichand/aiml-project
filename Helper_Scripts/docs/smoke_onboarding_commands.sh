#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "[onboarding-smoke] starting optional environment smoke checks"

if ! command -v docker >/dev/null 2>&1; then
  echo "[onboarding-smoke] docker not found; skipping docker/postgres checks"
  echo "[onboarding-smoke] done (skipped)"
  exit 0
fi

if ! docker info >/dev/null 2>&1; then
  echo "[onboarding-smoke] docker daemon unavailable; skipping docker/postgres checks"
  echo "[onboarding-smoke] done (skipped)"
  exit 0
fi

echo "[onboarding-smoke] validating compose config for single-user docker profile"
docker compose -f Dockerfiles/docker-compose.yml config >/dev/null

echo "[onboarding-smoke] validating compose config for multi-user postgres profile"
docker compose \
  -f Dockerfiles/docker-compose.yml \
  -f Dockerfiles/docker-compose.postgres.yml \
  config >/dev/null

if command -v psql >/dev/null 2>&1; then
  echo "[onboarding-smoke] postgres client available: $(psql --version)"
else
  echo "[onboarding-smoke] psql not installed; postgres client check skipped"
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  echo "[onboarding-smoke] GPU detected:"
  nvidia-smi -L
else
  echo "[onboarding-smoke] nvidia-smi not available; GPU smoke check skipped"
fi

echo "[onboarding-smoke] done"
