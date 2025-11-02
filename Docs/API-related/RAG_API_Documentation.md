# RAG API Documentation

**Version**: Unified Pipeline 1.0.0
**Last Updated**: 2025-10-26
**Status**: Production Ready

## Table of Contents

1. Overview
2. Authentication
3. Endpoints
   - Unified Search
   - Streaming Search
   - Batch Search
   - Simple Search
   - Advanced Search
   - Ablations
   - Capabilities
   - Features
   - Implicit Feedback
   - Health & Ops
4. Data Models
5. Streaming Events
6. Configuration
7. Error Handling
8. Examples
9. Migration Guide

## Overview

The RAG (Retrieval-Augmented Generation) API provides hybrid retrieval and optional answer generation across your indexed content. It exposes a single unified pipeline with explicit parameters for all features, plus convenience endpoints for simple and advanced use cases.

Base URL

```
http://localhost:8000/api/v1/rag
```

## Authentication

- Single-user: send `X-API-KEY: <key>`
- Multi-user: send `Authorization: Bearer <JWT>`
- Rate limiting is enforced on search endpoints via centralized dependency checks; limits are configurable and may be bypassed in tests when `TEST_MODE=true`.

## Endpoints

### Unified Search

POST `/api/v1/rag/search`

Single endpoint with all features as parameters (`UnifiedRAGRequest`).

Example request

```json
{
  "query": "machine learning applications",
  "sources": ["media_db", "notes"],
  "search_mode": "hybrid",
  "fts_level": "media",
  "top_k": 10,
  "expand_query": true,
  "enable_reranking": true,
  "reranking_strategy": "flashrank",
  "enable_citations": false,
  "enable_generation": false
}
```

Example response (UnifiedRAGResponse)

```json
{
  "documents": [
    {
      "id": "doc_123",
      "content": "Full document content...",
      "metadata": {"title": "ML Applications", "source": "media_db"},
      "score": 0.92
    }
  ],
  "query": "machine learning applications",
  "expanded_queries": ["machine learning applications", "ML applications"],
  "metadata": {"cache_hit": false, "sources_searched": ["media_db", "notes"]},
  "timings": {"retrieval": 0.234, "reranking": 0.089, "total": 0.456}
}
```

### Streaming Search

POST `/api/v1/rag/search/stream`

Streams NDJSON events (media type `application/x-ndjson`). Requires `enable_generation: true` in the request body.

Emitted events

- `{"type":"delta","text":"..."}` - incremental tokens/chunks
- `{"type":"claims_overlay", ...}` - rolling claim verification overlay when claims are enabled
- `{"type":"final_claims", ...}` - final claim verification summary
- May also emit early context/rationale events when available:
  - `{"type":"contexts", "contexts":[{id,title,score,url,source},...], "why":{...}}`
  - `{"type":"plan", "plan": {...}}` and `{"type":"reasoning", "plan":["..."]}`
  - `{"type":"spans", "count": N, "provenance": [...]}`

### Batch Search

POST `/api/v1/rag/batch`

Process multiple queries concurrently (`UnifiedBatchRequest`). All parameters from the single search apply to each query.

Example request

```json
{
  "queries": ["What is AI?", "Explain neural networks"],
  "max_concurrent": 5,
  "top_k": 5,
  "enable_reranking": true
}
```

### Simple Search

GET `/api/v1/rag/simple?query=...&top_k=10`

Returns `{"query": str, "documents": [...], "count": int}`.

### Advanced Search

GET `/api/v1/rag/advanced?query=...&with_citations=true&with_answer=true`

Returns unified response with common features enabled (expansion, citations, generated answer).

### Ablations

POST `/api/v1/rag/ablate`

Compares retrieval/generation across baseline, reranked, and agentic modes. Body fields include: `query`, `top_k`, `search_mode`, `with_answer`, `agentic_top_k_docs`, `agentic_window_chars`, `agentic_max_tokens_read`, `reranking_strategy`.

### Capabilities

GET `/api/v1/rag/capabilities`

Returns supported features, defaults, limits, auth mode, and quick-start bodies. Includes info about agentic chunking, reranking strategies (`flashrank`, `cross_encoder`, `hybrid`, `llama_cpp`), table/VLM settings, caching, streaming endpoint and events.

### Features

GET `/api/v1/rag/features`

Returns a categorized list of features and their parameter names (query expansion, caching, security, citations, generation, reranking, feedback, monitoring, table/VLM processing, enhanced chunking, batch, resilience).

