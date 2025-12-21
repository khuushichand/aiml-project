# Speech-to-Speech Chat Pipeline PRD

Owner: Core Voice & Chat Team
Status: Draft (v0.1)

## 1. Summary

Build a first-class speech-to-speech chat experience on top of existing STT, LLM, and TTS modules. Users speak into a microphone and receive spoken responses, with text transcripts and conversation context managed by the server. The overall roadmap covers both simple “send clip, get spoken reply” and low-latency streaming conversations, with **v1 focused on non-streaming** and **v2 adding streaming**.

## 2. Background & Motivation

- Existing capabilities:
  - STT via `WS /api/v1/audio/stream/transcribe` and `POST /api/v1/audio/transcriptions`.
  - LLM chat via `POST /api/v1/chat/completions`.
  - TTS via `POST /api/v1/audio/speech` (streaming + non-streaming).
- Clients can orchestrate STT → LLM → TTS manually, but:
  - Every client reinvents orchestration logic.
  - Conversation context handling and transcripts are inconsistent.
  - Latency, error handling, and UX patterns differ per client.
- Goal: provide a single, well-defined speech chat API that bundles these into a coherent, low-friction experience for the WebUI and external clients.

### 2.1 Assumptions

- v1 is strictly non-streaming: one REST request per turn, with the server running STT → LLM → TTS sequentially for that audio clip.
- v1 does not introduce background jobs or async workers for audio chat; any such offload would be a later optimization or separate design.
- v2 builds on existing unified streaming STT/TTS infrastructure and may evolve in lockstep with `Docs/Audio_Streaming_Protocol.md` and `Docs/Product/Realtime_Voice_Latency_PRD.md`.

## 3. Goals

- Provide a unified speech-to-speech chat pipeline: speech in → text transcript → LLM response → speech out.
- Reuse existing:
  - STT engines and configuration options.
  - LLM provider routing and chat schemas.
  - TTS engines and voice catalog.
- v1 (Non-streaming):
  - “Audio in, audio out” chat turns via a single REST endpoint.
  - Stable session/context handling and transcript persistence.
  - WebUI “press to talk” voice chat experience.
- v2 (Streaming):
  - Streaming conversational mode suitable for real-time voice chat.
  - Partial transcripts, streaming LLM, and streaming TTS.
- Persist:
  - Conversation text history for each session.
  - Optional audio + transcripts for later retrieval, evaluation, and RAG.
- Make it easy for:
  - `tldw-frontend` to add a “voice chat” UI.
  - External clients to integrate via OpenAI-like patterns.

## 4. Non-Goals

- Designing new STT/TTS models or providers.
- Multi-party diarization and speaker separation beyond “user vs assistant”.
- Advanced voice cloning or prosody control beyond existing TTS parameters.
- Full duplex “barge-in” handling (interrupting AI speech mid-utterance) in v1.
- Designing an entirely new AuthNZ or rate-limiting scheme.

## 5. Target Users & Use Cases

### 5.1 Target Users

- Hands-free users who prefer talking instead of typing (e.g., in motion, accessibility).
- Researchers using ingested media/documents who want spoken summaries and follow-ups.
- Users of companion/character chat sessions driven entirely by voice.
- Developers integrating voice chat into their own apps using a single endpoint.

### 5.2 Key Use Cases

1. **Ask & answer**
   - User presses a button and speaks a short question.
   - Server transcribes, calls LLM, and returns both text and an audio reply.
2. **Streaming conversation (v2)**
   - User holds-to-talk or uses VAD-based streaming.
   - Receives partial transcripts followed by streamed TTS of the LLM reply.
3. **Contextual voice chat**
   - Conversation state persists across turns, including persona/system prompts, chatbooks, notes, and RAG context.

## 6. User Experience

### 6.1 Non-Streaming Voice Turn (MVP UX)

- Client:
  - Records audio clip (e.g., 5–30 seconds).
  - Calls a new endpoint (see §7) with audio, session ID (existing or new), and STT/LLM/TTS config.
