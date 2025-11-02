# RAG API Documentation - Unified Pipeline

## Overview

The RAG (Retrieval-Augmented Generation) API provides a unified pipeline where ALL features are accessible through direct parameters. No configuration files, no presets - just explicit parameter control for maximum flexibility.

**Base URL**: `/api/v1/rag/`

## Authentication

All endpoints require authentication (when auth is enabled):
```bash
Authorization: Bearer <your-jwt-token>
```

## Primary Endpoints

### POST `/search` - Unified RAG Search

The main RAG endpoint with complete feature access.

#### Request Schema (matches UnifiedRAGRequest)

```json
{
  // ========== REQUIRED ==========
  "query": "string (1-2000 chars)",

  // ========== DATA SOURCES ==========
  "sources": ["media_db", "notes", "characters", "chats"],  // Default: ["media_db"]

  // ========== SEARCH CONFIGURATION ==========
  "search_mode": "hybrid",  // "fts" | "vector" | "hybrid"
  "hybrid_alpha": 0.7,      // 0=FTS only, 1=Vector only
  "enable_intent_routing": false, // analyze intent and adjust hybrid/top_k
  "top_k": 10,              // Max results (1-100)
  "min_score": 0.0,         // Minimum relevance score

  // ========== QUERY ENHANCEMENT ==========
  "expand_query": false,
  "expansion_strategies": ["acronym", "synonym", "domain", "entity"],
  "spell_check": false,

  // ========== FILTERING ==========
  "keyword_filter": ["term1", "term2"],  // Must contain these keywords

  // ========== CACHING ==========
  "enable_cache": true,
  "cache_threshold": 0.85,    // Semantic similarity threshold (0.0-1.0)

  // ========== DOCUMENT PROCESSING ==========
  "enable_reranking": true,
  "reranking_strategy": "two_tier",  // "flashrank" | "cross_encoder" | "hybrid" | "llm_scoring" | "two_tier" | "llama_cpp"
  "rerank_top_k": 20,             // Docs to rerank (defaults to top_k)
  // Two-Tier request-level overrides (optional)
  "rerank_min_relevance_prob": 0.50,  // minimum calibrated prob to allow generation
  "rerank_sentinel_margin": 0.15,     // minimum (top_prob - sentinel_prob) margin
  // Corpus namespace (enables corpus-specific synonyms for query rewrites)
  "index_namespace": "my_corpus"
  // Advanced retrieval
  "enable_multi_vector_passages": false, // ColBERT-style max-span scoring on retrieved docs
  "enable_numeric_table_boost": false,   // Slight boost for table/number-dense chunks on numeric queries
  "enable_table_processing": false,
  "enable_parent_expansion": false,
  "parent_context_size": 500,      // Characters of parent context
  "include_sibling_chunks": false,
  "sibling_window": 1,
  "include_parent_document": false,
  "parent_max_tokens": 1200,

  // ========== CITATIONS ==========
  "enable_citations": false,
  "citation_style": "apa",  // "apa" | "mla" | "chicago" | "harvard" | "ieee"
  "include_page_numbers": false,
  "enable_chunk_citations": true,

  // ========== GENERATION GUARDRAILS ==========
  "enable_injection_filter": true,          // Down-weight risky chunks pre-generation
  "injection_filter_strength": 0.5,         // Score multiplier for risky chunks
  "require_hard_citations": false,          // Require per-sentence supporting spans (doc_id + offsets)
  "enable_numeric_fidelity": false,         // Verify numeric tokens are present in sources
  "numeric_fidelity_behavior": "continue", // "continue" | "ask" | "decline" | "retry"

  // ========== ANSWER GENERATION ==========
  "enable_generation": false,
  "strict_extractive": false,              // Assemble answer only from retrieved spans (no free-form generation)
  "generation_model": "gpt-4o",     // Model name
  "generation_prompt": "string (optional)",
  "max_generation_tokens": 500,
  // Abstention & multi-turn synthesis (optional)
  "enable_abstention": false,
  "abstention_behavior": "continue",  // "continue" | "ask" | "decline"
  "enable_multi_turn_synthesis": false,
  "synthesis_time_budget_sec": 5.0,
  "synthesis_draft_tokens": 300,
  "synthesis_refine_tokens": 500,

  // ========== POST-VERIFICATION (ADAPTIVE) ==========
  "enable_post_verification": false,
  "adaptive_max_retries": 1,
  "adaptive_unsupported_threshold": 0.15,
  "adaptive_max_claims": 20,
  "adaptive_time_budget_sec": 10.0,
  "low_confidence_behavior": "continue",  // "continue" | "ask" | "decline"
  // Agentic also honors NLI low-confidence gating via the same behavior when claims verification is enabled

  // ========== ADAPTIVE RERUN (LOW CONFIDENCE) ==========
  "adaptive_rerun_on_low_confidence": false,      // Trigger a single rerun when post-verification shows low confidence
  "adaptive_rerun_include_generation": true,      // Include generation in rerun (true) or stop after retrieval/rerank (false)
  "adaptive_rerun_bypass_cache": false,           // Force enable_cache=false for the rerun to avoid stale cache hits
  "adaptive_rerun_time_budget_sec": 5.0,          // Optional soft cap; emits rag_phase_budget_exhausted_total{phase="adaptive_rerun"} on breach
  "adaptive_rerun_doc_budget": 8,                 // Optional: cap docs fed into quick verification during adoption check

  // ========== SECURITY & PRIVACY ==========
  "enable_security_filter": false,
  "detect_pii": false,
  "redact_pii": false,
  "sensitivity_level": "public",    // "public" | "internal" | "confidential" | "restricted"
  "content_filter": false,

  // ========== ANALYTICS & FEEDBACK ==========
  "collect_feedback": false,
  "feedback_user_id": "string (optional)",
  "apply_feedback_boost": false,
  "user_id": "string (optional)",
  "session_id": "string (optional)",

  // ========== PERFORMANCE ==========
  "enable_monitoring": false,
  "enable_observability": false,
  "trace_id": "string (optional)",
  "enable_performance_analysis": false,
  "timeout_seconds": 10.0,
  "debug_mode": false,

  // ========== RESILIENCE ==========
  "enable_resilience": false,
  "retry_attempts": 3,
  "circuit_breaker": false,

  // ========== OUTPUT CONFIGURATION ==========
  "highlight_results": false,
  "highlight_query_terms": false,
  "track_cost": false
}
```

