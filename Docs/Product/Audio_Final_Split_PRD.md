# PRD: Audio Endpoints Final Split (Phase 2)

- Title: Audio Endpoints Final Split (Phase 2)
- Owner: Server API Team
- Status: Draft
- Target Version: v0.2.x
- Last Updated: 2026-02-08

## Summary

The first audio split is complete (`endpoints/audio/` package exists), but core complexity remains concentrated in a few large modules. This PRD defines the final split to reduce risk in WebSocket flows, TTS/STT orchestration, and test-shim compatibility while preserving all public API behavior.

## Current State (Repo Evidence)

- Aggregator exists: `tldw_Server_API/app/api/v1/endpoints/audio/audio.py`.
- Split modules exist: `audio_tts.py`, `audio_transcriptions.py`, `audio_streaming.py`, `audio_tokenizer.py`, `audio_voices.py`, `audio_health.py`, `audio_jobs.py`, `audio_history.py`, `audiobooks.py`.
- Large remaining files:
  - `audio_streaming.py` ~2663 lines
  - `audio_tts.py` ~912 lines
  - `audio_transcriptions.py` ~885 lines
- Core helper modules already exist and should be expanded, not duplicated:
  - `tldw_Server_API/app/core/Audio/tts_service.py`
  - `tldw_Server_API/app/core/Audio/transcription_service.py`
  - `tldw_Server_API/app/core/Audio/tokenizer_service.py`
  - `tldw_Server_API/app/core/Audio/streaming_service.py`
- Compatibility shims currently relied on by tests:
  - Package shim: `tldw_Server_API/app/api/v1/endpoints/audio/__init__.py`
  - Re-export shim: `tldw_Server_API/app/api/v1/endpoints/audio/audio.py`
  - Quota helper patch points: `can_start_job`, `finish_job`, `increment_jobs_started`

## Problem Statement

Audio routing is modular at file level but still has high-risk concentrated handlers. WebSocket state machines, quota management, BYOK resolution, and error payload shaping are mixed with endpoint code, increasing regression risk and reducing test isolation.

## Goals

- Preserve full API and protocol compatibility for all HTTP and WebSocket endpoints.
- Split `audio_streaming.py` into focused modules by transport/workflow.
- Reduce endpoint-level business logic in `audio_tts.py` and `audio_transcriptions.py`.
- Keep all current monkeypatch/test compatibility points stable.
- Improve unit testability of authentication, quota, payload normalization, and provider selection.

## Non-Goals

- No route path changes.
- No schema or response contract changes.
- No provider behavior changes.
- No DB schema migration.

## Scope

### In Scope

- Internal module refactors under:
  - `tldw_Server_API/app/api/v1/endpoints/audio/`
  - `tldw_Server_API/app/core/Audio/`
- Final breakup of heavy endpoint handlers into smaller orchestration units.

### Out of Scope

- New audio features.
- New providers or model capabilities.
- Jobs framework redesign.

## Target Architecture

### Endpoint Modules (Target)

- Keep `audio.py` as thin router aggregator + compatibility re-exports.
- Convert `audio_streaming.py` to package-style split:
  - `audio_streaming_auth.py` (WS auth and policy checks)
  - `audio_streaming_transcribe_ws.py`
  - `audio_streaming_chat_ws.py`
  - `audio_streaming_tts_ws.py`
  - `audio_streaming_http.py` (`/stream/status`, `/stream/limits`, `/stream/test`, `/chat`)
  - `audio_streaming_payloads.py` (error payload construction and serialization helpers)
- Split TTS endpoint internals:
  - keep route wrappers in `audio_tts.py`
  - move orchestration branches to core service functions in `core/Audio/tts_service.py`
- Split transcription endpoint internals:
  - keep route wrappers in `audio_transcriptions.py`
  - move validation and provider orchestration to `core/Audio/transcription_service.py`

### Core Services (Target)

- Expand `core/Audio/streaming_service.py` for reusable WS state-machine helpers.
- Expand `core/Audio/tts_service.py` for BYOK + provider override + output mapping orchestration.
- Expand `core/Audio/transcription_service.py` for:
  - file validation
  - canonical conversion flow
  - quota checks
  - provider/model resolution
  - response formatting helpers
- Keep tokenizer-specific logic in `core/Audio/tokenizer_service.py`.

## Compatibility Requirements

- Preserve all existing route registrations and tags.
- Preserve all response status codes and body shapes.
- Preserve all current module-level patch points in:
  - `tldw_Server_API/app/api/v1/endpoints/audio/audio.py`
  - `tldw_Server_API/app/api/v1/endpoints/audio/__init__.py`
- Keep WS protocol message formats and close code behavior unchanged.

## Migration Plan

### Phase 1: Helper Extraction

- Move pure helper functions from `audio_streaming.py`, `audio_tts.py`, `audio_transcriptions.py` to core modules.
- Add pass-through wrappers where tests monkeypatch by old symbol paths.

### Phase 2: WebSocket Decomposition

- Introduce streaming submodules and compose them into `audio_streaming.py` (or convert `audio_streaming` to package).
- Keep public import path stable (`audio_streaming` module symbol availability).

### Phase 3: TTS and STT Endpoint Slimming

- Reduce `create_speech` and `create_transcription` handlers to request parsing + response mapping.
- Move orchestration branches into core service functions.

### Phase 4: Cleanup and Final Compatibility Pass

- Remove dead internal glue.
- Verify all shim points still resolve and are monkeypatchable.

## Testing Strategy

- Endpoint contract tests (existing suites) must remain green.
- Add focused unit tests for extracted core helpers:
  - WS auth outcomes
  - quota branches
  - BYOK resolution branches
  - error payload mapping
- Add regression tests for module-level patch compatibility in audio shims.
- Validate WS protocol parity for:
  - `/stream/transcribe`
  - `/chat/stream`
  - `/stream/tts`
  - `/stream/tts/realtime`

## Risks and Mitigations

- Risk: WS regressions due to subtle state-machine differences.
  - Mitigation: extract helpers first, then move handlers with parity tests.
- Risk: Test failures due to changed monkeypatch paths.
  - Mitigation: preserve and document all shim exports until migration complete.
- Risk: Circular imports between endpoint and core service modules.
  - Mitigation: enforce one-way dependency (endpoint -> core service).

## Success Metrics

- `audio_streaming.py` reduced to under ~900 lines.
- `audio_tts.py` and `audio_transcriptions.py` reduced to thin endpoint wrappers.
- No API/WS contract regressions.
- Existing and new audio tests green.

## Acceptance Criteria

- All audio routes and WS endpoints unchanged from client perspective.
- All current compatibility exports in `audio.py` and `audio/__init__.py` preserved.
- New module boundaries are documented and covered by tests.
- CI shows no regression in audio endpoint and WS suites.