- Server:
  - Transcribes audio → `user` text message.
  - Appends to conversation history.
  - Calls chat pipeline → `assistant` text message.
  - Synthesizes audio reply from `assistant` text.
  - Responds with:
    - Output audio (single chunk).
    - Text transcript (user + assistant).
    - Updated session metadata (tokens, models, etc.).
- UX:
  - Client plays returned audio and optionally displays captions.

### 6.2 Streaming Voice Conversation (v2)

- WebSocket-based pipeline:
  - Client sends audio frames while capturing mic.
  - Server emits:
    - Partial STT transcripts (for live captions).
    - Final STT transcript for the turn.
    - LLM streaming tokens (optional).
    - Streamed TTS audio frames.
- UX:
  - “Walkie-talkie” style or VAD-based “start/stop listening”.
  - Live captions and progress indicator for response synthesis.

## 7. Functional Requirements

### 7.1 Core Pipeline Behavior

- Accept user audio input:
  - v1: uploaded audio file via a non-streaming REST request.
  - v2: streaming audio frames over WebSocket.
- Produce:
  - Text transcript of user input.
  - Text response from LLM.
  - Audio rendering of LLM response.
- Maintain per-session chat context (equivalent to `/api/v1/chat/completions`):
  - `system`, `user`, `assistant`, and optional `tool` messages.
  - Character/persona configuration.
  - References to ingested media / RAG context.

### 7.2 New API Surface

#### 7.2.1 Non-Streaming Endpoint (v1)

- `POST /api/v1/audio/chat`
- Request (high-level):
  - Auth: same AuthNZ as existing APIs (API key or JWT).
  - Content type: `application/json` (v1).
  - Body:
    - `session_id` (optional): identifies the chat session.
    - `input_audio` (required): base64-encoded audio data for the user utterance.
    - `input_audio_format`: `wav`, `mp3`, `ogg`, etc.
    - `stt_config`:
      - `provider`/`model` (reusing existing audio STT config).
      - `language` (optional).
      - `temperature`/`beam_size`, etc., as supported.
    - `llm_config`:
      - `model`, `provider`, system prompt, tools, temperature, etc.
      - `max_tokens`, `stream` (ignored for non-streaming v1).
    - `tts_config`:
      - `provider`, `voice_id`, `speed`, `format` (e.g., `mp3`, `wav`), etc.
    - `metadata`:
      - Client metadata, trace IDs, etc.
- Response (high-level):
  - Content type: `application/json` (v1).
  - `session_id`: assigned or reused.
  - `user_transcript`: full user text.
  - `assistant_text`: full LLM reply text.
  - `output_audio`: base64-encoded audio data; format per `tts_config`.
  - `output_audio_mime_type`: MIME type for `output_audio` (e.g., `audio/mpeg`, `audio/wav`).
  - `timing`:
    - STT duration, LLM duration, TTS duration.
  - `token_usage`:
    - Prompt/completion tokens.
  - `error` (if any) with structured details.

#### 7.2.2 Streaming Endpoint (v2)

- `WS /api/v1/audio/chat/stream`
- Handshake message:
  - Same `session_id`, `stt_config`, `llm_config`, `tts_config` as above.
- Upstream messages:
  - `audio` frames (binary).
  - Optional control messages (`start_turn`, `end_turn`, `cancel`).
- Downstream messages:
  - `stt_partial` (text, `is_final: false`).
  - `stt_final` (text, `is_final: true`).
  - `llm_delta` (optional text chunks).
  - `tts_audio_chunk` (binary frames, sequence indexed).
  - `turn_complete` event with timing and token usage.
  - `error` events.

### 7.3 Session & Context Management

- A “speech chat session” maps 1:1 with existing chat sessions:
  - Stored in existing notes/chats DB (ChaChaNotes conversations/messages) where possible.
  - Each turn adds:
    - `user` message: STT transcript + reference to audio input.
    - `assistant` message: LLM reply + reference to audio output.
