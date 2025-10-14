# Embeddings System Architecture

This directory contains both the production embeddings path (single-user friendly) and a future, scale-out worker architecture. This document reflects the current production behavior and APIs.

## Current Status

- ACTIVE: Single-user/monolithic API using `tldw_Server_API/app/api/v1/endpoints/embeddings_v5_production_enhanced.py`
- WIP: Multi-user scale-out worker system (implemented here but not wired to public API routes)

## Production Embeddings API (Active)

The production path is an OpenAI-compatible REST API with caching, connection pooling, and a circuit breaker around provider calls.

### Key Files
- API: `tldw_Server_API/app/api/v1/endpoints/embeddings_v5_production_enhanced.py`
- Core engine: `tldw_Server_API/app/core/Embeddings/Embeddings_Server/Embeddings_Create.py`
- Vector store helpers: `tldw_Server_API/app/core/Embeddings/ChromaDB_Library.py`

### What Works Today
- Providers: OpenAI and HuggingFace via Transformers; ONNX (optimum + onnxruntime) and Local API supported by the core engine. Provider names like Cohere/Google/Mistral/Voyage are scaffolded in the endpoint but not fully integrated in the engine yet.
- Caching: TTL cache (default TTL 3600s, size 5000) with metrics for hits/size.
- Fault tolerance: Circuit breaker per provider; automatic connection cleanup and retries for transient failures.
- Metrics: Prometheus counters/histograms/gauges (requests, duration, cache, active requests).
- Input validation: strings or list[str] only; up to 2048 inputs; per-model token limits with clear error payload when exceeded; optional base64 encoding of vectors; L2-normalization for float outputs.
- Rate limiting: Optional (off by default). Enable with `EMBEDDINGS_RATE_LIMIT=on`.

### Qwen3 Embeddings (Transformers)
- When the HuggingFace model id contains `Qwen3` and `Embedding` (e.g., `Qwen/Qwen3-Embedding-0.6B`), the engine:
  - Applies an instruction-aware format per text using keys in `Config_Files/Prompts/embeddings.prompts.yaml`:
    - `qwen3_embeddings_instruction` (default: “Given a web search query, retrieve relevant passages that answer the query”).
    - `qwen3_embeddings_mode` (`auto` | `document` | `query`).
      - `auto`: heuristically formats short question-like inputs as `<Query>:`; others as `<Document>:`.
  - Uses last-token pooling instead of mean pooling for Qwen3.
- No ChatML system/assistant blocks are used for embeddings.

### Public Endpoints
- `POST /api/v1/embeddings` — Create embeddings (OpenAI-compatible schema). For non-OpenAI providers, the `model` field in the response includes a `provider:model` prefix.
- `GET /api/v1/embeddings/models` — List known/allowed models and defaults.
- Admin-only:
  - `POST /api/v1/embeddings/models/warmup`
  - `POST /api/v1/embeddings/models/download`
  - `DELETE /api/v1/embeddings/cache`
  - `GET /api/v1/embeddings/metrics`
  - `GET /api/v1/embeddings/circuit-breakers`
  - `POST /api/v1/embeddings/circuit-breakers/{provider}/reset`
- Health: `GET /api/v1/embeddings/health` (reports cache stats and circuit-breaker status)

### Notes and Constraints
- Token arrays as input are not currently supported by the endpoint (even though the Pydantic schema allows them). Send strings only.
- `dimensions` in the request is passed through but only applies to specific providers (e.g., OpenAI text-embedding-3); for HF/ONNX it does not alter output size.
- Provider/model allowlists exist via settings but are enforced only in test mode with API key headers.

## Media Embeddings (Batching for uploaded media)

For generating and storing per-chunk embeddings of ingested media, use:
- `tldw_Server_API/app/api/v1/endpoints/media_embeddings.py`

This endpoint chunks media text with the chunking module, calls the same embeddings engine, and writes to per-user ChromaDB collections. It exposes status and simple job-tracking for media embedding runs.

## Scale-Out Worker System (WIP)

The scale-out design (not exposed via public API routes yet) follows a fan-out pipeline:
1. Chunking workers — prepare text chunks
2. Embedding workers — generate vectors (model pooling, batching)
3. Storage workers — persist to ChromaDB and SQL

Key components:
- Job Manager: `job_manager.py` — job lifecycle, quotas, scheduling (WIP)
- Workers: `workers/` — `base_worker.py`, `chunking_worker.py`, `embedding_worker.py`, `storage_worker.py`
- Queue Schemas: `queue_schemas.py` — typed messages between stages
- Orchestrator: `worker_orchestrator.py` — pool management, metrics, graceful shutdown

These pieces are present for future horizontal scaling but are not hooked up to `/api/v1/embeddings` today.

## Future Enhancements
- Additional first-class providers (Cohere/Google/Mistral/Voyage)
- Policy/allowlist enforcement outside test mode
- Multi-region deployment
- Advanced model routing based on content
- Real-time streaming of results
- Edge processing capabilities
- A/B testing framework for models

## Environment Variables
- `EMBEDDINGS_RATE_LIMIT`: `on` to enable per-endpoint rate limiting (default `off`).
- `EMBEDDINGS_DIMENSION_POLICY`: `reduce` | `pad` | `ignore` (default `reduce`) for post-hoc dimension adjustment.
- `EMBEDDINGS_ENFORCE_POLICY`: `true|false` to enforce provider/model allowlists (defaults to `true` in tests, `false` otherwise); `EMBEDDINGS_ENFORCE_POLICY_STRICT` disables admin bypass when `true`.
- `PRELOAD_EMBEDDING_MODELS`: Comma-separated list of models to warm up on startup (CI-only by default).
- `AUTO_DOWNLOAD_MODELS`: `true|false` to auto-download models during CI warmup (default `true`).
- `TRUSTED_HF_REMOTE_CODE_MODELS`: List of patterns to enable `trust_remote_code` for HuggingFace models.
- `CHROMADB_FORCE_STUB`: `true|false` to force in-memory Chroma stub for tests.
- `TESTING` / `USE_REAL_OPENAI_IN_TESTS`: When `TESTING=true` and `USE_REAL_OPENAI_IN_TESTS!=true`, OpenAI embeddings are deterministically synthesized.
- `EMBEDDINGS_CACHE_TTL_SECONDS`: Override cache TTL (default 3600).
- `EMBEDDINGS_CACHE_MAX_SIZE`: Override cache max entries (default 5000).
- `EMBEDDINGS_CACHE_CLEANUP_INTERVAL`: Override cache cleanup interval seconds (default 300).
- `EMBEDDINGS_MAX_BATCH_SIZE`: Maximum uncached texts processed per internal batch (default 100).
