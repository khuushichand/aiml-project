# API Design

## Introduction
This document outlines the current API design for the TL;DW Server (tldw_server).

## Principles
- RESTful JSON over HTTP (OpenAPI 3.0 with FastAPI)
- Streaming where applicable (Chat, Audio)
- Prefer capability toggles via request payloads over endpoint sprawl
- Liberal input acceptance, strict parsing, explicit errors

## Base URLs
- API base path: `/api/v1` (host depends on deployment)
- Local development:
  - OpenAPI docs: `http://127.0.0.1:8000/docs`
  - ReDoc: `http://127.0.0.1:8000/redoc`
  - Quickstart: `http://127.0.0.1:8000/api/v1/config/quickstart`

## Auth Modes
- Single user: header `X-API-KEY: <key>`
- Multi user: `Authorization: Bearer <JWT>` with OAuth2 login

----------------------------------

## Resource Map (Current)
- Authentication & Users
  - `/api/v1/auth/*` (login, refresh, logout, register)
  - `/api/v1/users/*` (profile, password, sessions, storage)
- Chat (OpenAI-compatible)
  - `/api/v1/chat/completions`
  - Conversation metadata: `/api/v1/chat/conversations`, `/api/v1/chat/analytics` (alias: `/api/v1/chats/conversations`)
  - Additional: per-user dictionaries, document generator
- Audio (STT/TTS)
  - `/api/v1/audio/speech` (TTS)
  - `/api/v1/audio/transcriptions`, `/api/v1/audio/translations` (STT)
  - WebSocket: `/api/v1/audio/stream/transcribe`
- Media
  - `/api/v1/media` (ingest/list/update/delete)
  - `/api/v1/media/search` (POST)
  - Rich ingestion/processing sub-operations
- RAG (Unified)
  - `/api/v1/rag/search` (hybrid FTS5 + embeddings + re-ranking)
  - `/api/v1/rag/capabilities`
  - Convenience: `/api/v1/rag/simple` and `/api/v1/rag/advanced`
- Embeddings & Vector Stores (OpenAI-compatible)
  - `/api/v1/embeddings`
  - `/api/v1/vector-stores/*` (indexes, vectors, batches)
- Characters & Chats
  - `/api/v1/characters/*`
  - Character chat sessions/messages under `/api/v1/chats` and related paths
- Prompts & Prompt Studio
  - `/api/v1/prompts/*` (library)
  - Prompt collections: `/api/v1/prompts/collections/*` (user-scoped, DB-backed)
  - Prompt Studio: projects, prompts, tests, optimization, websocket
  - Keywords for prompts: `/api/v1/prompts/keywords/*` (no global `/keywords`)
- Notes
  - `/api/v1/notes/*`
- Evaluations (Unified)
  - `/api/v1/evaluations/*` (OpenAI-compatible shapes + TL;DW-specific)
- LLM Providers & Local LLM
  - `/api/v1/llm/providers`, `/api/v1/llm/models/metadata`
  - Llama.cpp helpers: `/api/v1/llamacpp/*`
- Research & Paper Search
  - `/api/v1/research/websearch`
  - `/api/v1/paper-search/{arxiv|biorxiv|semantic-scholar}`
- Chatbooks (Import/Export)
  - `/api/v1/chatbooks/export`, `/api/v1/chatbooks/import` (+ job/status)
- System, Health & Monitoring
  - `/health`, `/ready`
  - `/metrics` (Prometheus), `/api/v1/metrics` (JSON)
  - MCP Unified, config info, sync, admin

----------------------------------

## Notes and Clarifications
- OpenAI compatibility:
  - Chat: `/api/v1/chat/completions`
  - Embeddings: `/api/v1/embeddings`
  - Audio STT/TTS: `/api/v1/audio/transcriptions`, `/api/v1/audio/speech`
- Keywords:
  - No global `/api/v1/keywords`. Prompt keywords live under `/api/v1/prompts/keywords/*`. Media keywords are provided via media payloads/DB.
