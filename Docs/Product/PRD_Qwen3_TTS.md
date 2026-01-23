# PRD: Qwen3-TTS Adapter Support

## Background

tldw_server provides a unified TTS system with adapter registry, provider config, and OpenAI compatible endpoints. Qwen3-TTS is an open source TTS model series from the Qwen team, supporting streaming speech generation, voice design, and voice cloning, with broad multilingual coverage. The Qwen team announced the Qwen3-TTS 0.6B and 1.7B releases on January 22, 2026. The released models include CustomVoice, VoiceDesign, and Base (voice clone), plus a tokenizer model for encode/decode. Qwen3-TTS supports 10 languages (Chinese, English, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian) and provides instruction control for CustomVoice and VoiceDesign. The CustomVoice models ship with 9 named speakers and descriptions. Sources: the Qwen3-TTS GitHub README and official Hugging Face model cards.

## Goals

- Add Qwen3-TTS provider support through the TTS adapter registry.
- Support all released Qwen3-TTS models (12Hz tokenizer, 0.6B/1.7B CustomVoice, 1.7B VoiceDesign, 0.6B/1.7B Base).
- Provide streaming output consistent with Qwen3-TTS capabilities.
- Provide instruction control and voice clone workflows using existing OpenAI compatible request schemas.
- Expose the Qwen3-TTS tokenizer encode/decode via API endpoints.
- Keep the default path offline first; auto download must be explicit.

## Non-goals

- Training or fine tuning workflows.
- Exposing Qwen3-TTS DashScope APIs or SaaS endpoints.
- Supporting unreleased model variants (e.g., 25Hz series) until official publication.
- Replacing existing TTS providers or changing their behavior.

## Decisions

