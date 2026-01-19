# API Documentation

## Overview

API uses FastAPI framework.
Designed to be simple and easy to use.
Generative endpoints follow openai API spec where possible.
See [API Design](API_Design.md) for more details. For a quick map of OpenAPI tags to their docs, see the [API Tag Index](API_Tags_Index.md).

See also: `Docs/Published/Code_Documentation/Ingestion_Pipeline_Audio.md` for the audio processing endpoint (`POST /api/v1/media/process-audios`).

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

The RAG module provides advanced search and question-answering capabilities across your content. It achieves 100% test coverage and is production-ready.

##### Search Endpoints

- **`POST /api/v1/rag/search`** - Simple search with hybrid (BM25 + semantic) capabilities
  - Search across multiple databases (media, notes, characters, chat history)
  - Support for keyword filtering
  - Configurable search types (hybrid, semantic, fulltext)

- **`POST /api/v1/rag/search/advanced`** - Advanced search with full configuration control
  - Multiple search strategies (vanilla, query_fusion, HyDE)
  - Fine-tuned hybrid weights and similarity thresholds
  - Metadata filters and date range queries
  - Reranking and score inclusion options

##### Agent Endpoints

- **`POST /api/v1/rag/agent`** - Simple Q&A agent with automatic context retrieval
  - Conversational interface with memory
  - Automatic search across specified databases
  - Returns response with source citations

- **`POST /api/v1/rag/agent/advanced`** - Research agent with advanced capabilities
  - Multiple modes (RAG, research)
  - Tool support (web_search, reasoning, calculator, code_execution)
  - Custom system prompts
  - Streaming support via Server-Sent Events
  - Detailed statistics and metrics

##### Health Check

- **`GET /api/v1/rag/health`** - Service health status
  - Monitor RAG service availability
  - Used for load balancer health checks

For comprehensive documentation, see:
- [RAG API Consumer Guide](RAG-API-Guide.md) - Complete API reference with examples
- [RAG API Documentation](RAG_API_Documentation.md) - Architecture and implementation details

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
