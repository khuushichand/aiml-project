# Chatterbox Upstream Parity Design

## Summary

Update tldw's Chatterbox integration from its current upstream `0.1.4`-era assumptions to current upstream parity with:

- Standard English TTS
- Multilingual TTS
- Turbo TTS
- Voice conversion

The integration must preserve tldw's current policy of removing the upstream Perth watermark by default.

## Goals

- Preserve the existing `chatterbox` provider key for TTS.
- Add first-class support for the current upstream model family:
  - `ChatterboxTTS`
  - `ChatterboxMultilingualTTS`
  - `ChatterboxTurboTTS`
  - `ChatterboxVC`
- Keep existing `model="chatterbox"` and `model="chatterbox-emotion"` callers working.
- Add explicit support for canonical model aliases such as `chatterbox-multilingual` and `chatterbox-turbo`.
- Add a dedicated voice-conversion API surface instead of forcing VC through the OpenAI-compatible `/audio/speech` schema.
- Make validation, config, docs, and discovery surfaces mode-aware.
- Re-enable real local/offline loading through config instead of treating `model_path` as dead configuration.

## Non-Goals

- Do not change the provider key from `chatterbox` to multiple new providers.
- Do not enable upstream watermarking by default.
- Do not force voice conversion into the OpenAI-compatible text-to-speech contract.
- Do not add streaming voice conversion in the first pass unless it falls out naturally from shared response helpers.

## Current Problems

### 1. The adapter only models the older upstream family

The current adapter in `tldw_Server_API/app/core/TTS/adapters/chatterbox_adapter.py` only manages standard English and multilingual TTS. It does not expose Turbo or VC, and its cleanup logic only tracks the two older model instances.

### 2. Request routing is text-first

`/api/v1/audio/speech` is built around `OpenAISpeechRequest.input`, `_sanitize_speech_request()`, and the TTS service path. That makes it the wrong place to expose voice conversion as a model alias because VC is audio-to-audio, not text-to-audio.

### 3. Validation is provider-wide, not model-family-aware

Current validation treats `chatterbox` as one provider with one set of language, format, and voice-reference rules. That is no longer true once standard, multilingual, Turbo, and VC are all supported.

### 4. Model discovery is duplicated

Chatterbox model names are hardcoded in multiple places:

- backend registry aliases
- OpenAPI schema descriptions
- frontend fallback model lists

This already drifted once and will drift again if the new model family is added piecemeal.

### 5. Dependency/config support is stale

The current `TTS_chatterbox` extra predates upstream Turbo/VC needs, and config still labels `model_path` as unused even though upstream now provides `from_local()` loaders.

## Revised Design

### A. Keep one provider, add an internal family mode

The `chatterbox` provider remains the single provider key in the adapter registry and TTS service.

Inside the adapter, introduce an internal resolved mode:

- `standard`
- `multilingual`
- `turbo`

Voice conversion is also part of the Chatterbox integration, but it is not a TTS mode surfaced through `/audio/speech`.

Mode resolution order:

1. explicit request model alias
2. provider config default variant
3. backward-compatible config aliasing
4. fallback to `standard`

Planned canonical model aliases:

- `chatterbox`
- `chatterbox-emotion`
- `chatterbox-multilingual`
- `chatterbox-turbo`

`chatterbox-vc` is intentionally not added to the TTS model catalog.

### B. Add a dedicated Chatterbox voice-conversion endpoint

Voice conversion should be exposed under a dedicated audio endpoint such as:

- `POST /api/v1/audio/voice-conversion`

Rationale:

- VC is audio-to-audio, not text-to-audio.
- The existing OpenAI-compatible speech schema is not the right contract.
- It keeps model discovery honest instead of pretending VC is a text model.

The request contract should accept:

- source audio payload
- source audio format hint if needed
- target voice reference audio or stored custom voice id
- output format
- optional `return_download_link`

The initial VC endpoint should be non-streaming by default. Upstream VC returns a full waveform, and non-streaming keeps the first implementation simpler and more accurate.

### C. Make Chatterbox validation mode-aware

Validation should continue to key off provider `chatterbox`, but it must derive a Chatterbox family mode from the requested model.

Validation responsibilities:

- `standard`
  - English TTS
  - emotion/exaggeration controls allowed
- `multilingual`
  - accept supported language ids from the upstream multilingual list
- `turbo`
  - accept Turbo model alias
  - allow paralinguistic tags in text
  - do not claim unsupported controls work
  - ignore unsupported tuning knobs in generation with clear metadata
- `voice conversion`
  - handled in the dedicated VC endpoint/schema, not in `TTSInputValidator.validate_request()`

Voice-reference validation should become provider-and-mode aware rather than relying on one generic `min_duration` override. The validator should still use shared audio validation primitives, but Chatterbox-specific duration/format rules should be derived from mode.

### D. Restore real local/offline loading

The adapter should stop treating `model_path` as dead configuration.