- Requirements:
  - Can create new session implicitly when `session_id` is omitted.
  - Can resume existing sessions with `session_id`.
  - Optional association with:
    - Character/persona.
    - Media documents / RAG pipelines.
    - Chatbooks for export.

### 7.4 Configuration & Defaults

- Provide sensible defaults:
  - Default STT model (fast + decent quality).
  - Default LLM model (small enough for latency, configurable).
  - Default TTS voice (neutral, natural).
- Clients may override:
  - STT model/provider and language.
  - LLM model/provider and parameters.
  - TTS provider/voice/format.
- Validation:
  - Use existing config validation for each subsystem.
  - Return clear errors if requested models/providers are unavailable.

### 7.5 Error Handling

- If STT fails:
  - Return a detailed error (e.g., “audio too short/long”, “unsupported format”).
  - Do not call LLM or TTS.
- If LLM fails:
  - Return STT transcript (if available) and LLM error.
  - Do not call TTS.
- If TTS fails:
  - Return STT and LLM text; include TTS error.
- In all cases:
  - Log errors with context via loguru.
  - Never log raw audio or sensitive text by default (only IDs / hashes).

## 8. Non-Functional Requirements

### 8.1 Performance

- v1 (non-streaming mode, typical 5–10s user utterance):
  - STT: < 1.5s.
  - LLM: configurable; recommend < 3s for default model.
  - TTS: < 1.5s.
  - End-to-end P50: < 5–6s for default settings.
- v2 (streaming mode):
  - First partial STT: < 400ms.
  - First TTS audio chunk: < 1.5–2s after end-of-speech.

### 8.2 Scalability & Limits

- Enforce:
  - Per-user and global limits on concurrent speech chat sessions.
  - Rate limits on audio upload / streaming connections.
  - Max turn duration (e.g., 60–120s per utterance, configurable).
- Behavior when limits exceeded:
  - Explicit error responses (429/403-like semantics).
  - Clear guidance on retry/backoff in error payload.

### 8.3 Security & Privacy

- Reuse AuthNZ middleware and rate limiting:
  - `X-API-KEY` (single-user) or JWT (multi-user).
- Audio/media:
  - Stored only when explicitly configured (e.g., via server config and/or a per-request `store_audio` flag, for chatbooks/evals).
  - Encrypted at rest where supported by current DB/filesystem config.
- Never log:
  - Raw audio payloads.
  - Full transcripts by default (configurable opt-in for debugging in dev).

### 8.4 Reliability

- Graceful degradation when a provider is down:
  - Fallback to alternative STT/LLM/TTS if configured.
  - If no fallback, fail the turn with clear errors.
- Timeouts:
  - Per-subsystem timeouts with safe cancellation (no hung requests).

## 9. Technical Notes & Module Reuse

- **STT**:
  - Reuse implementations behind:
    - `WS /api/v1/audio/stream/transcribe`.
    - `POST /api/v1/audio/transcriptions`.
  - Leverage existing model configuration (faster_whisper, NeMo, Qwen2Audio).
- **LLM**:
  - Use unified interface in `tldw_Server_API/app/core/LLM_Calls/`.
  - Reuse `/api/v1/chat/completions` schemas for `llm_config` wherever possible.
- **TTS**:
  - Reuse `tldw_Server_API/app/api/v1/endpoints/audio.py` TTS handling and `tldw_Server_API/app/core/TTS/`.
  - Use `GET /api/v1/audio/voices/catalog` to populate `voice_id` options in WebUI.
- **New orchestration layer**:
  - Add a dedicated service (e.g., `SpeechChatService`) in a suitable `core` submodule to:
    - Orchestrate STT → LLM → TTS.
    - Manage sessions, timing, and error propagation.
