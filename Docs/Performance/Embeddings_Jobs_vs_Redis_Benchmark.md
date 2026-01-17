# Embeddings Jobs vs Redis Benchmark (Stage 0)

Purpose: capture baseline vs candidate throughput/latency for the embeddings
pipeline (chunking -> embedding -> storage) per Job System Unification PRD.

This runbook uses the repo script:
`Helper_Scripts/benchmarks/embeddings_jobs_vs_redis_benchmark.py`.

## What This Benchmark Measures
- Synthetic three-stage pipeline throughput and end-to-end latency.
- Baseline: Redis Streams pipeline (synthetic fallback if legacy manager removed).
- Candidate: Jobs-backed pipeline (Worker SDK inside the script).

Notes:
- The script now falls back to an in-script Redis Streams pipeline when the
  legacy `EmbeddingJobManager` is unavailable.
- If you want the historical Redis pipeline baseline, run the script from a
  commit that still includes `tldw_Server_API/app/core/Embeddings/job_manager.py`.

## Prerequisites
- Redis running (for Redis baseline).
- Python environment with project dependencies.
- Optional: local Jobs DB path or Postgres URL.

## Quick Start (Compare Mode)
```bash
python Helper_Scripts/benchmarks/embeddings_jobs_vs_redis_benchmark.py \
  --mode compare \
  --job-count 200 \
  --text-bytes 8000 \
  --chunk-size 1000 \
  --chunk-overlap 200 \
  --redis-url redis://localhost:6379 \
  --jobs-db-path ./Databases/jobs.db \
  --report-dir Docs/Performance
```

Outputs: JSON + Markdown reports under `Docs/Performance/` with a timestamped
filename (prefix `embeddings_jobs_vs_redis_*`).

## Baseline Only (Redis)
```bash
python Helper_Scripts/benchmarks/embeddings_jobs_vs_redis_benchmark.py \
  --mode redis \
  --job-count 200 \
  --text-bytes 8000 \
  --redis-url redis://localhost:6379 \
  --report-dir Docs/Performance
```

## Candidate Only (Jobs)
```bash
python Helper_Scripts/benchmarks/embeddings_jobs_vs_redis_benchmark.py \
  --mode jobs \
  --job-count 200 \
  --text-bytes 8000 \
  --jobs-db-path ./Databases/jobs.db \
  --report-dir Docs/Performance
```

## Optional Inputs
- `--corpus-file`: newline-delimited text corpus to use instead of synthetic text.
- `--jobs-workers CHUNK EMBED STORE`: worker counts per stage (defaults 2/4/1).
- `--stage-sleep-ms CHUNK EMBED STORE`: per-stage sleep to simulate latency.
- `--poll-interval`, `--timeout-seconds`, `--no-progress-seconds`: control loop timing.

## Legacy Redis Pipeline Baseline (Optional)
If you need the historical Redis pipeline baseline:
1. Checkout a commit that still includes the Redis embeddings job manager.
2. Run the same script in `--mode redis`.
3. Record the commit hash alongside the report in `Docs/Performance/`.

## Report Checklist
Record this metadata in the report (or a companion note):
- Commit hash: `<git rev-parse HEAD>`
- Date/time:
- Hardware:
- Redis version/config:
- Jobs DB backend:
- Benchmark parameters:

## Latest Run
- Commit hash: `dade47fe8aeafe71035baeae26dc6cdf646e6716`
- Date/time: `2026-01-12 15:48:17`
- Redis baseline: synthetic Redis Streams fallback (legacy manager removed)
- Reports:
  - `Docs/Performance/embeddings_jobs_vs_redis_0e73a1e5d341_20260112_154817.md`
  - `Docs/Performance/embeddings_jobs_vs_redis_0e73a1e5d341_20260112_154817.json`

## Results
| Mode | Jobs | Completed | Failed | Duration (s) | Jobs/s | Chunks/s | p50 (ms) | p95 (ms) | p99 (ms) | Timed Out |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| redis | 200 | 200 | 0 | 1.039 | 192.509 | 1540.074 | 17.1 | 24.8 | 24.9 | False |
| jobs | 200 | 200 | 0 | 2.331 | 85.793 | 686.347 | 1961.1 | 2100.3 | 2112.1 | False |

Comparison notes:
- Throughput ratio (jobs/redis): 0.446
- p95 latency ratio (jobs/redis): 84.690
