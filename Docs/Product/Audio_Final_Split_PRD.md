# PRD: Audio Endpoints Final Split (Phase 2)

- Title: Audio Endpoints Final Split (Phase 2)
- Owner: Server API Team
- Status: Execution Ready
- Target Version: v0.2.x
- Last Updated: 2026-02-08

## Summary

Audio endpoint splitting is partially complete, but most complexity is still concentrated in three modules: `audio_streaming.py`, `audio_tts.py`, and `audio_transcriptions.py`. This PRD defines the final extraction plan to make those modules thin orchestration layers while preserving all HTTP and WebSocket contracts and all test monkeypatch paths.

## Repo Evidence (Current Baseline)

- Audio endpoint package exists at `tldw_Server_API/app/api/v1/endpoints/audio/`.
- Current line counts:
  - `audio_streaming.py`: 2663 lines
  - `audio_tts.py`: 912 lines
  - `audio_transcriptions.py`: 885 lines
  - `audio.py` aggregator: 257 lines
  - `__init__.py` package shim: 75 lines
- Current route concentration:
  - `audio_streaming.py` contains 4 WS handlers and 4 HTTP handlers.
  - `audio_tts.py` contains `/speech`, `/speech/metadata`, provider/voice/metrics endpoints.
  - `audio_transcriptions.py` contains `/transcriptions`, `/translations`, `/segment/transcript`.
- Existing core modules already available for expansion:
  - `tldw_Server_API/app/core/Audio/streaming_service.py`
  - `tldw_Server_API/app/core/Audio/tts_service.py`
  - `tldw_Server_API/app/core/Audio/transcription_service.py`
  - `tldw_Server_API/app/core/Audio/error_payloads.py`
  - `tldw_Server_API/app/core/Audio/quota_helpers.py`
  - `tldw_Server_API/app/core/Audio/tokenizer_service.py`

## Problem Statement

The endpoint layer still owns too much business logic:

- `audio_streaming.py` mixes WS auth, quota checks, protocol error payloads, state-machine orchestration, shim indirection, and HTTP handlers.
- `audio_tts.py` mixes request sanitization, BYOK/provider resolution, content-type handling, streaming lifecycle, non-streaming aggregation, and history persistence.
- `audio_transcriptions.py` mixes upload validation, temp-file lifecycle, provider/model resolution, quota enforcement, and response shaping.

This makes behavior difficult to test in isolation and increases regression risk when touching transport-level logic.

## Goals

- Preserve all `/api/v1/audio/*` path behavior and WS protocol behavior.
- Decompose `audio_streaming.py` into workflow-specific modules.
- Slim `create_speech` and `create_transcription` into endpoint wrappers.
- Expand existing core audio service modules instead of duplicating logic.
- Preserve all existing compatibility exports used by tests.

## Non-Goals

- No path/schema/response contract changes.
- No provider capability changes.
- No audio jobs/audiobooks redesign.
- No DB schema changes.

## Scope

### In Scope

- Refactors in:
  - `tldw_Server_API/app/api/v1/endpoints/audio/`
  - `tldw_Server_API/app/core/Audio/`
- Final extraction of heavy logic from streaming/TTS/transcription endpoints.

### Out of Scope

- New audio features.
- New providers.
- Worker/job orchestration redesign.

## Compatibility Contract (Must Preserve)

### Stable Endpoint Entry Points

- `tldw_Server_API.app.api.v1.endpoints.audio.audio`
- `tldw_Server_API.app.api.v1.endpoints.audio` (package shim)

### Critical Monkeypatch/Import Symbols

From `audio.py`:
- `_resolve_tts_byok`
- `_audio_ws_authenticate`
- `_stream_tts_to_websocket`
- `CHAT_HISTORY_MAX_MESSAGES`
- `websocket_transcribe`
- `websocket_audio_chat_stream`
- `websocket_tts`
- `websocket_tts_realtime`
- `can_start_job`
- `finish_job`
- `increment_jobs_started`

From `audio/__init__.py`:
- `create_speech`
- `get_tts_service`
- `_resolve_tts_byok`
- `check_rate_limit`
- `get_usage_event_logger`
- `save_and_register_tts_audio`
- shared quota helpers currently re-exported there

No symbol above should disappear during split phases.

## Target Module Map

### Endpoint Layer

- Keep `audio.py` as aggregator + compatibility re-export layer.
- Keep `audio/__init__.py` as package-level shim.
- Decompose `audio_streaming.py` into siblings, then retain `audio_streaming.py` as facade:
  - `audio_streaming_ws_auth.py`
  - `audio_streaming_ws_transcribe.py`
  - `audio_streaming_ws_chat.py`
  - `audio_streaming_ws_tts.py`
  - `audio_streaming_http.py`
  - `audio_streaming_shims.py` (shared shim lookup/compat glue)

### Core Layer