#### Response Schema

```json
{
  "documents": [
    {
      "id": "string",
      "content": "string",
      "metadata": {
        "title": "string",
        "author": "string",
        "date": "string",
        "url": "string",
        // ... additional metadata
      },
      "source": "media_db",  // DataSource enum
      "score": 0.95,         // Relevance score
      "source_document_id": "string",
      "chunk_index": 0,
      "total_chunks": 5,
      "page_number": 42,
      "section_title": "Chapter 3"
    }
  ],
  "query": "original query",
  "expanded_queries": ["expanded", "queries"],
  "metadata": {
    "total_results": 10,
    "search_mode": "hybrid",
    "sources_searched": ["media_db", "notes"],
    "cache_hit": false,
    "reranked": true
  },
  "timings": {
    "total_time": 0.245,
    "retrieval_time": 0.120,
    "reranking_time": 0.085,
    "citation_time": 0.040
  },
  "metadata": {
    // ... other metadata fields
    "post_verification": {
      "unsupported_ratio": 0.2,
      "total_claims": 10,
      "unsupported_count": 2,
      "fixed": false,
      "reason": "threshold_not_exceeded"
    },
    "adaptive_rerun": {
      "performed": true,
      "duration": 1.23,
      "old_ratio": 0.3,
      "new_ratio": 0.15,
      "adopted": true,
      "bypass_cache": true,
      "old_nf_missing": 2,
      "new_nf_missing": 1,
      "old_hard_citation_coverage": 0.6,
      "new_hard_citation_coverage": 0.8,
      "budget_exhausted": false
    },
    "hard_citations": {
      "coverage": 0.75,
      "total": 4,
      "supported": 3,
      "sentences": [
        {
          "text": "WidgetCo revenue reached $10M in 2024.",
          "citations": [ { "doc_id": "doc-1", "start": 120, "end": 148 } ]
        }
      ]
    },
    "numeric_fidelity": {
      "present": ["1234"],
      "missing": ["50%"],
      "source_numbers": ["1234", "3000000", "12%"],
      "retry_docs_added": 3
    }
  },
  "citations": [
    "Smith, J. (2024). Machine Learning Fundamentals. Tech Publications."
  ],
  "chunk_citations": [
    {
      "chunk_id": "doc1",
      "source_document_id": "source1",
      "source_document_title": "ML Introduction",
      "location": "Page 42, Section: Chapter 3",
      "text_snippet": "Machine learning is...",
      "confidence": 0.95,
      "usage_context": "Direct answer to query"
    }
  ],
  "feedback_id": "fb_12345",  // For user feedback collection
  "generated_answer": "Machine learning is a subset of artificial intelligence...",
  "cache_hit": false,
  "errors": [],
  "security_report": {
    "pii_detected": ["email"],
    "content_filtered": false,
    "risk_level": "low"
  },
  "total_time": 0.245
}
```

