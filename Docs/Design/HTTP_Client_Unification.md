# HTTP Client Unification Design

## Summary
Unify outbound HTTP behavior behind `tldw_Server_API/app/core/http_client.py` with
a transport adapter interface. Async + streaming traffic use aiohttp by default;
httpx remains only for legacy sync paths during migration and is removed once all
sync callers are converted.

## Goals
- Centralize egress policy, retries, timeouts, logging, and metrics.
- Provide consistent async + streaming behavior across modules.
- Remove direct requests/httpx/aiohttp usage from business logic (SDKs exempt).
- Simplify tests by patching a single adapter or client factory.

## Non-Goals
- Change external API contracts.
- Wrap vendor SDKs that encapsulate their own HTTP clients.
- Add HTTP/2 support in this iteration.

## Current State
- `http_client.py` is httpx-based and already enforces egress policy, retries,
  metrics, JSON guards, and streaming helpers.
- Direct outbound calls still exist in multiple modules using requests, httpx,
  and aiohttp with duplicated retry/timeout logic.

## Proposed Architecture
### Transport Adapter Interface
Define a small adapter surface that performs IO only:
- `request(...) -> Response` for sync callers (legacy only).
- `arequest(...) -> Response` for async callers.
- `stream_bytes(...) -> AsyncIterator[bytes]`.
- `stream_sse(...) -> AsyncIterator[SSEEvent]` or reuse centralized SSE parser.

All policy enforcement (egress, retries, timeouts, metrics, redirects) remains
in `http_client.py`. Adapters must not bypass policy or metrics hooks.

### Adapter Selection
- Async + streaming: aiohttp adapter (default).
- Sync: httpx adapter (transitional during migration).
- Adapter selection is not configurable in production.

### Request Options and Files Contract
- `files` uses httpx/requests-style multipart data:
  mapping or sequence of `(field, (filename, file-like or bytes, content_type))`.
- Adapters do not accept file paths or open files.
- File-like objects must be seekable when retries are enabled.
- Upload buffering/streaming behavior is delegated to the transport.

### Streaming Semantics
- SSE parsing behavior stays aligned with existing `http_client` rules.
- Transport read timeout disabled for streaming; first-byte and idle timeouts are
  enforced in `http_client`.
- Streaming is never retried after first byte.

### Client Lifecycle
- `http_client` owns client instances and reuses them.
- Async clients are cached per event loop.
- Clients are closed on app shutdown and test loop teardown.

## Migration Inventory (Direct HTTP Usage)
Priority targets to migrate:
- `app/core/LLM_Calls/legacy_chat_calls.py` (requests streaming)
- `app/core/Embeddings/connection_pool.py` (aiohttp)
- `app/core/Web_Scraping/enhanced_web_scraping.py` (aiohttp)
- `app/core/External_Sources/google_drive.py` (aiohttp)
- `app/core/External_Sources/notion.py` (aiohttp)
- `app/core/Sync/Sync_Client.py` (requests)
- `app/core/Ingestion_Media_Processing/Audio/Audio_Transcription_External_Provider.py` (httpx)
- `app/core/Evaluations/webhook_manager.py` (aiohttp)
- `app/core/Evaluations/webhook_security.py` (aiohttp)
- `app/core/Watchlists/fetchers.py` (aiohttp)
- `app/core/RAG/rag_service/quick_wins.py` (aiohttp)
- `app/core/Chunking/async_chunker.py` (aiohttp)

## Testing Plan
- Unit: adapter request/stream paths enforce egress policy, retries, and timeouts.
- Unit: SSE parsing and streaming timeout coverage (first-byte, idle, heartbeat).
- Integration: streaming provider endpoints and web scraping flows.
- Regression: ensure no tests patch raw requests/httpx/aiohttp clients.

## Rollout Notes
- No production toggle for adapter selection.
- Track performance regressions via metrics; rollback via prior release if needed.

## Open Questions
- Are there transport-specific features required by any module that need adapter
  extensibility beyond request/stream semantics?
