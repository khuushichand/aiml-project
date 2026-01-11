# Embeddings Service Deployment Guide

Version: 1.0
Last Updated: 2025-10-08
Service Version: v5 Enhanced (with Circuit Breaker)

## Table of Contents
1. Architecture Overview
2. Deployment Decision Tree
3. Single-User Deployment
4. Enterprise Deployment
5. Configuration Reference
6. Monitoring & Observability
7. Troubleshooting
8. Support

---

## Architecture Overview

The embeddings service is implemented as part of the FastAPI application and supports two deployment topologies:

### Single-User Architecture (<5 concurrent users)
- Implementation: `tldw_Server_API/app/api/v1/endpoints/embeddings_v5_production_enhanced.py`
- Processing: Inline HTTP handling; no external queue required
- Infra: Minimal (no Redis/queues required)
- Best for: Personal use, small teams, development

### Enterprise Architecture (≥5 concurrent users)
- Implementation: Core Jobs worker (`core/Embeddings/services/jobs_worker.py`)
- Processing: Queue-based Jobs pipeline (chunking → embedding → storage) via core Jobs
- Infra: Jobs DB (SQLite/Postgres) and worker processes; no Redis required
- Best for: Production, multi-tenant, high volume

Note: The “mode” depends on which processes you run (API only vs API + Jobs worker). There is no runtime flag that switches the API behavior; `EMBEDDINGS_MODE` is a deployment convention, not an API setting.

---

## Deployment Decision Tree

```
┌─────────────────────────┐
│ How many concurrent     │
│ users will you have?    │
└───────────┬─────────────┘
            │
    ┌───────┴───────┐
    │               │
   <5             ≥5
    │               │
    v               v
┌──────────┐  ┌──────────┐
│ Single-  │  │Enterprise│
│  User    │  │  Mode    │
└──────────┘  └──────────┘
```

---

## Single-User Deployment

### Prerequisites
```bash
# Required packages
pip install -e .

# Optional (choose what your environment supports)
pip install torch              # GPU acceleration for HuggingFace models
pip install onnxruntime-gpu    # GPU acceleration for ONNX models
```

### Environment Variables
```bash
# Auth mode (pick one)
export AUTH_MODE=single_user
export SINGLE_USER_API_KEY="your-single-user-api-key"   # Used via X-API-KEY header
# OR
# export AUTH_MODE=multi_user
# export JWT_SECRET_KEY="your-32+char-jwt-secret"       # Multi-user JWT mode

# Provider API keys (as needed by your configured providers)
export OPENAI_API_KEY="sk-..."
export COHERE_API_KEY="..."
export GOOGLE_API_KEY="..."
export MISTRAL_API_KEY="..."
export VOYAGE_API_KEY="..."

# Optional: user DB base directory (default: Databases/user_databases)
export USER_DB_BASE_DIR="$(pwd)/Databases/user_databases"  # USER_DB_BASE is deprecated alias

# Optional: enable endpoint rate limiting guard on embeddings
export EMBEDDINGS_RATE_LIMIT=on   # Uses built-in limit in the API endpoint
```

`USER_DB_BASE_DIR` is defined in `tldw_Server_API.app.core.config` (defaults to `Databases/user_databases/` under the project root). Override via environment variable or `Config_Files/config.txt` as needed.

### Dockerfile (API)
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir -e .

# Copy application
COPY tldw_Server_API/ ./tldw_Server_API/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/v1/embeddings/health || exit 1

