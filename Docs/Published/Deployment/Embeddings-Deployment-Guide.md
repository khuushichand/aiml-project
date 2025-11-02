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
- Implementation: Orchestrated workers (`core/Embeddings/worker_orchestrator.py` + `core/Embeddings/workers/*`)
- Processing: Queue-based, distributed workers (chunking → embedding → storage)
- Infra: Redis streams, orchestrator process, multiple worker tasks
- Best for: Production, multi-tenant, high volume

Note: The “mode” depends on which processes you run (API only vs API + orchestrator). There is no runtime flag that switches the API behavior; `EMBEDDINGS_MODE` is a deployment convention, not an API setting.

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
export USER_DB_BASE_DIR="$(pwd)/Databases/user_databases"

# Optional: enable endpoint rate limiting guard on embeddings
export EMBEDDINGS_RATE_LIMIT=on   # Uses built-in limit in the API endpoint
```

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

# Redis server (for queues)
sudo apt-get install -y redis-server
# OR
docker run -d --name redis -p 6379:6379 redis:alpine

# Optional: GPU support for HF models
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

> **Dev/Test Note**
> When a Redis server is unavailable the API now falls back to an in-process
> Redis stub automatically. This keeps local sandboxes and CI runs from failing,
> but production deployments should still provision a real Redis service for
> durability and multi-worker coordination.

### Environment and Orchestrator
```bash
export REDIS_URL="redis://localhost:6379"
export PROMETHEUS_PORT=9090   # optional
```

Use the orchestrator config at `tldw_Server_API/app/core/Embeddings/embeddings_config.yaml` to control worker pool sizes, GPU allocation, and queues. Start the orchestrator (it manages worker tasks in-process):

```bash
python -m tldw_Server_API.app.core.Embeddings.worker_orchestrator
```

### Docker Compose (API + Orchestrator)
```yaml
version: '3.8'

