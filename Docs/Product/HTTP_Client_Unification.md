# HTTP Client Unification Design

## Summary
Unify outbound HTTP behavior behind `tldw_Server_API/app/core/http_client.py`.
Today this is implemented via centralized helpers that route async/streaming
traffic to aiohttp when available and sync traffic to httpx, with a curl backend
available for simple fetches. A formal transport adapter interface is planned
but not yet implemented.

## Goals
- Centralize egress policy, retries, timeouts, logging, and metrics.
- Provide consistent async + streaming behavior across modules.
- Remove direct requests/httpx/aiohttp usage from business logic (SDKs exempt).
- Simplify tests by patching a single adapter or client factory.

## Non-Goals
- Change external API contracts.
- Wrap vendor SDKs that encapsulate their own HTTP clients.
- Tune HTTP/2 behavior (httpx enables HTTP/2 by default today).

## Current State
- `http_client.py` centralizes egress policy, retries, timeouts, logging, metrics,
  JSON guards, and streaming helpers.
- Async helpers default to aiohttp when available; httpx remains for sync and
  for async fallback/utility helpers.
- Simple `fetch()` supports a curl backend (curl_cffi) or httpx, selected via
  `backend=...`.
- Direct outbound calls in app core largely route through `http_client` now;
  remaining mentions of requests/aiohttp are primarily in tests/docs.

## Implementation Status (Current vs Target)
**Transport adapter interface**
Current: no adapter interface; helpers branch internally between aiohttp/httpx.
Target: adapter surface (`request/arequest/stream_bytes/stream_sse`) in
`http_client.py` with policy enforced above the adapter.

**Adapter selection**
Current: async/streaming use aiohttp if available; sync uses httpx; `fetch()`
exposes `backend` for simple fetches.
Target: no production-time adapter selection; only internal routing.

**Streaming semantics**
Current: SSE parsing is centralized; transport read timeouts use defaults (e.g.,
aiohttp `sock_read`); no explicit first-byte/idle timeout layer; retries happen
for early failures but there is no explicit "no retries after first byte" guard.
Target: first-byte/idle timeouts enforced in `http_client`; streaming never
retries after the first byte.

**Client lifecycle**
Current: aiohttp sessions are cached per event loop and closed at shutdown;
httpx clients are created per call unless callers pass their own.
Target: `http_client` owns reusable clients consistently across transports.

## Target Architecture (Planned)
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
- Adapter selection is not configurable in production; only simple `fetch()`
  exposes an explicit `backend` switch for testing/benchmarks.

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
Status: most of the prior targets now use `http_client` helpers. In app core,
direct imports of requests/aiohttp appear limited to `http_client.py` itself.
If new direct outbound usage is added, update this list and migrate back to
`http_client`.

## Testing Plan
- Unit: http_client request/stream paths enforce egress policy, retries, timeouts.
- Unit: SSE parsing coverage exists; first-byte/idle timeout coverage is still
  needed if those controls are added.
- Integration: streaming provider endpoints and web scraping flows.
- Regression: enforce no tests patch raw requests/httpx/aiohttp clients via the
  pre-commit guard, pytest plugin, and CI lint step
  (`Helper_Scripts/checks/guard_http_client_patching.py`).

## Rollout Notes
- No production toggle for adapter selection (outside simple `fetch()` backend
  selection).
- Track performance regressions via metrics; rollback via prior release if needed.

## Open Questions
- Are there transport-specific features required by any module that need adapter
  extensibility beyond request/stream semantics?
- Do we want to enforce first-byte/idle streaming timeouts in `http_client`
  (separate from transport read timeouts)?
