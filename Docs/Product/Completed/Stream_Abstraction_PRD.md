# Stream Abstraction — PRD

- Status: Complete (GA; currently `STREAMS_UNIFIED` is default ON in dev/test/non‑prod; production can opt out via feature flag; see §9 Rollout Plan and Docs/Issues/STREAMS_UNIFIED_Rollout_Tracking.md)
- Last Updated: 2025-11-16
- Authors: Codex (coding agent)
- Stakeholders: API (Chat/Embeddings), Audio, MCP, WebUI, Docs

---

## 1. Overview

### 1.1 Summary
Unify streaming across Server‑Sent Events (SSE) and WebSockets under a single abstraction so features share consistent framing, normalization, heartbeat, and completion semantics. Introduce an `AsyncStream` interface with transport‑specific implementations (`SSEStream`, `WebSocketStream`) that route all provider data through a single normalization path and standardized DONE/error frames (with canonical error codes).

### 1.2 Motivation & Background
- Symptom: repeated, inconsistent SSE/WebSocket line formatting, normalization, and completion handling across endpoints and modules.
- Duplicates/examples today:
  - Endpoint‑local SSE line builder: `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py:1..120` (`_extract_sse_data_lines`).
  - Central SSE helpers already exist: `tldw_Server_API/app/core/LLM_Calls/sse.py`.
  - Provider line normalization scattered: `tldw_Server_API/app/core/LLM_Calls/streaming.py`.
  - SSE emitters in embeddings orchestrator: `tldw_Server_API/app/api/v1/endpoints/embeddings_v5_production_enhanced.py:3500+`.
  - WebSockets in Audio and MCP with similar framing/heartbeat/error behavior:
    - `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Streaming_Unified.py`.
    - `tldw_Server_API/app/core/MCP_unified/server.py`.

Unifying principle: All outputs are streams — just different transports.

### 1.3 Goals
1. Single, composable interface for streaming outputs across transports.
2. One normalization path for provider outputs (OpenAI‑compatible SSE chunks; consistent WS frames).
3. Standard DONE and error semantics (code + message); no duplicate `[DONE]` emission.
4. Consistent heartbeat/keepalive policy for SSE and WS.
5. Reduce code duplication and simplify endpoint logic.
6. Provide clear backpressure behavior for SSE (bounded queue) and consistent WS close code mapping.

### 1.4 Non‑Goals
- Changing wire payload shapes for domain data (e.g., audio partials, MCP JSON‑RPC responses). The abstraction standardizes framing/lifecycle, not domain schemas.
- Introducing a new message bus or queueing layer.

### 1.5 Current Status

- Abstractions implemented with metrics: `SSEStream` and `WebSocketStream` (complete).
- Provider control pass‑through + SSE idle/max enforcement (complete).
- Chat SSE (main, character chat, and document‑generation) unified behind `STREAMS_UNIFIED` with duplicate `[DONE]` suppressed; metrics flowing (complete).
- Embeddings orchestrator SSE unified behind flag (complete):
  - Preserves `event: summary`; emits heartbeats and standardized non‑fatal error frames when configured.
- Evaluations SSE (A/B test events) unified (complete):
  - Uses `SSEStream` with labels; standardized heartbeats; DONE semantics.
- Jobs Admin SSE (events outbox) unified (complete):
  - Uses `SSEStream`; preserves `id:` and `event:` lines for clients using Last‑Event‑ID.
- Prompt Studio SSE fallback unified behind flag (complete):
  - Uses `SSEStream` when `STREAMS_UNIFIED=1`; retains legacy generator when flag is off.
- Audio WS lifecycle standardized with `WebSocketStream` (complete):
  - Compat alias `error_type` present; close‑code mapping in place; metrics emitting.
- MCP WS lifecycle standardized with `WebSocketStream` (complete):
  - JSON‑RPC payloads unchanged; ping/idle metrics emitting.

Operational note
- `STREAMS_UNIFIED` is the default in dev/test/non‑prod configs; production can opt out or roll back by toggling the flag.

---

## 2. User Stories

| Story | Persona | Description |
| --- | --- | --- |
| US1 | API consumer (Chat) | “When I stream chat completions, I want consistent SSE framing and a single `[DONE]` sentinel across providers.” |
| US2 | WebUI engineer | “I want identical heartbeat and error semantics whether a feature uses SSE or WebSockets.” |
| US3 | Backend dev | “I want to implement streaming without re‑writing `[DONE]` and error handling for each endpoint.” |
| US4 | Maintainer | “I want to delete endpoint‑local SSE helpers and rely on a central abstraction with tests.” |

---

## 3. Requirements