- **Streaming alignment (v2)**:
  - The streaming endpoint (`WS /api/v1/audio/chat/stream`) should align with `Docs/Audio_Streaming_Protocol.md` and `Docs/Product/Realtime_Voice_Latency_PRD.md` for transport details, metrics, and latency/SLO definitions.

## 10. WebUI Integration Requirements

- Add “Voice Chat” mode to `tldw-frontend`:
  - Mic button:
    - Tap-to-record (non-streaming first).
    - Future: hold-to-talk or auto-VAD.
  - Visual indicators:
    - Recording vs processing vs speaking.
    - Live or post-hoc captions.
- Settings panel:
  - Select STT model, LLM model, and TTS voice.
  - Per-session configuration persistence.
- Accessibility:
  - Always show text transcripts.
  - Allow muting TTS while keeping text.

## 11. Metrics & Success Criteria

- **Usage**:
  - Number of speech chat sessions per day.
  - Number of distinct users invoking speech chat.
- **Performance**:
  - End-to-end latency distribution (P50/P90).
  - Failure rates per subsystem (STT/LLM/TTS).
- **Quality (subjective)**:
  - User feedback on transcription accuracy and TTS naturalness.
- **Stability**:
  - WebSocket disconnect/error rate (for streaming).

- Success criteria for v1:
  - ≥ 90% of non-streaming requests complete without error under expected load.
  - Median end-to-end latency under defined thresholds with default models.
  - WebUI users can complete multi-turn voice conversations without manual orchestration.

## 12. Phasing

- **v1 – Non-Streaming Speech Chat**
  - Implement `POST /api/v1/audio/chat` orchestration (STT → LLM → TTS).
  - Wire into existing chat session storage and WebUI “press to talk”.
  - Ship metrics and logging for non-streaming voice turns.
- **v2 – Streaming Speech Chat**
  - Implement `WS /api/v1/audio/chat/stream` with partial STT, streaming LLM, and streaming TTS.
  - Integrate VAD-based turn detection and low-latency playback.
  - Extend WebUI with true “live conversation” mode and streaming metrics.

## 13. Open Questions

- How aggressive should VAD and segmentation be for streaming mode (v2)?
- Do we want interruption (“barge-in”) support in v2 or later?
- Which defaults should we ship for STT/LLM/TTS to balance latency vs quality?
- Any additional metadata (e.g., emotion, confidence scores) that should be exposed in API responses?

---

## Implementation Plan

This plan tracks staged implementation for the Speech-to-Speech pipeline as specified above. Each stage lists goals, success criteria, and concrete test notes. Update **Status** as work progresses.

### Stage 1: v1 API & Schemas
**Goal**: Define and ship the non-streaming REST endpoint `POST /api/v1/audio/chat` with validated schemas and docs.

**Success Criteria**:
- New request/response schemas for `audio chat` live under `tldw_Server_API/app/api/v1/schemas/` and are wired into OpenAPI.
- `POST /api/v1/audio/chat` accepts multipart uploads (or base64) and basic `stt_config`, `llm_config`, and `tts_config`.
- AuthNZ, rate limiting, and basic validation (audio type/size, model availability) match existing `/audio/transcriptions`, `/chat/completions`, and `/audio/speech` patterns.
- Docs page in `Docs/API` describes the endpoint, parameters, and example requests/responses.

**Tests**:
- Unit: schema validation for required/optional fields, config normalization, and error responses for invalid audio or unsupported models.
- Integration: happy-path call using local test audio that exercises STT → stub LLM → stub TTS (or small real models when available), verifying full JSON response shape and HTTP status codes.

**Status**: Not Started

### Stage 2: v1 Orchestration Service (STT → LLM → TTS)
**Goal**: Implement a dedicated orchestration service that performs the end-to-end STT → LLM → TTS pipeline for non-streaming turns.

**Success Criteria**:
- New `SpeechChatService` (or equivalent) lives under `tldw_Server_API/app/core/` and:
  - Invokes existing STT APIs/providers to produce a user transcript.
  - Invokes the unified LLM chat pipeline using existing `/chat/completions` helpers.
  - Invokes TTS providers to synthesize assistant audio.