- Single provider with multiple model ids: Implement one adapter (qwen3_tts) and dispatch internally by model name. This matches existing registry behavior (MODEL_PROVIDER_MAP) and avoids duplicating adapter logic.
- Offline first: default to local model paths or pre downloaded weights. If auto download is enabled, it must honor existing egress allowlists.
- Reuse existing OpenAI compatible request schema: Use model, voice, lang_code, and extra_params. No new top level API fields. Allow extra_params.language as a provider-specific override when needed; lang_code remains the primary field.
- Voice cloning uses existing voice manager: stored reference audio and optional reference text are resolved via custom:<voice_id>.
- Default model selection is "auto": choose the best available CustomVoice model at runtime based on GPU capability (prefer 1.7B on capable GPU, otherwise 0.6B). "auto" is only valid for CustomVoice requests; VoiceDesign/Base must specify an explicit model id.
- Language handling uses "auto" when language is omitted; explicit "auto" is accepted in the API and forwarded to the adapter.
- Tokenizer encode/decode is exposed via new API endpoints under /api/v1/audio/tokenizer/*.

## In-scope Models (Released)

Tokenizer:
- Qwen/Qwen3-TTS-Tokenizer-12Hz

TTS models:
- Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
- Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
- Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
- Qwen/Qwen3-TTS-12Hz-1.7B-Base
- Qwen/Qwen3-TTS-12Hz-0.6B-Base

CustomVoice speakers (9):
- Vivian, Serena, Uncle_Fu, Dylan, Eric, Ryan, Aiden, Ono_Anna, Sohee

## User Stories

- As a user, I can select a Qwen3 CustomVoice speaker and provide an instruction to control style or emotion.
- As a user, I can design a voice using a short natural language description and generate speech.
- As a user, I can clone a voice from a reference clip and transcript, then reuse it for multiple outputs.
- As a developer, I can stream audio chunks for low latency playback.
- As a developer, I can encode audio into Qwen3-TTS tokens and decode tokens back to audio for debugging and tooling.
- As an operator, I can pre download model assets for offline or air gapped deployments.

## Functional Requirements

### 1) Adapter Registry and Provider Wiring

- Add a new provider enum: qwen3_tts.
- Register the adapter in TTSAdapterRegistry.DEFAULT_ADAPTERS.
- Add model aliases to MODEL_PROVIDER_MAP for all in scope model ids.

### 2) Provider Configuration

Add a config block in tts_providers_config.yaml:

- providers.qwen3_tts.enabled (default false)
- providers.qwen3_tts.model (default to "auto"; auto selects model at runtime)
- providers.qwen3_tts.model_path (optional local path override)
- providers.qwen3_tts.tokenizer_model (default Qwen3-TTS-Tokenizer-12Hz)
- providers.qwen3_tts.device (cpu, cuda, mps)
- providers.qwen3_tts.dtype (float16, bfloat16, float32)
- providers.qwen3_tts.attn_implementation (flash_attention_2 or default)
- providers.qwen3_tts.auto_download (default false)
- providers.qwen3_tts.max_concurrent_generations (optional throttle)
- providers.qwen3_tts.stream_chunk_size_ms (optional)
- providers.qwen3_tts.auto_min_vram_gb (default 12)
- providers.qwen3_tts.max_text_length (default: conservative; enforce in validation)
- providers.qwen3_tts.tokenizer_max_audio_seconds (default: conservative)
- providers.qwen3_tts.tokenizer_max_tokens (default: conservative)
- providers.qwen3_tts.tokenizer_max_payload_mb (default: conservative)
- providers.qwen3_tts.voice_clone_prompt_max_kb (default: conservative)

### 2.1) Auto Model Selection Heuristic

When providers.qwen3_tts.model is "auto", select a CustomVoice model using GPU capability:

- If device is "cuda" and CUDA is available:
  - Read total VRAM for the selected device.
  - If total_vram_gb >= auto_min_vram_gb: use Qwen3-TTS-12Hz-1.7B-CustomVoice.
  - Else: use Qwen3-TTS-12Hz-0.6B-CustomVoice.
- If device is "mps": use Qwen3-TTS-12Hz-0.6B-CustomVoice.
- If device is "cpu": use Qwen3-TTS-12Hz-0.6B-CustomVoice.
- Log the resolved model and the capability decision (device, VRAM, threshold).
- If the request targets VoiceDesign or Base, reject "auto" with a validation error and require an explicit model id.

### 3) Capability Reporting

Expose TTSCapabilities:

- supported_languages: Chinese, English, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian
- supported_formats: at least wav and pcm; allow mp3/opus/aac via audio_converter
- supported_streaming_formats: pcm, wav, and mp3/opus/aac when real-time transcoding is enabled
- supports_streaming: true
- supports_voice_cloning: true (Base models)
- supports_emotion_control: true (instruction control)
- supported_voices: 9 CustomVoice speakers listed above

### 4) Request Mapping and Dispatch

Map TTSRequest to Qwen3-TTS calls:

CustomVoice (model ends with CustomVoice):
- speaker: request.voice (required)
- language: resolve from request.lang_code or request.extra_params.language (if missing, use "auto" or default from config; pass "auto" through to Qwen3-TTS)
- instruct: request.extra_params.instruct (optional)
- function: generate_custom_voice(text, language, speaker, instruct)

VoiceDesign (model ends with VoiceDesign):
- language: resolve from request.lang_code or request.extra_params.language
- instruct: request.extra_params.instruct (required)
- function: generate_voice_design(text, language, instruct)

Base voice clone (model ends with Base):
- language: resolve from request.lang_code or request.extra_params.language
- ref_audio: request.voice_reference OR stored voice (custom:<voice_id>)
- ref_text: request.extra_params.reference_text OR stored metadata
- x_vector_only_mode: request.extra_params.x_vector_only_mode (optional, true allows missing ref_text but degrades quality)
- voice_clone_prompt: request.extra_params.voice_clone_prompt (optional cached prompt)
- function: generate_voice_clone(text, language, ref_audio, ref_text, x_vector_only_mode, voice_clone_prompt)

Tokenizer (exposed via API):
- Qwen3TTSTokenizer.encode/decode exposed via /api/v1/audio/tokenizer/encode and /api/v1/audio/tokenizer/decode

### 5) Voice Management Integration

- Support voice="custom:<voice_id>" for Base models.
- Store and load reference_text in voice metadata when present.
- Optionally store serialized voice_clone_prompt artifacts to avoid recomputing features for repeated cloning.

### 6) Streaming Behavior

- When request.stream is true, use the Qwen3-TTS streaming interface (if exposed) or incremental chunking from decoded audio as a fallback.
- Default streaming output format for the adapter is pcm (s16le) at 24kHz mono. If response_format requests mp3/opus/aac and streaming is enabled, attempt real-time transcoding from PCM.
- Note: the OpenAI speech schema defaults response_format to mp3; treat this as an explicit mp3 request and attempt real-time transcoding when stream=true.
- Fail fast if streaming is requested for a format that cannot be streamed by the current pipeline (or when real-time transcoding is unavailable).

### 7) Validation Rules

- Validate speaker names against the 9 CustomVoice speakers for CustomVoice models (case-insensitive; normalize spaces/hyphens to underscores).
- Validate that Base models have reference audio, unless x_vector_only_mode is true.
- Enforce max_text_length via provider limits (start with a conservative default, configurable in YAML).
- Validate voice_clone_prompt type/size (see API contracts).
- Validate supported language set (or allow "auto").

### 8) Error Handling

- Missing or invalid speaker: TTSValidationError
- Missing reference audio: TTSInvalidVoiceReferenceError
- Model load or path issues: TTSModelNotFoundError / TTSModelLoadError
- Dependency errors (missing qwen-tts, torch, flash-attn): TTSProviderInitializationError
- Invalid voice_clone_prompt payload: TTSValidationError

### 9) Observability

- Add provider specific metrics: tts_requests_total, tts_request_duration_seconds, tts_stream_ttfb_seconds
- Log provider, model, mode (custom, design, clone), and device (cpu/cuda/mps)

## API and Data Contracts

- Use existing POST /api/v1/audio/speech schema.
- Language should be provided via lang_code; optional request.extra_params.language may override for Qwen3-TTS.
- Use request.extra_params for Qwen3-TTS specific fields:
  - instruct (string)
  - reference_text (string)
  - x_vector_only_mode (bool)
  - voice_clone_prompt (opaque payload; see validation)
  - language (optional override)

voice_clone_prompt payload contract:
- Accept either a base64 string (raw prompt bytes) or an object: {format: "qwen3_tts_prompt_v1", data_b64: "<base64>", sha256: "<optional hex>"}.
- Enforce providers.qwen3_tts.voice_clone_prompt_max_kb and reject unknown formats.
- Treat payload as opaque bytes; never deserialize into executable objects.

AuthNZ:
- Register an audio.tokenizer scope and map it to appropriate roles. In single-user mode, API key access should include tokenizer endpoints by default.

Tokenizer API endpoints:

1) POST /api/v1/audio/tokenizer/encode
   - Input: audio file (multipart) or base64 audio in JSON.
   - Parameters: tokenizer_model (default Qwen3-TTS-Tokenizer-12Hz), sample_rate (optional; if omitted, detect or require).
   - Output: tokens (list[int] or base64 encoded), sample_rate, frame_rate, tokenizer_model, duration_seconds.
   - Auth: dedicated audio.tokenizer scope (single-user mode should treat API key as full audio scope).
   - Limits: enforce tokenizer_max_audio_seconds, tokenizer_max_payload_mb, tokenizer_max_tokens.

2) POST /api/v1/audio/tokenizer/decode
   - Input: tokens (list[int] or base64), tokenizer_model (default Qwen3-TTS-Tokenizer-12Hz), response_format (wav or pcm).
   - Output: audio bytes in response_format, sample_rate, duration_seconds.
   - Auth: dedicated audio.tokenizer scope (single-user mode should treat API key as full audio scope).
   - Limits: enforce tokenizer_max_tokens, tokenizer_max_payload_mb.

## Storage and Data

- Store reference audio and metadata under user voices path.
- Metadata fields for Qwen3-TTS: reference_text, voice_clone_prompt (optional), voice_clone_prompt_format.

## Dependencies

- qwen-tts Python package
- torch
- soundfile
- Optional: flash-attn for lower GPU memory usage (requires float16 or bfloat16)

## Non-functional Requirements

- Performance: Streaming should produce first audio chunk with low latency when supported by Qwen3-TTS.
- Reliability: Adapter should reuse model instances across requests and obey concurrency limits.
- Security: Never log reference audio or text content.
- Security: voice_clone_prompt must be treated as untrusted input; validate size and accept only base64 (or {format, data_b64}) payloads. Never deserialize into executable objects.
- Offline by default: no auto download unless explicitly enabled.

## UX / UI

- Out of scope for this PRD. Frontend/UX work will be handled separately.

## Testing

Unit tests:
- Provider map resolves all Qwen3-TTS model ids to qwen3_tts.
- Validation rejects invalid speakers and missing reference audio.
- Config parsing for qwen3_tts block.

Integration tests:
- Mock adapter outputs for each mode (custom, design, clone).
- Streaming path returns non empty chunks.
- Tokenizer encode/decode endpoints round trip sample audio.

Property tests:
- Voice reference validation (size, type, duration).

## Risks

- GPU memory constraints for 1.7B models.
- Streaming pipeline may require format or chunk size tuning.
- Voice cloning quality drops when ref_text is omitted (x_vector_only_mode).

## Milestones

M1: Provider wiring and config
- Add provider enum, adapter stub, config block, model alias mapping.

M2: Generation modes
- Implement CustomVoice and VoiceDesign paths.
- Implement Base voice clone path with reference audio and text.

M3: Streaming and voice prompt reuse
- Streaming output support with chunking.
- Optional voice_clone_prompt caching.

M4: Tokenizer API and docs
- Add tokenizer encode/decode endpoints and schemas.
- Example requests in docs.

## References

- https://github.com/QwenLM/Qwen3-TTS
- https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
- https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
- https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base
- https://huggingface.co/Qwen/Qwen3-TTS-Tokenizer-12Hz
