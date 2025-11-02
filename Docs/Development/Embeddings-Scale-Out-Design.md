# Embeddings Scale-Out Architecture Design

Status: WIP (design aligned with implemented orchestrator/workers)
Last Updated: 2025-10-14

## Overview

This document specifies the production-scale, queue-based embeddings pipeline used to process large and concurrent workloads. It evolves the single-request path into a horizontally scalable topology using Redis Streams, worker pools, and an orchestrator. The design preserves provider flexibility, per-user isolation, and batch efficiency while adding fairness, quotas, and observability.

Scope and audience
- Scope: Embeddings pipeline (chunk → embed → store) and its orchestration.
- Audience: Backend engineers, SREs, maintainers. Related API docs live separately.

## Current System Snapshot

Active components (implemented in code):
- Orchestrator: `tldw_Server_API/app/core/Embeddings/worker_orchestrator.py`
- Job Manager (Redis Streams): `tldw_Server_API/app/core/Embeddings/job_manager.py`
- Workers: `tldw_Server_API/app/core/Embeddings/workers/{chunking_worker,embedding_worker,storage_worker}.py`
- Queue Schemas: `tldw_Server_API/app/core/Embeddings/queue_schemas.py`
- Config: `tldw_Server_API/app/core/Embeddings/worker_config.py`, `tldw_Server_API/app/core/Embeddings/embeddings_config.yaml`
- Vector store helpers: `tldw_Server_API/app/core/Embeddings/ChromaDB_Library.py`

Notes:
- Redis Streams with consumer groups is the standard queue backend. RabbitMQ is not required.
- The public REST endpoint (`/api/v1/embeddings`) remains single-request; the orchestrator/queues are used for media batch embeddings and enterprise deployments.
- Production API path and engine details: `tldw_Server_API/app/api/v1/endpoints/embeddings_v5_production_enhanced.py` and `Embeddings_Server/Embeddings_Create.py`.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌───────────────────┐
│   API Layer │────▶│ Embedding Jobs   │────▶│ Redis Streams     │
└─────────────┘     │  (Job Manager)   │     │  + Consumer Groups│
                    └─────────┬────────┘     └──────────┬────────┘
                              │                          │
              ┌───────────────┼──────────────────────────┼─────────────────┐
              │               │                          │                 │
        ┌─────▼─────┐   ┌─────▼─────┐              ┌─────▼─────┐    ┌─────▼─────┐
        │ Chunking   │   │ Embedding │              │  Storage  │    │ Monitoring│
        │  Queue     │   │  Queue    │              │  Queue    │    │  + Autoscale
        └─────┬──────┘   └─────┬─────┘              └─────┬─────┘    └───────────┘
              │                │                           │
        ┌─────▼──────┐   ┌─────▼────────┐            ┌─────▼──────┐
        │ Chunking    │   │ Embedding    │            │  Storage   │
        │  Workers    │   │  Workers     │            │  Workers   │
        └─────────────┘   └──────────────┘            └────────────┘
```

Queue names and consumer groups (defaults)
- Chunking: `embeddings:chunking` / group `chunking-workers`
- Embedding: `embeddings:embedding` / group `embedding-workers`
- Storage: `embeddings:storage` / group `storage-workers`

## Component Design

### 1) Job Manager (Redis Streams)
Responsibilities
- Accept embedding jobs (per media, per user) and emit `ChunkingMessage` to `embeddings:chunking`.
- Track job status in Redis Hash `job:{job_id}`; expose status/lookup and cancellation.
- Enforce per-tier limits and quotas; compute effective priority with aging and usage penalties.

Implementation entry: `tldw_Server_API/app/core/Embeddings/job_manager.py`

### 2) Worker Types

Chunking Workers
- Purpose: Split content into embedding-ready chunks; preserve metadata and order.
- Scaling: CPU-bound; horizontally scalable.
- Config: `ChunkingWorkerPoolConfig` (default chunk size/overlap) in `worker_config.py`.

Embedding Workers
- Purpose: Generate embeddings from chunks; provider-aware and batch-optimized.
- Scaling: CPU/GPU depending on provider/model; GPU assignment via `gpu_allocation`.
- Features (implemented in `embedding_worker.py`):
  - Model selection per chunk (category-based) with fallbacks.
  - LRU+TTL embedding cache (optional) and batch-size adaptation on OOM.
  - HF `trust_remote_code` allowlist; OpenAI and ONNX supported via `Embeddings_Create`.

Storage Workers
- Purpose: Persist embeddings to ChromaDB and update SQL metadata/indices.
- Scaling: I/O-bound; batching and transactional writes.

### 3) Orchestrator
- Starts/stops/scales worker pools; exposes Prometheus metrics and queue depth gauges.
- Optional autoscaling loop driven by queue depths and configured thresholds.
- File: `tldw_Server_API/app/core/Embeddings/worker_orchestrator.py`.

## Message Schemas (authoritative)

Defined in `tldw_Server_API/app/core/Embeddings/queue_schemas.py`.

```python
class EmbeddingJobMessage(BaseModel):
    job_id: str
    user_id: str
    media_id: int
    priority: int  # 0-100
    user_tier: UserTier = UserTier.FREE
    created_at: datetime
    updated_at: datetime
    retry_count: int = 0
    max_retries: int = 3
    trace_id: Optional[str] = None