- Expand `core/Audio/streaming_service.py` for transport-agnostic helpers.
- Consolidate WS payload helpers into `core/Audio/error_payloads.py` (preserve existing payload shape).
- Keep quota/env parsing in `core/Audio/quota_helpers.py` and remove duplicate endpoint-local variants.
- Expand `core/Audio/tts_service.py` for TTS orchestration helpers currently embedded in endpoint code.
- Expand `core/Audio/transcription_service.py` for STT flow orchestration and response builders.

## Function-Level Extraction Plan

### `audio_streaming.py`

- Move shim selector helpers (`_audio_shim_attr` + `_shim_*`) into `audio_streaming_shims.py`.
- Move WS error payload builders (`_audio_ws_error_payload`, `_audio_ws_quota_error_payload`) into `core/Audio/error_payloads.py` or a thin endpoint adapter around it.
- Split WS handlers by route:
  - `/stream/transcribe` -> `audio_streaming_ws_transcribe.py`
  - `/chat/stream` -> `audio_streaming_ws_chat.py`
  - `/stream/tts` and `/stream/tts/realtime` -> `audio_streaming_ws_tts.py`
- Keep HTTP handlers in `audio_streaming_http.py`:
  - `audio_chat_turn`
  - `streaming_status`
  - `streaming_limits`
  - `test_streaming`

### `audio_tts.py`

- Keep route declarations in `audio_tts.py`.
- Move orchestration branches from `create_speech`/`create_speech_metadata` into `core/Audio/tts_service.py`:
  - BYOK/provider resolution flow
  - content-type mapping and response selection
  - streaming vs non-streaming generation paths
  - history write payload composition and status derivation

### `audio_transcriptions.py`

- Keep route declarations in `audio_transcriptions.py`.
- Move workflow blocks from `create_transcription` into `core/Audio/transcription_service.py`:
  - request normalization/default model resolution
  - upload persistence/temp file workflow
  - quota guards and minute accounting
  - provider/model adapter execution path
  - response payload assembly (including optional segment data)

## Implementation Phases

### Phase 1: Extract Pure Helpers (Low Risk)

- Move stateless helper functions first.
- Add wrappers in old modules to preserve symbol paths.

### Phase 2: Streaming Decomposition

- Extract WS/HTTP handlers from `audio_streaming.py` into dedicated modules.
- Leave `audio_streaming.py` as compatibility facade exporting `router`, `ws_router`, and legacy symbols.

### Phase 3: TTS Endpoint Slimming

- Move orchestration internals out of `create_speech` and `create_speech_metadata`.
- Keep endpoint signatures/dependencies unchanged.

### Phase 4: Transcription Endpoint Slimming

- Move orchestration internals out of `create_transcription` and `create_translation`.
- Keep route behavior and response contracts unchanged.

### Phase 5: Compatibility and Cleanup

- Remove dead duplicate logic.
- Keep all documented shim symbols and verify monkeypatch compatibility.

## Test Plan

### Required Regression Suites

- `tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py`
- `tldw_Server_API/tests/TTS_NEW/integration/test_transcription_auth.py`
- `tldw_Server_API/tests/STT/test_audio_transcription_api.py`
- `tldw_Server_API/tests/Audio/test_audio_chat_endpoint.py`
- `tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py`
- `tldw_Server_API/tests/Audio/test_ws_tts_endpoint.py`
- `tldw_Server_API/tests/Audio/test_ws_tts_realtime_endpoint.py`
- `tldw_Server_API/tests/Audio/test_stream_status_endpoint.py`
- `tldw_Server_API/tests/Audio/test_stream_limits_endpoint.py`
- `tldw_Server_API/tests/Audio/test_ws_quota.py`

### New/Updated Unit Coverage

- Shim resolution behavior (`audio` module vs package-level overrides).
- WS error payload formatting parity.
- BYOK resolution and missing-credential branches.
- Transcription provider resolution and quota-guard branches.

### Contract Verification

- OpenAPI paths under `/api/v1/audio/*` remain unchanged.
- WS endpoints remain unchanged:
  - `/api/v1/audio/stream/transcribe`
  - `/api/v1/audio/chat/stream`
  - `/api/v1/audio/stream/tts`
  - `/api/v1/audio/stream/tts/realtime`

## Risks and Mitigations

- Risk: WS protocol regressions (error shape/close behavior).
  - Mitigation: snapshot parity tests before and after each extraction phase.
- Risk: Test breakage from monkeypatch symbol movement.
  - Mitigation: keep facade exports in `audio.py` and package shim in `audio/__init__.py`.
- Risk: Circular imports across endpoint and core modules.
  - Mitigation: enforce one-way dependency (endpoint -> core service), use lazy imports where necessary for shims.

## Success Metrics

- `audio_streaming.py` reduced from 2663 to <900 lines.
- `audio_tts.py` and `audio_transcriptions.py` reduced to thin orchestration wrappers.
- No API/WS contract regressions.
- Regression suites and new unit tests pass.

## Acceptance Criteria

- Route paths and response contracts remain stable for clients.
- WS message and close-code behavior remains unchanged.
- Compatibility exports in `audio.py` and `audio/__init__.py` remain importable.
- Heavy orchestration logic is relocated to focused endpoint submodules and `core/Audio/*` services.