### Implicit Feedback

POST `/api/v1/rag/feedback/implicit`

Records user interaction signals from the WebUI for learning-to-rank and personalization. Body matches `ImplicitFeedbackEvent` (event_type: click|expand|copy; optional `query`, `doc_id`, `rank`, `impression_list`, `corpus`, `user_id`, `session_id`).

### Health & Ops

- GET `/api/v1/rag/health` - comprehensive health (circuit breakers, cache, metrics, batch processor)
- GET `/api/v1/rag/health/live` - liveness
- GET `/api/v1/rag/health/ready` - readiness
- GET `/api/v1/rag/health/simple` - quick pipeline check
- GET `/api/v1/rag/cache/stats` - cache statistics and recommendations
- POST `/api/v1/rag/cache/clear` - clear caches
- GET `/api/v1/rag/cache/warm` - cache warmer status
- GET `/api/v1/rag/metrics/summary` - recent metrics summary
- GET `/api/v1/rag/costs/summary` - LLM API cost summary (when available)
- GET `/api/v1/rag/batch/jobs` - batch job states

## Data Models

Key requests and responses (summarized):

- UnifiedRAGRequest - main POST body
  - Required: `query`
  - Sources: `sources` one or more of `media_db`, `notes`, `characters`, `chats` (aliases: `media` → `media_db`, `character_cards` → `characters`)
  - Search config: `search_mode` (`fts`|`vector`|`hybrid`), `fts_level` (`media`|`chunk`), `hybrid_alpha`, `top_k`, `min_score`, `enable_intent_routing`
  - Expansion & caching: `expand_query`, `expansion_strategies`, `spell_check`, `enable_cache`, `cache_threshold`, `adaptive_cache`
  - Filtering: `keyword_filter`, `include_media_ids`, `include_note_ids`
  - Security: `enable_security_filter`, `detect_pii`, `redact_pii`, `sensitivity_level`, `content_filter`
  - Table/VLM: `enable_table_processing`, `table_method` (`markdown`|`html`|`hybrid`), `enable_vlm_late_chunking`, `vlm_backend`, `vlm_detect_tables_only`, `vlm_max_pages`, `vlm_late_chunk_top_k_docs`
  - Context: `chunk_type_filter`, `enable_parent_expansion`, `parent_context_size`, `include_sibling_chunks`, `sibling_window`, `include_parent_document`, `parent_max_tokens`
  - Agentic: `strategy` (`standard`|`agentic`), `agentic_top_k_docs`, `agentic_window_chars`, `agentic_max_tokens_read`, `agentic_max_tool_calls`, `agentic_extractive_only`, `agentic_quote_spans`, `agentic_debug_trace`
  - Advanced retrieval: `enable_multi_vector_passages`, `mv_span_chars`, `mv_stride`, `mv_max_spans`, `mv_flatten_to_spans`, `enable_numeric_table_boost`
  - Reranking: `enable_reranking`, `reranking_strategy` (`flashrank`|`cross_encoder`|`hybrid`|`llama_cpp`|`llm_scoring`|`two_tier`|`none`), `rerank_top_k`, `reranking_model`, `rerank_min_relevance_prob`, `rerank_sentinel_margin`
  - Citations: `enable_citations`, `citation_style`, `include_page_numbers`, `enable_chunk_citations`
  - Generation: `enable_generation`, `strict_extractive`, `generation_model`, `generation_prompt`, `max_generation_tokens`, `enable_abstention`, `abstention_behavior`, `enable_multi_turn_synthesis`, `synthesis_*`
  - Claims & NLI: `enable_claims`, `claim_extractor`, `claim_verifier`, `claims_top_k`, `claims_conf_threshold`, `claims_max`, `claims_concurrency`, `nli_model`
  - Post-verification: `enable_post_verification`, `adaptive_*`, `low_confidence_behavior`
  - Feedback/monitoring/perf: `collect_feedback`, `feedback_user_id`, `apply_feedback_boost`, `enable_monitoring`, `enable_observability`, `trace_id`, `enable_performance_analysis`, `timeout_seconds`
  - Convenience: `highlight_results`, `highlight_query_terms`, `track_cost`, `debug_mode`
  - Resilience: `enable_resilience`, `retry_attempts`, `circuit_breaker`
  - User context: `user_id`, `session_id`, `corpus`, `index_namespace`

