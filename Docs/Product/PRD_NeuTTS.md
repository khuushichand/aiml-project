# PRD: NeuTTS-Nano and NeuTTS-Air Support

## Background

tldw_server supports multiple TTS providers with OpenAI-compatible endpoints. NeuTTS provides on-device, English-only, voice cloning TTS using a lightweight LLM plus codec pipeline, with streaming supported only for GGUF backbones (llama.cpp). This PRD describes how to add NeuTTS-Nano and NeuTTS-Air as local TTS providers.

## Goals

- Add NeuTTS-Nano and NeuTTS-Air as supported local TTS providers.
- Enable voice cloning using stored reference codes and reference text.
- Support streaming synthesis when GGUF backbones are used.
- Keep the default path fully offline.

## Non-goals

- Multilingual TTS (NeuTTS is English-only today).
- Training or finetuning workflows.
- Automatic model download by default.

## Decisions

- Voice references map to stored reference codes (no per-request reference audio/text).
- Bundle a default reference voice for quick-start usage.
- Storage location should follow the existing voice storage pattern in the codebase; confirm by reviewing current voice management utilities.
- Automatic model download is disabled by default.
- Streaming output format should favor widest compatibility; default to PCM s16le, 24kHz, mono, with WAV chunking allowed if needed by clients.

## User Stories

- As a local user, I can generate speech using a stored voice reference without re-uploading reference audio.
- As a power user, I can use GGUF backbones for low-latency streaming output.
- As an offline user, I can point to local model and codec files without network access.
- As a new user, I can try NeuTTS immediately using a bundled default voice.

## Functional Requirements (MVP)

- Provider integration:
  - New provider option: `neutts` with models `neutts-nano` and `neutts-air`.
  - Support local paths and HF repo IDs for backbone/codec (downloads disabled by default).
- Voice mapping:
  - `voice` references stored `ref_codes` and `ref_text` rather than requiring reference audio per request.
  - Extend voice upload/encode flow to generate and persist NeuTTS reference codes.
- Output requirements:
  - Sample rate: 24kHz output.
  - Non-streaming responses follow existing `response_format` values.
  - Streaming responses default to PCM s16le, 24kHz, mono.
- Streaming:
  - Streaming supported only for GGUF backbones.
  - Clear error if streaming is requested with non-GGUF backbones.
- Caching:
  - Reuse loaded backbone and codec per worker.
  - Optional cache for reference codes by voice ID.
- Validation:
  - Enforce reference audio constraints on upload/encode (mono, 16-44kHz, 3-15s recommended).
  - Validate file size/type and sanitize filenames.
- Errors:
  - Clear errors for missing dependencies (espeak-ng, llama-cpp-python, onnxruntime).
  - Clear errors for invalid or missing reference codes.

## API and Data Contracts

- Existing endpoint: `POST /api/v1/audio/speech`
- `voice` maps to stored reference codes (use existing `custom:{voice_id}` pattern).

Example request:

```json
{
  "model": "neutts-nano",
  "input": "Hello world",
  "voice": "custom:default",
  "response_format": "pcm",
  "stream": true
}
```

Voice creation options:

- Extend `POST /api/v1/audio/voices/upload` to accept reference audio/text for NeuTTS and store reference codes.
- Optional endpoint if needed: `POST /api/v1/audio/voices/encode` to re-encode reference audio into NeuTTS codes.

## Storage and Voice Management

- Use the existing voice storage pattern in the codebase for per-user voices.
- Store NeuTTS reference codes and reference text alongside the processed audio.
- Keep an in-memory registry for fast lookup, with filesystem scan fallback.
- Bundle a default reference voice and pre-encoded codes; ensure licensing allows redistribution.

## Configuration

- New config keys (defaults):
  - `NEUTTS_ENABLED=true|false`
  - `NEUTTS_DEFAULT_MODEL=neuphonic/neutts-nano`
  - `NEUTTS_DEFAULT_CODEC=neuphonic/neucodec-onnx-decoder`
  - `NEUTTS_BACKBONE_DEVICE=cpu|gpu`
  - `NEUTTS_CODEC_DEVICE=cpu`
  - `NEUTTS_ALLOW_NETWORK_DOWNLOADS=false`
- Dependencies:
  - `neutts`, `neucodec`, `phonemizer`, `espeak-ng`
  - `llama-cpp-python` for GGUF
  - `onnxruntime` for ONNX decoder
  - `perth` optional for watermarking

## UX / UI

- TTS settings:
  - Provider selection: NeuTTS-Nano / NeuTTS-Air / GGUF variants.
  - Default voice visible and selectable.
  - Upload voice and store for reuse (maps to stored codes).
- Voice library:
  - List saved voices with metadata.
  - Delete voices.

## Non-functional Requirements

- Performance: real-time on CPU for Nano where feasible.
- Memory: avoid per-request model loads; reuse per worker.
- Security: never log reference audio/text; sanitize inputs.
- Offline by default; explicit opt-in for downloads.

## Observability

- Log provider, model, device, latency, stream vs non-stream.
- Track missing dependency errors and invalid reference inputs.

## Testing

- Unit tests:
  - Schema validation for NeuTTS fields.
  - Reference audio validation rules.
- Integration tests:
  - `/api/v1/audio/speech` with NeuTTS mock.
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
- M2: Voice upload/encode stores reference codes and updates voice catalog.
- M3: Streaming support for GGUF and UI updates.
- M4: Documentation and deployment guidance updated.

## Open Questions

- Which default voice sample should be bundled, and under what license?
- Should WAV chunk streaming be enabled alongside PCM for compatibility?
- Do we need a dedicated `voices/encode` endpoint or should upload always encode?