### 3.1 Functional Requirements
1. Provide `AsyncStream` interface (or compatible concrete classes) with at least:
   - `send_event(event: str, data: Any | None = None)` — named event emission (maps to `event:` + `data:` for SSE; may map to `{type: "event", event, data}` for WS on endpoints explicitly designed for event-framed WS payloads; Audio and MCP WS endpoints MUST use `send_json` for domain payloads).
   - `send_json(payload: dict)` — structured data (maps to `data:` for SSE; JSON frame over WS).
   - `done()` — emit end‑of‑stream (SSE: `data: [DONE]`; WS: `{type: "done"}`) and close if appropriate.
   - `error(code: str, message: str, *, data: dict | None = None)` — emit structured error frame and close when transport requires.
2. Implement `SSEStream` for FastAPI `StreamingResponse` generators:
   - Internals: async queue‑backed emitter; `iter_sse()` async generator yields lines to the response.
   - Use `sse.ensure_sse_line`, `sse.sse_data`, `sse.sse_done`, `sse.normalize_provider_line`.
   - Suppress provider `[DONE]`; ensure exactly one terminal `[DONE]` from our layer.
   - Optional `heartbeat_interval_s` emitting `":"` comment lines (default); support `data` heartbeat mode.
   - Provide `send_raw_sse_line(line: str)` as SSE‑specific helper for hot paths; not part of `AsyncStream`.
   - Bounded queue (`queue_maxsize`) with documented backpressure policy.
3. Implement `WebSocketStream` over Starlette/FastAPI WS:
   - Lifecycle frames: `{type: "error", code, message, data?}`; `{type: "done"}`; `{type: "ping"}`/`{type: "pong"}`.
   - Optional pings via `{type: "ping"}` at `heartbeat_interval_s`; reply to `{type: "pong"}`.
   - Map application error codes to WS close reasons consistently.
   - Event frames `{type: "event", event, data}` are optional; domain payloads remain unchanged for Audio/MCP.
4. Centralize provider stream normalization:
   - Reuse `app/core/LLM_Calls/streaming.py` for `requests` and `httpx` SSE iteration.
   - Route all chat provider streams through this module before transport emission.
5. Backward compatible payloads:
   - Chat/OpenAI SSE: preserve `choices[].delta.content` shapes.
   - Embeddings orchestrator: keep `event: summary` structure; move emission to `SSEStream.send_event("summary", payload)`.
   - Audio and MCP WS: keep domain JSON schemas; only standardize lifecycle (error/done/heartbeat).
6. Observability:
   - Consistent log messages for start/stop/error with `stream_id`/`connection_id`.
   - Metrics (labels: include `transport`, `kind` where applicable, and optional stream `labels` from constructors like `{`"component"`:"chat"}`):
     - `sse_enqueue_to_yield_ms` (histogram, ms): time from call to enqueue to iterator yield/write.
     - `ws_send_latency_ms` (histogram, ms): time to complete `send_json` writes; `kind` in {event,json,error,done,ping}.
     - `sse_queue_high_watermark` (gauge): max queue depth observed.
     - `ws_pings_total` (counter): ping frames sent.
     - `ws_ping_failures_total` (counter): ping send errors.
     - `ws_idle_timeouts_total` (counter): WS connections closed due to idle timeout.
   - Drop counters are emitted only when drop‑oldest mode is enabled.

### 3.2 Non‑Functional Requirements
- No measurable latency regression vs current code paths.
- Memory footprint stable under long‑lived streams.
- High availability under intermittent network conditions (graceful error frames).

### 3.3 Canonical Error Codes
- `quota_exceeded` — request exceeds quotas or limits
- `idle_timeout` — idle timeout reached
- `transport_error` — network/stream transport failure
- `provider_error` — upstream LLM/provider signaled an error
- `validation_error` — bad client input
- `internal_error` — server-side error

### 3.4 WebSocket Close Code Mapping
- 1000 — normal closure (e.g., `{type: "done"}`)
- 1001 — going away/idle timeout
- 1008 — policy violation (e.g., auth/rate-limit failures)
- 1011 — internal server error

Usage guidance:
- `quota_exceeded`: send `{type:"error", code:"quota_exceeded", ...}` then close with 1008.
- `idle_timeout`: close with 1001 (a preceding error frame is optional and generally omitted for simplicity).
- `internal_error`: send `{type:"error", code:"internal_error", ...}` then close with 1011.
- `transport_error`: often cannot send an error reliably; close with 1011 if possible.

---

## 4. UX & API Design

### 4.1 Transport Semantics
- SSE
  - Media type: `text/event-stream`.
  - Heartbeat: `":"\n\n"` comments at configurable interval (default 10s). Configurable mode to send `data: {"heartbeat": true}` if needed.
  - Termination: single `data: [DONE]\n\n`.
  - Errors: `data: {"error": {"code", "message", "data"}}`.
    - Closure policy: configurable (default `close_on_error=True`). Per-call override available on `SSEStream.error(..., close=bool)`.
    - Example (non-fatal error that keeps the stream open):
      ```python
      await stream.error("transient_provider_issue", "upstream timeout; continuing", close=False)
      await stream.send_json({"status": "retrying"})
      ```
