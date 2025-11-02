**Embeddings Module - Developer README**

This module implements both the production embeddings path (OpenAI-compatible API) and a scale-out worker pipeline. It focuses on reliability (circuit breaker, retries), performance (TTL cache, connection pooling, batching), and observability (metrics, health, DLQ tools).

**Status**
- Active: production API `tldw_Server_API/app/api/v1/endpoints/embeddings_v5_production_enhanced.py`
- Ready-to-wire: Redis/worker pipeline (`workers/`, orchestrator) for horizontal scale

**Key Files**
- API: `tldw_Server_API/app/api/v1/endpoints/embeddings_v5_production_enhanced.py` - REST handlers, TTL cache, circuit breaker, rate limiting, policy/fallback chain, health + admin endpoints (DLQ, metrics, cache control).
- Engine: `tldw_Server_API/app/core/Embeddings/Embeddings_Server/Embeddings_Create.py` - provider adapters (OpenAI, HuggingFace/Transformers, ONNX, Local API), model caching/LRU + memory caps, revision pinning, Qwen3 behaviors, warmup.
- Vector store: `tldw_Server_API/app/core/Embeddings/ChromaDB_Library.py` - per-user Chroma management (with in-memory stub for tests), safe pathing, collection helpers.
- Infra utils: `connection_pool.py`, `request_batching.py`, `rate_limiter.py`, `multi_tier_cache.py`, `circuit_breaker.py`, `metrics_integration.py`, `audit_adapter.py`, `request_signing.py`.
- Workers (pipeline): `workers/{base_worker,chunking_worker,embedding_worker,storage_worker}.py`, `worker_config.py`, `worker_orchestrator.py`, `job_manager.py`, `queue_schemas.py`, `messages.py`.
- Services: `services/{reembed_worker.py, reembed_consumer.py, vector_compactor.py}` - re-embed expansion, scheduled re-embed, vector cleanup for soft-deleted media.
- DB helpers: `media_embedding_jobs_db.py`, `vector_store_{meta,batches}_db.py`.

**Production API Behavior**
- Providers: OpenAI; HuggingFace (Transformers); ONNX via `optimum`/`onnxruntime`; Local API. Endpoint maps `provider:model` when non-OpenAI.
- Cache: in-process TTL cache (default 3600s, size 5000) with background cleanup and hit/miss/size metrics.
- Fault tolerance: per-provider circuit breaker; retries with exponential backoff; connection pool reuse (aiohttp sessions).
- Policy + fallback: allowlists/denylists by provider/model; optional fallback chain (e.g., HF → OpenAI) with header override control.
- Rate limiting: optional global/tenant RPS; per-request limiter guarded by `EMBEDDINGS_RATE_LIMIT`/`EMBEDDINGS_TENANT_RPS`.
- Inputs: strings or list[str] (up to internal caps). `dimensions` honored where supported (e.g., OpenAI t-e-3). Optional base64 output.
- Qwen3 specifics: instruction-aware formatting per text and last-token pooling when model id matches a Qwen3 Embedding variant; prompts loaded from `Config_Files/Prompts/embeddings.prompts.yaml`.

**Public Endpoints**
- `POST /api/v1/embeddings` - create embeddings (OpenAI-compatible payload/response).
- `GET /api/v1/embeddings/models` - list allowed models/providers.
- Admin: `POST /api/v1/embeddings/models/{warmup,download}`, `DELETE /api/v1/embeddings/cache`, `GET /api/v1/embeddings/{metrics,circuit-breakers}`, `POST /api/v1/embeddings/circuit-breakers/{provider}/reset`.
- Health: `GET /api/v1/embeddings/health` - cache size, breaker states.

**Media Embeddings**
- See `tldw_Server_API/app/api/v1/endpoints/media_embeddings.py` - chunks text with the Chunking module, embeds, and persists to per-user Chroma (or pgvector via RAG storage adapters). Includes status and simple job tracking.

**Scale-Out Worker Pipeline**
- Stages: chunking → embedding → storage (Redis Streams per stage, DLQs mirrored per stage).
- Queues and schema: `queue_schemas.py`, `messages.py` define typed messages, job status, metrics payloads, and idempotency/ledger keys.
- Workers: `workers/` run stage loops with heartbeats, batch processing, and Prometheus stage metrics.
- Orchestration: `worker_orchestrator.py` manages worker pools (scales up/down), exposes queue depth, liveness gauges, and requeue token bucket.
- Re-embed: `services/reembed_worker.py` (Jobs-driven) expands re-embed jobs into stage messages; `services/reembed_consumer.py` (stream-driven) supports an older request/scheduled stream.
- Compactor: `services/vector_compactor.py` periodically deletes vectors for soft-deleted media.

