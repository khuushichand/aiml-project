# Parakeet ONNX Default Transcription Design

**Date:** 2026-02-25  
**Status:** Approved

## Context

The repository already supports Parakeet ONNX transcription and currently defaults to Parakeet with variant `mlx` in `tldw_Server_API/Config_Files/config.txt`.  
The ONNX loader already defaults to the Hugging Face repository `istupakov/parakeet-tdt-0.6b-v3-onnx`.

The requested outcome is to make Parakeet ONNX the default transcription path and ensure fail-fast behavior by default for both:

1. Batch/offline paths (REST uploads, ingestion, jobs)
2. Streaming paths (WebSocket)

With one explicit exception:

1. Keep streaming fallback logic available as an operator-controlled escape hatch
2. Default streaming fallback to disabled

## Goals

1. Make `parakeet-onnx` the default transcription model for batch/offline paths.
2. Make `parakeet-onnx` the default transcription model for streaming paths.
3. Make ONNX model id and revision configurable in `[STT-Settings]`.
4. Enforce fail-fast behavior for ONNX failures in batch paths (no silent Whisper fallback).
5. Enforce fail-fast default in streaming, while retaining opt-in `streaming_fallback_to_whisper`.

## Non-Goals

1. No rewrite of provider architecture (no new dedicated `parakeet-onnx` provider type).
2. No broad model parser redesign for arbitrary ONNX Hugging Face IDs in request `model`.
3. No changes to unrelated audio providers (Canary, Qwen2Audio, Qwen3-ASR, VibeVoice).

## Chosen Approach

Use dual defaults with explicit path separation:

1. Batch default key for REST/ingestion/jobs.
2. Streaming default key for WebSocket.
3. Configurable Parakeet ONNX model id + revision.
4. Fail-fast for batch ONNX failures.
5. Streaming fail-fast by default with optional fallback flag retained.

This minimizes blast radius, keeps behavior explicit by path, and preserves operational control.

## Configuration Design

Add/standardize these `[STT-Settings]` keys:

1. `default_batch_transcription_model = parakeet-onnx`
2. `default_streaming_transcription_model = parakeet-onnx`
3. `parakeet_onnx_model_id = istupakov/parakeet-tdt-0.6b-v3-onnx`
4. `parakeet_onnx_revision = <pinned_revision>`
5. `streaming_fallback_to_whisper = false` (default)

Notes:

1. Explicit request-level `model` values continue to override defaults.
2. Existing keys (`default_transcriber`, `default_stt_provider`, `nemo_model_variant`) remain for compatibility, but batch/streaming default selection should prefer the new explicit keys.

## Architecture Changes

### 1) Batch Default Resolution

Affected areas:

1. `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/stt_provider_adapter.py`
2. `tldw_Server_API/app/api/v1/endpoints/audio/audio_transcriptions.py`
3. Batch/ingestion/jobs call paths using `resolve_default_transcription_model(...)`

Design:

1. Update default-model resolver to prefer `default_batch_transcription_model` when batch model is omitted.
2. Preserve fallback behavior only for legacy compatibility in non-Parakeet flows where explicitly intended.

### 2) Streaming Default Resolution

Affected areas:

1. `tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py`
2. `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Streaming_Unified.py`

Design:

1. Update initial streaming config model resolution to prefer `default_streaming_transcription_model`.
2. Keep existing fallback logic branch, but default `streaming_fallback_to_whisper=false` to make fail-fast the default operational mode.

### 3) ONNX Loader Configuration

Affected area:

1. `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Transcription_Parakeet_ONNX.py`

Design:

1. Replace hardcoded-only default with config-driven lookup:
   1. `parakeet_onnx_model_id`
   2. `parakeet_onnx_revision`
2. Keep current defaults as safety fallback values when config is missing.
3. Ensure revision pin is passed into `snapshot_download(...)` deterministically.

## Data Flow

### Batch (REST/Ingestion/Jobs)

1. Request has no `model`.
2. Resolver chooses `default_batch_transcription_model`.
3. `parakeet-onnx` maps to provider `parakeet`, variant `onnx`.
4. ONNX loader uses configured model id + revision.
5. Transcription proceeds or fails.
6. On failure, return explicit error; do not downgrade silently to Whisper.

### Streaming (WS)

1. WS session starts without explicit model in config frame.
2. Server chooses `default_streaming_transcription_model`.
3. Transcriber initializes Parakeet ONNX.
4. On init failure:
   1. If `streaming_fallback_to_whisper=false`, return `model_unavailable` and stop.
   2. If `true`, existing fallback warning + Whisper fallback path is allowed.

## Error Handling Policy

### Batch

1. Parakeet ONNX errors should surface as explicit failures (typed as STT/provider/model unavailable depending callsite).
2. Error payloads include provider/model/variant and a concise operator hint.
3. Do not auto-switch provider to Whisper for Parakeet ONNX failures.

### Streaming

1. Default behavior is fail-fast.
2. Optional fallback remains operator-controlled and explicit.
3. Error frames should continue using stable error taxonomy:
   1. `model_unavailable`
   2. `provider_error`

## Testing Strategy

### Unit

1. Resolver tests for:
   1. `default_batch_transcription_model` behavior.
   2. `default_streaming_transcription_model` behavior.
2. ONNX loader tests confirm:
   1. model id from config is used.
   2. revision from config is used.
3. `speech_to_text` Parakeet ONNX failure path verifies no Whisper fallback in batch path.

### Integration

1. `/api/v1/audio/transcriptions` with omitted `model` resolves to batch default ONNX.
2. Forced ONNX init failure returns fail-fast error.
3. WS streaming default uses ONNX.
4. WS with `streaming_fallback_to_whisper=false` fails fast.
5. WS with `streaming_fallback_to_whisper=true` can fallback to Whisper.

## Documentation Updates

1. `tldw_Server_API/Config_Files/config.txt`
2. `tldw_Server_API/Config_Files/README.md`
3. `Docs/API-related/Audio_Transcription_API.md`
4. Published mirror docs where applicable

Document:

1. New config keys.
2. Default model behavior split (batch vs streaming).
3. Default fail-fast semantics.
4. How to opt into streaming fallback.

## Rollout and Compatibility

1. Explicit client-provided `model` remains highest priority.
2. Legacy deployments can still recover streaming behavior quickly by setting `streaming_fallback_to_whisper=true`.
3. Keep compatibility for existing provider naming and parser aliases.

## Risks and Mitigations

1. **Risk:** Environments without ONNX dependencies fail more often after default switch.  
   **Mitigation:** Clear error hints and optional streaming fallback toggle.

2. **Risk:** Mixed semantics between old and new default keys.  
   **Mitigation:** deterministic precedence and updated documentation.

3. **Risk:** Regressions in jobs/ingestion silent fallback assumptions.  
   **Mitigation:** targeted regression tests on batch failure paths.

## Acceptance Criteria

1. Omitted-model batch requests default to `parakeet-onnx`.
2. Omitted-model streaming sessions default to `parakeet-onnx`.
3. ONNX model id and revision are configurable and used at runtime.
4. Batch Parakeet ONNX failures are fail-fast and not auto-downgraded to Whisper.
5. Streaming fail-fast is default; optional fallback remains available behind `streaming_fallback_to_whisper=true`.