- WebSocket
  - Heartbeat: `{type: "ping"}` at configurable interval (default 10s) with optional client `{type: "pong"}`.
  - Termination: `{type: "done"}` followed by close (default 1000; configurable).
  - Errors: `{type: "error", code, message, data}` then close as needed (mapping in 3.4).
    - Transitional compatibility (Audio/WebUI): include `error_type` alias mirroring `code` during rollout.

### 4.2 Developer Interface (Illustrative)
```python
class AsyncStream(Protocol):
    async def send_event(self, event: str, data: Any | None = None) -> None: ...
    async def send_json(self, payload: dict) -> None: ...
    async def done(self) -> None: ...
    async def error(self, code: str, message: str, *, data: dict | None = None) -> None: ...

class SSEStream(AsyncStream):
    # queue-backed; exposes iter_sse() to yield SSE lines; supports optional send_raw_sse_line();
    # note: send_raw_sse_line is SSE-only (not on AsyncStream) to aid hot-path migrations; prefer structured send_json over time
    # configurable error closure policy via close_on_error (default True; per-call override)
    # constructors accept optional labels: Dict[str,str] to tag metrics (e.g., {"component":"chat"})
    ...

class WebSocketStream(AsyncStream):
    # wraps WebSocket send_json / close with standard frames & optional ping loop
    # constructors accept optional labels: Dict[str,str] to tag metrics (e.g., {"component":"audio"})
    ...
```

### 4.4 SSE Endpoint Example

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from tldw_Server_API.app.core.Streaming.streams import SSEStream

router = APIRouter()

@router.get("/chat/stream")
async def chat_stream():
    stream = SSEStream(
        heartbeat_interval_s=10,
        heartbeat_mode="data",
        labels={"component": "chat", "endpoint": "chat_stream"},
    )

    async def generator():
        # In a real endpoint, start a background task to feed the stream
        # await stream.send_json({...}) / await stream.send_event("summary", {...}) / await stream.done()
        async for line in stream.iter_sse():
            yield line

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(generator(), media_type="text/event-stream", headers=headers)
```

### 4.3 Backward Compatibility
- Existing SSE clients continue to receive identical `data:` frames (including OpenAI style deltas and a final `[DONE]`).
- Existing WS clients continue to receive domain JSON; only lifecycle frames become standardized (`error`, `done`, `ping`).

---

## 5. Technical Approach

1. Abstraction
   - New module: `tldw_Server_API/app/core/Streaming/streams.py`, containing `AsyncStream`, `SSEStream`, `WebSocketStream`.
   - Import `sse.ensure_sse_line`, `sse.normalize_provider_line`, `sse.sse_data`, `sse.sse_done`.
2. Normalization
   - Keep a single normalization path in `LLM_Calls/streaming.py` for iterating provider SSE and suppressing provider `[DONE]`.
   - Endpoints compose:
     - Option A (hot path): `for line in iter_sse_lines_requests(...): await sse_stream.send_raw_sse_line(line)`.
     - Option B (structured): build OpenAI‑compatible deltas and `await stream.send_json(openai_delta)`.
   - Recommendation: prefer Option B for new endpoints; use Option A only to minimize churn during migration.
3. Heartbeats
   - Shared config: `STREAM_HEARTBEAT_INTERVAL_S` (default 10), `STREAM_IDLE_TIMEOUT_S`, `STREAM_MAX_DURATION_S` — overridable per endpoint.
   - SSE: comment line `":"` (or `data: {"heartbeat": true}` when configured).
   - WS: `{type: "ping"}`; optional `{type: "pong"}` handling; idle timeout closes with 1001.
4. Error Handling
   - Convert transport/iteration errors into structured frames via `stream.error(code, message, ...)`.
   - Ensure exactly one terminal `done()` is emitted per stream on normal completion; no double‐DONE.
5. Refactors (per‑module)
   - Chat/Characters: replace `_extract_sse_data_lines` and local builders with `SSEStream`.
   - Embeddings orchestrator: replace custom `yield f"event: ..."` with `SSEStream.send_event("summary", payload)` and heartbeat via abstraction.
   - Audio WS: replace bespoke status/error frames where possible with `WebSocketStream.error/done/ping`; retain domain payloads.
   - MCP WS: reuse `WebSocketStream` for ping loop and standardized error/done; keep JSON‑RPC responses intact.

### 5.1 SSE Response Headers
- Recommend headers to avoid buffering through proxies:
  - `Cache-Control: no-cache`
  - `Connection: keep-alive` (HTTP/1.1 only; HTTP/2 ignores this header)
  - `X-Accel-Buffering: no` (for NGINX)
  - Notes:
    - Under HTTP/2, `Connection` is not meaningful and may be stripped; focus on disabling proxy buffering and keeping the response streaming (e.g., NGINX `proxy_buffering off;`, Caddy `encode`/`buffer` tuning).
    - In reverse‑proxy/CDN environments (NGINX, Caddy, Cloudflare), prefer data heartbeats (`STREAM_HEARTBEAT_MODE=data`) to encourage flushes and reduce buffering.

### 5.2 Provider Control/Event Pass-through
- Normalization ignores `event:`/`id:`/`retry:` and comment lines by default.
- Provide a provider-specific pass-through mode to preserve control fields when needed.
- Emit debug logs when dropping unknown control lines during normalization to aid troubleshooting.
- Global toggle: `STREAM_PROVIDER_CONTROL_PASSTHRU=1` enables pass-through (default off).
- Per-endpoint flag: endpoints may request pass-through (e.g., `SSEStream(..., provider_control_passthru=True)`), which overrides the global default.

- Transparent mode:
  - When pass-through is enabled, preserve `event:`/`id:`/`retry:` lines and forward them unchanged alongside `data:` payloads.
  - Add an optional hook for custom filtering/mapping (e.g., `control_filter(name: str, value: str) -> tuple[str, str] | None`) to rename/whitelist provider events.
  - Intended for providers whose clients rely on SSE event names; default remains normalized mode.

Example (provider control pass-through)
```python
# Preserve provider control fields as-is
stream = SSEStream(provider_control_passthru=True)
# Or whitelist specific controls
stream = SSEStream(provider_control_passthru=True,
                   control_filter=lambda n, v: (n, v) if n in {"event", "id", "retry"} else None)
