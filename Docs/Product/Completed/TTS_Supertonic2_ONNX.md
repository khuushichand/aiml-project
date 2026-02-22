# PRD: Supertonic2 ONNX TTS Provider

## 1. Overview

This document specifies how to integrate Supertonic2 ONNX TTS as a local provider in the existing TTS module.

- Scope: add a new adapter-based provider ("supertonic2") that plugs into:
  - TTSServiceV2 and the adapter registry
  - OpenAI-compatible /api/v1/audio/speech
  - Voice catalog (/api/v1/audio/voices/catalog)
- Asset model: users supply Supertonic2 ONNX models and voice style JSON files; the project ships:
  - A provider adapter
  - Configuration wiring
  - Optional installer guidance
- Non-goals:
  - Training or fine-tuning models
  - Voice cloning in v1
  - True incremental streaming (use pseudo-streaming)
  - Using the "supertonic" PyPI package (this PRD focuses on ONNX assets)

This PRD targets the current TTS architecture in tldw_Server_API/app/core/TTS/.

## 2. Goals and User Stories

### 2.1 Goals

- Add a local Supertonic2 ONNX TTS provider that:
  - Uses the existing TTSAdapter interface
  - Is selectable via OpenAISpeechRequest.model and config
  - Supports streaming and non-streaming responses
  - Exposes Supertonic2 voices in the unified voice catalog
- Support multilingual synthesis for:
  - en, ko, es, pt, fr
- Allow users to control:
  - Speech speed
  - Quality vs speed via denoising steps
  - Voice style selection

### 2.2 User Stories

- Local-first user:
  - As a self-hoster, I want a high-quality local TTS based on Supertonic2 without remote APIs.
- Multilingual user:
  - As a multilingual user, I want to synthesize in English, Korean, Spanish, Portuguese, and French via a single provider.
- Power user:
  - As a power user, I want to adjust speed and denoising steps to trade latency for fidelity.

## 3. Architectural Fit

### 3.1 Existing TTS Architecture (Short)

- TTSServiceV2 (tts_service_v2.py)
- TTSAdapterRegistry and TTSAdapterFactory (adapter_registry.py)
- Provider contract (adapters/base.py)
- Validation (tts_validation.py)
- Config (tts_config.py + Config_Files/tts_providers_config.yaml)
- Audio formatting (streaming_audio_writer.py + TTSAdapter.convert_audio_format)
- API entrypoint (api/v1/endpoints/audio.py)

### 3.2 New Components and Touchpoints

1. Enum and registry
   - Add SUPERTONIC2 = "supertonic2" to TTSProvider in adapter_registry.py.
   - Register default adapter mapping:
     - TTSProvider.SUPERTONIC2: "tldw_Server_API.app.core.TTS.adapters.supertonic2_adapter.Supertonic2OnnxAdapter"
2. New adapter
   - File: tldw_Server_API/app/core/TTS/adapters/supertonic2_adapter.py
   - Class: Supertonic2OnnxAdapter(TTSAdapter)
3. Vendor namespace
   - Folder: tldw_Server_API/app/core/TTS/vendors/supertonic2/
   - Purpose: vendored helper based on the Supertonic2 ONNX example (multilingual preprocessing, language tags)
4. Model routing
   - Extend TTSAdapterFactory.MODEL_PROVIDER_MAP with:
     - "tts-supertonic2-1" (canonical)
     - "supertonic2", "supertonic-2", "supertonic2-onnx" (aliases)
5. Provider hinting for validation
   - Extend _infer_tts_provider_from_model in api/v1/endpoints/audio.py so model names starting with
     "supertonic2", "supertonic-2", or "tts-supertonic2" map to provider key "supertonic2".
6. Config
   - Add a "supertonic2" block under providers in tts_providers_config.yaml.
   - Keep existing "supertonic" provider unchanged to avoid regressions.

## 4. Functional Requirements

### 4.1 Provider Behavior

- Provider key: "supertonic2"
- Adapter class: Supertonic2OnnxAdapter
- Exposed via:
  - TTSServiceV2.get_capabilities() under capabilities["supertonic2"]
  - TTSServiceV2.list_voices() under voices_by_provider["supertonic2"]

TTSRequest fields used:

- text: input text
- voice: Supertonic2 voice style ID (example: supertonic2_m1)
- language: one of en, ko, es, pt, fr (default "en")
- format: mp3 or wav
- speed: speech speed, recommended 0.9 to 1.5
- stream: whether to return audio_stream
- extra_params.total_step: denoising steps (quality vs speed)

TTSResponse:

- Non-streaming: audio_data populated with encoded bytes
- Streaming: audio_stream yields encoded bytes in chunks
- sample_rate is sourced from the engine (default 24000)

### 4.2 Supertonic2 Engine Integration

Upstream contract (from example_onnx.py + helper.py):

