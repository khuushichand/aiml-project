# Embeddings API Documentation

## Overview

The tldw_server Embeddings API provides an OpenAI-compatible interface for generating text embeddings with caching, metrics, and a circuit breaker around provider calls.

Status:
- Supported today: string inputs (single or list), OpenAI and HuggingFace providers, optional base64 encoding, TTL cache, health/metrics/admin endpoints, model listing.
- Not supported: token-array inputs, generic batch endpoint (`/embeddings/batch`), explicit cache stats endpoint, generic test endpoint. Dimension reduction is provider-specific and may be ignored by non-OpenAI providers.

## Key Concepts

### What are Embeddings?

Embeddings are dense vector representations of text that capture semantic meaning. They enable:
- Semantic search and similarity comparisons
- Clustering and classification
- Recommendation systems
- RAG (Retrieval-Augmented Generation) systems

### Token Array Inputs (not currently supported)

Token arrays are the numerical representation of text after tokenization. In the tokenization process:

1. **Text Input**: `"Hello, world!"`
2. **Tokenization**: Text is split into tokens: `["Hello", ",", " world", "!"]`
3. **Token IDs**: Each token maps to a vocabulary ID: `[15339, 11, 1917, 0]`

This API does not currently accept token IDs directly. The following content is kept for future consideration. It would be useful when:
- You've pre-tokenized text for efficiency
- You're working with token-level operations
- You need to maintain exact tokenization consistency across systems
- You're integrating with systems that work with token IDs

## API Endpoints

### 1. Create Embeddings

**Endpoint**: `POST /api/v1/embeddings`

**Description**: Generate embeddings for text inputs (strings or list of strings). Optional base64 encoding; dimensions affect specific providers only (e.g., OpenAI text-embedding-3).

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

### 2. Batch Embeddings

Not implemented. Send multiple inputs in one request to `POST /api/v1/embeddings` (max 2048 items).

#### Request Body

Array of embedding requests (max 10):

```json
[
  {
    "input": "First request text",
    "model": "text-embedding-3-small",
    "dimensions": 512
  },
  {
    "input": [15339, 11, 1917, 0],  // Token array
    "model": "text-embedding-3-large",
    "dimensions": 1024
  }
]
```

#### Response

Array of embedding responses corresponding to each request.

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

### 4. Cache Statistics

Not implemented as a dedicated endpoint. See `GET /api/v1/embeddings/health` and `GET /api/v1/embeddings/metrics` (admin) for cache/operational stats.

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

### 6. Test Endpoint

**Endpoint**: `POST /api/v1/embeddings/test` (not implemented)

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

### Dimension Reduction

For `text-embedding-3-*` models, you can specify a lower dimension count to reduce the embedding size:

```json
{
  "input": "Text to embed",
  "model": "text-embedding-3-small",
  "dimensions": 512  // Reduces from 1536 to 512 dimensions
}
```

**How it works**: The API uses truncation (following OpenAI's approach) which preserves the most important dimensions. This is based on Matryoshka Representation Learning where earlier dimensions capture more important information.

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

Error responses include detailed messages:

```json
{
  "detail": "Dimensions parameter is only supported for text-embedding-3-* models, not text-embedding-ada-002"
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

This API is fully compatible with OpenAI's embeddings API. Simply:
1. Change the base URL to your tldw_server instance
2. All existing code should work without modification
3. Additional features (token arrays, caching) are available when needed

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

# Token-array inputs are not supported by the current endpoint (strings only)

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

# Token-array input examples are intentionally omitted (not supported)
```

## Troubleshooting

### Common Issues

1. **"Dimensions parameter not supported"**: Only `text-embedding-3-*` models support dimension reduction
2. **"Token decoding failed"**: Ensure token IDs are valid for the specified model
3. **"Model not found"**: Check that the model is configured in your settings
4. **Rate limiting**: Implement exponential backoff for retries
5. **Large inputs failing**: Break into smaller batches (< 100 items)

### Debug Tips

- Use `/api/v1/embeddings/test` endpoint to verify functionality
- Check `/api/v1/embeddings/health` for service status
- Monitor `/api/v1/embeddings/cache/stats` for cache performance
- Enable debug logging for detailed request/response info

## Related Documentation

- [RAG Service Documentation](./RAG_Service_Documentation.md)
- [API Design Guide](./API_Design.md)
- [Authentication Documentation](./Authentication_Documentation.md)

## Version History

- **v3.0**: Added token array input support, enhanced documentation
- **v2.0**: Added dimension reduction, batch processing, caching
- **v1.0**: Initial OpenAI-compatible implementation
