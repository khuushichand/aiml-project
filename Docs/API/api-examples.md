# API Examples

Practical curl examples for the most common tldw_server operations.  All examples assume the server is running at `http://localhost:8000`.

## Authentication

### Single-User Mode (API Key)

Pass the key via the `X-API-KEY` header:

```bash
curl -H "X-API-KEY: $TLDW_API_KEY" \
     http://localhost:8000/api/v1/media/search?query=hello
```

### Multi-User Mode (JWT)

Obtain a token:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=changeme" | jq -r .access_token)
```

Use the token:

```bash
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/media/search?query=hello
```

## Media Ingestion

### Ingest a YouTube Video

```bash
curl -X POST http://localhost:8000/api/v1/media/process \
  -H "X-API-KEY: $TLDW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
    "transcribe": true,
    "summarize": true,
    "api_name": "openai",
    "keywords": ["music", "video"]
  }'
```

### Ingest a Local File

```bash
curl -X POST http://localhost:8000/api/v1/media/process \
  -H "X-API-KEY: $TLDW_API_KEY" \
  -F "file=@/path/to/document.pdf" \
  -F "keywords=research,paper"
```

### Search Ingested Content

```bash
curl -G http://localhost:8000/api/v1/media/search \
  -H "X-API-KEY: $TLDW_API_KEY" \
  --data-urlencode "query=machine learning" \
  -d "limit=10"
```

## Chat Completions

### Basic Chat (OpenAI-Compatible)

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "X-API-KEY: $TLDW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Summarise the key ideas of reinforcement learning."}
    ],
    "max_tokens": 500
  }'
```

### Streaming Chat

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/completions \
  -H "X-API-KEY: $TLDW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Tell me a short story."}
    ],
    "stream": true
  }'
```

## RAG Search

### Unified RAG Search

```bash
curl -X POST http://localhost:8000/api/v1/rag/search \
  -H "X-API-KEY: $TLDW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are transformer architectures?",
    "search_type": "hybrid",
    "top_k": 5
  }'
```

## Audio

### Transcribe an Audio File

```bash
curl -X POST http://localhost:8000/api/v1/audio/transcriptions \
  -H "X-API-KEY: $TLDW_API_KEY" \
  -F "file=@/path/to/audio.mp3" \
  -F "model=whisper-1"
```

### Text-to-Speech

```bash
curl -X POST http://localhost:8000/api/v1/audio/speech \
  -H "X-API-KEY: $TLDW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Hello, welcome to tldw server.",
    "voice": "alloy",
    "model": "tts-1"
  }' \
  --output speech.mp3
```

## Admin Operations

### List Roles

```bash
curl http://localhost:8000/api/v1/admin/roles \
  -H "X-API-KEY: $TLDW_API_KEY"
```

### Get Cleanup Settings

```bash
curl http://localhost:8000/api/v1/admin/cleanup-settings \
  -H "X-API-KEY: $TLDW_API_KEY"
```

### Update Registration Settings

```bash
curl -X POST http://localhost:8000/api/v1/admin/registration-settings \
  -H "X-API-KEY: $TLDW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "open_registration": false,
    "require_email_verification": true
  }'
```

### List LLM Providers

```bash
curl http://localhost:8000/api/v1/llm/providers \
  -H "X-API-KEY: $TLDW_API_KEY"
```

## Embeddings

### Generate Embeddings (OpenAI-Compatible)

```bash
curl -X POST http://localhost:8000/api/v1/embeddings \
  -H "X-API-KEY: $TLDW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "The quick brown fox jumps over the lazy dog.",
    "model": "text-embedding-ada-002"
  }'
```

## Health Check

```bash
curl http://localhost:8000/api/v1/health
```

## Notes

- Replace `$TLDW_API_KEY` with your actual API key.
- All endpoints return JSON unless otherwise noted (e.g., audio/speech returns binary).
- Add `?pretty=true` to most GET endpoints for formatted JSON output.
- See the interactive docs at `http://localhost:8000/docs` for the full OpenAPI schema.
