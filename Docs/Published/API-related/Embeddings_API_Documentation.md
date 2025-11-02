# Embeddings API Documentation

## Overview

The tldw_server Embeddings API provides an OpenAI-compatible interface for generating text embeddings with caching, metrics, and a circuit breaker around provider calls.

Status (current):
- Supported: string inputs (single or list), token-array inputs, optional base64 encoding, TTL cache, health + metrics (admin), model listing, model metadata, provider fallback, collection management (ChromaDB), and a batch endpoint.
- Not implemented: a dedicated cache stats endpoint (cache stats are available via health/metrics), a generic “test” endpoint.
- Dimensions: server-side dimension adjustment works across providers using a configurable policy (`reduce`, `pad`, or `ignore`).

## Authentication

Authentication follows the server’s AuthNZ mode:
- Single-user mode: include `X-API-KEY: <your_key>` header
- Multi-user mode: include `Authorization: Bearer <JWT>` header
All endpoints require authentication; some endpoints are admin-only and enforce additional checks.

## Key Concepts

### What are Embeddings?

Embeddings are dense vector representations of text that capture semantic meaning. They enable:
- Semantic search and similarity comparisons
- Clustering and classification
- Recommendation systems
- RAG (Retrieval-Augmented Generation) systems

### Token Array Inputs

Token arrays are the numerical representation of text after tokenization. In the tokenization process:

1. **Text Input**: `"Hello, world!"`
2. **Tokenization**: Text is split into tokens: `["Hello", ",", " world", "!"]`
3. **Token IDs**: Each token maps to a vocabulary ID: `[15339, 11, 1917, 0]`

This API accepts token IDs directly. This is useful when:
- You've pre-tokenized text for efficiency
- You're working with token-level operations
- You need to maintain exact tokenization consistency across systems
- You're integrating with systems that work with token IDs

## API Endpoints

### 1. Create Embeddings

**Endpoint**: `POST /api/v1/embeddings`

**Description**: Generate embeddings for text inputs (strings or token arrays, single or list). Optional base64 encoding. When `dimensions` is set, the API applies a server-side dimension policy: `reduce` (slice), `pad` (zero-pad), or `ignore` (no change). Default policy: `reduce`.

#### Request Body

```json
{
  "input": string | string[],
  "model": string,
  "encoding_format": "float" | "base64",  // optional, default: "float"
  "dimensions": number,  // optional; OpenAI supports it for text-embedding-3-*; server can apply post-process policy across providers
  "user": string  // optional
}
```

#### Input Formats

The `input` field supports multiple formats:

1. **Single String**:
```json
{
  "input": "Hello, world!",
  "model": "text-embedding-3-small"
}
```

2. **Array of Strings** (max 2048 items):
```json
{
  "input": ["First text", "Second text", "Third text"],
  "model": "text-embedding-3-small"
}
```

3. **Token Array** (single tokenized text):
```json
{
  "input": [15339, 11, 1917, 0],
  "model": "text-embedding-3-small"
}
```

4. **Batch Token Arrays** (multiple tokenized texts):
```json
{
  "input": [
    [15339, 11, 1917, 0],     // "Hello, world!"
    [1115, 374, 264, 1296],   // "This is a test"
    [315, 279, 40188, 5446]   // "of the embeddings API"
  ],
  "model": "text-embedding-3-small"
}
```

#### Response

```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "embedding": [0.0023064255, -0.009327292, ...],  // or base64 string
      "index": 0
    }
  ],
  "model": "text-embedding-3-small",
  "usage": {
    "prompt_tokens": 12,
    "total_tokens": 12
  }
}
```

Response headers (when applicable):
- `X-Embeddings-Provider`: actual provider used
- `X-Embeddings-Fallback-From`: original provider if fallback occurred
- `X-Embeddings-Dimensions-Policy`: the dimension policy applied (`reduce`, `pad`, `ignore`)

### 2. Batch Embeddings

**Endpoint**: `POST /api/v1/embeddings/batch`

**Description**: Create embeddings for a batch of texts (strings only; use array inputs on the standard endpoint for token arrays).