#### HTTP Status Codes

- `200` - Success
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized
- `422` - Validation Error
- `429` - Rate Limited
- `500` - Internal Server Error

#### Example Requests

**Basic Search**:
```bash
curl -X POST "http://localhost:8000/api/v1/rag/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "sources": ["media_db"],
    "top_k": 5
  }'
```

**Advanced Search with Citations**:
```bash
curl -X POST "http://localhost:8000/api/v1/rag/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain neural networks in detail",
    "sources": ["media_db", "notes"],
    "search_mode": "hybrid",
    "expand_query": true,
    "expansion_strategies": ["acronym", "synonym", "domain"],
    "enable_reranking": true,
    "reranking_strategy": "hybrid",
    "enable_citations": true,
    "citation_style": "apa",
    "enable_chunk_citations": true,
    "enable_generation": true,
    "generation_model": "gpt-4o",
    "top_k": 15
  }'
```

**Abstention with Clarifying Question (Two-Tier gating)**:
```bash
curl -X POST "http://localhost:8000/api/v1/rag/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Summarize obscure topic with little evidence",
    "sources": ["media_db"],
    "search_mode": "hybrid",
    "enable_reranking": true,
    "reranking_strategy": "two_tier",
    "enable_generation": true,
    "enable_abstention": true,
    "abstention_behavior": "ask"
  }'
```

**Multi-Turn Synthesis (draft→critique→refine)**:
```bash
curl -X POST "http://localhost:8000/api/v1/rag/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain topic X",
    "sources": ["media_db"],
    "enable_generation": true,
    "enable_multi_turn_synthesis": true,
    "synthesis_time_budget_sec": 5.0,
    "synthesis_draft_tokens": 256,
    "synthesis_refine_tokens": 512
  }'
```

### POST `/batch` - Batch RAG Processing

Process multiple queries concurrently.

### GET `/vlm/backends` - VLM Backends

List the available Vision-Language (VLM) backends used for PDF table/image detection in VLM late chunking.

Request:
```bash
curl -s -H "X-API-KEY: $API_KEY" \
  http://127.0.0.1:8000/api/v1/rag/vlm/backends | jq
```

Response:
```json
{
  "backends": {
    "hf_table_transformer": { "available": true },
    "docling": { "available": false }
  }
}
```

Notes:
- The capabilities endpoint exposes this route under `features.vlm_late_chunking.backends_endpoint` for discovery.

## Operational Notes

### Two-Tier Reranking and Generation Gating

