## Stage 1: Registry + Config + Validation Wiring
**Goal**: Add Echo-TTS as a recognized provider with config aliases and validation rules (no adapter yet).
**Success Criteria**:
- `TTSProvider.ECHO_TTS` exists and is mapped in `DEFAULT_ADAPTERS` and `MODEL_PROVIDER_MAP`.
- Provider config aliases for `echo_tts_*` resolve correctly from `providers.echo_tts`.
- Validation includes UTF-8 byte cap (767 bytes + BOS) and explicit voice_reference required rule with HTTP 422 mapping.
- `audio_utils` includes Echo voice reference requirements (duration, SR).
**Tests**:
- Unit: provider mapping + model alias lookup.
- Unit: validation rejects missing voice_reference for `echo_tts`.
- Unit: byte-cap validation rejects multi-byte text > 767 bytes.
**Status**: Not Started

## Stage 2: Adapter Core (Non-Streaming) + CUDA Guard + Caching
**Goal**: Implement Echo-TTS adapter non-streaming generation with CUDA-only enforcement and speaker latent cache.
**Success Criteria**:
- Adapter initializes when CUDA is available; `device="auto"` resolves to `cuda`.
- If CUDA unavailable and `cpu_allow=false`, initialization fails with a clear error.
- Voice reference required: base64/bytes accepted and processed to 44.1kHz mono wav.
- LRU cache stores speaker_latent/mask on CPU by default; cache bypasses on memory pressure.
- Non-streaming `/audio/speech` returns valid audio bytes.
**Tests**:
- Unit: adapter init fails on CPU when `cpu_allow=false`.
- Unit: `device="auto"` resolves to `cuda`.
- Unit: cache hit skips speaker latent recompute.
- Integration: `/audio/speech` with `model=echo-tts` + voice_reference returns audio.
**Status**: Not Started

## Stage 3: Streaming via Blockwise Sampling
**Goal**: Add `generate_stream()` for Echo-TTS using blockwise sampling with a single stream finalization.
**Success Criteria**:
- Streaming yields multiple chunks and finalizes once (no repeated headers).
- Blockwise loop yields per-block audio using continuation latents.
- If blockwise module unavailable, `supports_streaming=False` and streaming requests return a clear error.
**Tests**:
- Unit: streaming generator yields >1 chunk and finalizes.
- Integration: `/audio/stream/tts` yields chunks for Echo-TTS on CUDA.
**Status**: Not Started

## Stage 4: Docs, Installer/Extras, and Cleanup
**Goal**: Document configuration and ensure dependencies can be installed.
**Success Criteria**:
- `pyproject.toml` has `TTS_echo_tts` extra with required deps.
- Optional: installer wiring adds `echo_tts` to `TTS_ENGINES` and `TTS_DEPENDENCIES`.
- TTS docs updated with Echo-TTS setup and example config.
**Tests**:
- Doc checks: references match config keys and defaults.
**Status**: Not Started
