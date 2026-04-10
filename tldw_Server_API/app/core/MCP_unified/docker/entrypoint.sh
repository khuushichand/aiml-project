#!/usr/bin/env bash
set -euo pipefail

mkdir -p /data/databases /data/logs /data/cache /data/media /data/transcripts

exec "$@"