- `reranking_strategy="two_tier"` performs a fast cross-encoder shortlist (default top 50) followed by an LLM reranker (default top 10) under existing LLM time/doc budgets.
- A sentinel “irrelevant” document is added internally to calibrate low-evidence scenarios. The final score is a calibrated probability of relevance derived from original retrieval score, CE score, and LLM score via a logistic mapping.
- If the top calibrated probability is below `RAG_MIN_RELEVANCE_PROB` (default 0.35) or too close to the sentinel probability (margin < `RAG_SENTINEL_MARGIN`, default 0.10), answer generation is gated.
- Calibration metadata is returned in `metadata.reranking_calibration`.

### Indexing & Chunking

- Adaptive chunking with overlap tuning is enabled by default during ingestion; for media transcripts you can submit a `timecode_map` array in chunk options (server-side integration) to attach `start_time`/`end_time` to chunk metadata.
- Each chunk receives a stable `chunk_uid` for incremental updates.
- Ingest-time deduplication removes near-duplicate chunks (configurable via `INGEST_*` env). Duplicates are annotated with `metadata.duplicate_of`.
- Per-corpus synonyms/aliases: place JSON files under `Config_Files/Synonyms/<corpus>.json` mapping `term -> [aliases]`. When `index_namespace` is set on the request, synonyms and domain expansions will draw from that corpus list.

Environment variables (optional):
- `RAG_TRANSFORMERS_RERANKER_MODEL` (default `BAAI/bge-reranker-v2-m3`)
- `RAG_LLM_RERANK_TIMEOUT_SEC`, `RAG_LLM_RERANK_TOTAL_BUDGET_SEC`, `RAG_LLM_RERANK_MAX_DOCS`
- Calibration weights: `RAG_RERANK_CALIB_BIAS`, `RAG_RERANK_CALIB_W_ORIG`, `RAG_RERANK_CALIB_W_CE`, `RAG_RERANK_CALIB_W_LLM`
- Gating: `RAG_MIN_RELEVANCE_PROB`, `RAG_SENTINEL_MARGIN`

- Production mode: When `tldw_production=true`, retrievers do not use raw SQL fallbacks; they require database adapters. The unified RAG endpoints pass adapters automatically. If you call the unified pipeline directly, pass `media_db` and `chacha_db`.

- LLM reranking guardrails: For `reranking_strategy="llm_scoring"`, per-call timeout, total budget, and max-doc caps apply by default. Tune via environment:
  - `RAG_LLM_RERANK_TIMEOUT_SEC` (default `10`)
  - `RAG_LLM_RERANK_TOTAL_BUDGET_SEC` (default `20`)
  - `RAG_LLM_RERANK_MAX_DOCS` (default `20`)

- Adaptive post-verification: When `enable_post_verification=true`, the service validates claims and may attempt a bounded repair pass. Environment toggles:
  - `RAG_ADAPTIVE_ADVANCED_REWRITES` (default `true`) - enables HyDE + multi-strategy rewrites and diversity during the adaptive pass; set to `false` for a simple, single-query retrieval.
  - `RAG_ADAPTIVE_TIME_BUDGET_SEC` - optional hard cap (seconds) for post-verification.

#### Request Schema

```json
{
  "queries": ["query1", "query2", "query3"],  // Required: list of queries
  "max_concurrent": 3,                        // Max concurrent processing

  // All unified pipeline parameters supported
  "sources": ["media_db"],
  "search_mode": "hybrid",
  "enable_citations": true,
  "citation_style": "apa",
  "top_k": 10
  // ... any other unified pipeline parameters
}
```

#### Response Schema

```json
{
  "results": [
    {
      // Same structure as single search response
      "documents": [...],
      "query": "query1",
      "metadata": {...},
      // ... full unified search result
    },
    // ... results for each query
  ],
  "metadata": {
    "total_queries": 3,
    "successful_queries": 3,
    "failed_queries": 0,
    "total_time": 0.456,
    "concurrent_processing": true
  },
  "errors": [
    {
      "query_index": 1,
      "query": "problematic query",
      "error": "Error message"
    }
  ]
}
```

## Reranking Backends