**Request Body**
```json
{
  "texts": ["First request text", "Second"],
  "model": "text-embedding-3-small",
  "provider": "openai",
  "dimensions": 512
}
```

**Response**
```json
{
  "embeddings": [[0.1, 0.2, ...], [0.05, -0.12, ...]],
  "model": "text-embedding-3-small",
  "provider": "openai",
  "count": 2
}
```

### 3. List Models

**Endpoint**: `GET /api/v1/embeddings/models`

**Description**: List known models with allowlist/default flags.

#### Response

```json
{
  "data": [
    { "provider": "openai", "model": "text-embedding-3-small", "allowed": true, "default": true },
    { "provider": "openai", "model": "text-embedding-3-large", "allowed": true, "default": false },
    { "provider": "huggingface", "model": "sentence-transformers/all-MiniLM-L6-v2", "allowed": true, "default": false }
  ],
  "allowed_providers": null,
  "allowed_models": null
}
```

Note: In responses, the `model` field is the OpenAI model id for OpenAI requests. For non-OpenAI providers, the response `model` is prefixed with the provider (e.g., `"huggingface:sentence-transformers/all-MiniLM-L6-v2"`).

### 4. Provider/Model Configuration

**Endpoint**: `GET /api/v1/embeddings/providers-config`

**Description**: Return default provider/model and the enabled providers with their models (from simplified embeddings configuration).

---

Cache statistics are not exposed via a dedicated endpoint. For cache/operational stats, see `GET /api/v1/embeddings/health` and `GET /api/v1/embeddings/metrics` (admin).

### 5. Clear Cache

**Endpoint**: `DELETE /api/v1/embeddings/cache`

**Description**: Clear the embedding cache (admin only).

#### Response

```json
{
  "message": "Cache cleared successfully",
  "entries_removed": 1250
}
```
Notes:
- When the embeddings implementation is unavailable (e.g., optional dependencies not installed), this endpoint returns HTTP 503 and `status: "degraded"`.

### 6. Model Metadata

**Endpoint**: `GET /api/v1/embeddings/models/{model_id}`

**Description**: Return provider autodetection, dimension, and max tokens for the given model.

Example response:
```json
{
  "model": "text-embedding-3-small",
  "provider": "openai",
  "dimension": 1536,
  "max_tokens": 8192,
  "allowed": true
}
```

### 7. Health Check

**Endpoint**: `GET /api/v1/embeddings/health`

**Description**: Check if the embeddings service is operational.

#### Response

```json
{
  "status": "healthy",
  "service": "embeddings_v5_production_enhanced",
  "timestamp": "2024-01-01T12:00:00Z",
  "cache_stats": { "size": 123, "max_size": 5000, "ttl_seconds": 3600 },
  "active_requests": 2,
  "circuit_breakers": { "openai": { "state": "closed", "failure_count": 0 } }
}
```

### 8. Collections (ChromaDB)

Manage per-user ChromaDB collections associated with embeddings.

- Create collection (admin not required)
  - POST `/api/v1/embeddings/collections`
  - Body: `{ "name": "my_collection", "metadata": {"domain": "news"}, "embedding_model": "text-embedding-3-small", "provider": "openai" }`
  - Response 201: `{ "name": "my_collection", "metadata": {"provider": "openai", "embedding_model": "text-embedding-3-small", "embedding_dimension": 1536, "domain": "news" } }`

- List collections
  - GET `/api/v1/embeddings/collections`
  - Response 200: `[ { "name": "my_collection", "metadata": {...} }, ... ]`

- Delete collection
  - DELETE `/api/v1/embeddings/collections/{collection_name}`
  - Response 204 (no body)

- Collection stats
  - GET `/api/v1/embeddings/collections/{collection_name}/stats`
  - Response 200: `{ "name": "my_collection", "count": 123, "embedding_dimension": 1536, "metadata": {...} }`

### 9. Circuit Breakers (admin)

- Get circuit breaker status (all providers)
  - GET `/api/v1/embeddings/circuit-breakers`
  - Admin only; returns state, failure counts, and timestamps by provider