**Indexing & Storage (RAG integration)**
- Vector stores: local Chroma by default; pgvector supported by RAG factory (configure under `RAG.vector_store_type=pgvector` and `RAG.pgvector.*`).
- Incremental re-embed: compare `metadata.content_hash` to skip unchanged chunks (see `services/reembed_worker.py`).
- FTS helpers: optional synonyms, weighting, and title/content boosts live in Media DB and RAG modules.

**Environment Variables**
- Throughput/limits: `EMBEDDINGS_MAX_BATCH_SIZE` (default 100), `EMBEDDINGS_CONNECTION_POOL_SIZE` (default 50), `EMBEDDINGS_REQUEST_TIMEOUT` (default 30s), `EMBEDDINGS_MAX_RETRIES` (default 3).
- Cache: `EMBEDDINGS_CACHE_TTL_SECONDS` (3600), `EMBEDDINGS_CACHE_MAX_SIZE` (5000), `EMBEDDINGS_CACHE_CLEANUP_INTERVAL` (300), `EMBEDDINGS_TTLCACHE_DAEMON` (`true` to run cleaner thread).
- Policy: `EMBEDDINGS_ENFORCE_POLICY` (`true|false`), `EMBEDDINGS_ENFORCE_POLICY_STRICT` (`true` disables admin bypass), `EMBEDDINGS_ALLOW_FALLBACK_WITH_HEADER`.
- Dimensions: `EMBEDDINGS_DIMENSION_POLICY` (`reduce|pad|ignore`, default `reduce`).
- Rate limiting/backpressure: `EMBEDDINGS_RATE_LIMIT=on`, `EMBEDDINGS_TENANT_RPS`, `EMB_BACKPRESSURE_MAX_DEPTH`, `EMB_BACKPRESSURE_MAX_AGE_SECONDS`, `EMB_ORCH_MAX_SCAN_KEYS`.
- Warmup/models: `PRELOAD_EMBEDDING_MODELS`, `AUTO_DOWNLOAD_MODELS` (default `true`), `TRUSTED_HF_REMOTE_CODE_MODELS` (patterns for `trust_remote_code`).
- Storage/testing: `CHROMADB_FORCE_STUB`, `TESTING`, `USE_REAL_OPENAI_IN_TESTS`.
- Redis/queues: `REDIS_URL`, `EMBEDDING_LIVE_QUEUE` (default `embeddings:embedding`), DLQ stream names, `EMBEDDINGS_LEDGER_TTL_SECONDS`.
- Re-embed and compactor: `REEMBED_*` (e.g., `REEMBED_JOB_QUEUE`, `REEMBED_LEASE_SECONDS`, `REEMBED_SKIP_UNCHANGED`), `EMBEDDINGS_COMPACTOR_INTERVAL_SECONDS`, `COMPACTOR_USER_ID`, `MEDIA_DB_PATH`.

**Notes and Constraints**
- Accept only string inputs (or list[str]) at the endpoint; token arrays are not surfaced publicly.
- `dimensions` is provider-specific; HF/ONNX outputs are fixed by the model.
- Provider/model allowlists are strict in tests; in normal mode, enforcement is configurable.

**Testing**
- End-to-end: `tldw_Server_API/tests/e2e/test_embeddings_e2e.py` (upload → embed → verify RAG search).
- Chroma helpers and claim embeddings: `tldw_Server_API/tests/Claims/test_claim_embeddings_chroma.py`.
- RAG integration (pgvector multi-search): `tldw_Server_API/tests/RAG_NEW/integration/test_retriever_pgvector_multi_search.py`.
- Usage reporting: `tldw_Server_API/tests/Admin/test_llm_usage_endpoints.py` logs `embeddings` usage.
- For deterministic tests, set `TESTING=true` and avoid real OpenAI with `USE_REAL_OPENAI_IN_TESTS!=true`.

**Adding a New Provider**
- Engine: extend `Embeddings_Create.py` with a provider adapter (lazy-load heavy deps), implement batch creation, add to provider map.
- API: wire provider/model mapping + policy in `embeddings_v5_production_enhanced.py` (max tokens, dimension behavior, fallback chain).
- Config: add defaults in project settings; optionally add warmup support.
- Tests: unit test adapter behavior (mock upstream), add endpoint tests; ensure metrics and circuit breaker labels are correct.

**Operational Tips**
- Prefer smaller `MAX_BATCH_SIZE` when upstreams throttle; tune circuit breaker thresholds to avoid thrash.
- Pin HF revisions (`revision`) for reproducibility; restrict `trust_remote_code` via `TRUSTED_HF_REMOTE_CODE_MODELS`.
- Monitor: scrape Prometheus metrics from API and workers; watch DLQ depth, queue age, breaker trips.

**Security & Privacy**
- Validate `user_id` and `model_id` inputs (see `ChromaDB_Library.validate_user_id`, endpoint validators).
- Avoid logging raw inputs or secrets; DLQ payloads can be encrypted (`dlq_crypto`).
