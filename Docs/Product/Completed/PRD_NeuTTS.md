# PRD: NeuTTS-Nano and NeuTTS-Air Support

## Background

tldw_server supports multiple TTS providers with OpenAI-compatible endpoints. NeuTTS provides on-device, English-only, voice cloning TTS using a lightweight LLM plus codec pipeline, with streaming supported only for GGUF backbones (llama.cpp). This PRD describes how to add NeuTTS-Nano and NeuTTS-Air as local TTS providers.

## Goals

- Add NeuTTS-Nano and NeuTTS-Air as supported local TTS providers.
- Enable voice cloning using stored reference codes and reference text.
- Support optional per-request reference audio/text overrides when needed.
- Support streaming synthesis when GGUF backbones are used.
- Keep the default path fully offline.

## Non-goals

- Multilingual TTS (NeuTTS is English-only today).
- Training or finetuning workflows.
- Automatic model download by default.

## Decisions

- Voice cloning maps to stored reference codes by default via `voice="custom:<voice_id>"`.
- Per-request `voice_reference` + `extra_params.reference_text` is allowed as an optional override.
- Stored references can persist `reference_text` and provider artifacts (e.g., NeuTTS `ref_codes`) via `/api/v1/audio/voices/encode`.
- `extra_params.reference_text` and `extra_params.ref_codes` are accepted per request and override stored metadata when provided.
- Bundle a default reference voice from `/Helper_Scripts/Audio/Sample_Voices/Sample_Voice_1.wav`.
- Store reference audio and codes using the existing voice manager filesystem pattern under per-user voices directories.
- Automatic model download is disabled by default.
- Streaming output format defaults to PCM s16le, 24kHz, mono for widest compatibility.
- For NeuTTS streaming, WAV is not supported because current WAV streaming buffers until finalize; allow PCM/MP3/OPUS and reject WAV when `stream=true`.

## User Stories

- As a local user, I can upload a reference voice once and reuse it by passing `custom:<voice_id>`.
- As a local user, I can optionally provide reference audio/text per request for ad-hoc voices.
- As a power user, I can pre-encode NeuTTS reference codes for faster reuse.
- As a power user, I can use GGUF backbones for low-latency streaming output.
- As an offline user, I can point to local model and codec files without network access.
- As a new user, I can try NeuTTS immediately using the bundled default voice.

## Functional Requirements (MVP)

- Provider integration:
  - Provider option: `neutts` with models `neutts-nano` and `neutts-air`, plus GGUF variants.
  - Support local paths and HF repo IDs for backbone/codec (downloads disabled by default).
- Voice mapping:
  - Use `voice="custom:<voice_id>"` to load stored reference audio and metadata.
  - Accept optional per-request `voice_reference` (base64 audio) and `extra_params.reference_text`.
  - Persist optional `reference_text` on upload and provider artifacts via `voices/encode`.
  - `extra_params.ref_codes` accepted per request; stored artifacts are used by default.
- Output requirements:
  - Sample rate: 24kHz output.
  - Non-streaming responses follow existing `response_format` values.
  - Streaming responses default to PCM s16le, 24kHz, mono; MP3/OPUS are also supported (WAV is not).
- Streaming:
  - Streaming supported only for GGUF backbones.
  - Clear error if streaming is requested with non-GGUF backbones.
  - For NeuTTS, validate `response_format` when `stream=true` and allow PCM/MP3/OPUS (or other truly streaming formats). WAV must be rejected or coerced to non-streaming.
- Caching:
  - Reuse loaded backbone and codec per worker.
  - Optional cache for reference codes by voice ID.
- Validation:
  - Validate reference audio size/type; duration is recommended (3-15s) but not enforced yet.
  - Validate file size/type and sanitize filenames.
- Errors:
  - Clear errors for missing dependencies (espeak-ng, llama-cpp-python, onnxruntime).
  - Clear errors for invalid or missing reference codes.

## API and Data Contracts

- Existing endpoint: `POST /api/v1/audio/speech`
- `voice="custom:<voice_id>"` resolves stored references before validation.
- `voice_reference` and `extra_params.reference_text` are optional per request and override stored metadata.