- Service returns structured results: user transcript, assistant text, audio payload, timings, and token usage.
- Endpoint handler for `POST /api/v1/audio/chat` delegates all core logic to this service.
- Errors in any step (STT, LLM, TTS) propagate as structured errors while returning any partial outputs when available.

**Tests**:
- Unit: orchestration logic with mocked STT/LLM/TTS modules (success, each failure mode, and timeout paths).
- Integration: end-to-end pipeline with at least one configured provider stack (e.g., faster-whisper + a small LLM + Kokoro), verifying timings are recorded and partial failures behave as specified in the PRD.

**Status**: Not Started

### Stage 3: v1 Session Persistence, Context & WebUI Integration
**Goal**: Wire speech turns into existing chat/session storage and expose a usable “press to talk” experience in `tldw-frontend`.

**Success Criteria**:
- Speech chat sessions reuse existing chat/notes storage:
  - Each user utterance is persisted as a `user` message with transcript + audio reference.
  - Each assistant reply is persisted as an `assistant` message with text + audio reference.
- `session_id` semantics match text chat sessions (create on first call, reuse thereafter).
- WebUI adds a “Voice Chat” mode with:
  - Mic button to record and send audio via `POST /api/v1/audio/chat`.
  - Playback of assistant audio and display of both transcripts.
- Default STT/LLM/TTS model/voice selections are surfaced in WebUI settings and persisted per session.

**Tests**:
- Unit: DB/session helpers for storing and retrieving speech messages; mapping between session IDs and WebUI conversations.
- Integration: browser or headless WebUI test that records a short clip (or uses a canned file), sends it to the endpoint, and verifies messages appear correctly in the conversation with working audio playback.

**Status**: Not Started

### Stage 4: v1 Hardening (Metrics, Limits, Error UX)
**Goal**: Harden the non-streaming pipeline with metrics, limits, and clear error UX across API and WebUI.

**Success Criteria**:
- Metrics emitted for:
  - End-to-end non-streaming latency.
  - STT/LLM/TTS durations and error counts.
- Configurable limits:
  - Max audio duration and size per turn.
  - Per-user and global concurrency limits for `audio chat`.
- WebUI surfaces clear errors (e.g., audio too long, provider unavailable, quota exceeded) without breaking sessions.
- Logging uses loguru with correlation IDs and avoids raw audio or full transcripts in production logs.

**Tests**:
- Unit: limit-enforcement helpers, metrics registration, and error-mapping functions.
- Integration: load-style tests for multiple concurrent speech turns (within local constraints), and API/WebUI tests that hit known error paths (oversized audio, disabled provider, invalid config) and validate responses/UX.

**Status**: Not Started

### Stage 5: v2 Streaming Pipeline
**Goal**: Implement the streaming speech chat experience (backend and WebUI) building on v1 primitives.

**Success Criteria**:
- New WebSocket endpoint `WS /api/v1/audio/chat/stream` implements the v2 contract:
  - Accepts audio frames plus config/control messages.
  - Emits partial/final STT, optional LLM deltas, and TTS audio chunks.
- VAD-based turn detection is integrated into the streaming STT path and used to finalize turns promptly.
- Streaming TTS uses existing Kokoro/streaming infrastructure where possible and exposes a low-latency PCM option.
- WebUI “live conversation” mode:
  - Captures and streams mic audio.
  - Shows live captions and plays incremental TTS audio.
- Streaming metrics collected (voice-to-voice latency, stream error rates) and exposed alongside v1 metrics.

**Tests**:
- Unit: streaming handlers with mocked STT/LLM/TTS; VAD configuration and turn-finalization logic; backpressure handling.
- Integration: WebSocket tests that simulate audio frames and verify event sequencing; manual/automated WebUI tests measuring approximate voice-to-voice latency on a reference setup.

**Status**: Not Started