class ChunkingMessage(EmbeddingJobMessage):
    content: str
    content_type: str  # "text", "document", etc.
    chunking_config: ChunkingConfig
    source_metadata: Dict[str, Any] = {}

class EmbeddingMessage(EmbeddingJobMessage):
    chunks: List[ChunkData]
    embedding_model_config: Dict[str, Any]
    model_provider: str  # e.g., "huggingface", "openai"
    batch_size: Optional[int] = None

class StorageMessage(EmbeddingJobMessage):
    embeddings: List[EmbeddingData]
    collection_name: str
    total_chunks: int
    processing_time_ms: int
    metadata: Dict[str, Any] = {}
```

## Scheduling & Priority

Effective priority = f(tier multiplier, recent usage penalty, age bonus). Implemented in `PriorityCalculator` with:
- Tiers: free=1.0, premium=2.0, enterprise=3.0
- Usage penalty: recent jobs in last hour (capped)
- Age bonus: grows with wait time (capped)

Fairness guidance
- Prefer earliest-available within priority cohort; use consumer group distribution to shard load across workers.
- Prevent monopolization via recent-usage penalties and per-user concurrency limits.

## Resource Management

Model lifecycle
- EmbeddingWorker caches/warms models; selects per-chunk provider/model; supports HF/OpenAI/ONNX/Local.
- Batch size adapts on MemoryError; fallback model path on repeated provider error.

GPU allocation
- Per-worker static GPU mapping via `EmbeddingWorkerPoolConfig.gpu_allocation`.
- Worker sets `CUDA_VISIBLE_DEVICES` to the assigned GPU; optional GPU utilization metrics via NVML.

## Reliability & Failure Handling

Processing semantics
- Redis Streams + consumer groups; at-least-once delivery with idempotent storage expected.
- Workers acknowledge (`XACK`) upon successful stage completion; retries with exponential backoff on failure.

Retries and DLQ
- Exponential backoff per message; `max_retries` default 3. After exhaustion, job marked `failed`.
- Scheduled retries are implemented via a per-queue delayed ZSET (`<queue>:delayed`) with jitter; the orchestrator drains due items into the live stream (avoids sleeping workers).
- DLQ implemented: workers publish failures to `embeddings:chunking:dlq`, `embeddings:embedding:dlq`, or `embeddings:storage:dlq` with original payload and error context for operator action.

Idempotency
- Storage should be idempotent per `(job_id, chunk_id)` to tolerate replays. Recommend unique constraints or dedupe keys in vector store metadata.

Message schema & validation
- All messages include `msg_version` and `schema` (default `tldw.embeddings.v1`).
- A validator normalizes and validates stage messages before processing; future versions may evolve with migration shims.

Dedupe window
- Workers suppress accidental replays within a configurable window using Redis `SET NX` keyed by a stage-specific dedupe key (or explicit `dedupe_key`).

Progress & TTL
- Job status stored at `job:{job_id}`; progress fields updated by workers; TTL applied to completed/failed jobs (24h default).

Poison-pill handling
- Repeated serializer/schema errors should short-circuit to DLQ; worker should guard against infinite retry loops.

## Idempotent Upsert Spec (Storage Worker)

Goals
- Guarantee safe replays and prevent duplicate vectors for the same logical chunk.

Keys and identity
- Primary key: `chunk_id` (string) must be globally unique within a collection for a media item.
- Job independence: The same `chunk_id` must be reused on retries or replays; avoid embedding job-specific suffixes.

Operation
- Use vector-store upsert when available (Chroma: `collection.upsert`).
- Fallback path order: `upsert → add → update` (handling older adapters). On duplicate-ID errors, retry with `update`.

Metadata requirements
- Minimal metadata persisted with each item:
  - `media_id` (string)
  - `model_used` (string)
  - `dimensions` (string or int)
  - Optional: `chunk_index`, `total_chunks`, `file_name`, `contextualized`, `context_header`, `contextual_summary_ref`
- Recommend adding `embedding_version` when re-embedding logic changes.

Dimension changes
- If new embedding dimension != collection’s dimension, recreate or route to a new collection (as implemented in `ChromaDB_Library.store_in_chroma`).

Idempotency invariants
- Replaying the same `(collection_name, chunk_id)` must overwrite the vector and metadata but must not create duplicates.
- Storage must be safe under at-least-once delivery and partial batch failures.

## Security & Multi-Tenancy

- Enforce user isolation in collection naming and SQL writes; ensure no cross-tenant leakage via message payloads.
- Quotas and per-tier concurrency limits enforced by Job Manager.
- Never include secrets in logs; sanitize message payloads before logging.
- Validate and bound `chunking_config` to avoid resource abuse.

## Observability

Metrics
- Orchestrator exposes Prometheus gauges/counters: worker counts, queue depths, total jobs by status.
- Queue age histogram: `embedding_queue_age_seconds{queue_name}` (age of oldest message observed over time).
- Stage processing latency histogram: `embedding_stage_processing_latency_seconds{stage}` (observed from worker snapshots).
- Workers publish heartbeats and metrics in Redis (`worker:heartbeat:*`, `worker:metrics:*`).
- API exposes endpoint-level metrics and circuit breaker status for provider calls.
- DLQ metrics (orchestrator): `embedding_dlq_queue_depth{queue}` and `embedding_dlq_ingest_rate{queue}` (approximate rate via depth derivative).

Alerts (suggested)
- Queue depth > threshold per stage; worker heartbeat missing; error rate spikes; GPU memory > 90%; P95/P99 latency breaches.

SSE live updates
- Admin API exposes `/api/v1/embeddings/orchestrator/events` (SSE) for low-latency dashboard updates; WebUI toggles between polling and SSE.

Stage controls
- Admin API supports per-stage `pause`, `resume`, and `drain` flags. `drain` pauses new reads while allowing in-flight batches to finish.

## Operator Runbook

Common alerts → actions
- High queue depth (sustained):
  - Action: Increase workers in the orchestrator, enable autoscaling, or reduce producer rate. Check provider throughput and GPU utilization.
- Worker heartbeat missing:
  - Action: Restart affected worker pool; inspect logs for exceptions; verify Redis connectivity.
- Provider error rate spike (OpenAI/HF):
  - Action: Inspect circuit breaker status; throttle or failover to fallback models; verify API keys/quotas.
- GPU memory > 90% or OOM during embedding:
  - Action: Reduce batch size; switch to smaller model; redistribute GPU allocation.
- Storage errors or dimension mismatches:
  - Action: Verify `embedding_dimension` metadata; if mismatch, allow the library to recreate collection or route to a new collection.
- DLQ growth rate rising:
  - Action: Inspect `embeddings:*:dlq`; fix root cause; bulk requeue selected messages; trim DLQ.

Operational commands (examples)
- Inspect queue depth: `redis-cli XLEN embeddings:embedding`
- List DLQ tail: `redis-cli XREVRANGE embeddings:embedding:dlq + - COUNT 10`
- Requeue DLQ item: `redis-cli XADD embeddings:embedding '*' job_id <JOB_ID> payload '<JSON>'`

## Configuration & Ops

Primary knobs
- `REDIS_URL` for all workers and Job Manager.
- Orchestrator YAML: pool sizes, GPU allocation, autoscaling thresholds.
- Embeddings engine config (`embeddings_config.yaml`): provider defaults and storage paths.

References
- Deployment guide: `Docs/Published/Deployment/Embeddings-Deployment-Guide.md`
- Embeddings README: `tldw_Server_API/app/core/Embeddings/README.md`

## Implementation Phases (with status)

Phase 1: Foundation
- [x] Base worker classes and interfaces
- [x] Job Manager with Redis Streams
- [x] Monitoring and basic metrics

Phase 2: Core Workers
- [x] Chunking workers using existing logic
- [x] Embedding workers with model selection/cache/batching
- [x] Storage workers with transactional writes
- [x] Error handling and retries

Phase 3: User Awareness
- [x] Priority calculation (tier/usage/age)
- [x] Per-user quotas and concurrent job limits
- [ ] Fair scheduling refinements (aging within queues)
- [ ] Admin APIs for quota/priority inspection

Phase 4: Advanced Features
- [ ] Streaming partial results for very large media
- [ ] Intelligent global batching across jobs for GPU efficiency
- [ ] Auto-scaling policies based on queue depths and saturation (initial loop exists)
- [ ] DLQ and reprocessing tools

## Migration & Rollback

Parallel run
1) Run API-only path for standard requests; run orchestrator for media batch embeddings.
2) Gradually shift larger/longer media jobs to queue path.
3) Observe metrics and error profiles; compare P95/P99.

Rollback
- Kill orchestrator workers; drain queues; route back to API path. Keep feature flags/toggles at the routing layer.

Data consistency
- Enforce idempotent writes in storage; validate collection counts vs. expected chunk totals. Provide verification tools for reindex.

## Testing Strategy

- Unit tests for Job Manager priority/quotas and schema validation.
- Integration tests per worker stage; end-to-end with Redis Streams (ephemeral container in CI).
- Property tests for dedupe/idempotency on replay and for backoff behavior.
- Load tests: synthetic large media to validate GPU/CPU saturation and autoscaling.

## Risks & Mitigations

- Stream backlog growth → autoscale and alerts, shed load by tier.
- Provider failures → circuit breaker, fallback models, cached embeddings.
- Memory pressure → dynamic batch size, model unload timers, GPU pinning.
- Multi-tenant contention → quotas, per-user concurrency caps, priority aging.

## Open Questions / Next Steps

- Align with generic Jobs module (`Docs/Design/Jobs-Module-1.md`): reuse leases/DB persistence where appropriate or keep Redis Streams for this pipeline and bridge via adapters.
- Define DLQ schema and operator workflows.
- Formalize idempotency keys/constraints at storage layer.
- [ ] Build user dashboard for job tracking

### Phase 4: Advanced Features (Week 7-8)
- [ ] Implement streaming for large results
- [ ] Add intelligent batching for GPU efficiency
- [ ] Create auto-scaling based on queue depth
- [ ] Build comprehensive monitoring dashboard

## Migration Strategy

### Parallel Running Approach
1. Deploy new system alongside existing
2. Route percentage of traffic to new system
3. Monitor performance and errors
4. Gradually increase traffic percentage
5. Deprecate old system after validation

### Rollback Plan
- Feature flags for instant rollback
- Queue draining procedures
- Data consistency verification
- Performance baseline comparison

## Monitoring and Alerting

### Key Metrics
- **Queue Depth**: Jobs waiting per queue
- **Processing Time**: P50, P95, P99 per stage
- **Model Utilization**: GPU/CPU usage per model
- **Error Rates**: Failures per worker type
- **User Metrics**: Jobs per user, wait times by tier

### Alerts
- Queue depth > threshold
- Worker failures > threshold
- GPU memory > 90%
- Processing time > SLA
- Model loading failures

## Security Considerations

1. **Job Isolation**: Ensure jobs cannot access other users' data
2. **Resource Limits**: Prevent DoS through quota enforcement
3. **Model Security**: Validate model sources and checksums
4. **API Security**: Secure internal worker APIs

## Performance Targets

- **Throughput**: 1000 embedding jobs/minute
- **Latency**: < 5s for small texts, < 30s for documents
- **Availability**: 99.9% uptime
- **Scalability**: Linear scaling up to 10 workers per type

## Cost Optimization

1. **Spot Instances**: Use for non-critical workloads
2. **Model Sharing**: Maximize model reuse across users
3. **Batch Processing**: Group similar requests
4. **Tiered Storage**: Archive old embeddings to cheaper storage

## Future Enhancements

1. **Multi-Region**: Deploy workers across regions
2. **Edge Processing**: Client-side embeddings for privacy
3. **Model A/B Testing**: Test new models on subset of traffic
4. **Adaptive Scaling**: ML-based prediction of load patterns