Example request:

```json
{
  "model": "neutts-air",
  "input": "Hello world",
  "voice": "custom:default",
  "response_format": "pcm",
  "stream": true,
}
```

Voice creation options:

- `POST /api/v1/audio/voices/upload` stores reference audio (optionally `reference_text`).
- `POST /api/v1/audio/voices/encode` generates provider artifacts (NeuTTS `ref_codes`) for a stored voice.

Stored voice request example:

```json
{
  "model": "neutts-air",
  "input": "Hello world",
  "voice": "custom:VOICE_ID",
  "response_format": "pcm",
  "stream": false
}
```

Optional per-request override example:

```json
{
  "model": "neutts-air",
  "input": "Hello world",
  "voice": "custom:VOICE_ID",
  "response_format": "pcm",
  "stream": false,
  "voice_reference": "<base64-audio>",
  "extra_params": {
    "reference_text": "Hello world"
  }
}
```

## Storage and Voice Management

- NeuTTS integrates with the voice manager for stored references.
- Stored reference audio is kept per user; metadata includes `reference_text` and provider artifacts.
- `custom:` voice IDs resolve to stored audio + metadata; per-request values override stored metadata.
- Storage is adapter-neutral so future TTS providers can reuse stored references.
- Default voice assets ship from `/Helper_Scripts/Audio/Sample_Voices/Sample_Voice_1.wav` and are registered on first use.

## Configuration

- Provider config keys (defaults via `tts_providers_config.yaml`):
  - `providers.neutts.enabled=true|false`
  - `providers.neutts.backbone_repo=neuphonic/neutts-air`
  - `providers.neutts.codec_repo=neuphonic/neucodec`
  - `providers.neutts.backbone_device=cpu|gpu`
  - `providers.neutts.codec_device=cpu`
  - `providers.neutts.auto_download=false`
- Dependencies:
  - `neutts`, `neucodec`, `phonemizer`, `espeak-ng`
  - `llama-cpp-python` for GGUF
  - `onnxruntime` for ONNX decoder
  - `perth` optional for watermarking

## UX / UI

- TTS settings:
  - Provider selection: NeuTTS-Nano / NeuTTS-Air / GGUF variants.
  - Reference audio + reference text optional per request; stored `custom:` voices are the default path.
- Voice library:
  - List saved voices with metadata.
  - Encode stored voices for NeuTTS reference codes.
  - Delete voices.

## Non-functional Requirements

- Performance: real-time on CPU for Nano where feasible.
- Memory: avoid per-request model loads; reuse per worker.
- Security: never log reference audio/text; sanitize inputs.
- Offline by default; explicit opt-in for downloads.

## Streaming Limitations

- NeuTTS streaming is supported only for GGUF backbones (llama-cpp).
- WAV is not considered a true streaming format in the current stack because headers are finalized at the end; for NeuTTS `stream=true`, allow PCM/MP3/OPUS (and other truly streaming formats) only.

## Observability

- Log provider, model, device, latency, stream vs non-stream.
- Track missing dependency errors and invalid reference inputs.

## Testing

- Unit tests:
  - Schema validation for NeuTTS fields.
  - Reference audio validation rules.
- Integration tests:
  - `/api/v1/audio/speech` with NeuTTS mock.
  - `/api/v1/audio/voices/encode` and `custom:` voice resolution.
  - Streaming path for GGUF with stubbed backend.
- Property-based tests:
  - Reference input validation (size/type/length).
- Mock external downloads; tests must be offline-capable.

## Risks

- Licensing: NeuTTS-Air is Apache 2.0; NeuTTS-Nano uses NeuTTS Open License 1.0.
- Default voice sample licensing and redistribution constraints.
- Dependency friction for espeak-ng and phonemizer.

## Milestones

- M1: Backend provider wired to TTS service and adapters.
- M2: Voice upload/encode stores reference codes and custom voice resolution is supported.
- M3: Streaming support for GGUF and UI updates.
- M4: Documentation and deployment guidance updated.