- UnifiedRAGResponse - includes `documents`, `query`, `expanded_queries`, `metadata`, `timings`; may also include `citations`, `academic_citations`, `chunk_citations`, `generated_answer`, `feedback_id`, `cache_hit`, `errors`, `security_report`, `total_time`, `claims`, `factuality`.

- UnifiedBatchRequest / UnifiedBatchResponse - for `/batch`.

## Streaming Events

The streaming endpoint returns NDJSON lines. Clients should parse line-by-line and dispatch by `type`.

- Text stream: `delta`
- Claims overlay: `claims_overlay`, `final_claims`
- Early context/rationale (may appear for agentic/explain flows): `contexts`, `plan`, `reasoning`, `spans`

Notes

- `search/stream` requires `enable_generation=true` or returns 400 with `enable_generation must be true for streaming.`
- Media type is `application/x-ndjson`.

## Configuration

Configuration is loaded from `Config_Files/config.txt` and environment variables. `/rag/capabilities` reflects effective defaults.

- Contextual defaults (parent/sibling expansion)
  - `RAG_INCLUDE_PARENT_DOCUMENT` (bool)
  - `RAG_PARENT_MAX_TOKENS` (int)
  - `RAG_INCLUDE_SIBLING_CHUNKS` (bool)
  - `RAG_SIBLING_WINDOW` (int)
  - `RAG_DEFAULT_FTS_LEVEL` (`media`|`chunk`)

- Retriever and cache (see `RAG_SERVICE_CONFIG`)
  - `retriever.hybrid_alpha`, `retriever.fts_top_k`, `retriever.vector_top_k`
  - `cache.cache_ttl`, `cache.max_cache_size`, `cache.cache_search_results`

- VLM late chunking (table detection)
  - `VLM_TABLE_MODEL_NAME` (e.g., `microsoft/table-transformer-detection`)
  - `VLM_TABLE_REVISION`
  - `VLM_TABLE_THRESHOLD` (default `0.9`)

- Claims (optional)
  - Model/provider overrides for extractor/verifier and budgets via Claims block in config.

## Error Handling

- 400 for validation errors or unsupported combinations (e.g., streaming without `enable_generation`)
- 401/403 for authentication/authorization failures
- 429 when rate limit exceeded
- 500 on internal errors

## Examples

### cURL

```bash
# Simple search
curl -G http://localhost:8000/api/v1/rag/simple \
  -H "X-API-Key: your-api-key" \
  --data-urlencode "query=machine learning"

# Unified search (hybrid)
curl -X POST http://localhost:8000/api/v1/rag/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "query": "deep learning vs machine learning",
    "search_mode": "hybrid",
    "fts_level": "media",
    "top_k": 20,
    "enable_reranking": true,
    "reranking_strategy": "cross_encoder"
  }'

# Streaming with claims overlay
curl -N -X POST http://localhost:8000/api/v1/rag/search/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "query": "Summarize key findings of ResNet",
    "strategy": "agentic",
    "enable_generation": true,
    "enable_claims": true,
    "claims_top_k": 5
  }'

# Health check
curl http://localhost:8000/api/v1/rag/health -H "X-API-Key: your-api-key"
```

### JavaScript/TypeScript

```typescript
interface SearchRequest {
  query: string;
  top_k?: number;
}

async function search(request: SearchRequest): Promise<any> {
  const params = new URLSearchParams({ query: request.query, top_k: String(request.top_k ?? 10) });
  const response = await fetch(`http://localhost:8000/api/v1/rag/simple?${params.toString()}`, {
    headers: { 'X-API-Key': 'your-api-key' }
  });
  return response.json();
}
```

## Migration Guide

From legacy RAG docs to the unified pipeline

- Endpoints: use `POST /api/v1/rag/search` (primary), `POST /api/v1/rag/search/stream` (NDJSON), `GET /simple`, `GET /advanced`, `POST /batch`.
- Strategy selection: `strategy` is `standard` (default) or `agentic` (query-time synthetic chunking and explain traces).
- Search types: replace legacy `search_type` with `search_mode` (`fts`|`vector`|`hybrid`) and optional `fts_level` (`media`|`chunk`).
- Reranking: use `reranking_strategy` among `flashrank`, `cross_encoder`, `hybrid`, `llama_cpp`, `llm_scoring`, `two_tier`, or `none`.
- Sources: valid values are `media_db`, `notes`, `characters`, `chats` (aliases handled as noted above).
