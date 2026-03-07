# Voice Chat Overlap + Interrupt Design

## Context

`tldw_server` already has a production voice stack with:

- `WS /api/v1/audio/chat/stream` for STT -> LLM -> TTS streaming
- `WS /api/v1/audio/stream/tts/realtime` for realtime text-to-speech session streaming
- `apps/packages/ui/src/hooks/useVoiceChatStream.tsx` as the web client hook

Current `audio/chat/stream` behavior is sequential per turn: stream LLM deltas, then start TTS. This increases first-audio latency and weakens interruption semantics when users barge in.

## Goals

1. Reduce perceived turn latency by overlapping LLM and TTS generation.
2. Add explicit interruption semantics (`interrupt` + `interrupted`) while preserving backward compatibility.
3. Apply interruption support to both:
   - `WS /api/v1/audio/chat/stream`
   - `WS /api/v1/audio/stream/tts/realtime`
4. Add test coverage for overlap and interruption (backend + frontend).

## Non-Goals

- No breaking protocol changes.
- No auth/quota model redesign.
- No transport migration (keep current JSON+binary WS framing).

## Considered Approaches

### Approach 1: Incremental overlap in `audio/chat/stream` (Recommended)

Keep existing route and frames. Add per-turn orchestration so LLM deltas are chunked into phrases and committed into realtime TTS session during generation. Add additive interrupt events.

Pros:
- Lowest migration risk
- Reuses existing TTS realtime session primitives
- Preserves existing clients

Cons:
- More turn-state management in one endpoint

### Approach 2: Bridge through `audio/stream/tts/realtime`

Internally proxy `audio/chat/stream` LLM output through a nested realtime TTS flow.

Pros:
- Strong endpoint reuse

Cons:
- Added indirection, harder tracing/debugging, higher orchestration complexity

### Approach 3: Client-only overlap

Keep server flow, do phrase-level TTS requests from client.

Pros:
- Minimal backend work

Cons:
- Weak cancellation guarantees, races, duplicated client complexity

## Recommendation

Implement Approach 1.

## Architecture

### 1) `audio/chat/stream` Turn Orchestrator

Add connection-scoped state in `websocket_audio_chat_stream`:

- `active_turn_id: str | None`
- `active_llm_task: asyncio.Task | None`
- `active_tts_sender_task: asyncio.Task | None`
- `active_realtime_tts_session: RealtimeTTSSession | None`
- `turn_cancelled: bool`

Each emission path (delta/text/audio/status) checks `turn_id == active_turn_id` before sending.

### 2) Overlapped LLM -> Phrase Chunker -> Realtime TTS

Inside finalize flow:

1. Start LLM streaming as today.
2. Route deltas to:
   - client (`llm_delta`)
   - phrase chunker buffer
3. On phrase boundary, `session.push_text(phrase)` + `session.commit()`.
4. Start TTS sender task once session is ready; emit:
   - `tts_start` on first audio bytes
   - binary frames continuously
   - `tts_done` when stream drains

The full assistant text still emits via `llm_message` and `assistant_summary`.

### 3) Realtime TTS Endpoint Interrupt Support

For `websocket_tts_realtime`:

- Accept new frame: `{"type":"interrupt","reason":"..."}`.
- On interrupt:
  - cancel current synthesis/buffered in-flight chunks
  - keep connection/session reusable for new text frames
  - emit `{"type":"interrupted", ...}`.

### 4) Frontend Voice Chat Hook

In `useVoiceChatStream`:

- when barge-in is enabled and user speech resumes during speaking, send `interrupt` (not only commit/stop behaviors).
- handle `interrupted` frame to transition to `listening` cleanly.
- ignore late audio for interrupted turn via turn guard metadata.

## Protocol Changes (Additive)

### Client -> Server

- `interrupt`
  - `{"type":"interrupt","reason":"barge_in|user_stop|client_cancel"}`

### Server -> Client

- `interrupted`
  - `{"type":"interrupted","turn_id":"...","phase":"llm|tts|both","reason":"..."}`.

### Compatibility

- Existing frames remain unchanged.
- Existing clients that never send `interrupt` keep current behavior.
- Clients ignoring `interrupted` still function.

## Data Flow

### `audio/chat/stream`

1. Client sends audio chunks.
2. STT emits partials.
3. Commit/auto-commit finalizes transcript.
4. LLM delta stream begins.
5. Phrase chunker commits phrase text to realtime TTS session.
6. TTS binary frames stream while LLM still producing deltas.
7. Final `llm_message` + `assistant_summary` + `tts_done`.

### Interrupt Path

1. Client sends `interrupt`.
2. Server marks active turn cancelled.
3. Cancel LLM stream + TTS session sender task.
4. Drop stale late chunks by turn guard.
5. Emit `interrupted`.
6. Return to listening/next-turn ready state.

## Concurrency and Error Handling

1. Single active turn per socket. New commit while active turn exists can either:
   - auto-interrupt previous turn then start next, or
   - return warning and require explicit interrupt.
   Recommendation: auto-interrupt with explicit `interrupted`.
2. Exactly one terminal turn event:
   - normal completion path OR interrupted path (never both).
3. Error handling:
   - LLM failure: `error(code=llm_error)` and clean turn teardown.
   - TTS failure: `error(code=tts_error)` + `interrupted(phase="tts")`.
4. Keep socket open unless explicit `stop` or transport failure.

## Metrics and Observability

Keep existing metrics; add labels/counters for interruption quality:

- `audio_chat_interrupt_total{reason,phase}`
- `audio_chat_stale_chunk_drop_total{phase}`
- Optional histogram for `interrupt_to_quiet_seconds`

Continue existing:

- `stt_final_latency_seconds{endpoint="audio.chat.stream"}`
- `voice_to_voice_seconds{route="audio.chat.stream"}`
- `tts_ttfb_seconds`

## Testing Strategy

### Backend

Extend:

- `tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py`
  - interrupt cancels in-flight LLM/TTS
  - stale audio dropped after interrupt
  - overlap starts TTS before final LLM completion
  - backward compatibility behavior
- `tldw_Server_API/tests/Audio/test_ws_tts_realtime_endpoint.py`
  - interrupt cancels current synthesis without closing
  - post-interrupt text resumes synthesis

### Frontend

Add hook tests for:

- `useVoiceChatStream` sends `interrupt` on barge-in during speaking.
- transitions on `interrupted`.
- stale audio rejection for interrupted turn.

## Rollout

1. Add behind env toggle:
   - `AUDIO_CHAT_WS_OVERLAP_ENABLED=1` (default off initially)
   - `AUDIO_WS_INTERRUPT_ENABLED=1` (default on)
2. Enable in dev/staging first.
3. Validate latency harness and interruption tests.
4. Flip overlap default on after metrics baseline is stable.

## Risks and Mitigations

1. Race conditions from task cancellation
   - mitigation: strict `turn_id` guards + deterministic teardown ordering.
2. Realtime adapter variance across providers
   - mitigation: use existing `BufferedRealtimeSession` fallback path.
3. Client divergence
   - mitigation: additive protocol and compatibility tests.

## Acceptance Criteria

1. `audio/chat/stream` can emit TTS bytes before final `llm_message` on long replies.
2. Sending `interrupt` during speaking prevents further audio from the interrupted turn.
3. `audio/stream/tts/realtime` accepts `interrupt` and continues usable session lifecycle.
4. Existing clients without `interrupt` continue operating unchanged.
5. New backend/frontend tests pass and prevent regressions.