services:
  redis:
    image: redis:alpine
    ports: ["6379:6379"]
    volumes: ["redis_data:/data"]
    command: redis-server --appendonly yes

  api:
    build: .
    ports: ["8000:8000"]
    environment:
      - AUTH_MODE=single_user
      - SINGLE_USER_API_KEY=${SINGLE_USER_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - REDIS_URL=redis://redis:6379
    depends_on: [redis]
    volumes:
      - ./Databases/user_databases:/app/Databases/user_databases
      - ./models/embedding_models_data:/app/models/embedding_models_data

  orchestrator:
    build: .
    command: python -m tldw_Server_API.app.core.Embeddings.worker_orchestrator
    environment:
      - REDIS_URL=redis://redis:6379
      - PROMETHEUS_PORT=9090
    depends_on: [redis]
    ports: ["9090:9090"]

volumes:
  redis_data:
```

### Kubernetes (example)
Deploy API and orchestrator as separate Deployments, and a Redis Service. Health probes should use `GET /api/v1/embeddings/health` on the API.

---

## Configuration Reference

### Core Settings
Most runtime behavior is configured via code defaults or YAML, not environment variables. Key toggles:
- `AUTH_MODE` (`single_user` | `multi_user`)
- `SINGLE_USER_API_KEY` (single-user mode)
- `JWT_SECRET_KEY` (multi-user mode)
- Provider keys: `OPENAI_API_KEY`, `COHERE_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`, `VOYAGE_API_KEY`
- `USER_DB_BASE_DIR` (optional; default `Databases/user_databases`)
- `EMBEDDINGS_RATE_LIMIT=on` enables the built-in rate limiter for the embeddings endpoint

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
- Prefer running during off-peak hours; set caps via `HYDE_MAX_VECTORS_PER_DOC` and orchestrator backpressure/quotas.
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

### Orchestrator Summary & SSE

The orchestrated embeddings pipeline exposes live operational state for dashboards and automation.

- SSE (live stream, admin-only):
  - `GET /api/v1/embeddings/orchestrator/events`
  - Streams a JSON snapshot every few seconds as SSE `data:` frames.

- Polling summary (admin-only):
  - `GET /api/v1/embeddings/orchestrator/summary`
  - Returns the same snapshot payload as a single JSON object.
  - Fallback behavior: if Redis is unavailable, returns HTTP 200 with a zeroed payload (all maps empty, stable keys present) so dashboards don’t break.

Snapshot payload keys:
- `queues`: map of live queue depths by stream (e.g., `embeddings:embedding`)
- `dlq`: map of DLQ depths by stream (e.g., `embeddings:embedding:dlq`)
- `ages`: seconds since oldest message per live queue (0.0 when empty)
- `stages`: aggregated counters `{ processed, failed }` per stage
- `flags`: stage control flags `{ paused, drain }` per stage
- `ts`: server timestamp (seconds)

Examples:
```bash
# SSE (watch raw events)
curl -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  http://localhost:8000/api/v1/embeddings/orchestrator/events

# Polling summary (one-shot JSON)
curl -s -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  http://localhost:8000/api/v1/embeddings/orchestrator/summary | jq .
```

Sample response (polling):
```json
{
  "queues": {"embeddings:embedding": 2},
  "dlq": {"embeddings:embedding:dlq": 0},
  "ages": {"embeddings:embedding": 1.2},
  "stages": {"embedding": {"processed": 120, "failed": 3}},
  "flags": {"embedding": {"paused": false, "drain": false}},
  "ts": 1700001000.123
}
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
  - Use the orchestrator summary/SSE to watch `ages` and `queues` while tuning thresholds.
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
    - `COMPACTOR_USER_ID` (default: `SINGLE_USER_FIXED_ID`; in multi-user deployments, run one compactor instance per user, or extend to iterate users as needed)
    - `MEDIA_DB_PATH` (optional; default: per-user `Databases/user_databases/<user_id>/Media_DB_v2.db`)

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
- Prefer SSE for live dashboards; fall back to polling when SSE/WebSockets are blocked.
- A zeroed payload indicates Redis is unreachable or snapshot encountered an error; alert if sustained.

### Logging
The service uses Loguru and Prometheus instrumentation. Tune `LOG_LEVEL`, and scrape `/metrics` for Prometheus-formatted metrics.

Structured JSON logs
- Enable with `LOG_JSON=true` (or `ENABLE_JSON_LOGS=true`). The JSON sink includes request/trace correlation fields when available:
  - `request_id` (from `X-Request-ID` middleware)
  - `trace_id`, `span_id`, and computed `traceparent`
  - Workers bind `job_id` and `stage` to aid operator drill-down.
  - Responses include `X-Trace-Id` and `traceparent` headers for easy hop-by-hop correlation.

### Dead-Letter Queues (DLQ)

Purpose
- Persist messages that exceeded max retries for operator inspection and recovery.

How it works
- Each stage has a DLQ Redis Stream with suffix `:dlq`.
  - Chunking DLQ: `embeddings:chunking:dlq`
  - Embedding DLQ: `embeddings:embedding:dlq`
  - Storage DLQ: `embeddings:storage:dlq`
- When a worker exhausts `max_retries`, it marks the job `failed` and publishes the original payload and error to the stage DLQ. The worker still `XACK`s the failed message to prevent hot looping.

Security and privacy
- PII/secret redaction: DLQ payload previews in the API/UI redact common secret fields (api_key, authorization, token, password). Avoid logging sensitive content.
- Optional encryption at rest: set `EMBEDDINGS_DLQ_ENCRYPTION_KEY` to enable AES-GCM encryption of DLQ payload bodies. The API will decrypt for previews when the key is present. Without the key, previews omit payloads.

RBAC and auditing
- All DLQ admin endpoints require admin privileges.
- Admin actions are audit-logged (state changes, (bulk) requeues), including operator, stage, and results.

Operator tasks
- Inspect latest DLQ entries:
```bash
# Show the most recent 10 entries from the embedding DLQ
redis-cli XREVRANGE embeddings:embedding:dlq + - COUNT 10
```
- Or via admin API (requires admin):
```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8000/api/v1/embeddings/dlq?stage=embedding&count=10"
```
- Re-enqueue a DLQ entry back to the active stream after correcting the cause:
```bash
# Example: requeue a DLQ item back to the embedding stream
# (Adjust fields to your payload; prefer re-using the original payload JSON)
redis-cli XADD embeddings:embedding '*' job_id <JOB_ID> user_id <USER_ID> payload '<JSON>'
```
- Or via admin API:
```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"stage":"embedding","entry_id":"1-0","delete_from_dlq":true}' \
  http://localhost:8000/api/v1/embeddings/dlq/requeue
```
- Trim DLQs to control growth (approximate):
```bash
redis-cli XTRIM embeddings:embedding:dlq MAXLEN ~ 5000
redis-cli XTRIM embeddings:chunking:dlq  MAXLEN ~ 5000
redis-cli XTRIM embeddings:storage:dlq   MAXLEN ~ 5000
```

Recommendations
- Alert on DLQ growth rate; sustained growth indicates systemic issues.
- Build a small admin tool to list, filter by `job_id`, and requeue DLQ items safely.
- Keep DLQ retention sized to your operating posture (e.g., 7-14 days worth of failures).

### Prometheus Alerts (examples)

Add alerting rules to detect DLQ issues and pipeline stalls.

```yaml
groups:
  - name: tldw-embeddings
    rules:
      # DLQ depth too high for too long
      - alert: EmbeddingsDLQDepthHigh
        expr: sum(embedding_dlq_queue_depth) > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Embeddings DLQ depth high"
          description: "DLQ depth is {{ $value }} across queues for >5m"

      # DLQ ingest rate sustained
      - alert: EmbeddingsDLQIngestRateHigh
        expr: sum(embedding_dlq_ingest_rate) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Embeddings DLQ ingest rate high"
          description: "DLQ ingest > 0.5 msg/s for >10m"

      # Pipeline stagnation: high queue depth but near-zero processing
      - alert: EmbeddingsStageStagnation
        expr: (sum(embedding_queue_depth) > 100)
              and (sum(rate(embedding_stage_jobs_processed_total[5m])) < 0.1)
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Embeddings processing stalled"
          description: "High queue depth with low processing rate for >10m"

      # Oldest message age by queue (p95 over window)
      - alert: EmbeddingsQueueAgeHigh
        expr: max_over_time(embedding_queue_age_seconds[10m]) > 300
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Embeddings queue age high"
          description: "Oldest message age exceeded 5 minutes for >5m"

      # Stage processing latency outliers
      - alert: EmbeddingsStageLatencyHigh
        expr: histogram_quantile(0.95, sum(rate(embedding_stage_processing_latency_seconds_bucket[5m])) by (le, stage)) > 5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Embeddings stage latency high (p95)"
          description: "p95 processing latency > 5s for stage {{ $labels.stage }}"

      # Worker liveness: any stalled workers for a sustained period
      - alert: EmbeddingsWorkersStalled
        expr: sum(embedding_workers_stalled) > 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Embeddings workers stalled"
          description: "One or more workers have missing/expired heartbeats for >5m"

      # Possible drainer throttling/backlog: queue ages rising while processing is low
      - alert: EmbeddingsRequeueThrottled
        expr: (max_over_time(embedding_queue_age_seconds[15m]) - min_over_time(embedding_queue_age_seconds[15m])) > 120
              and (sum(rate(embedding_stage_jobs_processed_total[5m])) < 0.5)
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Embeddings requeue possibly throttled/backlogged"
          description: |
            Queue ages increased >2m over 15m while processing is low. The delayed drainer uses
            a token bucket for safety; consider temporarily increasing EMBEDDINGS_REQUEUE_RATE/BURST during recovery.
```

### SLOs & Error Budgets

Define clear service goals and alert on burn rates to catch problems early while avoiding alert fatigue.

- Suggested SLOs
  - Availability (job success): <0.5% failed jobs over 1h (pipeline-wide)
  - Queue time (freshness): P95 queue age < 2 minutes
  - Latency (processing): p95 stage latency < 5 seconds (per stage)

- Supporting metrics
  - `embedding_stage_jobs_processed_total{stage}` and `embedding_stage_jobs_failed_total{stage}`
  - `embedding_queue_age_seconds_bucket{queue_name}` (histogram)
  - `embedding_stage_processing_latency_seconds_bucket{stage}` (histogram)
  - Newly added: `embedding_stage_batch_size{stage}` and `embedding_stage_payload_bytes_bucket{stage}` (histograms) for tuning batch/payload sizing.

- Example alert rules

```yaml
groups:
  - name: tldw-embeddings-slos
    rules:
      # Error budget burn: failed / (failed + processed) over 1h > 0.5%
      - alert: EmbeddingsErrorBudgetBurn
        expr: (
          sum(increase(embedding_stage_jobs_failed_total[1h]))
          /
          (sum(increase(embedding_stage_jobs_failed_total[1h])) + sum(increase(embedding_stage_jobs_processed_total[1h])))
        ) > 0.005
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Embeddings pipeline error budget burn"
          description: "Failed jobs exceeded 0.5% over 1h"

      # Queue age p95 too high for any queue
      - alert: EmbeddingsQueueAgeP95High
        expr: histogram_quantile(0.95, sum by (le, queue_name) (rate(embedding_queue_age_seconds_bucket[5m]))) > 120
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Embeddings queue age p95 high"
          description: "Queue p95 ({{ $labels.queue_name }}) > 2m for >10m"

      # Stage processing latency p99 high (optional tighter SLO)
      - alert: EmbeddingsStageLatencyP99High
        expr: histogram_quantile(0.99, sum by (le, stage) (rate(embedding_stage_processing_latency_seconds_bucket[5m]))) > 10
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Embeddings stage latency p99 high"
          description: "Stage {{ $labels.stage }} p99 > 10s for >10m"
```

Notes
- Histograms use Prometheus’ `histogram_quantile` on per-bucket rates; ensure your scrape interval matches your cardinality/retention targets.
- Consider multi-window, multi-burn-rate patterns for SLOs if you prefer Google SRE-style alerting.

## Reliability & Delivery

The embeddings pipeline includes protective mechanisms to deliver reliably and avoid overload during recovery:

- Scheduled retries with backoff and jitter
  - Workers classify failures as `transient` vs `permanent` and schedule exponential backoff + jitter for transient errors.
  - After `max_retries`, jobs are marked failed and sent to the stage DLQ with structured fields `error_code` and `failure_type`.

- Token-bucket guard against requeue storms
  - The orchestrator drains delayed queues via a per-queue token bucket so re-enqueues are smoothed.
  - Tuning via environment variables:
    - `EMBEDDINGS_REQUEUE_RATE` (tokens per second; default 50)
    - `EMBEDDINGS_REQUEUE_BURST` (max tokens; default 200)

- Operator skip for known-poison messages
  - Mark a job as skipped (admin-only): `POST /api/v1/embeddings/job/skip { job_id, ttl_seconds }`
  - Check status: `GET /api/v1/embeddings/job/skip/status?job_id=...`
  - Workers consult the skip registry and will ACK/cancel without processing.

- Stage controls & liveness
  - Pause/Resume/Drain per stage: `POST /api/v1/embeddings/stage/control`
  - Orchestrator gauges: `embedding_workers_active{worker_type}`, `embedding_workers_stalled{worker_type}` to monitor worker fleet health.

### Messaging & DLQ Hardening

- Message schema versioning (+ schema URL)
  - Each message carries `msg_version`, `msg_schema`, and `schema_url` (current: `tldw.embeddings.v1`, URL points to the bundled JSON Schema).
  - Ingress validation uses a small JSON Schema bundle to validate core envelope fields.

- De-dup window (operation_id)
  - Workers suppress replays with a short TTL using RedisBloom (if available) or `SET NX` keyed by `operation_id`.
  - Configure TTL via `EMBEDDINGS_DEDUPE_TTL_SECONDS`.

- DLQ quarantine states
  - States: `quarantined`, `approved_for_requeue`, `ignored`.
  - Admin API: `POST /api/v1/embeddings/dlq/state` with `{ stage, entry_id, state, operator_note? }`.
  - Approval requires an `operator_note`; requeue endpoints enforce `approved_for_requeue` when state exists.
  - WebUI exposes state, note, and Quarantine/Approve/Ignore actions.

- Optional durability
  - The pipeline uses Redis Streams and consumer groups. If workload grows, consider adding a dedicated Redis cluster or a lightweight Kafka topic for at-least-once delivery and long-lived retention.

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
- Reduce concurrent load; scale out using orchestrator
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
