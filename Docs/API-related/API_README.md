# API Documentation

## Overview

API uses FastAPI framework.
Designed to be simple and easy to use.
Generative endpoints follow openai API spec where possible.
See [API Design](API_Design.md) for more details.

See also:
- `Docs/Code_Documentation/Ingestion_Pipeline_Audio.md` for the audio processing endpoint (`POST /api/v1/media/process-audios`).
- `Docs/API-related/Email_Processing_API.md` for the email processing endpoint (`POST /api/v1/media/process-emails`) and email ingestion via `/media/add`.

### URLs
- **URLs**
    - Main page: http://127.0.0.1:8000
    - API Documentation page: http://127.0.0.1:8000/docs




### Endpoints

#### Chat

- Chat API (OpenAI-compatible): `POST /api/v1/chat/completions`
  - Streaming (SSE), persistence toggle, multi-provider support
  - See: [Chat API Documentation](Chat_API_Documentation.md)

- Character Chat API: sessions and messages under `/api/v1/chats` and `/api/v1/messages`
  - Create/list/update/delete chats, send/edit/delete/search messages
  - Export chat history; fetch messages formatted for completions
  - Use Chat API for LLM replies with `conversation_id`/`character_id`
  - See: [API Design](API_Design.md) for character chat endpoints overview

#### RAG (Retrieval-Augmented Generation) - `/api/v1/rag`

Unified RAG endpoints provide hybrid search (FTS5 + vectors + reranking), optional answer generation, citations, and streaming.

##### Core Endpoints

- `POST /api/v1/rag/search` - Unified search (all features via parameters)
- `POST /api/v1/rag/search/stream` - NDJSON streaming of answer chunks (set `enable_generation=true`)
- `GET /api/v1/rag/simple` - Convenience query param search with sensible defaults
- `GET /api/v1/rag/advanced` - Convenience endpoint with common features enabled (citations/answer)
- `POST /api/v1/rag/batch` - Batch multiple queries concurrently

Notes:
- “Agent” endpoints are not exposed in the current server. Use `/rag/search` with `enable_generation=true` or `/rag/search/stream`.
- Health and ops endpoints are available under `/api/v1/rag/health*` and `/api/v1/rag/cache*`.

For comprehensive documentation, see:
- [RAG API Consumer Guide](RAG-API-Guide.md) - Complete API reference with examples
- [RAG Developer Guide](../Development/RAG-Developer-Guide.md) - Architecture and implementation details
