# Supertonic Implementation Plan

## Stage 1: Adapter Skeleton & Registry Wiring
**Goal**: Add a `SupertonicOnnxAdapter` skeleton that plugs into the existing TTS adapter registry, with configuration stubs and no real engine calls yet.
**Success Criteria**: `TTSProvider.SUPERTONIC` is defined; Supertonic aliases (`tts-supertonic-1`, `supertonic`, `supertonic-onnx`) are added to `TTSAdapterFactory.MODEL_PROVIDER_MAP`; the registry can initialize a stub adapter when `supertonic` is enabled; `/api/v1/audio/providers` shows a placeholder Supertonic capabilities entry without breaking existing providers.
**Tests**:
- Unit: Factory maps the Supertonic aliases to `TTSProvider.SUPERTONIC`, and the registry returns a `SupertonicOnnxAdapter` instance when `providers.supertonic.enabled=true` in `tts_providers_config.yaml`; unknown model ids are unaffected.
- Integration: `/api/v1/audio/providers` and `/api/v1/audio/voices/catalog` still succeed with existing providers; Supertonic appears with minimal capability stubs and an empty voice list.
**Status**: Complete

## Stage 2: Engine Integration & Concurrency Guard
**Goal**: Wire the Supertonic ONNX engine into the adapter, including configuration‑driven model/voice paths and an `asyncio.Lock` guarding all engine calls.
**Success Criteria**: `SupertonicOnnxAdapter.initialize()` loads `load_text_to_speech` and voice style mappings from the configured directories; concurrent `initialize()`/`generate()` calls do not race or crash; missing default voice or model paths surface as clear `TTSModelNotFoundError`/`TTSModelLoadError`.
**Tests**:
- Unit: Mocked `load_text_to_speech` and `load_voice_style` are called with the expected `onnx_dir` and `voice_styles_dir`; missing default voice or ONNX dir raises the correct TTS exceptions.
- Concurrency: Two simultaneous `generate()` calls with a mocked engine see serialized `self._engine(...)` invocations (via `self._engine_lock`) and complete without race conditions.
**Status**: Complete

## Stage 3: Non‑Streaming Generation & Format Conversion
**Goal**: Implement full non‑streaming generation for `tts-supertonic-1`, including float→int16 normalization and `AudioFormat` conversion via `convert_audio_format`.
**Success Criteria**: A single `/api/v1/audio/speech` request using `model="tts-supertonic-1"` and `response_format="mp3"` or `"wav"` returns non‑empty audio bytes; Supertonic’s `speed` and `total_step` parameters are honored via `OpenAISpeechRequest.speed` and `extra_params.total_step`.
**Tests**:
- Unit: `SupertonicOnnxAdapter.generate()` with a mocked engine returns `TTSResponse.audio_data` with correct `format`, `sample_rate`, and `voice_used`; `total_step` and `speed` values are passed through to the engine as expected.
- Integration: With a dummy or small Supertonic model, `/api/v1/audio/speech` for `model="tts-supertonic-1"` and `stream=false` produces valid `mp3`/`wav` output and does not affect other TTS providers.
**Status**: Complete

## Stage 4: Pseudo‑Streaming & Capabilities/Voices
**Goal**: Add pseudo‑streaming support (chunked bytes after full synthesis) and expose accurate Supertonic capabilities and voice metadata to the voice catalog.
**Success Criteria**: `SupertonicOnnxAdapter.generate()` returns an `audio_stream` that yields multiple chunks when `stream=true`; `get_capabilities()` reports correct `supported_formats`, `supported_languages`, `max_text_length`, `supports_streaming=True`, and a `voices` list reflecting the configured voice id→filename map.
**Tests**:
- Unit: Pseudo‑streaming generator splits encoded audio into configured chunk sizes; `get_capabilities()` returns a `TTSCapabilities` object whose `voices` entries match the `voice_files` mapping from config.
- Integration: `/api/v1/audio/speech` with `model="tts-supertonic-1"` and `stream=true` yields at least one non‑empty chunk; `/api/v1/audio/voices/catalog` includes a `supertonic` entry with the expected voices and does not regress other providers.
**Status**: Complete

## Stage 5: Validation, Logging, & Installer Hook
**Goal**: Finalize provider‑specific validation limits, logging, and installer guidance, ensuring consistent behavior with the Supertonic PRD.
**Success Criteria**: `ProviderLimits` and `TTSInputValidator` entries for `supertonic` are in place and aligned; `_infer_tts_provider_from_model` routes `supertonic`/`tts-supertonic` models to the provider hint; speed outside `[0.9, 1.5]` is rejected with `TTSInvalidInputError`; logs clearly show model/voice directories and per‑request parameters; the Supertonic installer script stub exists with clear user instructions.
**Tests**:
- Unit: Validation rejects `speed` outside `[0.9, 1.5]` for `supertonic` and enforces `{mp3, wav}` formats and `max_text_length`; `_infer_tts_provider_from_model` returns `"supertonic"` for `supertonic`/`tts-supertonic` prefixes; logging calls fire on init and per request (provider, voice, text length, speed, total_step).
- Integration: Misconfigured paths (missing ONNX dir, missing default voice file) produce clear HTTP 500s with descriptive messages; running a minimal `install_tts_supertonic.py` stub prints instructions without modifying the environment unexpectedly.
**Status**: Complete