Config should support:

- `model_path`
  - repo id or local directory for standard/multilingual/VC
- `turbo_model_path`
  - repo id or local directory for Turbo
- `variant`
  - `standard`, `multilingual`, or `turbo`
- `use_multilingual`
  - backward-compatible alias for `variant=multilingual`
- `disable_watermark`
  - default `true`
- `auto_download`
  - default preserves current tldw behavior

Loader behavior:

- If configured path is local and exists, use `from_local()`.
- If configured value looks like a repo id, use `from_pretrained()` and allow auto-download/offline behavior.
- If `auto_download` is false, set offline HF env hints before loading.

### E. Centralize Chatterbox model catalog data

Introduce one backend source of truth for Chatterbox model aliases and family metadata.

That catalog should drive:

- adapter-registry alias resolution
- capability/model discovery responses
- schema descriptions or helper-generated docs

The frontend should continue to prefer provider discovery/OpenAPI data and only keep a minimal fallback list with canonical ids.

### F. Share audio response/persistence helpers with VC

The VC endpoint should not reimplement TTS response finalization from scratch.

Refactor shared pieces out of `audio_tts.py` into reusable helpers for:

- content-type/header shaping
- artifact persistence
- history writes
- usage logging hooks

VC should use those helpers where the semantics match, but maintain separate metric/event names so TTS and VC are distinguishable.

## API Shape

### Existing `/api/v1/audio/speech`

Keep the current endpoint and schema, but expand model descriptions to include new canonical Chatterbox TTS model ids:

- `chatterbox`
- `chatterbox-emotion`
- `chatterbox-multilingual`
- `chatterbox-turbo`

### New `/api/v1/audio/voice-conversion`

Add a dedicated request/response schema.

Proposed request fields:

- `input_audio`: base64 audio payload
- `input_audio_format`: `wav|mp3|flac|ogg|opus|m4a`
- `target_voice_reference`: optional base64 audio payload
- `target_voice_id`: optional stored voice id or `custom:<id>`
- `response_format`
- `return_download_link`
- `normalization_options`: omitted, since this is not text generation

Rules:

- require one target voice source
- reject requests that provide neither `target_voice_reference` nor `target_voice_id`
- initially return non-streaming audio

## Adapter Behavior

### Standard

- continue existing emotion/exaggeration mapping
- continue voice cloning from `voice_reference`
- continue no-op watermark replacement by default

### Multilingual

- load upstream multilingual runtime lazily
- validate language codes against upstream supported set
- preserve no-op watermark replacement

### Turbo

- load upstream Turbo runtime lazily
- preserve no-op watermark replacement
- expose Turbo-specific defaults where useful
- ignore unsupported controls such as CFG/exaggeration when Turbo cannot honor them, and report that in response metadata rather than silently pretending support exists

### VC

- load upstream `ChatterboxVC` lazily
- convert source audio to the target voice reference
- preserve no-op watermark replacement
- allow stored custom voices to be reused as target references through the existing voice manager

## Dependency Changes

Review and update `TTS_chatterbox` extras to cover the current upstream family, especially runtime imports exercised by Turbo and VC. At minimum this likely includes:

- `resemble-perth`
- `pyloudnorm`

Only add new dependencies that are actually required by the code paths tldw will exercise.

## Testing Strategy

### Unit tests

- model alias -> family resolution
- standard/multilingual/turbo parameter mapping
- watermark disabling still applied across all families
- Turbo ignores unsupported controls in a predictable way
- VC request validation
- VC adapter source/target audio handling

### Integration tests

- `/api/v1/audio/speech` accepts new Chatterbox model aliases
- provider/model discovery surfaces include the new TTS model ids
- `/api/v1/audio/voice-conversion` returns converted audio and optional artifact metadata
- stored custom voice ids can be used as VC targets

### Regression tests

- existing `model="chatterbox"` callers still resolve successfully
- `chatterbox-emotion` remains backward compatible
- docs/config examples reflect the new family without re-enabling watermarking

## Risks And Mitigations

### Risk: VC accidentally leaks into the TTS contract

Mitigation:

- keep VC in a dedicated endpoint/schema
- do not add `chatterbox-vc` to the TTS model alias catalog

### Risk: Turbo parity fails at runtime because extras are incomplete

Mitigation:

- review upstream dependency imports before implementation
- add unit tests that fail fast on missing optional imports where practical

### Risk: stale duplicate model lists

Mitigation:

- centralize Chatterbox model catalog metadata on the backend
- make frontend fallback list minimal and canonical

### Risk: resource leaks with four lazy runtimes

Mitigation:

- extend adapter cleanup/resource-manager integration to cover Turbo and VC explicitly

## Implementation Notes

- Preserve tldw's current default of removing the Perth watermark.
- Prefer repo conventions (`Docs/Plans`) over introducing a new lowercase planning tree.
- Avoid destructive changes to existing TTS request contracts unless required for compatibility.
