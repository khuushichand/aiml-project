# Audio Startup Import Hardening Design

Date: 2026-03-13
Status: Approved for planning

## Summary

Harden backend startup so importing `tldw_Server_API.app.main` does not eagerly pull native audio/STT stacks such as `torch`, `ctranslate2`, `faster_whisper`, or `transformers`.

The immediate bug surfaced as:

- `OMP: Error #179: Function Can't open SHM2 failed`
- backend import failing inside the Codex sandbox
- the failure happening before any audio route was actually used

The root cause is import-time coupling, not runtime request handling. The audio route layer and transcription library still load optional heavy backends too early.

This design keeps the fix narrow:

- make `audio_streaming.py` import-safe by removing direct `Audio_Streaming_Unified` imports from module load
- extract the lightweight `QuotaExceeded` exception so the route layer does not need the full unified streaming module
- make `Audio_Transcription_Lib.py` load `faster_whisper` and `transformers` lazily instead of at import time
- add regression tests that prove route and app imports survive broken optional backends

## Problem Statement

The backend currently imports optional audio/STT backends during startup, even when no audio endpoint is invoked. In constrained environments this can terminate the interpreter during import.

Two import-time choke points matter here:

1. `audio_streaming.py`
   - directly imports `QuotaExceeded`, `UnifiedStreamingConfig`, `UnifiedStreamingTranscriber`, `SileroTurnDetector`, and `handle_unified_websocket` from `Audio_Streaming_Unified`
   - importing that module pulls in the unified streaming stack before a request arrives

2. `Audio_Transcription_Lib.py`
   - imports `faster_whisper.WhisperModel` and `transformers` Qwen2Audio classes at module load
   - these imports can initialize native backends during plain module import

This is a startup architecture problem: optional backends are being treated like core dependencies.

## Goals

- Allow `tldw_Server_API.app.main` to import without touching heavy optional audio backends.
- Keep the existing HTTP and WebSocket route surface unchanged.
- Preserve current audio behavior once a request actually needs the backend.
- Make import failures surface at use time with meaningful errors instead of process death at startup.
- Add deterministic regression tests around import resilience.

## Non-Goals

- Re-architect the full audio subsystem.
- Rewrite streaming transcribers or STT providers.
- Change API shapes or user-facing audio endpoint semantics.
- Remove optional audio/STT backends from the project.

## Existing Repo Anchors

- Audio route aggregation:
  - `tldw_Server_API/app/api/v1/endpoints/audio/audio.py`
- Streaming route module:
  - `tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py`
- Unified streaming implementation:
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Streaming_Unified.py`
- Transcription library:
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Transcription_Lib.py`
- Existing audio import resilience test:
  - `tldw_Server_API/tests/Audio/test_audio_router_import_resilience.py`
- Existing transcription unit tests:
  - `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_audio_transcription.py`

## Reviewed Risks And Adjustments

### 1. Reworking Route Registration Is Larger Than Necessary

Risk: removing `audio_streaming` from startup entirely would require duplicating or proxying every FastAPI route definition in `audio.py`.

Adjustment:

- keep existing route registration
- instead make `audio_streaming.py` itself safe to import
- lazy-load the heavy unified backend only inside request-time helpers

### 2. `QuotaExceeded` Is Embedded In A Heavy Module

Risk: `audio_streaming.py` currently imports `QuotaExceeded` from `Audio_Streaming_Unified`, so even exception wiring forces the heavy module to load.

Adjustment:

- move `QuotaExceeded` to a tiny shared module under `app/core/Audio/`
- have both the route layer and unified streaming layer import the shared exception

### 3. `WhisperModel` Subclassing Forces An Eager Backend Import

Risk: `Audio_Transcription_Lib.py` subclasses `faster_whisper.WhisperModel` at import time, which prevents true laziness.

Adjustment:

- replace eager inheritance with a lazy wrapper that instantiates the real backend class on demand
- preserve the public `WhisperModel` name and `valid_model_sizes` metadata so callers do not need to change

### 4. Import-Safe Code Can Still Hide Runtime Errors

Risk: making imports lazy can defer failures until endpoint execution, which is correct, but only if the user gets a meaningful error.

Adjustment:

- when lazy imports fail, raise descriptive runtime errors that explain the backend is unavailable
- keep current route-level error handling in place so failures surface as API errors instead of startup crashes

## Approved Design

### 1. Make `audio_streaming.py` Import-Safe

Remove the direct import of unified streaming symbols from module load:

- `UnifiedStreamingConfig`
- `UnifiedStreamingTranscriber`
- `SileroTurnDetector`
- `handle_unified_websocket`

Replace them with small request-time loaders:

- one module loader for `Audio_Streaming_Unified`
- constructor helpers for config/transcriber/VAD
- an async wrapper for `handle_unified_websocket`

This keeps the route module importable while preserving the same endpoint behavior once a request arrives.

The route module may still import the lightweight shared `QuotaExceeded` exception at module load.

### 2. Extract `QuotaExceeded` Into A Lightweight Shared Module

Create a small module, for example:

- `tldw_Server_API/app/core/Audio/streaming_exceptions.py`

Move the simple `QuotaExceeded` class there and import it from both:

- `audio_streaming.py`
- `Audio_Streaming_Unified.py`

That breaks the last forced dependency from the route layer back into the heavy unified module.

### 3. Make `Audio_Transcription_Lib.py` Lazy For Optional Heavy Backends

Remove the eager imports of:

- `faster_whisper.WhisperModel`
- `transformers.AutoProcessor`
- `transformers.Qwen2AudioForConditionalGeneration`

Add explicit lazy loaders:

- `_get_original_whisper_model()`
- `_get_qwen2audio_classes()`

Refactor the public `WhisperModel` wrapper to instantiate the real faster-whisper class only inside `__init__`. Preserve:

- `WhisperModel` public name
- `WhisperModel.valid_model_sizes`
- existing model path normalization and cache behavior

For Qwen2Audio, only call the transformers loader inside `load_qwen2audio()`.

### 4. Regression Tests Must Prove Import Safety, Not Just Runtime Behavior

Add focused tests that deliberately poison optional modules and verify imports still succeed:

1. importing `audio_streaming.py` with a broken `Audio_Streaming_Unified` module in `sys.modules`
   - should succeed because no unified symbols are touched at import time
2. importing `tldw_Server_API.app.main` with a broken unified streaming module
   - should succeed because startup no longer requires the unified backend
3. importing `Audio_Transcription_Lib.py` with broken `faster_whisper` and `transformers` modules
   - should succeed because those dependencies are loaded only on demand

These tests should validate the import contract directly, not infer it through unrelated endpoint behavior.

## Testing Strategy

Targeted test coverage:

- `tldw_Server_API/tests/Audio/test_audio_router_import_resilience.py`
  - add import-resilience tests for `audio_streaming.py`
  - add an app-import test for `tldw_Server_API.app.main`
- `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_audio_transcription.py`
  - add import-resilience coverage for `Audio_Transcription_Lib.py`

Verification commands:

- focused pytest runs for the touched tests
- a lightweight `python -c "import tldw_Server_API.app.main"` probe in the project venv
- Bandit on the touched backend paths

## Expected Outcome

After this change:

- backend startup no longer imports heavy optional audio/STT backends by default
- `tldw_Server_API.app.main` can import in constrained environments that do not permit those native backends at startup
- audio/STT failures move to request-time where they can be handled normally
- the current route surface and runtime behavior remain intact for valid environments
