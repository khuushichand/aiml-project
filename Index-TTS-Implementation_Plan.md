## Stage 1: Requirements & API Mapping
**Goal**: Understand IndexTTS2 runtime expectations and map its inference options to the unified TTS adapter contract.  
**Success Criteria**: Document dependency footprint, supported features (voice cloning, emotion prompts, streaming), expected sample rate/output format, and the request parameter mapping (e.g., `voice_reference`, `extra_params`).  
**Tests**: N/A (analysis/documentation stage).  
**Status**: Complete  
**Findings**:  
- Core runtime depends on PyTorch (with CUDA/MPS optional), torchaudio, librosa, transformers, modelscope, safetensors, omegaconf, plus IndexTTS-specific modules; GPU strongly recommended but CPU fallback exists.  
- Model assets (config, checkpoints, Qwen emotion model, semantic codec) expected under a shared `model_dir` (default `checkpoints/`). Supports HF/modelscope download flows.  
- Baseline inference uses `IndexTTS2.infer(...)` requiring speaker reference audio (`spk_audio_prompt` path). Optional emotional conditioning via secondary audio (`emo_audio_prompt`), emotion vector, or text-driven emotion modes (QwenEmotion); alpha scaling supported.  
- Output audio produced at 22.05 kHz as 16-bit PCM; default pipeline saves to file or returns `(sampling_rate, numpy array)`; streaming mode yields torch tensors + silence buffers. Adapter maintains native rate and documents the difference from the 24 kHz default used elsewhere.  
- Unified request mapping:  
  * `TTSRequest.voice_reference` (bytes) → temp file for `spk_audio_prompt`.  
  * `extra_params.emo_audio_reference` (bytes, base64-encoded in API payload) or `extra_params.emo_audio_path` → `emo_audio_prompt`. Plan to decode and size-check in Stage 2 validation.  
  * `extra_params.emo_alpha`, `emo_vector`, `use_emo_text`, `emo_text`, `use_random`, `interval_silence`, `max_text_tokens_per_segment` → direct pass-through.  
  * `extra_params.generation` dict to hold advanced kwargs (e.g., `top_p`, `temperature`, `max_mel_tokens`).  
- Supports non-streaming via adapter `generate`; streaming will be handled in later stages to allow dedicated testing around chunk timing and encoding.  
- Validation implications: provider must enforce presence of speaker prompt, restrict to supported formats (`wav`/`mp3` outputs via conversion), surface 22.05 kHz sample rate (but advertise 24 kHz post-resample in capabilities), and gate advanced emotion controls behind `extra_params`.

## Stage 2: Adapter Implementation
**Goal**: Implement an `IndexTTS2Adapter` that wraps `indextts.infer_v2.IndexTTS2`, handles initialization, request validation, audio conversion, and non-streaming generation. (Streaming deferred to Stage 3.)  
**Success Criteria**: Adapter passes unit tests with mocked IndexTTS2 engine, returns correct `TTSResponse` for non-streaming requests, gracefully surfaces missing dependency/model errors, enforces required inputs (speaker prompt, etc.), decodes/validates emotion reference bytes, normalizes audio (int16 conversion at native 22.05 kHz with format conversion via existing `audio_converter` utilities), and updates `TTSCapabilities` to reflect the delivered format/sample rate.  
**Tests**: `python -m pytest tldw_Server_API/tests/TTS/adapters/test_index_tts_adapter.py`.  
**Status**: Complete  
**Notes**: Added `IndexTTS2Adapter` with lazy engine loading, base64 emotion reference handling, native 22.05 kHz normalization + format conversion, and cleanup of temporary reference files. Unit tests cover validation, mp3 normalization (with converters patched), and unsupported-format guards.

## Stage 3: Platform Integration
**Goal**: Register the new provider across the TTS system (registry, enums, config manager/YAML, validation, voice mappings), expose configuration toggles, and implement streaming support by adapting `infer_generator` to unified async chunking.  
**Success Criteria**: `TTSProvider.INDEXTTS` available via API, configuration defaults disabled but functional when enabled, validation accepts provider-specific parameters (including base64 emotion references), streaming endpoint delivers byte chunks with consistent pacing, and fallbacks handle provider availability correctly.  
**Tests**: `python -m pytest -k "TTSAdapterRegistry or audio"` for config wiring, plus new streaming tests in `tldw_Server_API/tests/TTS/adapters/test_index_tts_adapter.py`.  
**Status**: Complete  
**Notes**: Registry enum/mapping added, config YAML + validator updated, streaming adapter returns async chunks with `StreamingAudioWriter`, unit tests cover streaming path and registry presence, and `voice_mappings` now includes the `index_tts` `clone_required` placeholder + format preferences alignment.

## Stage 4: QA & Documentation
**Goal**: Finalize documentation and verification steps (TTS README, deployment notes, config samples) and run existing regression suites.  
**Success Criteria**: Docs explain dependency installation/model download, default settings, and usage examples; automated TTS suites pass; manual smoke test plan drafted for GPU environments.  
**Tests**: `python -m pytest -k "TTS_NEW"`; optional manual smoke test notes for GPU environment.  
**Status**: In Progress  
**Notes**: Updated `TTS-README.md`, `TTS-DEPLOYMENT.md`, and `TTS-VOICE-CLONING.md` with IndexTTS2 setup, streaming guidance, voice mapping expectations, and a GPU smoke test checklist. Outstanding: execute regression suite (`python -m pytest -k "TTS"`), capture GPU smoke test results once hardware available, and publish any additional model-download automation if needed.