```

### 5.3 WS Event Frames Guardrails
- Explicitly forbid wrapping domain WS payloads for MCP and Audio in `{type: "event"}` frames.
- Only use event frames on endpoints designed for them; lifecycle frames (`ping`, `error`, `done`) remain standardized everywhere.
- Add helper naming guidance and code review checklist item to reduce misuse.

MCP JSON-RPC done semantics:
- `done` is session-level only for MCP WebSockets. It must never be emitted as a JSON‑RPC message.
- JSON‑RPC results/errors are sent as specified by JSON‑RPC; lifecycle frames (`ping`, `error`, session‑level `done`) are separate from JSON‑RPC content.

### 5.4 Endpoint Examples (Rollout-friendly)

```python
# Audio WebSocket handler example with transitional error alias
from tldw_Server_API.app.core.Streaming.streams import WebSocketStream

async def audio_ws_handler(websocket):
    stream = WebSocketStream(
        websocket,
        heartbeat_interval_s=10,
        compat_error_type=True,   # include error_type alias during rollout
        close_on_done=True,
        labels={"component": "audio", "endpoint": "audio_ws"},
    )
    await stream.start()
    try:
        # Emit domain payloads directly (no event frames)
        await stream.send_json({"type": "partial", "text": "..."})
        # ...
    except QuotaExceeded as e:
        await stream.error("quota_exceeded", str(e), data={"limit": e.limit})
        await stream.done()
    finally:
        await stream.stop()

# MCP WebSocket: lifecycle frames standardized, JSON-RPC payloads unchanged
async def mcp_ws_handler(websocket):
    stream = WebSocketStream(
        websocket,
        heartbeat_interval_s=10,
        compat_error_type=True,  # temporary alias for clients expecting error_type
        close_on_done=False,      # MCP may manage session lifetime explicitly
        labels={"component": "mcp", "endpoint": "mcp_ws"},
    )
    await stream.start()
    try:
        # Send JSON-RPC results as-is
        await stream.send_json({"jsonrpc": "2.0", "result": {...}, "id": 1})
        # ...
    except Exception as e:
        await stream.error("internal_error", f"{e}")
    finally:
        await stream.stop()