## Open Questions

- Should we add true WAV streaming support (header-first) or keep WAV disabled for NeuTTS streaming?

## Staged Implementation Plan

### Stage 1: Provider wiring + config validation
**Goal**: Expose NeuTTS provider through the TTS adapter registry and configuration with offline defaults.
**Scope/Deliverables**:
- Add provider config block for NeuTTS with `auto_download=false` by default.
- Register NeuTTS in adapter registry and provider catalog.
- Extend validation maps to include NeuTTS formats, languages, and max text length.
**Key Tasks**:
- Update `tts_providers_config.yaml` and config parsing to include NeuTTS settings.
- Ensure provider resolution maps model names to NeuTTS.
- Add `neutts` to format/language validation tables.
**Dependencies**:
- NeuTTS adapter module available and importable.
**Success Criteria**: NeuTTS appears in provider catalog, config keys are parsed, and validation recognizes NeuTTS formats/languages.
**Tests**: Unit tests for config parsing and `tts_validation` provider maps; adapter registry lookup tests.
**Status**: Not Started

### Stage 2: Voice storage + default voice
**Goal**: Store NeuTTS reference audio, ref_text, and ref_codes using the existing voice manager filesystem layout and register a default voice from `/Helper_Scripts/Audio/Sample_Voices/Sample_Voice_1.wav`.
**Scope/Deliverables**:
- Persist per-voice metadata for `reference_text` and `ref_codes`.
- Add default voice registration on first use or service startup.
- Ensure `custom:<voice_id>` resolves to stored metadata.
**Key Tasks**:
- Extend voice upload/encode pipeline to store `reference_text` and `ref_codes` for NeuTTS.
- Define how metadata is stored alongside voice files (metadata file or sidecar).
- Register default voice for each user if not present.
**Dependencies**:
- Default voice file exists and licensing is approved.
- Voice manager storage paths are stable.
**Success Criteria**: `custom:<voice_id>` resolves to stored reference metadata; default voice is available on first use.
**Tests**: Integration tests for voice upload/encode and custom voice resolution; file storage layout checks.
**Status**: Not Started

### Stage 3: Streaming enforcement + format gating
**Goal**: Enforce GGUF-only streaming and allow PCM streaming only for NeuTTS.
**Scope/Deliverables**:
- Validate streaming requests against GGUF capability.
- Enforce PCM/MP3/OPUS (or other truly streaming formats) for NeuTTS streaming.
- Reject WAV streaming or coerce to non-streaming.
**Key Tasks**:
- Check `request.stream` with NeuTTS capability and gate non-GGUF backbones.
- Add format gating in NeuTTS adapter or service layer for streaming requests.
- Ensure PCM streaming path uses normalized int16 chunk output.
**Dependencies**:
- NeuTTS streaming implementation uses `infer_stream` for GGUF only.
**Success Criteria**: `stream=true` with non-GGUF models fails fast; PCM/MP3/OPUS streams successfully; WAV streaming is rejected or coerced to non-streaming.
**Tests**: Streaming tests for GGUF path; negative tests for non-GGUF streaming and WAV streaming.
**Status**: Not Started

### Stage 4: API polish + UI + docs
**Goal**: Finalize API ergonomics (optional per-request override), update UI controls, and document NeuTTS setup and limitations.
**Scope/Deliverables**:
- OpenAI-compatible request examples for NeuTTS (stored voice + per-request override).
- UI model/voice selection and default voice visibility.
- Documentation for dependencies, offline setup, and streaming constraints.
**Key Tasks**:
- Update API schema docs and example payloads.
- Update UI to surface NeuTTS models and stored voices.
- Add setup guidance and streaming limitation notes to TTS docs.
**Dependencies**:
- UI configuration for provider catalog is in place.
**Success Criteria**: UI shows NeuTTS models/voices; docs describe dependencies and streaming constraints; OpenAI-compatible API examples updated.
**Tests**: UI smoke tests; docs/examples lint checks if applicable.
**Status**: Not Started
