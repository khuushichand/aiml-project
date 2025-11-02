# RAG API Documentation

**Version**: 3.0
**Last Updated**: 2025-08-19
**Status**: Production Ready

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Authentication](#authentication)
4. [Endpoints](#endpoints)
   - [Unified Search](#unified-search)
   - [Streaming Search](#streaming-search)
   - [Batch Search](#batch-search)
   - [Simple Search](#simple-search)
   - [Advanced Search](#advanced-search)
   - [Capabilities & Features](#capabilities--features)
   - [Health Check](#health-check)
5. [Data Models](#data-models)
6. [Configuration](#configuration)
7. [Error Handling](#error-handling)
8. [Performance](#performance)
9. [Examples](#examples)
10. [Migration Guide](#migration-guide)

## Overview

The RAG (Retrieval-Augmented Generation) API provides powerful search and AI-powered question-answering capabilities across your indexed content. It uses a **functional pipeline architecture** where composable functions are chained together to create custom retrieval workflows.

### Key Features

- **Functional Pipeline**: Composable pure functions for flexible workflows
- **Hybrid Search**: Combines keyword (FTS5) and semantic search for optimal results
- **Multi-Database Support**: Search across media, notes, prompts, and character cards
- **Query Expansion**: Automatic enhancement with synonyms, acronyms, and domain terms
- **Smart Caching**: Semantic cache with adaptive thresholds
- **Document Reranking**: Multiple strategies for relevance optimization
- **Resilience**: Optional circuit breakers and retry logic for production
- **Performance Monitoring**: Built-in metrics and timing analysis

### Base URL

```
http://localhost:8000/api/v1/rag
```

## Architecture

The RAG API uses a functional pipeline architecture:

```
Query → [Expand] → [Cache Check] → [Retrieve] → [Rerank] → [Cache Store] → Response
           ↓           ↓              ↓            ↓            ↓
      (optional)  (optional)    (required)   (optional)   (optional)
```

Pre-built wrappers (for convenience):
- **/simple**: sensible defaults for quick lookups
- **/advanced**: common features enabled (expansion, citations, answer)
The primary API is a single unified endpoint where all features are parameters.

## Authentication

In single-user mode (default), generate a strong API key and set it via `SINGLE_USER_API_KEY`:

```bash
export SINGLE_USER_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

Use that value when calling the API:

```http
X-API-Key: YOUR_API_KEY
```

In multi-user mode, use JWT Bearer tokens:

```http
Authorization: Bearer <your-jwt-token>
```

## Endpoints

### Unified Search

POST `/api/v1/rag/search`

Single endpoint with all features as parameters (UnifiedRAGRequest).

Example request:

```json
{
  "query": "machine learning applications",
  "sources": ["media_db", "notes"],
  "search_mode": "hybrid",
  "top_k": 10,
  "expand_query": true,
  "enable_reranking": true,
  "enable_citations": false
}
```

Example response (UnifiedRAGResponse):

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

Streams NDJSON events. Requires `enable_generation: true` in the request.

Events:
- `{"type":"delta","text":"..."}`
- `{"type":"claims_overlay", ...}` (when claims enabled)
- `{"type":"final_claims", ...}`

### Batch Search

POST `/api/v1/rag/batch`

Process multiple queries concurrently (UnifiedBatchRequest).

```json
{
  "queries": ["What is AI?", "Explain neural networks"],
  "max_concurrent": 5,
  "top_k": 5,
  "enable_reranking": true
}
```

#### Configuration Options

##### Pipeline Selection
- `minimal` - Basic retrieval and reranking
- `standard` - Includes caching and query expansion
- `quality` - All features enabled
- `enhanced` - Advanced chunking and parent retrieval
- `custom` - Build your own (specify functions)

##### Custom Pipeline
```json
{
  "pipeline": "custom",
  "custom_functions": [
    "expand_query",
    "check_cache",
    "retrieve_documents",
    "process_tables",
    "rerank_documents",
    "store_in_cache"
  ]
}
```

#### Response

```json
{
  "results": [
    {
      "id": "doc_123",
      "content": "Full document content...",
      "source": "media_db",
      "metadata": {
        "title": "ML Applications",
        "author": "John Doe",
        "date": "2024-01-15",
        "media_type": "video",
        "duration": 3600,
        "tags": ["ml", "ai", "tutorial"]
      },
      "score": 0.92,
      "relevance_scores": {
        "bm25": 0.88,
        "vector": 0.94,
        "rerank": 0.95
      },
      "chunk_info": {
        "chunk_id": 5,
        "total_chunks": 10,
        "chunk_type": "paragraph"
      }
    }
  ],
  "total_results": 15,
  "metadata": {
    "pipeline_used": "quality",
    "cache_hit": false,
    "query_expanded": true,
    "expansion_count": 3,
    "databases_searched": ["media_db", "notes"],
    "reranking_applied": true,
    "processing_time": 0.456,
    "component_timings": {
      "query_expansion": 0.023,
      "cache_lookup": 0.012,
      "retrieval": 0.234,
      "reranking": 0.089,
      "total": 0.456
    }
  },
  "debug_info": {
    "original_query": "machine learning applications",
    "expanded_queries": [
      "machine learning applications",
      "ML apps",
      "artificial intelligence applications"
    ],
    "search_stats": {
      "documents_retrieved": 50,
      "documents_after_filtering": 30,
      "documents_after_reranking": 15
    }
  }
}
```

### Simple Search

GET `/api/v1/rag/simple?query=...&top_k=10`

Returns `{"query": str, "documents": [...], "count": int}`.

### Advanced Search

GET `/api/v1/rag/advanced?query=...&with_citations=true&with_answer=true`

Returns unified response with common features enabled.

### Capabilities & Features {#capabilities--features}

GET `/api/v1/rag/capabilities` - service capabilities, defaults, limits

GET `/api/v1/rag/features` - available feature list and parameters

### Health Check

GET `/api/v1/rag/health`

Sample response:

```json
{
  "status": "healthy",
  "timestamp": "2025-08-19T12:00:00",
  "version": "1.0.0",
  "components": {
    "cache": {"status": "healthy", "hit_rate": 0.45, "size": 123},
    "metrics": {"status": "healthy", "recent_queries": 42},
    "batch_processor": {"status": "healthy", "active_jobs": 0, "success_rate": 1.0}
  }
}
```

Additional health endpoints:
- GET `/api/v1/rag/health/simple`
- GET `/api/v1/rag/health/live`
- GET `/api/v1/rag/health/ready`
- GET `/api/v1/rag/cache/stats`
- POST `/api/v1/rag/cache/clear`

## Data Models

Key requests and responses:

- UnifiedRAGRequest: unified POST body with fields like `query`, `sources`, `search_mode`, `top_k`, `expand_query`, `enable_reranking`, `enable_citations`, `enable_generation`, `enable_claims`, etc.
- UnifiedRAGResponse: fields include `documents`, `query`, `expanded_queries`, `metadata`, `timings`, `citations`, `generated_answer` (optional), `cache_hit`, `errors`, `total_time`.
- UnifiedBatchRequest / UnifiedBatchResponse: for POST `/batch`.

## Configuration

### Environment Variables

```bash
# API Configuration
TLDW_API_HOST=0.0.0.0
TLDW_API_PORT=8000

# Database Paths
MEDIA_DB_PATH=/path/to/media.db
NOTES_DB_PATH=/path/to/notes.db

# Cache Settings
ENABLE_CACHE=true
CACHE_TTL=3600
CACHE_SIZE=1000

# Performance
MAX_WORKERS=4
BATCH_SIZE=32

# Resilience
ENABLE_RESILIENCE=true
CIRCUIT_BREAKER_THRESHOLD=5
RETRY_MAX_ATTEMPTS=3
```

### Configuration File (config.toml)

```toml
[rag]
default_pipeline = "standard"
enable_monitoring = true

[rag.retrieval]
default_top_k = 10
min_score = 0.0
use_fts = true
use_vector = false

[rag.expansion]
enabled = true
strategies = ["acronym", "synonym"]
max_expansions = 5

[rag.cache]
enabled = true
threshold = 0.85
adaptive = true
ttl = 3600

[rag.reranking]
enabled = true
strategy = "hybrid"
diversity = 0.3

[rag.resilience]
enabled = false
retry_attempts = 3
circuit_breaker_threshold = 5
```

## Error Handling

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Invalid authentication |
| 404 | Not Found - Resource not found |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |
| 503 | Service Unavailable - Circuit breaker open |

### Error Response Format

```json
{
  "error": {
    "code": "INVALID_QUERY",
    "message": "Query must be between 1 and 1000 characters",
    "details": {
      "field": "query",
      "provided_length": 1500,
      "max_length": 1000
    }
  },
  "request_id": "req_123456",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Common Error Codes

- `INVALID_QUERY` - Query validation failed
- `DATABASE_ERROR` - Database connection or query failed
- `CACHE_ERROR` - Cache operation failed
- `RERANKING_ERROR` - Reranking failed
- `CIRCUIT_BREAKER_OPEN` - Service temporarily unavailable
- `RATE_LIMIT_EXCEEDED` - Too many requests

## Performance

### Typical Response Times

| Pipeline | Cache Hit | Cache Miss |
|----------|-----------|------------|
| minimal | 20-30ms | 50-100ms |
| standard | 20-30ms | 200-300ms |
| quality | 30-40ms | 500-800ms |
| enhanced | 40-50ms | 800-1200ms |

### Optimization Tips

1. **Enable Caching**: Dramatically improves response time for repeated queries
2. **Use Minimal Pipeline**: For simple lookups where speed is critical
3. **Batch Requests**: Use batch endpoints for multiple queries
4. **Configure Limits**: Set appropriate `top_k` values
5. **Enable Monitoring**: Track performance metrics

## Examples

### Python Client

```python
import httpx
import asyncio

async def search(query: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/rag/search/simple",
            json={"query": query},
            headers={"X-API-Key": "your-api-key"}
        )
        return response.json()

# Simple search
results = asyncio.run(search("What is RAG?"))

# Complex search with custom config
async def complex_search(query: str):
    config = {
        "pipeline": "quality",
        "expansion": {"strategies": ["acronym", "synonym"]},
        "reranking": {"strategy": "cross_encoder"}
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/rag/search/complex",
            json={"query": query, "config": config},
            headers={"X-API-Key": "your-api-key"}
        )
        return response.json()
```

### cURL Examples

```bash
# Simple search
curl -X POST http://localhost:8000/api/v1/rag/search/simple \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"query": "machine learning"}'

# Unified search (hybrid)
curl -X POST http://localhost:8000/api/v1/rag/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "query": "deep learning vs machine learning",
    "search_mode": "hybrid",
    "top_k": 20,
    "enable_reranking": true,
    "reranking_strategy": "cross_encoder"
  }'

# Health check
curl http://localhost:8000/api/v1/rag/health \
  -H "X-API-Key: your-api-key"
```

### JavaScript/TypeScript

```typescript
interface SearchRequest {
  query: string;
  databases?: string[];
  top_k?: number;
}

async function search(request: SearchRequest): Promise<any> {
  const response = await fetch('http://localhost:8000/api/v1/rag/search/simple', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': 'your-api-key'
    },
    body: JSON.stringify(request)
  });

  return response.json();
}

// Usage
const results = await search({
  query: 'machine learning',
  databases: ['media', 'notes'],
  top_k: 5
});
```

## Migration Guide

### From v2 to v3

The v3 API uses a functional pipeline architecture. Key changes:

1. **Endpoint Consolidation**
   - Old: `/api/v1/rag/v2/search`, `/api/v1/rag/v3/search`
   - New: `/api/v1/rag/search/simple`, `/api/v1/rag/search/complex`

2. **Configuration Structure**
   ```python
   # Old (v2)
   {
     "query": "test",
     "search_type": "hybrid",
     "kwargs": {...}
   }

   # New (v3)
   {
     "query": "test",
     "config": {
       "pipeline": "standard",
       "retrieval": {...}
     }
   }
   ```

3. **Pipeline Selection**
   - v2: Fixed search types (simple, hybrid, semantic)
   - v3: Flexible pipelines (minimal, standard, quality, custom)

4. **Response Format**
   - More detailed metadata
   - Component timings included
   - Debug information available

### Backward Compatibility

For backward compatibility during migration:

1. Use the simple search endpoint for basic queries
2. Map old search types to new pipelines:
   - `simple` → `minimal` pipeline
   - `hybrid` → `standard` pipeline
   - `semantic` → `quality` pipeline with vector search

## Monitoring and Metrics

### Available Metrics

- `rag_queries_total` - Total number of queries processed
- `rag_query_duration_seconds` - Query processing time
- `rag_cache_hits_total` - Cache hit count
- `rag_cache_misses_total` - Cache miss count
- `rag_errors_total` - Error count by type
- `rag_documents_retrieved_total` - Documents retrieved
- `rag_reranking_duration_seconds` - Reranking time

### Logging

Structured logging with levels:
- `DEBUG` - Detailed execution flow
- `INFO` - Normal operations
- `WARNING` - Performance issues, fallbacks
- `ERROR` - Failures requiring attention

### Performance Dashboard

Access metrics at: `http://localhost:8000/metrics`

## Support

For issues or questions:
- GitHub Issues: [tldw_server/issues](https://github.com/your-org/tldw_server/issues)
- Documentation: [Full Documentation](https://docs.tldw-server.com)
- API Status: [status.tldw-server.com](https://status.tldw-server.com)