The unified pipeline supports multiple reranking strategies. Choose via `reranking_strategy` (pipeline) or via HTTP endpoints under `/v1/reranking` (see README for public aliases).

- Strategies
  - `flashrank`: Lightweight neural reranker (fast, CPU-friendly)
  - `cross_encoder`: Transformers-based cross-encoder (GPU recommended)
  - `llama_cpp`: Embedding-based cosine reranker using llama.cpp GGUF models
  - `hybrid`: Combines multiple strategies

- Transformers Cross-Encoder
  - Use `reranking_strategy: "cross_encoder"` and set `reranking_model` to an HF model id (e.g., `BAAI/bge-reranker-v2-m3`)
  - Pipeline loads via sentence-transformers CrossEncoder if available, otherwise raw Transformers
  - Set default via config: `RAG_TRANSFORMERS_RERANKER_MODEL`
  - Typical models: BGE (BAAI/bge-reranker-*), Jina rerankers

- llama.cpp (GGUF)
  - Use `reranking_strategy: "llama_cpp"` and set `reranking_model` to a GGUF file path
  - The pipeline shells out to `llama-embedding` with `--embd-output-format json+` and a separator to score `[query] + documents`
  - Auto-instruct formatting for BGE GGUF (adds `query: ` / `passage: ` prefixes)
  - Default pooling is model-smart (BGE/Jina → mean; Qwen → last). Override via config if needed
  - Set defaults via config keys under `[RAG]` (see README): `llama_reranker_*`

- Backends via HTTP (public aliases)
  - `POST /v1/reranking` accepts `{ backend: "auto|llamacpp|transformers", model, query, documents, top_n }`
  - Auto selection: `.gguf` → llama.cpp; `model` containing `/` (HF id) → transformers

### Configuration Keys (summary)

- Transformers cross-encoder
  - `RAG_TRANSFORMERS_RERANKER_MODEL`: default HF model id

- llama.cpp reranker
  - `RAG_LLAMA_RERANKER_MODEL`, `RAG_LLAMA_RERANKER_BIN`, `RAG_LLAMA_RERANKER_NGL`
  - `RAG_LLAMA_RERANKER_OUTPUT` (default `json+`), `RAG_LLAMA_RERANKER_SEP` (default `<#sep#>`)
  - `RAG_LLAMA_RERANKER_POOLING`, `RAG_LLAMA_RERANKER_NORMALIZE`, `RAG_LLAMA_RERANKER_MAX_DOC_CHARS`
  - `RAG_LLAMA_RERANKER_TEMPLATE_MODE` (auto|bge|jina|none), `RAG_LLAMA_RERANKER_QUERY_PREFIX`, `RAG_LLAMA_RERANKER_DOC_PREFIX`

### GET `/simple` - Simplified Search Interface

Quick search with common parameters only.

#### Query Parameters

- `query` (required): Search query
- `top_k`: Max results (default: 10)

#### Example

```bash
curl "http://localhost:8000/api/v1/rag/simple?query=machine%20learning&top_k=5"
```

### GET `/advanced` - Pre-configured Advanced Search

Advanced search with commonly used features enabled.

#### Query Parameters

Same as simple, plus:
- `expand`: Enable query expansion (true/false)
- `rerank`: Enable reranking (true/false)
- `citations`: Enable citations (true/false)
- `style`: Citation style (mla/apa/chicago/harvard/ieee)

### GET `/features` - Available Features

Get list of all available features and parameters.

#### Response