- Reset a provider’s circuit breaker
  - POST `/api/v1/embeddings/circuit-breakers/{provider}/reset`
  - Admin only; returns a confirmation message

### 10. Model Warmup/Download (admin)

- Warmup a model (preload and validate)
  - POST `/api/v1/embeddings/models/warmup`
  - Body: `{ "model": "text-embedding-3-small", "provider": "openai" }`

- Download/prepare a model
  - POST `/api/v1/embeddings/models/download`
  - Body: `{ "model": "sentence-transformers/all-MiniLM-L6-v2", "provider": "huggingface" }`

## Advanced Features

### Dimension Adjustment

For `text-embedding-3-*` models, you can specify a lower dimension count to reduce the embedding size:

```json
{
  "input": "Text to embed",
  "model": "text-embedding-3-small",
  "dimensions": 512  // Reduces from 1536 to 512 dimensions
}
```

**How it works**: The API applies the configured policy: `reduce` slices the first-N dimensions; `pad` zero-pads up to `dimensions`; `ignore` leaves vectors unchanged. Set policy with `EMBEDDINGS_DIMENSION_POLICY` env var. The response includes `X-Embeddings-Dimensions-Policy`.

**Benefits**:
- Reduced storage requirements
- Faster similarity computations
- Lower memory usage
- Minimal loss of semantic information

### Batch Processing

The API automatically processes large input lists in optimized batches:
- Batch size: 100 items per batch (sequential across batches)
- Provider backends may parallelize internally
- Automatic chunking for inputs > 100 items

### Caching

The API implements an in-memory TTL cache:
- Cache size: 5,000 entries (default)
- TTL: 1 hour (3600 seconds)
- Cache key: Hash of (text, provider, model, dimensions)
- Background cleanup of expired entries and metrics for hit/size

### Rate Limiting

- Disabled by default; enable with `EMBEDDINGS_RATE_LIMIT=on`.
- When enabled, requests may receive HTTP 429 depending on configured policy.

## Working with Token Arrays

### Converting Text to Token Arrays

Using Python with tiktoken:

```python
import tiktoken

# Get the tokenizer for a specific model
encoding = tiktoken.encoding_for_model("text-embedding-3-small")

# Tokenize text
text = "Hello, world!"
tokens = encoding.encode(text)
print(tokens)  # [15339, 11, 1917, 0]

# Decode tokens back to text
decoded = encoding.decode(tokens)
print(decoded)  # "Hello, world!"
```

### When to Use Token Arrays

1. **Pre-tokenization for Performance**: When processing large volumes of text, pre-tokenizing can reduce API processing time.

2. **Consistency Across Systems**: When you need exact tokenization matches between different parts of your system.

3. **Token-Level Operations**: When working with token-level features like attention masks or position embeddings.

4. **Integration with LLMs**: When your embeddings need to align with LLM tokenization for tasks like RAG.

### Example: Using Token Arrays with the API

```python
import requests
import tiktoken

# Prepare token arrays
encoding = tiktoken.encoding_for_model("text-embedding-3-small")
texts = ["Hello, world!", "This is a test", "of the embeddings API"]
token_arrays = [encoding.encode(text) for text in texts]

# Send to API
response = requests.post(
    "http://localhost:8000/api/v1/embeddings",
    json={
        "input": token_arrays,
        "model": "text-embedding-3-small",
        "dimensions": 512
    },
    headers={"Authorization": "Bearer YOUR_JWT_OR_API_KEY", "X-API-KEY": "YOUR_API_KEY_IF_SINGLE_USER"}
)

embeddings = response.json()["data"]
```

## Errors

### Input Too Long
If an input exceeds the model’s maximum tokens, the API returns a top-level error object:

```json
{
  "error": "input_too_long",
  "message": "One or more inputs exceed max tokens 8192 for model text-embedding-3-small",
  "details": [
    { "index": 0, "tokens": 9000 }
  ]
}
```

Other errors follow standard HTTP error shapes (e.g., `{ "detail": "..." }` for validation errors).