- Engine load: load_text_to_speech(onnx_dir, use_gpu)
- Voice style load: load_voice_style([style_path])
- Inference (non-batch):
  - wav, duration = engine(text, lang, style, total_step, speed)
- Inference (batch):
  - wav, duration = engine.batch(text_list, lang_list, style, total_step, speed)

Important behaviors to preserve:

- Text preprocessing is language-aware and wraps text with <lang> tags
- Available languages: en, ko, es, pt, fr
- Automatic text chunking:
  - ko uses max_len 120
  - all others use max_len 300
- Default speed is 1.05

Adapter requirements:

- Pass request.language (default to "en") into the engine
- Use non-batch mode for v1 requests to preserve long-form chunking behavior
- Guard engine calls with an asyncio.Lock to avoid concurrent use

### 4.3 Configuration

Add a provider block to Config_Files/tts_providers_config.yaml:

```yaml
providers:
  supertonic2:
    enabled: false
    model_path: "models/supertonic2/onnx"
    sample_rate: 24000
    device: "cpu"
    extra_params:
      voice_styles_dir: "models/supertonic2/voice_styles"
      default_voice: "supertonic2_m1"
      voice_files:
        supertonic2_m1: "M1.json"
        supertonic2_f1: "F1.json"
      default_total_step: 5
      default_speed: 1.05
```

Notes:

- The project must not ship models or voice styles.
- Required ONNX assets (user-supplied):
  - duration_predictor.onnx
  - text_encoder.onnx
  - vector_estimator.onnx
  - vocoder.onnx
  - tts.json
  - unicode_indexer.json

### 4.4 Validation and Limits

Add provider limits in tts_validation.py:

- ProviderLimits entry:
  - max_text_length: 15000
  - languages: [en, ko, es, pt, fr]
  - valid_formats: {mp3, wav}
  - min_speed: 0.9
  - max_speed: 1.5
- TTSInputValidator:
  - MAX_TEXT_LENGTHS["supertonic2"] = 15000
  - SUPPORTED_LANGUAGES["supertonic2"] = {"en", "ko", "es", "pt", "fr"}
  - SUPPORTED_FORMATS["supertonic2"] = {AudioFormat.MP3, AudioFormat.WAV}

Validation behavior:

- Reject unsupported languages before adapter invocation
- Reject response_format outside mp3 or wav
- Enforce speed within 0.9 to 1.5 for supertonic2

### 4.5 Capabilities and Voice Catalog

get_capabilities() should return:

- provider_name = "Supertonic2"
- supported_languages = {"en", "ko", "es", "pt", "fr"}
- supported_formats = {AudioFormat.MP3, AudioFormat.WAV}
- max_text_length = 15000
- supports_streaming = True (pseudo-streaming)
- supports_voice_cloning = False
- supports_speech_rate = True
- sample_rate = engine sample rate (default 24000)
- default_format = AudioFormat.WAV

VoiceInfo entries should be built from the configured voice_files mapping.
VoiceInfo.language can remain "en" for compatibility, but should not be used
for validation. Supported languages come from supported_languages.

### 4.6 API Integration

Model routing:

- Add to TTSAdapterFactory.MODEL_PROVIDER_MAP:
  - "tts-supertonic2-1": TTSProvider.SUPERTONIC2
  - "supertonic2": TTSProvider.SUPERTONIC2
  - "supertonic-2": TTSProvider.SUPERTONIC2
  - "supertonic2-onnx": TTSProvider.SUPERTONIC2

Provider hinting:

- In _infer_tts_provider_from_model, if model starts with "supertonic2",
  "supertonic-2", or "tts-supertonic2", return "supertonic2".

## 5. Non-Functional Requirements

- CPU-first: GPU mode is not supported per upstream notes
- Lazy initialization: models are loaded on first use
- Streaming: pseudo-streaming by chunking encoded audio bytes
- Concurrency: protect engine calls with asyncio.Lock
- Logging: include onnx_dir, voice_styles_dir, voice_id, language, speed, total_step

## 6. Testing and Validation

Unit tests (new):

- Adapter initialization succeeds with mocked vendor module
- Missing default voice triggers TTSModelNotFoundError
- generate() calls engine with (text, language, style, total_step, speed)
- Streaming mode yields multiple chunks

Validation tests:

- Language validation rejects unsupported languages for provider "supertonic2"
- Speed validation enforces 0.9 to 1.5
- Format validation enforces mp3/wav

Integration tests:

- /api/v1/audio/voices/catalog includes supertonic2 voices when enabled
- /api/v1/audio/speech returns non-empty bytes with model "tts-supertonic2-1"

## 7. Risks and Open Questions

- Voice set: confirm which style JSONs are provided by the supertonic-2 repo
- Language tags: verify upstream expects <lang> wrappers for all languages
- Performance: measure CPU latency for long-form synthesis
- Packaging: decide whether to add a helper installer script for Supertonic2 assets

Once this PRD is accepted, the next step is to write a staged implementation plan
and then add the adapter, registry entries, validation updates, and docs.
