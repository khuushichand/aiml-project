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
- Conversation metadata API: list/search, tree view, analytics, and knowledge-save under `/api/v1/chat/conversations` and `/api/v1/chat/analytics` (alias: `/api/v1/chats/conversations`)
  - Includes ranking modes (`bm25|recency|hybrid|topic`) and topic/state filters

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

#### Media Ingestion - `/api/v1/media`

- `POST /api/v1/media/add` - ingest and persist media (synchronous)
- `POST /api/v1/media/ingest/jobs` - async ingest (one job per item)
- `GET /api/v1/media/ingest/jobs/{job_id}` - job status
- `DELETE /api/v1/media/ingest/jobs/{job_id}` - cancel job

See: [Media Ingest Jobs API](Media_Ingest_Jobs_API.md)

#### Reading List - `/api/v1/reading`

Reading List supports URL capture, clean text extraction, tagging, import/export, and actions (summarize/TTS).

- `POST /api/v1/reading/save` - save a URL
- `GET /api/v1/reading/items` - list/search items
- `GET /api/v1/reading/items/{id}` - item detail
- `PATCH /api/v1/reading/items/{id}` - update metadata
- `DELETE /api/v1/reading/items/{id}` - delete (soft/hard)
- `POST /api/v1/reading/items/{id}/summarize` - summarize
- `POST /api/v1/reading/items/{id}/tts` - TTS audio
- `POST /api/v1/reading/import` - Pocket/Instapaper import
- `GET /api/v1/reading/export` - JSONL/ZIP export

See: [Reading List API](Reading_List_API.md)