## Error Handling

The API returns standard HTTP status codes:

- `200 OK`: Successful request
- `400 Bad Request`: Invalid input or parameters
- `401 Unauthorized`: Missing or invalid authentication
- `404 Not Found`: Model not found or not configured
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error during processing

Error responses include detailed messages. For some validation cases, a top-level JSON error object is returned:

```json
{
  "error": "input_too_long",
  "message": "One or more inputs exceed max tokens 8192 for model text-embedding-3-small",
  "details": [{"index": 0, "tokens": 12000}]
}
```

## Performance Considerations

1. **Batch Requests**: Use batch endpoints or array inputs for multiple texts
2. **Dimension Reduction**: Reduce dimensions when full precision isn't needed
3. **Caching**: Frequently requested embeddings are cached automatically
4. **Token Arrays**: Pre-tokenize when processing large volumes
5. **Model Selection**:
   - `text-embedding-3-small`: Best for most use cases
   - `text-embedding-3-large`: When highest quality is needed
   - `text-embedding-ada-002`: Legacy compatibility

## Configuration

The embeddings service can be configured in `config.txt`:

```ini
[Embeddings]
embedding_model = text-embedding-3-small
embedding_provider = openai
embedding_api_key = your-api-key-here
embedding_api_url = https://api.openai.com/v1/embeddings  # For OpenAI
# embedding_api_url = http://localhost:8080/v1/embeddings  # For local models
```

## Migration Guide

### From Standard Text Input to Token Arrays

1. **Install tiktoken**: `pip install tiktoken`
2. **Get appropriate tokenizer**: Use `tiktoken.encoding_for_model()`
3. **Tokenize your text**: Use `encoding.encode(text)`
4. **Send token arrays**: Pass integer arrays to the API
5. **Process results**: Same embedding format as text input

### From OpenAI API

This API is OpenAI-compatible. In most cases you can:
1. Change the base URL to your tldw_server instance
2. Keep your existing payloads (string inputs, `dimensions`, `encoding_format`)
3. Optional: use `x-provider` header or `provider:model` prefix (e.g., `huggingface:sentence-transformers/all-MiniLM-L6-v2`)
4. Optional: use token arrays (`List[int]` or `List[List[int]]`) when pre-tokenizing improves performance

## Best Practices

1. **Use Appropriate Models**: Choose based on quality vs. performance needs
2. **Batch When Possible**: Group multiple texts in single requests
3. **Cache Strategically**: Leverage caching for repeated queries
4. **Reduce Dimensions**: Use dimension reduction for large-scale applications
5. **Pre-tokenize for Scale**: Use token arrays when processing large volumes
6. **Monitor Usage**: Track token usage and cache hit rates
7. **Handle Errors Gracefully**: Implement retry logic for transient failures

## Examples

### Python Client Example

```python
import requests
from typing import List, Union

class EmbeddingsClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        # For single-user mode, set X-API-KEY. For multi-user, set Authorization: Bearer <JWT>.
        # Choose exactly one of the lines below based on your deployment:
        # self.headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        # self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def create_embeddings(
        self,
        input: Union[str, List[str], List[int], List[List[int]]],
        model: str = "text-embedding-3-small",
        dimensions: int = None
    ) -> List[List[float]]:
        """Create embeddings for input text or token arrays."""

        payload = {
            "input": input,
            "model": model
        }

        if dimensions:
            payload["dimensions"] = dimensions

        response = requests.post(
            f"{self.base_url}/api/v1/embeddings",
            json=payload,
            headers=self.headers
        )
        response.raise_for_status()

        data = response.json()
        return [item["embedding"] for item in data["data"]]

# Usage
client = EmbeddingsClient("http://localhost:8000", "your-api-key")

# Text input
embeddings = client.create_embeddings("Hello, world!")

# Token-array inputs are supported; pass `List[int]` or `List[List[int]]` to `input` when pre-tokenizing helps.

# Batch with dimension reduction
embeddings = client.create_embeddings(
    ["text1", "text2", "text3"],
    dimensions=512
)
```

### cURL Examples

