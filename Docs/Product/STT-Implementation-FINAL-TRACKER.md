# STT-Implementation-FINAL-TRACKER.md

Goal: deliver Waves 1–3 (stabilize STT, ship non-streaming voice command path, harden + harness) so users can issue voice commands and get actions/results.

## Wave 1 — Stabilize STT Baseline
- **VAD defaults + WS latency tests**
  - Tune `vad_threshold`, `min_silence_ms`, `turn_stop_secs` defaults; document recommended client overrides.
  - Add WS integration test with synthetic audio + pauses asserting single final, p50 latency target, and fail-open logging when Silero unavailable.  
  - Touchpoints: `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Streaming_Unified.py`, `tldw_Server_API/app/api/v1/endpoints/audio.py` (WS handler), tests under `tldw_Server_API/tests/audio/test_audio_streaming_unified.py` (or similar).
- **Normalized STT DB contract**
  - Add round-trip test: ingest normalized artifact → `Transcripts`/`MediaChunks`/`UnvectorizedMediaChunks` → reload and compare shape via `to_normalized_stt_artifact`.  
  - Touchpoints: `app/core/Ingestion_Media_Processing/Audio/stt_provider_adapter.py`, `app/core/DB_Management/Media_DB_v2.py`, tests under `tldw_Server_API/tests/media/test_transcripts_normalized_artifact.py` (or similar).
- **Docs**
  - Update `Docs/Audio_STT_Module.md` with VAD knobs, fail-open behavior, and WS latency notes; link to metrics already wired.
- **Exit**
  - WS latency test passes; DB contract test passes; doc merged; defaults locked.

## Wave 2 — Minimal Voice Command Path (Non-Streaming)
- **API + Schemas**
  - Add `POST /api/v1/audio/chat` request/response models (Pydantic) and OpenAPI wiring. Request shape: JSON with base64 audio per PRD (reject oversized/unsupported formats up front). Enforce auth, rate limits, duration/size bounds.  
  - Touchpoints: `app/api/v1/schemas/audio_chat.py` (new), `app/api/v1/endpoints/audio.py` (new route), `app/core/config` validation, size/duration validator shared with STT.
- **Orchestration Service**
  - Implement `SpeechChatService` (or equivalent) to run STT → LLM → TTS/action with structured partial-failure returns and timing fields.  
  - Touchpoints: `app/core/Speech_Chat/speech_chat_service.py` (new), reuse existing STT registry, chat pipeline, TTS service.
- **Action execution**
  - Map transcript to tool/workflow/action (stub or existing tool-calling adapter), enforce permissions/roles, and surface action result alongside text/audio.  
  - Touchpoints: action/tool invocation helper; guardrails for auth/quota; log-safe error mapping (no raw audio/transcript).
- **Persistence**
  - Store user transcript + audio ref as `user` message; assistant reply + audio ref as `assistant` message in existing chat/notes store; return/reuse `session_id`. Make audio retention optional (flag to skip storing audio in prod).  
  - Touchpoints: chat/notes storage layer (ChaChaNotes), schema helpers for message payloads; audio blob storage path/refs.
- **WebUI hook (minimal)**
  - Add “press to talk” path in `tldw-frontend` calling `/api/v1/audio/chat`, playing reply audio, showing transcripts. Keep settings for default STT/LLM/TTS selections.
- **Tests**
  - Unit: schema validation, orchestration success, and each failure leg (STT/LLM/TTS).  
  - Integration: happy path using small fixture audio + stub LLM/TTS/action; auth/quota regression; action execution happy/failure; chat message round-trip with transcript + audio refs.  
  - Touchpoints: `tldw_Server_API/tests/audio/test_audio_chat_api.py`, `tests/core/test_speech_chat_service.py`; WebUI smoke/manual.
- **Exit**
  - Endpoint e2e test green; transcripts persisted; WebUI manual smoke works; timings populated.

## Wave 3 — Hardening + Latency Harness
- **Metrics & Limits**
  - Ensure `/audio/chat` emits STT/LLM/TTS durations and voice-turn totals; propagate `X-Request-Id`. Enumerate metric names/labels (e.g., `audio_chat_latency_seconds{provider,model}`, reuse `voice_to_voice_seconds`, `stt_final_latency_seconds`, `tts_ttfb_seconds`), register once. Add test asserting metrics registry exposes expected series.  
  - Enforce max audio duration/size and per-user concurrency; map errors to clear payloads + WebUI display.  
  - Touchpoints: `audio.py` handler, metrics manager registration, limit helpers; WebUI error surface.
- **Latency Harness**
  - Finish `Helper_Scripts/voice_latency_harness/run.py` with `--short` mode; output JSON (p50/p90 for `stt_final_latency_seconds`, `tts_ttfb_seconds`, `voice_to_voice_seconds`). Provide deterministic mock mode for CI; gate real-provider runs behind env flags.  
  - Add sample fixture and docs on running/interpreting results; optionally expose Prom text output.
- **Docs**
  - Update `Docs/Audio_STT_Module.md` (or `Docs/Product` page) with `/audio/chat` contract, limits, metrics labels, harness usage, retention flags, and logging/PII guidance (avoid raw audio/transcript logs).
- **Tests**
  - Harness dry-run test in CI-ish mode; API tests for over-limit audio and disabled provider; metrics-series existence assertion; manual harness run on reference setup.
- **Exit**
  - Harness produces JSON locally; limit/error-path tests green; docs updated; metrics visible.

## Suggested Cadence (2 weeks)
- Days 1–3: Wave 1 tasks/tests/docs.
- Days 4–8: Wave 2 API/schemas/service/persistence + WebUI hook.
- Days 9–12: Wave 3 metrics/limits/error UX + harness + docs.
- Days 13–14: Buffer for flake fixes and handoff notes.