```json
{
  "features": {
    "query_expansion": {"description": "Synonyms, acronyms, domain, entity", "parameters": ["expand_query", "expansion_strategies", "spell_check"]},
    "caching": {"description": "Semantic cache with adaptive thresholds", "parameters": ["enable_cache", "cache_threshold", "adaptive_cache"]},
    "security": {"description": "PII detection and content filtering", "parameters": ["enable_security_filter", "detect_pii", "redact_pii", "sensitivity_level"]},
    "citations": {"description": "Academic + chunk-level citations", "parameters": ["enable_citations", "citation_style", "include_page_numbers", "enable_chunk_citations"]},
    "generation": {"description": "LLM answer generation", "parameters": ["enable_generation", "generation_model", "generation_prompt", "max_generation_tokens"]},
    "reranking": {"description": "FlashRank, Cross-Encoder, Hybrid", "parameters": ["enable_reranking", "reranking_strategy", "rerank_top_k"]},
    "table_processing": {"description": "Serializable tables", "parameters": ["enable_table_processing", "table_method"]},
    "enhanced_chunking": {"description": "Parent/sibling context controls", "parameters": ["enable_parent_expansion", "include_sibling_chunks", "sibling_window", "include_parent_document", "parent_max_tokens"]},
    "batch_processing": {"description": "Concurrent multi-query"},
    "resilience": {"description": "Retries + circuit breakers", "parameters": ["enable_resilience", "retry_attempts", "circuit_breaker"]}
  },
  "total_features": 12,
  "total_parameters": 50
}
```

### GET `/health` - Health Check

Check health status of all RAG components.

#### Response

```json
{
  "status": "healthy",
  "components": {
    "circuit_breaker_retrieval": {"status": "healthy", "state": "closed", "failure_rate": 0.0},
    "cache": {"status": "healthy", "hit_rate": 0.75, "size": 123},
    "metrics": {"status": "healthy", "recent_queries": 42},
    "batch_processor": {"status": "healthy", "active_jobs": 0, "success_rate": 1.0}
  },
  "version": "1.0.0",
  "timestamp": "2025-01-01T00:00:00Z"
}
```

## Parameter Reference

### Core Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | - | Search query (required) |
| `sources` | array | ["media_db"] | Databases to search |
| `search_mode` | string | "hybrid" | fts, vector, or hybrid |
| `top_k` | integer | 10 | Maximum results (1-100) |

### Query Enhancement

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `expand_query` | boolean | false | Enable query expansion |
| `expansion_strategies` | array | ["acronym"] | Expansion strategies |
| `spell_check` | boolean | false | Correct query spelling |

### Filtering

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `keyword_filter` | array | [] | Required keywords |
|  |  |  |  |

### Caching

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_cache` | boolean | true | Enable semantic caching |
| `cache_threshold` | float | 0.85 | Similarity threshold for cache |
| `cache_ttl` | integer | 3600 | Cache TTL in seconds |

### Document Processing

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_reranking` | boolean | true | Enable document reranking |
| `reranking_strategy` | string | "hybrid" | Reranking algorithm |
| `rerank_top_k` | integer | null | Candidates to rerank (defaults to top_k) |
| `enable_table_processing` | boolean | false | Process table content |
| `enable_parent_expansion` | boolean | false | Include parent context |
| `include_sibling_chunks` | boolean | false | Include adjacent chunk context |
| `sibling_window` | integer | 1 | Sibling window size per side |
| `include_parent_document` | boolean | false | Include full parent when under token limit |
| `parent_max_tokens` | integer | 1200 | Parent inclusion max tokens |

### Citations

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_citations` | boolean | false | Generate academic citations |
| `citation_style` | string | "apa" | Citation format |
| `enable_chunk_citations` | boolean | true | Include chunk citations |

### Answer Generation

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_generation` | boolean | false | Generate answer from retrieved context |
| `generation_model` | string | null | LLM model name |
| `generation_prompt` | string | null | Custom prompt template |
| `max_generation_tokens` | integer | 500 | Max tokens for generated answer |

### Post-Verification (Adaptive)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_post_verification` | boolean | false | Verify generated answer and optionally repair unsupported claims |
| `adaptive_max_retries` | integer | 1 | Max repair attempts (0-3) |
| `adaptive_unsupported_threshold` | float | 0.15 | Trigger when (refuted + NEI)/total_claims exceeds this |
| `adaptive_max_claims` | integer | 20 | Max claims analyzed during post-check |
| `adaptive_time_budget_sec` | number|null | null | Optional hard cap (seconds) for post-check work |
| `low_confidence_behavior` | enum | "continue" | Action when still insufficient after retries: continue | ask | decline |