```bash
# Single text input
# Single-user
curl -X POST http://localhost:8000/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{"input": "Hello, world!", "model": "text-embedding-3-small"}'

# Multi-user
curl -X POST http://localhost:8000/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{"input": "Hello, world!", "model": "text-embedding-3-small"}'

# Token-array input (single)
# Single-user (token array)
curl -X POST http://localhost:8000/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{"input": [15339, 11, 1917, 0], "model": "text-embedding-3-small"}'

# Token-array input (batch)
# Single-user (token array batch)
curl -X POST http://localhost:8000/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{"input": [[15339,11,1917,0],[1115,374,264,1296],[315,279,40188,5446]], "model": "text-embedding-3-small", "dimensions": 512}'
```

## Troubleshooting

### Common Issues

1. **"Dimensions parameter not supported"**: Only `text-embedding-3-*` models support dimension reduction
2. **"Token decoding failed"**: Ensure token IDs are valid for the specified model
3. **"Model not found"**: Check that the model is configured in your settings
4. **Rate limiting**: Implement exponential backoff for retries
5. **Large inputs failing**: Break into smaller batches (< 100 items)

### Debug Tips

- Check `/api/v1/embeddings/health` for service status (includes cache stats and circuit breaker states)
- Use `/api/v1/embeddings/metrics` (admin) for detailed counters and gauges
- Response headers may include `X-Embeddings-Provider`, `X-Embeddings-Fallback-From`, and `X-Embeddings-Dimensions-Policy`

## Related Documentation

- [RAG API Guide](./RAG-API-Guide.md)
- [API Design Guide](./API_Design.md)
- [AuthNZ API Guide](./AuthNZ-API-Guide.md)

### 9. Re-Embed Scheduling (Jobs)

Admin-only endpoint to schedule a re-embed expansion job via the Jobs module. The expansion worker reads the job, fetches original chunks for the media, and enqueues new embedding-stage messages directly to the pipeline.

Note: allow the queue and start the worker
- Set one of:
  - `JOBS_ALLOWED_QUEUES_EMBEDDINGS=reembed`
  - `JOBS_ALLOWED_QUEUES=reembed`
- Start the worker: set `EMBEDDINGS_REEMBED_WORKER_ENABLED=true` (integrated) or run `python -m tldw_Server_API.app.core.Embeddings.services.reembed_worker`.

Endpoint: `POST /api/v1/embeddings/reembed/schedule`

Description: Create a Jobs row (`domain=embeddings`, `queue=reembed`, `job_type=expand_reembed`). Returns the created job info.

Request Body
```json
{
  "media_id": 123,
  "priority": 50,
  "user_id": "1",
  "idempotency_key": "reembed:1:123:hf:stella",
  "dedupe_key": "reembed:1:123:hf:stella",
  "operation_id": "uuid-optional",
  "user_tier": "free",
  "embedder_name": "huggingface",
  "embedder_version": "dunzhang/stella_en_400M_v5"
}
```

Response
```json
{
  "id": 42,
  "uuid": "a9b5e8c0-...",
  "status": "queued",
  "domain": "embeddings",
  "queue": "reembed",
  "job_type": "expand_reembed"
}
```

Authorization
- Single-user: `X-API-KEY` with admin privileges (single user is treated as admin).
- Multi-user: `Authorization: Bearer <JWT>` for an admin user.

## Version History

- **v0.1**: OpenAI-compatible endpoint, token arrays support, batch endpoint, caching, health/metrics, circuit breaker, provider fallback
### Provider Selection

Choose a provider in one of two ways:
- Header: set `x-provider: openai | huggingface | onnx | local_api` (common options; additional providers may be available if configured)
- Model prefix: use `provider:model` form (e.g., `huggingface:sentence-transformers/all-MiniLM-L6-v2`)

If neither is supplied, the server auto-detects from the model name (common HF patterns) or defaults to OpenAI.

Notes:
- Header `x-provider` applies to the standard create endpoint (`POST /embeddings`). The batch endpoint accepts `provider` in the request body.

---
Last Updated: October 2025
