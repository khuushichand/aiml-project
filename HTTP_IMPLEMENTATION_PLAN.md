## HTTP Client Unification — Implementation Plan

## Stage 1: Design + Inventory
**Goal**: Define the transport adapter design and inventory the modules to migrate.
**Success Criteria**: Design doc exists in `Docs/Design/HTTP_Client_Unification.md`; async-only end state and files contract documented; migration inventory lists current direct HTTP callers to convert.
**Tests**: N/A (design stage).
**Status**: Complete

## Stage 2: Adapter Interface + Core Integration
**Goal**: Implement transport adapters and route http_client through them.
**Success Criteria**: Adapter interface defined for sync/async/streaming; aiohttp backs async + streaming; httpx is limited to legacy sync paths; centralized retry/egress/metrics remain intact.
**Tests**: Unit tests for adapter request/stream paths, SSE parsing, and streaming timeout behavior.
**Status**: Complete

## Stage 3: Module Migration + Test Updates
**Goal**: Move direct HTTP call sites to http_client and update tests accordingly.
**Success Criteria**: Modules listed in the PRD use http_client or adapter hooks only; tests patch http_client adapters/factories instead of raw requests/httpx/aiohttp.
**Tests**: Integration coverage for streaming provider endpoints and web scraping flows; unit coverage for migrated modules.
**Status**: In Progress
**Progress**:
- Migrated external sources, embeddings, sync client, web scraping, webhook services, ingestion helpers, RAG helpers, and watchlists to http_client.
- Removed direct requests/httpx usage in Local LLM handlers, chat orchestrator, LLM_Calls streaming helpers, local_chat_calls, and chat_calls; updated adapter error handling to use shared utilities.
- Updated tests to patch http_client factories (including local LLM paths and async streaming helpers).
- Migrated Local_Summarization_Lib off direct requests/httpx usage, replacing manual retry adapters with shared retry sessions and updating local summarization tests to patch http_client factories.
- Migrated OpenAI and ElevenLabs TTS adapters to http_client helpers for async fetch/streaming paths (afetch/astream_bytes) and removed direct client.stream usage.
- Updated TTS unit/integration tests to patch http_client helpers (apost/afetch/astream_bytes) instead of httpx.AsyncClient methods.
- Updated HuggingFaceAPI tests to patch the http_client async client factory instead of httpx.AsyncClient methods.

## Stage 4: Cleanup + Docs
**Goal**: Remove remaining legacy HTTP usage and finalize documentation.
**Success Criteria**: No direct requests/httpx/aiohttp usage in business logic (SDKs exempt); documentation updated for adapter usage and migration notes.
**Tests**: Regression checks for http_client performance and egress policy enforcement.
**Status**: In Progress
**Progress**:
- Updated core docs to replace httpx/requests examples with stdlib or curl usage.
- Removed direct requests/httpx usage from Local_Summarization_Lib and http_helpers, consolidating retries and streaming through http_client helpers.
- Pending final doc sweep and verification of any remaining legacy HTTP usage in business logic.