### Security & Privacy

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `detect_pii` | boolean | false | Detect PII in results |
| `content_filter` | boolean | false | Filter inappropriate/sensitive content |
| `sensitivity_level` | string | "public" | Max sensitivity allowed |
| `redact_pii` | boolean | false | Redact detected PII |

### Performance & Monitoring

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_monitoring` | boolean | false | Collect performance metrics |
| `enable_debug_mode` | boolean | false | Include debug information |

## Error Handling

### Common Error Responses

**Validation Error (422)**:
```json
{
  "detail": [
    {
      "loc": ["body", "top_k"],
      "msg": "ensure this value is less than or equal to 100",
      "type": "value_error.number.not_le",
      "ctx": {"limit_value": 100}
    }
  ]
}
```

**Rate Limited (429)**:
```json
{
  "detail": "Rate limit exceeded. Try again in 60 seconds.",
  "retry_after": 60
}
```

**Internal Error (500)**:
```json
{
  "detail": "Internal server error occurred",
  "error_id": "err_12345",
  "message": "Database connection failed"
}
```

## Rate Limits

- **Search endpoint** (`POST /search`): 30 requests per minute per client
- **Read endpoints** (e.g., `GET /simple`, `GET /advanced`, `GET /features`): 60 requests per minute per client
- **Batch endpoint** (`POST /batch`): 10 requests per minute per client

## Best Practices

### Performance Optimization

1. **Use Caching**: Enable `enable_cache=true` for repeated/similar queries
2. **Embedding Cache**: Embedding caching is automatic in the embeddings subsystem/vector store when enabled; no request flag is needed
3. **Limit Results**: Use appropriate `top_k` values (don't over-fetch)
4. **Batch Processing**: Use `/batch` endpoint for multiple queries

### Security Considerations

1. **PII Detection**: Enable for sensitive data sources
2. **Content Filtering**: Use appropriate filter levels
3. **Authentication**: Always authenticate requests
4. **Input Validation**: Validate query inputs client-side

### Citation Best Practices

1. **Academic Work**: Use `enable_citations=true` with appropriate style
2. **Verification**: Always enable `enable_chunk_citations=true`
3. **Confidence Thresholds**: Adjust `citation_threshold` based on needs
4. **Multiple Styles**: Different styles for different audiences

### Analytics Privacy

1. **User Consent**: Only enable analytics with user consent
2. **Data Minimization**: RAG automatically hashes sensitive data
3. **Retention**: Analytics data follows configured retention policies
4. **Transparency**: Users can see what analytics are collected

## Integration Examples

### Python SDK Example

```python
import httpx
import asyncio

async def search_rag(query: str, **kwargs):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/rag/search",
            json={"query": query, **kwargs}
        )
        return response.json()

# Usage
result = await search_rag(
    "What is machine learning?",
    sources=["media_db", "notes"],
    enable_citations=True,
    citation_style="apa",
    enable_generation=True,
    top_k=10
)
```

### JavaScript Example

```javascript
async function searchRAG(query, options = {}) {
  const response = await fetch('/api/v1/rag/search', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      query,
      ...options
    })
  });

  return response.json();
}

// Usage
const result = await searchRAG("Explain neural networks", {
  sources: ["media_db"],
  enable_citations: true,
  citation_style: "mla",
  top_k: 15
});
```

## Changelog

### v4.0 (Current)
- Unified pipeline architecture
- All features accessible via parameters
- Dual citation system
- Analytics integration
- Performance optimizations
- Batch processing
- Enhanced security features

### v3.0 (Deprecated)
- Functional pipeline with presets
- Limited feature accessibility
- Configuration-based approach

### v2.0 (Legacy)
- Object-oriented architecture
- Complex configuration classes
- Limited API coverage

---

For more information, see:
- [Implementation Status](IMPLEMENTATION_STATUS.md)
- [Main README](README.md)
