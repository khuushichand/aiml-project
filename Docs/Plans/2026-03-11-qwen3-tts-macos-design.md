# Qwen3-TTS On M-Series macOS Design

**Date:** 2026-03-11

## Goal

Add support for `qwen3_tts` on Apple Silicon macOS while preserving one public provider surface in `tldw_server`, and also support users who already run a hosted or sidecar Qwen backend and do not want a duplicate local process.

## Current State

The codebase already contains substantial Qwen3-TTS scaffolding:

- A registered `qwen3_tts` provider in the TTS registry.
- A `Qwen3TTSAdapter` with model routing, streaming, and voice-clone prompt handling.
- Provider validation for Qwen-specific request shapes.
- Voice metadata persistence for `voice_clone_prompt`.
- Tokenizer endpoints and tests.

However, the current adapter is effectively built around one backend assumption. It does not cleanly separate:

- Linux/CUDA upstream `qwen_tts`
- Apple Silicon in-process execution
- Remote OpenAI-compatible sidecar execution

It also currently advertises provider-wide capabilities that are too optimistic for a runtime-split design.

## Design Constraints

### Functional

- Keep one public provider key: `qwen3_tts`.
- Support three execution modes:
  - In-process upstream runtime
  - In-process Apple Silicon runtime
  - Remote sidecar/hosted runtime
- Preserve the existing `/api/v1/audio/speech` API shape for callers.
- Preserve existing Qwen-specific behavior already implemented in the adapter and service layer.

### Scope

Initial Apple Silicon support is intentionally limited:

- `mlx` runtime starts with preset-speaker `CustomVoice` only.
- It does **not** initially support:
  - Uploaded `custom:<voice_id>` voices
  - `Base` model reference-audio cloning
  - `VoiceDesign`
  - tokenizer-heavy flows that depend on unavailable runtime support

This wording is important. In the current codebase, uploaded custom voices flow through `Base`-style reference audio and stored prompt metadata, not through preset-speaker `CustomVoice`.

### Non-Goals

- No new public provider names such as `qwen3_tts_mlx`.
- No promise of full Qwen parity on Apple Silicon in v1.
- No fake CI claim that proves M-series runtime behavior without Apple Silicon hardware.

## Research Summary

- Official Qwen3-TTS upstream support exists and is current, but published examples are CUDA-oriented and recommend `flash-attn`.
- PyTorch MPS is a valid Apple Silicon execution substrate, but that alone does not guarantee upstream Qwen runtime maturity on macOS.
- `mlx-audio` is a practical Apple Silicon path and already exposes Qwen3-TTS models plus an OpenAI-compatible REST API.

Sources:

