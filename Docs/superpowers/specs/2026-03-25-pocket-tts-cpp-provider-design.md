# PocketTTS.cpp Provider Design

Date: 2026-03-25
Status: Approved for planning
Owner: Codex brainstorming session

## Summary

Add `pocket_tts_cpp` as a new local TTS provider backed by [PocketTTS.cpp](https://github.com/VolgaGerm/PocketTTS.cpp), while keeping the existing `pocket_tts` Python/ONNX runtime intact.

The provider should integrate with the existing unified TTS stack, support direct `voice_reference` inputs and stored `custom:<voice_id>` voices, and preserve PocketTTS.cpp voice caching by managing stable per-user voice files. The implementation should be subprocess-first for non-streaming requests. Streaming should start with a CLI feasibility check and may use PocketTTS.cpp's built-in HTTP server internally only if CLI stdout is not truly incremental.

## Problem

The repository already has a working `pocket_tts` provider, but it targets the Python/ONNX runtime in [pocket_tts_adapter.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/TTS/adapters/pocket_tts_adapter.py). That path is useful, but it does not expose the operational model of PocketTTS.cpp:

- no Python runtime dependency at request time
- a compiled local binary
- upstream-managed voice and KV caching
- a simpler CPU-focused deployment story
- an alternate low-latency streaming path

Trying to overload the existing `pocket_tts` provider with two unrelated runtime models would blur configuration, documentation, and operational expectations. The project needs a separate provider that fits the current TTS adapter architecture without regressing the existing PocketTTS path.

## Goals

- Add a distinct `pocket_tts_cpp` provider to the unified TTS registry.
- Preserve the existing `pocket_tts` provider unchanged.
- Support both:
  - direct `voice_reference` input
  - stored `custom:<voice_id>` voice resolution through the existing voice manager
- Preserve PocketTTS.cpp cache benefits by using stable provider-managed voice files instead of random temp filenames.
- Support non-streaming and streaming through the existing TTS API contract.
- Provide a repo-local installer helper for fetching, building, exporting, and wiring PocketTTS.cpp.
- Keep failure handling, validation, and cleanup aligned with current TTS adapter patterns.

## Non-Goals

- Replacing the existing `pocket_tts` Python provider.
- Unifying the two runtimes behind one provider key.
- Exposing PocketTTS.cpp through the shared admin audio installer UI in v1.
- Adding new public API endpoints specifically for PocketTTS.cpp.
- Supporting every optional PocketTTS.cpp flag in v1.
- Adding voice design, emotion control, pitch control, or speech-rate control that the upstream runtime does not natively guarantee.

## Current State

### Existing TTS Integration

The project already has a mature TTS adapter stack under [/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/TTS](file:///Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/TTS):

- adapter registry in [adapter_registry.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/TTS/adapter_registry.py)
- service orchestration in [tts_service_v2.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/TTS/tts_service_v2.py)
- provider config loading in [tts_config.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/TTS/tts_config.py)
- validation in [tts_validation.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/TTS/tts_validation.py)
- stored voice handling in [voice_manager.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/TTS/voice_manager.py)

### Existing PocketTTS Runtime

The repo already supports PocketTTS ONNX under the `pocket_tts` provider:

- config block in [tts_providers_config.yaml](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/Config_Files/tts_providers_config.yaml)
- adapter in [pocket_tts_adapter.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/TTS/adapters/pocket_tts_adapter.py)
- installer in [install_tts_pocket_tts_onnx.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/Helper_Scripts/TTS_Installers/install_tts_pocket_tts_onnx.py)
- mock and integration tests in [/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/TTS/adapters](file:///Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/TTS/adapters)

That work should remain a supported parallel path.

### Upstream PocketTTS.cpp Constraints

Based on the current upstream README, PocketTTS.cpp provides:

- a C++ CLI
- a built-in HTTP server
- optional shared library output
- OpenAI-compatible `/v1/audio/speech` server mode
- voice cloning from short audio samples
- disk caching for voice embeddings and transformer KV state

That runtime model maps naturally to a separate provider but not to the current Python-module-based `pocket_tts` adapter.

## Proposed Design

### 1. Add a Separate Provider: `pocket_tts_cpp`

Introduce `pocket_tts_cpp` as a new provider key across:

- `TTSProvider` enum
- registry default adapter mapping
- provider alias resolution
- config schema and YAML defaults
- validation and capability tables
- docs and provider capability summaries

This provider should not masquerade as `pocket_tts`, and model aliases should remain explicit. The distinction must be visible in config, API model listings, and troubleshooting docs.

### 2. Subprocess-First Adapter Shape

Create a new adapter under:

- `tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_adapter.py`

Recommended class:

- `PocketTTSCppCliAdapter`

Primary behavior:

- non-streaming requests use the PocketTTS.cpp CLI directly
- streaming requests try CLI streaming first
- if CLI streaming is not truly incremental, the adapter may internally use a short-lived PocketTTS.cpp server process for streaming only

The public tldw interface must remain unchanged regardless of which internal transport is used.

### 3. Provider-Managed Voice Files

PocketTTS.cpp cache reuse depends on stable voice-file identities. Random temp filenames would defeat most of the cache value.

The provider should therefore manage its own per-user runtime layout under the existing user voices directory, separate from the raw voice-manager storage layout.

Recommended structure:

```text
Databases/user_databases/<user_id>/voices/
  providers/
    pocket_tts_cpp/
      custom_<voice_id>.wav
      ref_<sha256>.wav
      .cache/
      runtime/
        logs/
```

Rules:

- stored `custom:<voice_id>` voices are normalized into deterministic provider-managed files
- direct `voice_reference` inputs are normalized into content-hashed files
- provider-managed files are user-scoped
- upstream `.cache/` remains user-scoped
- the adapter never relies on unstable random filenames for cacheable references

This keeps cache behavior predictable in multi-user mode, avoids cross-user cache mixing, and stays aligned with existing `DatabasePaths.get_user_voices_dir(...)` storage conventions.

### 4. Stored Voice Resolution

The current TTS service already resolves `custom:<voice_id>` voices through the voice manager.

For `pocket_tts_cpp`, the design should add a provider-specific path that:

1. resolves the stored voice through the existing voice manager
2. gets the canonical stored audio
3. converts and installs it into the provider-managed `voices/` area using a deterministic filename
4. passes that stable file path to PocketTTS.cpp

This path must not bypass existing voice authorization and lookup rules. It should reuse the existing user-scoped voice manager contract and only add provider-specific materialization.

### 5. Direct `voice_reference` Handling

When the request contains raw `voice_reference` bytes:

1. validate via the existing audio validation path
2. normalize to provider-safe WAV at the provider sample rate
3. hash the normalized bytes
4. materialize the result to `voices/ref_<sha256>.wav`
5. pass that stable path to PocketTTS.cpp

This approach avoids repeated random temp files and lets repeated direct-reference requests benefit from upstream voice/KV caching.

### 6. Streaming Strategy

Streaming has the highest technical risk in this design.

The implementation should start with a hard feasibility gate:

- prove that the CLI can emit truly incremental audio on stdout before process completion
- measure time-to-first-byte against total request completion
- verify this on at least one real voice sample and one real text sample

If the CLI stream is truly incremental:

- use CLI stdout for streaming
- wrap stdout chunks into the existing `StreamingAudioWriter`
- emit requested response formats through the current TTS streaming contract

If the CLI stream is not truly incremental:

- allow a short-lived internal PocketTTS.cpp server process for streaming only
- keep non-streaming on the CLI path
- do not change the public tldw API contract

This fallback is allowed because the user explicitly approved it during design review.

### 7. Non-Streaming Strategy

Non-streaming should stay subprocess-first.

Preferred order:

1. invoke the CLI with stdout output when the output format is safe and unambiguous
2. if stdout output is unsuitable for the requested format or proves unreliable, invoke the CLI with a file output and read the file back
3. normalize or transcode via the existing adapter/audio conversion pipeline to honor the requested response format

The adapter should use existing `convert_audio_format(...)` helper patterns from the base adapter rather than introducing a parallel conversion system.

### 8. Installer Design

Add a dedicated installer helper:

- `Helper_Scripts/TTS_Installers/install_tts_pocket_tts_cpp.py`

Responsibilities:

- verify required system tools such as `git`, `cmake`, and a C++ compiler
- clone or fetch the upstream PocketTTS.cpp repository into a temporary working area
- create an isolated build/export environment for exporter-side Python dependencies
- build the CLI binary
- run the upstream export step to produce ONNX assets
- copy runtime artifacts into the repo’s canonical layout
- update `tts_providers_config.yaml` with the `pocket_tts_cpp` provider block

Recommended repo-local layout:

```text
models/pocket_tts_cpp/
  onnx/
  tokenizer.model
bin/
  pocket-tts
```

The installer should be opt-in and separate from the current `pocket_tts` ONNX installer.

### 9. Config Shape

Add a provider block under `providers.pocket_tts_cpp` in [tts_providers_config.yaml](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/Config_Files/tts_providers_config.yaml).

Recommended fields:

```yaml
providers:
  pocket_tts_cpp:
    enabled: false
    binary_path: "bin/pocket-tts"
    models_dir: "models/pocket_tts_cpp/onnx"
    tokenizer_path: "models/pocket_tts_cpp/tokenizer.model"
    voice_runtime_subdir: "providers/pocket_tts_cpp"
    precision: "int8"
    threads: 0
    temperature: 0.7
    lsd_steps: 1
    request_timeout_seconds: 120
    warmup_on_initialize: false
    enable_voice_cache: true
    extra_params:
      streaming_transport: "auto"  # auto | cli | server
      stream_stdout_format: "f32le_pcm"
```

The config should be subprocess-centric, not Python-module-centric. The adapter should resolve the actual user-scoped runtime directory from the existing voices base path instead of treating `voice_runtime_subdir` as a standalone absolute storage root.

### 10. Validation Rules

Add provider-specific validation so `pocket_tts_cpp` requires one of:

- `voice_reference`
- `voice="custom:<voice_id>"`

Also define and document unsupported controls:

- `speed`
- `pitch`
- `emotion`
- `emotion_intensity`
- `style`

V1 behavior should be explicit and predictable:

- either reject unsupported controls for `pocket_tts_cpp`
- or ignore them consistently and document that they are ignored

The implementation should choose one rule and apply it consistently in validation and docs. The recommended choice is to ignore unsupported controls unless upstream adds a real equivalent, because that better matches OpenAI-compatible request shapes already used in the repo.

### 11. Error Handling

All subprocess interactions must use argv invocation, never shell interpolation.

Required behavior:

- enforce request timeouts
- kill child processes on timeout or cancellation
- capture stderr for server logs
- avoid leaking raw filesystem paths or full command lines in API error payloads
- clean up only provider-managed temporary files
- preserve user-managed and cacheable stable voice files

The adapter should raise existing structured TTS exceptions rather than custom ad hoc subprocess errors.

### 12. Warmup Behavior

If `warmup_on_initialize` is enabled:

- run a small probe generation using a known voice sample
- confirm the binary and models are usable
- do not block startup forever on warmup failure
- downgrade to a clear unavailable/error provider state instead

Warmup is operational verification, not a correctness substitute for request-time validation.

## Components

### New Files

- `tldw_Server_API/app/core/TTS/adapters/pocket_tts_cpp_adapter.py`
- `Helper_Scripts/TTS_Installers/install_tts_pocket_tts_cpp.py`
- `Docs/STT-TTS/POCKETTTS_CPP_SETUP.md`
- mock and integration tests for the new adapter

### Modified Files

- `tldw_Server_API/app/core/TTS/adapter_registry.py`
- `tldw_Server_API/app/core/TTS/tts_config.py`
- `tldw_Server_API/app/core/TTS/tts_validation.py`
- `tldw_Server_API/app/core/TTS/tts_service_v2.py`
- `tldw_Server_API/Config_Files/tts_providers_config.yaml`
- `tldw_Server_API/app/api/v1/schemas/audio_schemas.py`
- TTS capability docs and setup guides

## Data Flow

### Non-Streaming Request

1. API receives `/api/v1/audio/speech` request with `model: "pocket_tts_cpp"`.
2. TTS service resolves provider and applies standard request normalization.
3. If `voice` is `custom:<voice_id>`, the service and adapter resolve it through the existing voice manager and provider-managed voice installation.
4. If `voice_reference` is present, the adapter validates, converts, hashes, and materializes a provider-managed reference WAV.
5. Adapter launches PocketTTS.cpp via subprocess.
6. Adapter captures output, normalizes/transcodes via current audio helpers, and returns `TTSResponse(audio_data=...)`.

### Streaming Request

1. API receives a streaming TTS request.
2. Adapter decides transport:
   - CLI stdout if feasible and configured
   - otherwise internal short-lived server mode
3. Audio chunks are read incrementally.
4. Chunks are wrapped through `StreamingAudioWriter`.
5. API streams bytes using the existing TTS streaming contract.

## Testing Strategy

### Unit Tests

Add mock-focused tests for:

- provider registration and alias mapping
- config parsing
- binary path validation
- subprocess argv construction
- stable custom-voice file materialization
- hashed direct-reference file materialization
- timeout and cancellation handling
- stderr error wrapping
- cleanup behavior
- unsupported control handling

### Integration Tests

Add gated integration tests similar to the current PocketTTS integration pattern:

- skip unless explicit env flag enables them
- skip unless binary and assets are present
- verify one real non-streaming generation
- verify one real streaming request
- verify a real stored-voice flow if fixture setup makes that practical

### Service/API Tests

Add service and endpoint coverage for:

- OpenAI-compatible `/api/v1/audio/speech`
- fallback selection and provider resolution
- `custom:<voice_id>` behavior
- direct `voice_reference` behavior
- streaming and non-streaming responses

## Documentation

Update docs so `pocket_tts` and `pocket_tts_cpp` are always presented as distinct providers.

Required doc updates:

- new PocketTTS.cpp runbook under `Docs/STT-TTS/`
- TTS setup guide
- getting-started TTS guide
- provider capability tables in TTS README docs
- installer README

Docs must include:

- install command
- expected runtime layout
- config example
- one real generation verification command
- one real streaming verification command
- troubleshooting for missing compiler/toolchain, failed export, missing binary, and streaming fallback selection

## Risks And Mitigations

### Risk: CLI Streaming Is Not Truly Incremental

Mitigation:

- make it the first implementation spike
- treat it as a hard gate
- allow internal server-mode streaming fallback only if CLI streaming fails the gate

### Risk: Cache Reuse Regresses Due to Unstable Voice Files

Mitigation:

- use deterministic provider-managed voice files
- avoid random cacheable filenames
- keep provider-managed per-user `voices_dir` and `.cache/`

### Risk: Installer Is Too Heavy for Current Runtime Assumptions

Mitigation:

- keep installer opt-in
- isolate build/export environment
- keep v1 out of the shared admin audio installer UI

### Risk: Multi-User Filesystem Bleed

Mitigation:

- store provider-managed runtime artifacts per user
- never reuse one shared voices directory across users
- continue using the existing user-scoped voice manager as the source of truth

## Success Criteria

- `pocket_tts_cpp` appears as a distinct provider when enabled.
- Non-streaming generation works from direct `voice_reference`.
- Non-streaming generation works from stored `custom:<voice_id>`.
- Streaming works through the current API contract using either CLI stdout or the approved internal server fallback.
- Stable provider-managed voice files preserve PocketTTS.cpp cache reuse.
- Installer provisions the runtime into repo-local paths and updates config safely.
- Focused tests cover adapter behavior, service flow, and endpoint behavior.
- Documentation clearly separates `pocket_tts` from `pocket_tts_cpp`.

## Planning Notes

This spec is intentionally scoped to one provider integration. It does not include unrelated TTS UI work, generic installer expansion, or refactors of other local speech backends.