```

### 5.5 Backpressure Policy

- Default: block on full SSE queue (no drops). Producers back off until the consumer drains the queue.
- Optional mode: drop‑oldest (advanced; disabled by default). When enabled, the oldest queued item is dropped to make room for new items, and a counter increments for observability.
- Recommendation: keep default blocking mode for correctness; only enable drop‑oldest for non‑critical high‑throughput streams with tolerant clients.
 - Queue sizing guidance: Use a conservative default (e.g., 256 frames) and tune per endpoint based on typical payload size and client consumption rate. Track queue high‑water marks to inform tuning.

### 5.7 Reverse Proxy & HTTP/2 Considerations

- Heartbeats:
  - Prefer `STREAM_HEARTBEAT_MODE=data` behind reverse proxies/CDNs to reduce buffering and encourage periodic flushes.
  - Ensure proxy timeouts (read/idle) exceed heartbeat intervals.
- Proxy buffering:
  - Disable buffering on the reverse proxy (`proxy_buffering off;` for NGINX, appropriate Caddy/Envoy settings).
  - For NGINX, keep `X-Accel-Buffering: no` on responses.
- HTTP/1.1 vs HTTP/2:
  - `Connection: keep-alive` applies to HTTP/1.1; HTTP/2 handles persistence differently and may strip the header.
  - Do not rely on connection headers under HTTP/2; rely on correct streaming semantics and disabled buffering.

### 5.6 SSE Idle/Max Duration Enforcement

- Idle timeout (`STREAM_IDLE_TIMEOUT_S`):
  - Behavior: emit error frame `{"error": {"code": "idle_timeout", "message": "idle timeout"}}` followed by `[DONE]`, then close.
  - Client expectation: treat as terminal condition; retry logic is client‑specific.
- Max duration (`STREAM_MAX_DURATION_S`):
  - Behavior: emit error frame `{"error": {"code": "max_duration_exceeded", "message": "stream exceeded maximum duration"}}` followed by `[DONE]`, then close.
  - Client expectation: treat as terminal condition; consider resuming in a new stream.

---

## 6. Dependencies & Impact

- Reuse: `app/core/LLM_Calls/sse.py`, `app/core/LLM_Calls/streaming.py`.
- Touchpoints: Chat endpoints, Character chat, Embeddings orchestrator SSE, Audio WS, MCP WS.
- Docs: Update streaming sections in API docs and Audio/MCP protocol notes to mention standardized lifecycle frames.

---

## 7. Deletions & Cleanups

- Remove endpoint‑local SSE helpers and duplicate DONE handling:
  - `character_chat_sessions._extract_sse_data_lines`.
  - Custom SSE yields in `embeddings_v5_production_enhanced.orchestrator_events` generator.
- Replace bespoke heartbeat/error patterns in:
  - `Audio_Streaming_Unified.handle_unified_websocket` (use `WebSocketStream` ping/error/done).
  - `MCP_unified/server` ping loop and error frames where compatible with JSON‑RPC lifecycle.

---

## 8. Metrics & Success Criteria

| Metric | Target |
| --- | --- |
| Duplicate DONE frames in Chat SSE | 0 across providers |
| Stream error frames include `code` + `message` | 100% |
| Heartbeat parity (SSE/WS) | Enabled by default, configurable |
| Lines of duplicate streaming code removed | > 60% in affected files |
| Server-side latency regression (enqueue→yield or send_json) | ≤ ±1% vs baseline |

Note: Keep metrics labels low-cardinality (e.g., `component`, `endpoint`); avoid user/session IDs.

---

## 9. Rollout Plan

1. Phase 0 — Design (this document)
   - Align on interface and semantics.
2. Phase 1 — Abstraction + Chat pilot
   - Implement `AsyncStream`, `SSEStream`, `WebSocketStream`.
   - Migrate one Chat streaming endpoint; add unit tests for DONE/error/heartbeat.
3. Phase 2 — Embeddings SSE
   - Switch orchestrator SSE to `SSEStream`; keep `event: summary`.
4. Phase 3 — Audio WS
   - Integrate `WebSocketStream` for heartbeat/error/done; retain domain payloads.
5. Phase 4 — MCP WS
   - Use `WebSocketStream` ping/error where compatible; respect JSON‑RPC requirements.
6. Phase 5 — Cleanup
   - Delete endpoint‑local helpers; update docs/tests; enable by default.

Feature flag: `STREAMS_UNIFIED` (rollout complete; currently default ON in dev/test/non‑prod with opt‑out/rollback via flag; see Docs/Issues/STREAMS_UNIFIED_Rollout_Tracking.md).

---

## 9.1 Client Migration Checklist & Shims

- WebUI and client libraries
  - Update to consume `code` + `message` error shape; during rollout, accept `error_type` alias where present.
  - Ignore `{type:"ping"}` frames; treat `{type:"done"}` as terminal.
  - For SSE, handle `{"error": {"code", "message"}}` followed by `[DONE]` as terminal.
- Audio/MCP integrations
  - Keep domain payloads unchanged; enable `compat_error_type=True` on `WebSocketStream` during migration window.
  - Standardize lifecycle handling: single source of pings; `done` where appropriate (avoid for JSON‑RPC content itself).
- Observability
  - Add dashboards for stream starts/stops/errors, WS close codes, SSE queue high‑water marks.
  - Enable logs at `debug` for dropped control lines (when pass-through disabled) during the first release.
- Feature flag playbook
  - Roll out per‑endpoint; enable in pre‑prod/staging first.
  - In case of regression, disable `STREAMS_UNIFIED` to revert to legacy code paths.
  - Keep compatibility shims (`error_type`) until clients confirm migration.

---

## 10. Testing Strategy

- Unit tests
  - `SSEStream`: ensures normalization, exact one DONE, error payload shape, heartbeat interval.
  - `WebSocketStream`: ping scheduling, error/done frames, close behavior.
- Integration tests
  - Chat SSE end‑to‑end with mock provider streams including provider `[DONE]` and malformed lines.
  - Embeddings orchestrator SSE: event and heartbeat cadence.
  - Audio WS: partial/final frames + standardized error/done in shutdown sequences.
  - MCP WS: ping/idle timeout behavior with new helper.
- Backward‑compat checks
  - Snapshot tests for representative SSE/WS payload sequences before/after migration.
- Latency measurement
  - Instrument server-side latency: measure `enqueue→yield` for SSE (time from `send_*` to generator yield), and `send_json` call completion latency for WS. Compare distributions to baseline; target ≤ ±1%.
- Backpressure tests
  - SSE queue bounded behavior (block vs drop policy) with counters asserted.
  - Heartbeats and backpressure: document that heartbeats share the same queue and may be delayed under heavy backpressure. Acceptance: without payload backpressure, observed heartbeat intervals stay within 2× configured; under saturation, heartbeats may be delayed but resume within 2× after backlog drains.

---

## 11. Risks & Mitigations

- Risk: Subtle changes in timing/heartbeats can affect clients.
  - Mitigation: feature flag; document intervals; snapshot test WebUI behavior.
- Risk: Double DONE due to legacy code paths not removed.
  - Mitigation: centralized suppression + unit tests; code search to remove duplicates.
- Risk: MCP JSON‑RPC framing constraints.
  - Mitigation: scope `WebSocketStream` usage to ping/error/done helpers; do not wrap JSON‑RPC result payloads.

---

## 12. Open Questions

None at this time. Remaining compatibility work (e.g., Audio WS `error_type` alias removal and close-code migration to 1008) is tracked as follow-up tasks and does not block this abstraction from being considered complete.

---

## 13. Acceptance Criteria

- Chat SSE pilot endpoint emits standardized frames with no duplicate `[DONE]` across at least two providers.
- Embeddings orchestrator emits `event: summary` via `SSEStream` with heartbeats controlled by config.
- Audio WS adopts standardized `error` (code/message) and `done` frames and a single ping source; existing domain messages unchanged.
- MCP WS uses shared ping/idle handling and `error/done` helpers where compatible.
- Endpoint‑local SSE helpers removed; tests cover new abstraction; docs updated.

---

## 14. Configuration

- `STREAMS_UNIFIED`: feature flag (currently default ON in dev/test/non‑prod; production can opt out or roll back via flag)
- `STREAM_HEARTBEAT_INTERVAL_S`: default 10
- `STREAM_IDLE_TIMEOUT_S`: default disabled
- `STREAM_MAX_DURATION_S`: default disabled
- `STREAM_HEARTBEAT_MODE`: `comment` or `data` (default `comment`)
- `STREAM_PROVIDER_CONTROL_PASSTHRU`: `0|1` (default `0`), preserves provider SSE control fields when `1`
- `STREAM_QUEUE_MAXSIZE`: default 256 (bounded SSE queue size)

Label guidance: Use low-cardinality labels (e.g., `component`, `endpoint`); avoid user/session IDs. Default suggested: `STREAM_HEARTBEAT_INTERVAL_S=10` with per-endpoint overrides.

---

## 15. Implementation Plan

Stage 0 — Finalize Design and Defaults
- Goal: Lock interface, defaults, metrics, and headers guidance.
- Deliverables:
  - Error semantics (code + message), heartbeat modes, close code mapping confirmed.
  - Defaults: `STREAM_HEARTBEAT_INTERVAL_S=10`, `STREAM_HEARTBEAT_MODE=comment` (use `data` behind reverse proxies), SSE queue size target (~256), `STREAM_PROVIDER_CONTROL_PASSTHRU=0`.
  - Metrics catalog confirmed; labels policy (low-cardinality: component, endpoint) approved.
- Success: PRD approved; tracking issue created for each stage.

Stage 1 — Core Abstractions + Metrics (this PR/commit)
- Status: Complete
- Goal: Implement `SSEStream` and `WebSocketStream` with metrics hooks and labels.
- Code:
  - `tldw_Server_API/app/core/Streaming/streams.py` — abstractions, heartbeats, error/done, WS pings, metrics (`sse_enqueue_to_yield_ms`, `ws_send_latency_ms`, `sse_queue_high_watermark`, `ws_pings_total`, `ws_ping_failures_total`, `ws_idle_timeouts_total`).
  - `tldw_Server_API/app/core/LLM_Calls/sse.py` — debug logs for dropped control/comment lines.
- Tests:
  - `tldw_Server_API/tests/Streaming/test_streams.py` — basic SSE/WS behavior; expand to cover labels presence later.
- Docs:
  - This PRD, Chat/Audio code docs examples, Metrics README (+ Grafana JSON).
- Success: Unit tests pass; example code compiles; metrics exported without errors when registry is enabled.

Stage 2 — Add Provider Control Pass-through + SSE Idle/Max Enforcement
- Status: Complete
- Goal: Implement optional pass-through and SSE timers per PRD.
- Code:
  - Add `provider_control_passthru: bool` and optional `control_filter` hook to `SSEStream`; thread env `STREAM_PROVIDER_CONTROL_PASSTHRU`.
  - Add optional idle/max duration timers to `SSEStream`; on trigger, emit error per 5.6 then `[DONE]` and close.
  - Consider adjusting default `queue_maxsize` to 256 (as per 5.5 guidance).
- Tests:
  - Pass-through on/off snapshots; control filter mapping.
  - Idle and max duration enforcement cases (timeouts emit error + DONE).
- Success: Behavior matches PRD; no regressions in Chat SSE snapshots.

Stage 3 — Chat SSE Pilot Integration
- Status: Complete
- Goal: Migrate one Chat streaming endpoint to `SSEStream` behind `STREAMS_UNIFIED` flag.
- Code:
  - Replace endpoint-local SSE emission for a pilot endpoint (character chat streaming) with `SSEStream` gated by `STREAMS_UNIFIED`.
  - Replace local normalization with provider iterator output (`LLM_Calls/LLM_API_Calls.*iter_sse_lines_*`) and `normalize_provider_line` fallback for non-string chunks. Suppress provider `[DONE]`; call `stream.done()` once.
  - Route provider lines via `send_raw_sse_line` for minimal change.
 - Validate under flag with two providers (e.g., OpenAI + Groq) and with the WebUI client; verify metrics populate and no duplicate `[DONE]`.
  - If validation passes, flip `STREAMS_UNIFIED=1` in non-prod environments and stage a second chat endpoint migration.
 - Rollback: set `STREAMS_UNIFIED=0` and restart the app to revert to legacy code paths (no code changes required).

### Validation Checklist (non‑prod)

Environment
- Use dev/staging with unified streams enabled:
  - Compose overlay: `-f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.dev.yml`
  - or export `STREAMS_UNIFIED=1` in the environment prior to starting the API.
- Ensure provider keys are set for at least two providers (e.g., OpenAI and Groq).
- Optional: behind reverse proxies/CDNs, set `STREAM_HEARTBEAT_MODE=data`.

Functional
- Chat SSE (main): stream completion; assert only one `data: [DONE]` and proper OpenAI deltas.
- Character chat SSE: stream conversation; validate heartbeat presence during idle and single `DONE`.
- Chat document-generation SSE: stream doc; validate heartbeat and final `DONE` without duplicates.
- Embeddings orchestrator SSE (if used): confirm `event: summary` frames appear periodically.
- Prompt Studio SSE fallback (if used): connect and observe initial state + heartbeats.

WebSockets
- Audio WS: open a session; observe `{type:"ping"}` frames; trigger an error path and confirm error frame + close code mapping.
- MCP WS: open a session; confirm lifecycle frames (`ping`, `done` when closed) and that JSON‑RPC responses are unchanged.

Metrics & Dashboards
- Import `Docs/Deployment/Monitoring/Grafana_Streaming_Basics.json`.
- Confirm:
  - `sse_enqueue_to_yield_ms` histogram shows activity during SSE streams.
  - `sse_queue_high_watermark` increases during bursts.
  - `ws_send_latency_ms` histogram increments on WS sends.
  - `ws_pings_total` increments for WS endpoints; `ws_ping_failures_total` remains 0.

Rollback
- Toggle `STREAMS_UNIFIED=0` and restart app to revert to legacy streaming.
- Tests:
  - End-to-end chat SSE with at least two providers; no duplicate `[DONE]`.
  - Snapshot payloads pre/post match (except standardized error/heartbeat cadence).
- Success: Feature-flagged pilot works with WebUI; latency within server-side target.

- Stage 4 — Embeddings SSE Migration
- Status: Complete
- Goal: Move orchestrator events to `SSEStream` while preserving `event: summary`.
- Code:
  - Replace custom `yield f"event: ..."` with `send_event("summary", payload)`; heartbeats via abstraction.
  - Implemented behind `STREAMS_UNIFIED` in `embeddings_v5_production_enhanced.orchestrator_events`.
- Tests:
  - Event cadence and heartbeats; summary payload unchanged; pass-through remains disabled unless explicitly needed.
- Success: No client changes required; metrics visible in dashboard.

Stage 5 — Audio WS Standardization
- Status: Complete
- Goal: Adopt `WebSocketStream` for lifecycle (ping, error, done) without changing domain payloads.
- Code:
  - Unified handler uses `WebSocketStream(..., compat_error_type=True)` and labels `{component: audio, endpoint: audio_unified_ws}`.
  - Standardized error/done semantics; retained legacy quota close (4003) and `error_type` for client compatibility.
  - Routed status/summary frames via `stream.send_json` for metrics coverage; domain payloads unchanged.
- Tests:
  - Quota/concurrency WS tests pass; streaming unit tests cover WS metrics and error/done; additional ping/idle tests can be added if needed.
- Success: Clients unaffected; improved observability in streaming dashboard.

Stage 6 — MCP WS Lifecycle Adoption
- Status: Complete
- Goal: Use `WebSocketStream` for ping/idle/error; never wrap JSON‑RPC content or emit `done` as JSON‑RPC.
- Code:
  - MCP server uses `WebSocketStream` with labels `{component: mcp, endpoint: mcp_ws}`; origin/IP/auth guards in place.
  - Standardized close-code mapping; JSON‑RPC payloads unchanged; lifecycle metrics emitted.
- Tests:
  - Full MCP WS/HTTP test suite passes (JSON-RPC, security, rate limits, etc.).
  - Unified WS lifecycle verified by tests; metrics available for dashboards.
- Success: MCP dashboard unchanged for content; lifecycle metrics added.

Stage 7 — Cleanup, Docs, and Flip Default
- Status: Complete
- Goal: Remove endpoint‑local helpers, update docs, and flip `STREAMS_UNIFIED` default after non‑prod validation.
- Code:
  - Prompt Studio SSE fallback now uses `SSEStream` behind the flag.
  - Embeddings orchestrator, Evaluations SSE, Jobs Admin SSE, Chat SSE paths already unified.
  - Legacy local SSE helpers removed or guarded behind `STREAMS_UNIFIED` for one release window.
  - Default flip of `STREAMS_UNIFIED` applied in dev/test overlays; production can opt out via env or config.
- Docs:
  - API docs and protocol notes reflect standardized lifecycle and close‑code mapping.
  - Monitoring README includes labels guidance and references the Grafana Streaming Basics dashboard.
- Success criteria for this stage:
  - Non‑prod flip validated with WebUI + two providers; no duplicate `[DONE]`; dashboards show healthy SSE/WS metrics.
  - Clear rollback documented (toggle `STREAMS_UNIFIED=0`).

Risk Mitigation & Rollback
- Feature flag per endpoint; can revert to legacy implementation immediately if regressions occur.
- Keep `error_type` alias during rollout; remove after clients confirm.
- Monitor dashboards: p95 WS send latency, SSE enqueue→yield p95, idle timeouts, ping failures; react to anomalies.

Ownership & Tracking
- Create issues per stage with checklists:
  - Code changes with file paths
  - Tests added/updated
  - Docs touched
  - Rollout/flag steps
  - Validation (dashboards/alerts)

---

## 16. Compatibility Follow-ups

Audio WS legacy quota close code
- Current behavior: For client compatibility, the Audio WS handler emits an `error` frame with `error_type: "quota_exceeded"` and closes with code `4003` when quotas are exceeded.
- Target behavior: Migrate to standardized close code `1008` (Policy Violation) with structured `{type: "error", code: "quota_exceeded", message, data?}` and without the legacy `error_type` field once downstream clients have updated.
- Migration plan:
  - Phase 1 (current): Keep `4003` and include `error_type` alias (compat_error_type=True) in `WebSocketStream` for Audio. Documented in API/SDK release notes.
  - Phase 2 (flagged pilot): Expose an opt‑in environment toggle (ops only) to switch close code to `1008` while still including `error_type` for a release. Target: next minor release (v0.1.1).
  - Phase 3 (default switch): Change default to `1008` and keep `error_type` for one additional release. Target: following minor (v0.1.2).
  - Phase 4 (cleanup): Remove `error_type` alias for Audio WS and rely solely on `code` + `message`. Target: subsequent minor (v0.1.3).
  - Acceptance: No client breakages reported in non‑prod → prod flips; tests updated to assert `1008`.
  - Tracking: See Docs/Issues/STREAMS_UNIFIED_Rollout_Tracking.md (Audio `error_type` deprecation task).

Endpoint audit and duplicate closes
- WebSockets
  - Workflows WS, Sandbox WS, Prompt Studio WS, MCP Unified WS, and Persona WS are wrapped with `WebSocketStream` and emit standardized lifecycle metrics/frames. Domain payloads remain untouched where required.
  - Audio WS: outer endpoint still performs some direct `send_json/close` for auth/quota compatibility; the inner unified handler uses `WebSocketStream`. Double‑close risks are minimized (idempotent close), but a follow‑up refactor will consolidate closing into the unified layer after the quota close migration (above) to simplify logic.
  - Parakeet Core demo WS (`/core/parakeet/stream`) is a portable minimal router not mounted in the main app; it intentionally does not use `WebSocketStream` (kept as a standalone sample core).
- SSE
  - Chat: pilot paths (character chat, chat completions, document‑generation) are unified behind `STREAMS_UNIFIED`.
  - Embeddings orchestrator: unified to `SSEStream` behind `STREAMS_UNIFIED` while preserving `event: summary`.
  - Evaluations SSE (`evaluations_unified.py`) now uses `SSEStream` for standardized heartbeats and metrics.

Monitoring/dashboard validation
- Import `Docs/Deployment/Monitoring/Grafana_Streaming_Basics.json` in Grafana (Prometheus datasource UID `prometheus`).
- Confirm Persona WS series appear with labels `{component: persona, endpoint: persona_ws, transport: ws}` in the WS panels.
