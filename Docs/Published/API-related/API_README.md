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

- Anthropic Messages API (Anthropic-compatible): `POST /api/v1/messages` and `POST /v1/messages`
  - Includes `POST /api/v1/messages/count_tokens` and `POST /v1/messages/count_tokens`
  - Native providers: `anthropic`, `llama.cpp`; other providers use OpenAI conversion
  - Note: `/api/v1/messages` (no ID) is reserved for the Anthropic-compatible API; Character Chat uses `/api/v1/chats/{chat_id}/messages` and `/api/v1/messages/{message_id}`
  - See: [Anthropic Messages API](Anthropic_Messages_API.md)

- Character Chat API: sessions under `/api/v1/chats`; messages under `/api/v1/chats/{chat_id}/messages` and `/api/v1/messages/{message_id}`
  - Create/list/update/delete chats, send/edit/delete/search messages
  - Export chat history; fetch messages formatted for completions
  - Use Chat API for LLM replies with `conversation_id`/`character_id`
  - See: [API Design](API_Design.md) for character chat endpoints overview
- Conversation metadata API: list/search, tree view, and analytics under `/api/v1/chat/conversations` and `/api/v1/chat/analytics` (alias: `/api/v1/chats/conversations`)
  - Includes ranking modes (`bm25|recency|hybrid|topic`) and topic/state filters
- Knowledge-save API: `POST /api/v1/chat/knowledge/save`

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

#### Feedback - `/api/v1/feedback` and `/api/v1/rag/feedback/implicit`

Explicit feedback for chat/RAG and implicit feedback signals from the WebUI.

- `POST /api/v1/feedback/explicit` - explicit feedback (helpful/relevance/report)
- `POST /api/v1/rag/feedback/implicit` - implicit events (click/expand/copy/dwell)

See: [Feedback API](Feedback_API.md)

#### Media Ingestion - `/api/v1/media`

- `POST /api/v1/media/add` - ingest and persist media (synchronous)
- `POST /api/v1/media/ingest/jobs` - async ingest (one job per item)
- `GET /api/v1/media/ingest/jobs?batch_id=...` - list jobs for a batch
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

#### Collections Feeds - `/api/v1/collections/feeds`

Collections Feeds wraps Watchlists sources/jobs to ingest RSS/Atom into Collections items with `origin="feed"`.

- `POST /api/v1/collections/feeds` - create a feed subscription
- `GET /api/v1/collections/feeds` - list feed subscriptions
- `GET /api/v1/collections/feeds/{feed_id}` - get a feed subscription
- `PATCH /api/v1/collections/feeds/{feed_id}` - update a feed subscription
- `DELETE /api/v1/collections/feeds/{feed_id}` - delete a feed subscription

See: [Collections Feeds API](Collections_Feeds_API.md)

#### Items - `/api/v1/items`

Unified list across collections (reading list, watchlists, feeds) and Media DB fallback.

- `GET /api/v1/items` - list/search items
- `GET /api/v1/items/{item_id}` - item detail
- `POST /api/v1/items/bulk` - bulk update status/tags/favorite/delete

See: [Items API](Items_API.md)

#### Notes Graph - `/api/v1/notes`

Graph view over notes/tags/sources (stub responses for graph fetches).

- `GET /api/v1/notes/graph` - graph query
- `GET /api/v1/notes/{note_id}/neighbors` - neighbors
- `POST /api/v1/notes/{note_id}/links` - create manual link
- `DELETE /api/v1/notes/links/{edge_id}` - delete manual link

See: [Notes Graph API](Notes_Graph_API.md)

#### Data Tables - `/api/v1/data-tables`

Data Tables provide async LLM-generated tables with export support.

- `POST /api/v1/data-tables/generate` - submit a generation job
- `GET /api/v1/data-tables` - list tables
- `GET /api/v1/data-tables/{table_uuid}` - detail (columns/rows/sources)
- `GET /api/v1/data-tables/{table_uuid}/export` - export CSV/JSON/XLSX
- `GET /api/v1/data-tables/jobs/{job_id}` - job status

See: [Data Tables API](Data_Tables_API.md)

#### File Artifacts - `/api/v1/files`

Create structured files (tables, calendars, images) with optional server-side exports.

- `POST /api/v1/files/create` - create an artifact
- `GET /api/v1/files/{file_id}` - artifact metadata
- `GET /api/v1/files/{file_id}/export?format=...` - one-time download

See: [File Artifacts API](File_Artifacts_API.md)

#### Storage - `/api/v1/storage`

Manage generated files, folders, trash/restore, and quotas.

- `GET /api/v1/storage/files` - list files
- `GET /api/v1/storage/files/{file_id}/download` - download
- `GET /api/v1/storage/usage` - quota/usage summary

See: [Storage API](Storage_API_Documentation.md)

#### Sync - `/api/v1/sync`

Change-log based sync between clients and the server.

- `POST /api/v1/sync/send` - send client changes
- `GET /api/v1/sync/get` - fetch server changes

See: [Sync API](Sync_API.md)

#### Slides - `/api/v1/slides`

Create, generate, version, and export slide decks.

- `POST /api/v1/slides/generate` - generate from prompt/source
- `GET /api/v1/slides/presentations` - list presentations
- `GET /api/v1/slides/presentations/{id}/export` - export (zip/pdf/md/json)

See: [Slides API](../API/Slides.md)

#### Voice Assistant - `/api/v1/voice`

Voice commands and real-time sessions (REST + WebSocket).

- `POST /api/v1/voice/command` - process a text command
- `WS /api/v1/voice/assistant` - streaming voice assistant

See: [Voice Assistant API](../API/Voice_Assistant.md)

#### Quizzes - `/api/v1/quizzes`

Quizzes, questions, attempts, and generation from media.

See: [Quizzes API](Quizzes_API.md)

#### Writing Playground - `/api/v1/writing`

Sessions, templates, themes, tokenization, and wordclouds for writing tools.

See: [Writing API](Writing_API.md)