- Prompt collections:
  - `/api/v1/prompts/collections/*` is production-backed (user-scoped persistence in Prompts DB), not a test/dev-only in-memory surface.
- Sync send entities:
  - `POST /api/v1/sync/send` only accepts `Media`, `Keywords`, and `MediaKeywords` in change entries. Unsupported entities are rejected with `400`.
- Import/Export:
  - Use Chatbooks: `/api/v1/chatbooks/export` and `/api/v1/chatbooks/import`.
- Tools:
  - The `tools` router is minimal; web/paper search live under `research` and `paper-search`.
- Trash:
  - Soft delete exists in DBs, but a public `/api/v1/trash` surface is not exposed yet.
- LLM:
  - Text generation flows through Chat completions. `/api/v1/llm/generate` is not present.

----------------------------------

## Representative Endpoints
- Auth & Users
  - `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`
  - `POST /api/v1/auth/register`
  - `GET /api/v1/users/me`, `PUT /api/v1/users/me`
- Chat
  - `POST /api/v1/chat/completions`
  - `GET /api/v1/chat/conversations`, `PATCH /api/v1/chat/conversations/{id}`
  - `GET /api/v1/chat/conversations/{id}/tree`, `GET /api/v1/chat/analytics`
- Media
  - `GET /api/v1/media`, `GET /api/v1/media/{id}`
  - `POST /api/v1/media`, `PUT /api/v1/media/{id}`, `DELETE /api/v1/media/{id}`
  - `POST /api/v1/media/search`
- RAG
  - `POST /api/v1/rag/search`, `GET /api/v1/rag/capabilities`
- Embeddings & Vector Stores
  - `POST /api/v1/embeddings`
  - `POST /api/v1/vector-stores/indexes`, `GET /api/v1/vector-stores/indexes/{id}` (and related)
- Audio
  - `POST /api/v1/audio/speech`, `POST /api/v1/audio/transcriptions`
  - `WS /api/v1/audio/stream/transcribe`
- Prompts & Prompt Studio
  - `GET /api/v1/prompts`, `POST /api/v1/prompts`, `PUT /api/v1/prompts/{id}`, `DELETE /api/v1/prompts/{id}`
  - `POST /api/v1/prompts/search`, `GET /api/v1/prompts/export`, `POST /api/v1/prompts/import`
  - `GET /api/v1/prompts/{id}/versions`, `POST /api/v1/prompts/{id}/versions/{version}/restore`
  - `POST /api/v1/prompts/collections/create`, `GET /api/v1/prompts/collections/{collection_id}`
  - `POST /api/v1/prompts/templates/variables`, `POST /api/v1/prompts/templates/render`
  - `POST /api/v1/prompts/bulk/delete`, `POST /api/v1/prompts/bulk/keywords`
  - `GET /api/v1/prompts/keywords`, `POST /api/v1/prompts/keywords`
- Sync
  - `POST /api/v1/sync/send`, `GET /api/v1/sync/get`
- Evaluations
  - `POST /api/v1/evaluations`, `GET /api/v1/evaluations/runs`
- LLM Providers & Local LLM
  - `GET /api/v1/llm/providers`, `GET /api/v1/llm/models/metadata`
  - `POST /api/v1/llamacpp/start_server`, `POST /api/v1/llamacpp/stop_server`
- Research & Paper Search
  - `POST /api/v1/research/websearch`
  - `GET /api/v1/paper-search/arxiv`, `GET /api/v1/paper-search/biorxiv`, `GET /api/v1/paper-search/semantic-scholar`
- Chatbooks
  - `POST /api/v1/chatbooks/export`, `POST /api/v1/chatbooks/import`
- Health & Monitoring
  - `GET /health`, `GET /ready`, `GET /metrics`, `GET /api/v1/metrics`

----------------------------------

## Links
https://levelup.gitconnected.com/great-api-design-comprehensive-guide-from-basics-to-best-practices-9b4e0b613a44
https://github.com/TypeError/secure
