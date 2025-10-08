# Embeddings API Documentation

## Overview

The tldw_server Embeddings API provides an OpenAI‑compatible interface for generating text embeddings with caching, metrics, and a circuit breaker around provider calls.

Status (current):
- Supported: string inputs (single or list), token‑array inputs, optional base64 encoding, TTL cache, health + metrics (admin), model listing, model metadata, provider fallback, collection management (ChromaDB), and a batch endpoint.
- Not implemented: a dedicated cache stats endpoint (cache stats are available via health/metrics), a generic “test” endpoint.
- Dimensions: server‑side dimension adjustment works across providers using a configurable policy (`reduce`, `pad`, or `ignore`).

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

**Description**: Generate embeddings for text inputs (strings or token arrays, single or list). Optional base64 encoding. When `dimensions` is set, the API applies a server‑side dimension policy: `reduce` (slice), `pad` (zero‑pad), or `ignore` (no change). Default policy: `reduce`.

#### Request Body

```json
{
  "input": string | string[],
  "model": string,
  "encoding_format": "float" | "base64",  // optional, default: "float"
  "dimensions": number,  // optional, only for text-embedding-3-* models
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
  "message": "Cache cleared",
  "entries_removed": 1250
}
```

### 6. Model Metadata

**Endpoint**: `GET /api/v1/embeddings/models/{model_id}`

**Description**: Return provider autodetection, dimension, and max tokens for the given model.

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

**How it works**: The API applies the configured policy: `reduce` slices the first‑N dimensions; `pad` zero‑pads up to `dimensions`; `ignore` leaves vectors unchanged. Set policy with `EMBEDDINGS_DIMENSION_POLICY` env var. The response includes `X-Embeddings-Dimensions-Policy`.

**Benefits**:
- Reduced storage requirements
- Faster similarity computations
- Lower memory usage
- Minimal loss of semantic information

### Batch Processing

The API automatically processes large input lists in optimized batches:
- Batch size: 100 items per batch
- Parallel processing using ThreadPoolExecutor
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
    headers={"Authorization": "Bearer YOUR_API_KEY"}
)

embeddings = response.json()["data"]
```

## Error Handling

The API returns standard HTTP status codes:

- `200 OK`: Successful request
- `400 Bad Request`: Invalid input or parameters
- `401 Unauthorized`: Missing or invalid authentication
- `404 Not Found`: Model not found or not configured
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error during processing

Error responses include detailed messages. For some validation cases, a top‑level JSON error object is returned:

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

This API is OpenAI‑compatible. In most cases you can:
1. Change the base URL to your tldw_server instance
2. Keep your existing payloads (string inputs, `dimensions`, `encoding_format`)
3. Optional: use `x-provider` header or `provider:model` prefix (e.g., `huggingface:sentence-transformers/all-MiniLM-L6-v2`)
4. Optional: use token arrays (`List[int]` or `List[List[int]]`) when pre‑tokenizing improves performance

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
        self.headers = {"Authorization": f"Bearer {api_key}"}
    
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

# Token‑array inputs are supported; pass `List[int]` or `List[List[int]]` to `input` when pre‑tokenizing helps.

# Batch with dimension reduction
embeddings = client.create_embeddings(
    ["text1", "text2", "text3"],
    dimensions=512
)
```

### cURL Examples

```bash
# Single text input
curl -X POST http://localhost:8000/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "input": "Hello, world!",
    "model": "text-embedding-3-small"
  }'

# Token‑array input (single)
curl -X POST http://localhost:8000/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "input": [15339, 11, 1917, 0],
    "model": "text-embedding-3-small"
  }'

# Token‑array input (batch)
curl -X POST http://localhost:8000/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "input": [[15339,11,1917,0],[1115,374,264,1296],[315,279,40188,5446]],
    "model": "text-embedding-3-small",
    "dimensions": 512
  }'
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

- [RAG API Documentation](./RAG_API_Documentation.md)
- [API Design Guide](./API_Design.md)
- [AuthNZ API Guide](./AuthNZ-API-Guide.md)

## Version History

- **v0.1**: OpenAI‑compatible endpoint, token arrays support, batch endpoint, caching, health/metrics, circuit breaker, provider fallback
### Provider Selection

Choose a provider in one of two ways:
- Header: set `x-provider: openai | huggingface | onnx | local_api`
- Model prefix: use `provider:model` form (e.g., `huggingface:sentence-transformers/all-MiniLM-L6-v2`)

If neither is supplied, the server auto‑detects from the model name (common HF patterns) or defaults to OpenAI.