# Run API
ENV PYTHONPATH=/app
CMD ["uvicorn", "tldw_Server_API.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose (API only)
```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - AUTH_MODE=single_user
      - SINGLE_USER_API_KEY=${SINGLE_USER_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./Databases/user_databases:/app/Databases/user_databases
      - ./models/embedding_models_data:/app/models/embedding_models_data
    restart: unless-stopped
```

### systemd Service (API)
```ini
[Unit]
Description=TLDW Embeddings API (Single-User)
After=network.target

[Service]
Type=simple
User=tldw
Group=tldw
WorkingDirectory=/opt/tldw_server
Environment="AUTH_MODE=single_user"
Environment="PYTHONPATH=/opt/tldw_server"
ExecStart=/usr/bin/python3 -m uvicorn tldw_Server_API.app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Enterprise Deployment

### Prerequisites
```bash
# Required packages (same as single-user)
pip install -e .

# Optional: GPU support for HF models
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### Environment and Jobs Worker
```bash
export JOBS_DB_URL="sqlite:///Databases/jobs.db"  # optional; set Postgres URL for shared Jobs DB
```

Use `tldw_Server_API/app/core/Embeddings/embeddings_config.yaml` to control chunking/embedding defaults. Start the core Jobs worker:

```bash
python -m tldw_Server_API.app.core.Embeddings.services.jobs_worker
```

### Docker Compose (API + Jobs Worker)
```yaml
version: '3.8'

services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      - AUTH_MODE=single_user
      - SINGLE_USER_API_KEY=${SINGLE_USER_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./Databases/user_databases:/app/Databases/user_databases
      - ./models/embedding_models_data:/app/models/embedding_models_data

  jobs-worker:
    build: .
    command: python -m tldw_Server_API.app.core.Embeddings.services.jobs_worker
    environment:
      - JOBS_DB_URL=sqlite:///Databases/jobs.db
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./Databases:/app/Databases
      - ./models/embedding_models_data:/app/models/embedding_models_data
```

### Kubernetes (example)
Deploy API and jobs worker as separate Deployments. Ensure the Jobs DB (SQLite volume or Postgres service) is reachable. Health probes should use `GET /api/v1/embeddings/health` on the API.

---

## Configuration Reference

### Core Settings
Most runtime behavior is configured via code defaults or YAML, not environment variables. Key toggles:
- `AUTH_MODE` (`single_user` | `multi_user`)
- `SINGLE_USER_API_KEY` (single-user mode)
- `JWT_SECRET_KEY` (multi-user mode)
- Provider keys: `OPENAI_API_KEY`, `COHERE_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`, `VOYAGE_API_KEY`
- `USER_DB_BASE_DIR` (optional; defined in `tldw_Server_API.app.core.config`, default `Databases/user_databases/` under the project root; override via environment variable or `Config_Files/config.txt`)
- `EMBEDDINGS_RATE_LIMIT=on` enables the built-in rate limiter for the embeddings endpoint
- Embeddings compactor: `COMPACTOR_USER_ID` (required in multi-user mode; defaults to `SINGLE_USER_FIXED_ID` in single-user), `EMBEDDINGS_COMPACTOR_INTERVAL_SECONDS` (default: 1800), optional `MEDIA_DB_PATH` override.

Advanced constants like batch size, cache TTL, and connection pool are code-level defaults in `embeddings_v5_production_enhanced.py`.

### Vector Store Backend Selection (config.txt)
For production, vector store configuration is read from `config.txt` and determines whether ChromaDB (default) or pgvector is used.

Example `config.txt` snippet (RAG section):

```
[RAG]
vector_store_type = pgvector
pgvector_host = localhost
pgvector_port = 5432
pgvector_database = tldw_content
pgvector_user = tldw_user
pgvector_password = <your_password>
pgvector_sslmode = prefer
# Optional knobs
pgvector_pool_min_size = 1
pgvector_pool_max_size = 5
pgvector_hnsw_ef_search = 64
```

Notes:
- For normal server operation, the pgvector values above are authoritative; environment variables do not override them.
- Admin ef_search controls apply to pgvector only; Chroma treats them as no-ops.

### HYDE Retrieval Flags (optional)
If you enable HYDE/doc2query vector generation, you can tune retrieval fusion behavior via env flags:

```bash
# Fraction of top-k to allocate to HYDE question vectors (0..1)
export HYDE_K_FRACTION=0.5

# Additive weight applied to HYDE similarity before merging (0..1)
export HYDE_WEIGHT_QUESTION_MATCH=0.05

# Skip HYDE search when baseline is strong (early exit)
export HYDE_ONLY_IF_NEEDED=true
export HYDE_SCORE_FLOOR=0.30   # baseline score threshold for early exit

# Dedupe granularity
# false: merge/fuse at media level (default)
# true:  perform merge by parent_chunk_id for finer ranking
export HYDE_DEDUPE_BY_PARENT=false
```

Notes
- Media-level dedupe (default) keeps one entry per media_id. Chunk-level dedupe ranks distinct chunks from the same media when enabled.
- When HYDE_ONLY_IF_NEEDED is true and the baseline chunk search returns ≥k with a max score ≥ HYDE_SCORE_FLOOR, HYDE is skipped to reduce latency.

### HYDE Backfill CLI (optional)

For existing collections, you can backfill HYDE question vectors offline using the helper script:

```
python Helper_Scripts/hyde_backfill.py --collection <collection_name> --page-size 200
```

Notes:
- Respects HYDE_* configuration (provider, model, temperature, max tokens, language, prompt version).
- Uses best-effort generation; failures are logged and skipped (no DLQ for HYDE).
- Use `--dry-run` to preview changes without writing.
- Prefer running during off-peak hours; set caps via `HYDE_MAX_VECTORS_PER_DOC` and Jobs backpressure/quotas.
- The WebUI → Embeddings → Admin view shows a HYDE status badge so operators can confirm the current provider/model at a glance.

- HYDE vector generation itself is feature-flagged separately (see HYDE-Do-1.md). Retrieval flags above affect only the search/merge phase.


### Provider Configuration (model definitions)

For local models and provider defaults used by the embeddings implementation, define an Embeddings config compatible with `EmbeddingConfigSchema` (used by `Embeddings_Create`):

```yaml
default_model_id: hf_mpnet
model_storage_base_dir: ./models/embedding_models_data/
models:
  openai_small:
    provider: openai
    model_name_or_path: text-embedding-3-small
  hf_mpnet:
    provider: huggingface
    model_name_or_path: sentence-transformers/all-mpnet-base-v2
    trust_remote_code: false
  onnx_minilm:
    provider: onnx
    model_name_or_path: sentence-transformers/all-MiniLM-L6-v2
    onnx_providers: ["CPUExecutionProvider"]
  local_api_default:
    provider: local_api
    model_name_or_path: nomic-embed-text
    api_url: http://localhost:11434/api/embeddings
```

---

## Monitoring & Observability

### Prometheus Metrics
Prometheus metrics are exposed via the unified text endpoint:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'tldw'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

Key embeddings metrics (subset):
- `embedding_requests_total` - Request counter
- `embedding_request_duration_seconds` - Latency histogram
- `embedding_cache_hits_total` - Cache hit rate
- `active_embedding_requests` - Current load
- Circuit breaker status is available via admin endpoints

### pgvector backend metrics & admin
- Prometheus emits pgvector operation histograms/counters (in `/api/v1/metrics/text`):
  - `pgvector_upsert_latency_seconds`, `pgvector_query_latency_seconds`, `pgvector_delete_latency_seconds`
  - `pgvector_rows_upserted_total`, `pgvector_rows_deleted_total`
- Admin endpoints for pgvector/chroma:
  - `GET  /api/v1/vector_stores/{id}/admin/index_info` → backend & index info
  - `POST /api/v1/vector_stores/admin/hnsw_ef_search` → set session `ef_search` (pg only)
  - `POST /api/v1/vector_stores/{id}/admin/rebuild_index` → rebuild ANN index (`hnsw|ivfflat|drop`)
  - `POST /api/v1/vector_stores/{id}/admin/delete_by_filter` → delete by JSONB metadata filter
  - `GET  /api/v1/vector_stores/admin/health` → adapter health summary

Quick start:
```bash
docker-compose -f docker-compose.pg.yml up -d
export PGVECTOR_DSN=postgresql://postgres:postgres@localhost:5432/tldw
# Optional: seed and migrate a demo collection from Chroma stub
CHROMADB_FORCE_STUB=true \
python Helper_Scripts/chroma_to_pgvector_migrate.py --user-id 1 --collection demo_cli --seed-demo --rebuild-index hnsw
```

### Health Checks and Admin Metrics

```bash
# Basic health check
curl http://localhost:8000/api/v1/embeddings/health

# Detailed embeddings metrics (requires admin)
curl -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  http://localhost:8000/api/v1/embeddings/metrics

# Circuit breaker status (requires admin)
curl -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  http://localhost:8000/api/v1/embeddings/circuit-breakers
```

### Jobs Metrics & Status

The embeddings Jobs pipeline uses core Jobs metrics. There is no orchestrator SSE endpoint.

- Prometheus text metrics: `GET /metrics` or `GET /api/v1/metrics/text`
- Filter metrics by `domain="embeddings"` (for example, `jobs.queued`, `jobs.processing`, `jobs.duration_seconds`)

Example:
```bash
curl -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  http://localhost:8000/api/v1/metrics/text | rg 'jobs\\.' | head -50
```

### Backpressure & Quotas (HTTP 429)

When the orchestrated embeddings pipeline is overloaded, the API gates selected endpoints with backpressure to protect stability. Backpressure also applies to key media ingestion endpoints so upstream downloads and parsing do not exacerbate downstream queueing.

- Behavior
  - If any core embeddings queue’s depth or oldest message age exceeds a threshold, affected endpoints return HTTP 429 with a `Retry-After` header.
  - In multi-user mode, per-tenant request quotas (RPS) may also return HTTP 429 with `Retry-After: 1` and `X-RateLimit-*` headers.

- Affected endpoints (non-exhaustive)
  - Embeddings: `POST /api/v1/embeddings`, `POST /api/v1/embeddings/batch`
  - Paper ingestion: `POST /api/v1/paper-search/arxiv/ingest`, `POST /api/v1/paper-search/earthrxiv/ingest`
  - Web ingestion: `POST /api/v1/ingest-web-content`
  - MediaWiki ingest: `POST /api/v1/mediawiki/ingest-dump`

- Configuration
  - `EMB_BACKPRESSURE_MAX_DEPTH` (int, default 25000): max queue depth across `embeddings:{chunking|embedding|storage}` before 429.
  - `EMB_BACKPRESSURE_MAX_AGE_SECONDS` (float, default 300): max age (seconds) of oldest message before 429.
  - `EMBEDDINGS_TENANT_RPS` (int, default 0): per-tenant RPS for embeddings endpoints (429 when exceeded; 0 disables).
  - `INGEST_TENANT_RPS` (int, default 0): per-tenant RPS for ingestion endpoints (falls back to `EMBEDDINGS_TENANT_RPS` when unset).

- Operator tips
  - Use core Jobs metrics (`jobs.queue_latency_seconds`, `jobs.queued`) filtered by `domain="embeddings"` while tuning thresholds.
  - Start with higher thresholds and lower them once you have a baseline for normal load.
  - If tenants routinely hit throttle, increase `*_TENANT_RPS` or provision more workers.

- Examples
```bash
# Typical 429 from embeddings when overloaded
curl -i -X POST http://localhost:8000/api/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"input":"hello","model":"text-embedding-3-small"}'

# Response (example):
# HTTP/1.1 429 Too Many Requests
# Retry-After: 10

# Tenant quotas: query current limit/remaining (multi-user)
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/embeddings/tenant/quotas | jq .
```

### Startup Checks & Compaction (optional)

You can enable two optional maintenance features to harden indexing integrity and storage hygiene:

- Startup-time dimension sanity check
  - Verifies that each Chroma collection’s `embedding_dimension` metadata matches the actual vector length.
  - In `single_user` mode, checks the single user’s collections. In `multi_user` mode, iterates all user directories under `USER_DB_BASE_DIR` and checks each user’s collections.
  - Environment flags:
    - `EMBEDDINGS_STARTUP_DIM_CHECK_ENABLED` = `true|false` (default: false)
    - `EMBEDDINGS_DIM_CHECK_STRICT` = `true|false` (default: false). When true, any mismatch aborts startup with an error.

- Vector compactor (soft-delete propagation)
  - Periodically scans the Media DB for soft-deleted documents and removes their vectors from user collections.
  - Recommended for deployments with frequent deletes or where storage must stay tidy over time.
  - Environment flags:
    - `EMBEDDINGS_COMPACTOR_ENABLED` = `true|false` (default: false)
    - `EMBEDDINGS_COMPACTOR_INTERVAL_SECONDS` (default: 1800)
    - `COMPACTOR_USER_ID` (defaults to `SINGLE_USER_FIXED_ID` in single-user mode; required in multi-user deployments. Run one compactor instance per user, or extend to iterate users as needed.)
    - `MEDIA_DB_PATH` (optional; default: per-user `<USER_DB_BASE_DIR>/<user_id>/Media_DB_v2.db`)

Example (single-user):
```bash
export EMBEDDINGS_STARTUP_DIM_CHECK_ENABLED=true
export EMBEDDINGS_DIM_CHECK_STRICT=true  # fail fast on mismatch

export EMBEDDINGS_COMPACTOR_ENABLED=true
export EMBEDDINGS_COMPACTOR_INTERVAL_SECONDS=1200
```

Example (multi-user):
```bash
export AUTH_MODE=multi_user
export USER_DB_BASE_DIR=/opt/tldw/Databases/user_databases
export EMBEDDINGS_STARTUP_DIM_CHECK_ENABLED=true
# Optional strict mode; consider enabling in CI/staging
export EMBEDDINGS_DIM_CHECK_STRICT=false

# For compaction, either run per-user or use a supervisor to launch per user_id
export EMBEDDINGS_COMPACTOR_ENABLED=true
export COMPACTOR_USER_ID=42
```

Operator notes:
- Prefer `/metrics` and `/api/v1/metrics/text` for dashboards; filter `jobs.*` by `domain="embeddings"`.
- If metrics are empty, verify the Jobs DB and embeddings Jobs worker are running.

### Logging
The service uses Loguru and Prometheus instrumentation. Tune `LOG_LEVEL`, and scrape `/metrics` for Prometheus-formatted metrics.

Structured JSON logs
- Enable with `LOG_JSON=true` (or `ENABLE_JSON_LOGS=true`). The JSON sink includes request/trace correlation fields when available:
  - `request_id` (from `X-Request-ID` middleware)
  - `trace_id`, `span_id`, and computed `traceparent`
  - Workers bind `job_id` and `stage` to aid operator drill-down.
  - Responses include `X-Trace-Id` and `traceparent` headers for easy hop-by-hop correlation.

### Job Failures & Quarantine

Core Jobs records failures directly on the job row (status `failed` or `quarantined`).

Operator tasks
- List failed jobs (admin):
```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8000/api/v1/jobs/admin/list?domain=embeddings&status=failed&limit=50"
```
- Retry a job immediately (admin):
```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"job_id": 12345}' \
  http://localhost:8000/api/v1/jobs/retry-now
```
- Reschedule a job for later (admin):
```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"job_id": 12345, "available_at": "2026-01-10T12:00:00Z"}' \
  http://localhost:8000/api/v1/jobs/reschedule
```

Recommendations
- Alert on `jobs.failures_total` and `jobs.queue_latency_seconds` for `domain="embeddings"`.
- Use `error_message` and `result` fields for root-cause analysis.

### Prometheus Alerts (examples)

Add alerting rules against core Jobs metrics.

```yaml
groups:
  - name: tldw-embeddings
    rules:
      - alert: EmbeddingsJobsBacklogHigh
        expr: sum(jobs.backlog{domain="embeddings"}) > 200
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Embeddings backlog high"
          description: "Jobs backlog > 200 for >10m"

      - alert: EmbeddingsJobsLatencyHigh
        expr: histogram_quantile(0.95, sum(rate(jobs.queue_latency_seconds_bucket{domain="embeddings"}[5m])) by (le)) > 120
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Embeddings queue latency p95 high"
          description: "Queue latency p95 > 120s for >10m"

      - alert: EmbeddingsJobsFailuresHigh
        expr: sum(rate(jobs.failures_total{domain="embeddings"}[5m])) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Embeddings job failures high"
          description: "Failure rate > 0.5/s for >10m"
```

### SLOs & Error Budgets

Define clear service goals and alert on burn rates to catch problems early while avoiding alert fatigue.

- Suggested SLOs
  - Availability (job success): <0.5% failed jobs over 1h (domain-wide)
  - Queue time (freshness): P95 queue latency < 2 minutes
  - Latency (processing): p95 job duration < 5 seconds

- Supporting metrics
  - `jobs.completed_total{domain="embeddings"}` and `jobs.failures_total{domain="embeddings"}`
  - `jobs.queue_latency_seconds_bucket{domain="embeddings"}` (histogram)
  - `jobs.duration_seconds_bucket{domain="embeddings"}` (histogram)

- Example alert rules

```yaml
groups:
  - name: tldw-embeddings-slos
    rules:
      # Error budget burn: failed / (failed + completed) over 1h > 0.5%
      - alert: EmbeddingsErrorBudgetBurn
        expr: (
          sum(increase(jobs.failures_total{domain="embeddings"}[1h]))
          /
          (sum(increase(jobs.failures_total{domain="embeddings"}[1h])) + sum(increase(jobs.completed_total{domain="embeddings"}[1h])))
        ) > 0.005
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Embeddings error budget burn"
          description: "Failed jobs exceeded 0.5% over 1h"

      # Queue latency p95 too high
      - alert: EmbeddingsQueueLatencyP95High
        expr: histogram_quantile(0.95, sum by (le) (rate(jobs.queue_latency_seconds_bucket{domain="embeddings"}[5m]))) > 120
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Embeddings queue latency p95 high"
          description: "Queue latency p95 > 2m for >10m"

      # Job duration p99 high (optional tighter SLO)
      - alert: EmbeddingsDurationP99High
        expr: histogram_quantile(0.99, sum by (le) (rate(jobs.duration_seconds_bucket{domain="embeddings"}[5m]))) > 10
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Embeddings job duration p99 high"
          description: "Job duration p99 > 10s for >10m"
```

Notes
- Histograms use Prometheus’ `histogram_quantile` on per-bucket rates; ensure your scrape interval matches your cardinality/retention targets.
- Consider multi-window, multi-burn-rate patterns for SLOs if you prefer Google SRE-style alerting.

## Reliability & Delivery

The embeddings pipeline uses core Jobs leasing, retries, and backoff:

- Retries/backoff are managed by core Jobs (`max_retries`, exponential backoff, idempotency keys).
- Quarantined jobs are tracked with `status=quarantined` and can be retried via Jobs admin endpoints.
- Queue controls (pause/drain) and rescheduling are handled via `/api/v1/jobs/*` admin endpoints.

---

## Troubleshooting

### 1) Circuit Breaker Open
Symptom: 503 Service Unavailable.
Check and reset (admin-only in single-user):
```bash
curl -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  http://localhost:8000/api/v1/embeddings/circuit-breakers

curl -X POST -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  http://localhost:8000/api/v1/embeddings/circuit-breakers/openai/reset
```

### 2) High Memory Usage
Symptom: OOM or slow responses.
Actions:
- Prefer smaller models (e.g., `text-embedding-3-small`, `all-MiniLM-L6-v2`)
- Reduce concurrent load; scale out using additional Jobs workers
- For HF models, unload inactive models sooner (see `model_unload_timeout` in YAML)

### 3) Slow Embeddings
Symptom: High latency.
Actions:
- Verify GPU availability: `nvidia-smi`
- Warm up models (admin-only):
```bash
curl -X POST -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  http://localhost:8000/api/v1/embeddings/models/warmup \
  -H 'Content-Type: application/json' \
  -d '{"provider":"huggingface","model_id":"sentence-transformers/all-mpnet-base-v2"}'
```

### 4) Rate Limiting
Symptom: 429 Too Many Requests.
To enable the built-in limiter for the embeddings endpoint:
```bash
export EMBEDDINGS_RATE_LIMIT=on
```

### Debug Mode
```bash
export LOG_LEVEL=DEBUG
```

### Performance Tuning
GPU:
```bash
export CUDA_ALLOW_TF32=1   # Mixed precision where applicable
```
CPU:
```bash
export OMP_NUM_THREADS=8
```

---

## Support

- GitHub Issues: https://github.com/rmusser01/tldw_server/issues
- Documentation:
  - API-related: Embeddings API Documentation
  - Code: Embeddings Documentation
- Metrics: `/metrics` (Prometheus) or `/api/v1/metrics/text`