- [Qwen3-TTS README](https://github.com/QwenLM/Qwen3-TTS)
- [MLX-Audio README](https://github.com/Blaizzy/mlx-audio)
- [PyTorch MPS docs](https://docs.pytorch.org/docs/stable/notes/mps.html)

## Recommended Approach

Keep `qwen3_tts` as one logical provider and split execution behind it into runtime backends.

### Why

- Matches the current codebase, which already treats Qwen3-TTS as one provider with one adapter, one config block, one validation surface, and one set of voice metadata rules.
- Avoids leaking infrastructure choices into public API/provider names.
- Allows platform-specific truth without forcing callers to integrate against multiple providers.

## Architecture

### Public Surface

The following remain stable:

- Provider key: `qwen3_tts`
- Registry entry and model family
- Audio API endpoints
- Existing voice metadata persistence behavior

### Internal Structure

Refactor the current `Qwen3TTSAdapter` into:

- An orchestration layer that stays responsible for:
  - request normalization
  - model aliasing
  - mode selection
  - custom voice metadata resolution
  - Qwen-specific validation hooks
  - service-compatible `TTSResponse` generation
- Runtime backends that handle actual execution:
  - `UpstreamQwenRuntime`
  - `MlxQwenRuntime`
  - `RemoteQwenRuntime`

### Runtime Responsibilities

#### `UpstreamQwenRuntime`

- In-process runtime for `qwen_tts`
- Preferred on Linux/CUDA and any explicitly forced upstream environment
- Can continue to support the broader Qwen feature set where proven

#### `MlxQwenRuntime`

- In-process Apple Silicon runtime
- Preferred by `runtime=auto` on `Darwin + arm64`
- Initial support is intentionally limited to preset-speaker `CustomVoice`
- Must reject unsupported modes with structured validation errors

#### `RemoteQwenRuntime`

- Used when the user points `qwen3_tts` at an already-hosted backend
- Keeps the public provider name unchanged
- Must preserve Qwen-specific semantics rather than silently collapsing to generic OpenAI TTS

## Runtime Selection

Add a provider-level runtime selector under `providers.qwen3_tts`:

- `runtime: auto | upstream | mlx | remote`

Selection rules:

- `auto` on macOS arm64 prefers `mlx`
- `auto` on Linux/CUDA prefers `upstream`
- `auto` never silently chooses `remote` unless remote connectivity is explicitly configured
- Explicit runtime selection always wins

This avoids accidentally choosing an importable but less-stable upstream runtime on Apple Silicon.

## Capability Model

The current capability booleans are too coarse for this feature. The design should retain the existing `TTSCapabilities` envelope but extend the serialized payload for Qwen with runtime-aware metadata.

### Required Capability Fields

Existing fields remain, but Qwen capability serialization should also include:

- `runtime`
- `supported_modes`
  - `custom_voice_preset`
  - `base_clone`
  - `voice_design`
- `supports_uploaded_custom_voices`
- `supports_qwen_voice_clone_prompt`
- `runtime_notes`

### Initial Runtime Truth Table

#### `upstream`

- `custom_voice_preset`: supported
- `base_clone`: supported when upstream backend supports it
- `voice_design`: supported when upstream backend supports it
- `supports_uploaded_custom_voices`: true via existing `custom:<voice_id>` flow

#### `mlx`

- `custom_voice_preset`: supported
- `base_clone`: unsupported in v1
- `voice_design`: unsupported in v1
- `supports_uploaded_custom_voices`: false in v1

#### `remote`

- Capability truth depends on the remote backend
- If the remote backend cannot report capabilities, default to conservative values and do not over-advertise support

## Request And Data Flow

### Normal Flow

1. API receives `OpenAISpeechRequest`
2. `TTSServiceV2` resolves provider `qwen3_tts`
3. `Qwen3TTSAdapter`:
   - normalizes request
   - resolves model/mode
   - resolves stored voice metadata
   - selects runtime
4. Selected runtime validates mode support
5. Runtime produces PCM or a stream
6. Existing TTS service logic handles format conversion, history, and persistence

### Uploaded Custom Voice Behavior

Existing `custom:<voice_id>` semantics stay intact for supported runtimes. For `mlx`:

- do not silently degrade uploaded voices into preset speakers
- fail early with a structured validation error explaining that uploaded custom voices are not supported by the selected runtime

## Remote Runtime Contract

This needs to be explicit. A generic OpenAI-compatible `/audio/speech` request is not sufficient for full Qwen behavior because Qwen clone flows need fields such as:

- `ref_audio`
- `ref_text`
- `x_vector_only_mode`
- `voice_clone_prompt`

### v1 Remote Contract

`RemoteQwenRuntime` must target a **Qwen-extended OpenAI-compatible** backend contract, not a plain generic TTS endpoint.

That means:

- standard OpenAI TTS fields are still used where applicable
- Qwen-specific fields are passed through using documented request extensions
- if the remote backend does not support the Qwen extension contract, remote mode must either:
  - advertise only preset-speaker `CustomVoice`, or
  - fail configuration validation rather than silently dropping Qwen-only fields

Implementation note as of March 11, 2026:

- the MLX runtime uses `mlx_audio.tts.utils.load_model(...)` for preset-speaker synthesis
- the remote runtime sends Qwen extension data in `extra_body` using `ref_audio_b64`, `ref_text`, `voice_clone_prompt`, `x_vector_only_mode`, and `description`

## Configuration

Avoid unnecessary config sprawl. Reuse existing generic provider fields where possible.

### Additions Under `providers.qwen3_tts`

- `runtime`
- `base_url`
- `api_key`
- `mlx_model`
- `mlx_model_path`
- `capability_override` only if needed for remote truthing

### Do Not Add Unless Proven Necessary

- separate `remote_base_url`
- separate `remote_api_key`
- a nested runtime matrix config

The current provider config model already supports generic `base_url` and `api_key`, and remote mode should reuse that surface.

## Error Handling

Error behavior must distinguish configuration errors, unsupported-mode errors, and runtime failures.

### Expected Cases

- `runtime=mlx` on non-macOS arm64:
  - provider initialization error with explicit platform message
- `runtime=upstream` without `qwen_tts` installed:
  - provider initialization error naming missing dependency
- `runtime=remote` without usable `base_url`:
  - provider configuration error
- `runtime=mlx` with `Base` or `VoiceDesign`:
  - structured validation error
- `runtime=mlx` with `voice="custom:<id>"`:
  - structured validation error explaining uploaded custom voices are unsupported on MLX in v1
- `runtime=auto` with no viable backend:
  - initialization error describing which runtimes were attempted

## Health, Metrics, And Circuit Breakers

Public provider identity remains `qwen3_tts`, but operational state must include runtime identity.

### Required Improvement

Namespace runtime-specific operational metadata as:

- `qwen3_tts:upstream`
- `qwen3_tts:mlx`
- `qwen3_tts:remote`

This applies to:

- health detail envelopes
- circuit breaker state
- runtime-specific metrics/log context

Without this, one failing runtime path can pollute provider-wide state and make debugging misleading.

## Testing Strategy

### Unit Tests

- runtime selection for:
  - macOS arm64 auto
  - Linux/CUDA auto
  - explicit upstream
  - explicit mlx
  - explicit remote
- capability gating for each runtime
- rejection of unsupported MLX modes
- rejection of uploaded custom voices on MLX
- remote request translation of Qwen-specific extension fields

### Integration Tests

- fake upstream backend
- fake MLX backend
- fake remote backend
- provider-level API behavior remains stable for `qwen3_tts`
- capability payload exposes truthful runtime metadata

### Manual Verification

Document a manual Apple Silicon smoke checklist:

- install/runtime prerequisites
- minimal preset-speaker request
- streaming request
- provider health inspection
- failure behavior for unsupported `Base` and `VoiceDesign`

## Migration Notes

- No caller-facing provider rename
- Existing `qwen3_tts` requests remain valid
- Existing uploaded custom voice flows continue to work only on runtimes that actually support them
- Capability output becomes more precise, which may slightly change UI/provider-catalog behavior in a good way

## Risks

- The largest product risk is confusing “preset-speaker CustomVoice” with uploaded user voices
- The largest technical risk is under-defining the remote Qwen extension contract
- The largest operations risk is failing to namespace runtime-level breaker and health state

## Design Decision Summary

- One provider key: `qwen3_tts`
- Multiple internal runtimes: `upstream`, `mlx`, `remote`
- `auto` prefers MLX on Apple Silicon
- MLX v1 scope is preset-speaker `CustomVoice` only
- Remote mode must preserve Qwen-specific semantics or advertise a reduced capability set
- Capability reporting must become runtime-aware
- Health and breaker state must carry runtime identity
