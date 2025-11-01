# TTS (Text-to-Speech) Module

## Overview

The TTS module delivers a unified, production-grade interface over multiple text-to-speech engines. It wraps commercial APIs and local models behind a shared adapter contract, exposes OpenAI-compatible endpoints, and provides fallbacks, metrics, and resource management so the rest of the platform can treat TTS as a single capability.

## Feature Highlights

- **Provider federation**: built-in adapters for OpenAI, ElevenLabs, Kokoro, Higgs Audio, Dia, Chatterbox, VibeVoice, IndexTTS2, and NeuTTS; a mock adapter exists for tests and an AllTalk placeholder is reserved.
- **Streaming-first pipeline**: adapters implement chunked streaming where supported; the service coordinates fallbacks, normalization, and HTTP 200 vs. error streaming via `performance.stream_errors_as_audio` or the `TTS_STREAM_ERRORS_AS_AUDIO` override.
- **Voice cloning & management**: cloning-aware adapters accept reference audio while the `voice_manager` subsystem handles uploads, validation, quotas, and preview generation.
- **Unified configuration**: `TTSConfigManager` merges `tts_providers_config.yaml`, `Config_Files/config.txt`, and environment overrides with provider-specific settings and priority ordering.
- **Resilience & observability**: per-provider circuit breakers, resource checks, HTTP connection pooling, and Prometheus metrics (`tts_requests_total`, `tts_request_duration_seconds`, etc.) are registered automatically.
- **Security & validation**: input sanitization, text length enforcement, voice reference validation, rate limiting, and scope-based auth protect the API surface.

## Architecture & Layout

### Directory Layout

```
TTS/
├── adapters/                  # Provider adapters (cloud + local)
│   ├── base.py                # Adapter interface + data models
│   ├── chatterbox_adapter.py
│   ├── dia_adapter.py
│   ├── elevenlabs_adapter.py
│   ├── higgs_adapter.py
│   ├── index_tts_adapter.py
│   ├── kokoro_adapter.py
│   ├── neutts_adapter.py
│   ├── openai_adapter.py
│   └── vibevoice_adapter.py
├── adapter_registry.py        # Provider registry & factory
├── audio_converter.py         # Format conversion & resampling helpers
├── audio_utils.py             # Text + audio validation helpers
├── circuit_breaker.py         # Per-provider breaker management
├── streaming_audio_writer.py  # Streaming normalization utilities
├── tts_config.py              # Unified configuration manager (Pydantic)
├── tts_exceptions.py          # Error hierarchy
├── tts_resource_manager.py    # Resource pooling and cleanup
├── tts_service_v2.py          # High-level orchestration (fallback + metrics)
├── tts_validation.py          # Request sanitization/validation rules
├── voice_manager.py           # Custom voice upload/registry service
├── waveform_streamer.py       # Helpers for HTTP streaming responses
├── vendors/                   # Vendored engines (e.g., NeuTTS Air)
└── README.md / TTS-*.md       # Module documentation
```

### Core Components

- `TTSServiceV2`: coordinates provider selection, concurrency via an async semaphore, fallback, and exposes both OpenAI-compatible streaming and legacy adapter APIs.
- `TTSAdapterRegistry`: lazy-loads adapters, respects configuration enablement, and tracks failed providers to avoid repeated initialization.
- `TTSResourceManager`: manages HTTP clients, streaming sessions, and resource health (memory, temp files, GPU) while providing cleanup hooks.
- `VoiceManager`: validates and stores user-supplied voice references, enforces quotas, and powers `/api/v1/audio/voices/*` endpoints.
- `StreamingAudioWriter` & `AudioConverter`: normalize chunk sizes, convert sample rates / formats, and support provider-specific stream wrappers.
- `CircuitBreakerManager`: guards providers with failure thresholds and integrates with the fallback path.
- `tts_validation`: centralizes input sanitation, voice reference checks, and provider-specific limits.

## Provider Support Matrix

| Provider      | Type         | Streaming | Voice Cloning | Formats*               | Notes |
|---------------|--------------|-----------|---------------|------------------------|-------|
| OpenAI        | Cloud API    | Yes       | No            | mp3, opus, aac, flac, wav, pcm | Uses OpenAI `tts-1`/`tts-1-hd`; voice mapping + HTTP client pooling |
| ElevenLabs    | Cloud API    | Yes       | Yes (Pro)     | mp3, opus, wav, pcm    | Supports user voices, stability/similarity tuning |
| Kokoro        | Local ONNX   | Yes       | No            | mp3, wav, opus, flac, pcm | Lightweight offline synthesis with phoneme support |
| Higgs Audio   | Local PyTorch| Yes       | Yes           | wav, mp3, opus, flac, pcm | Multilingual, emotion control, background audio |
| Dia           | Local PyTorch| Yes       | Yes           | wav, mp3, opus, flac, pcm | Dialogue-focused multi-speaker generation |
| Chatterbox    | Local PyTorch| Yes       | Yes           | wav, mp3, opus, flac, pcm | Emotion exaggeration controls and style tuning |
| VibeVoice     | Local PyTorch| Yes       | Yes           | wav, mp3, opus, flac, pcm | Long-form generation, CFG controls, background music |
| IndexTTS2     | Local (Index)| Yes       | Yes (required)| mp3, wav               | Zero/one-shot cloning with emotion prompts; requires reference audio |
| NeuTTS Air    | Local Hybrid | Conditional†| Yes         | mp3, wav, opus, flac, pcm | On-device synthesis; streaming when loading quantized GGUF |
| Mock (tests)  | Test double  | Yes       | No            | wav                    | Deterministic adapter for test environments |
| AllTalk       | Planned      | -         | -             | -                      | Placeholder entry in `TTSProvider` for future work |

\* Actual formats depend on each adapter’s `TTSCapabilities`.

† Streaming is enabled when a quantized (GGUF) model is loaded; otherwise NeuTTS returns buffered audio.

Adapters expose `TTSCapabilities` describing supported languages, formats, and advanced features; discovery APIs surface this metadata to clients.

## Voice Management

The `voice_manager` module powers custom voice workflows:

- Validates uploads per provider (extensions, duration, sample rate, and size) and sanitizes filenames.
- Persists voice metadata with SHA hashes to deduplicate uploads under user-specific storage.
- Enforces configurable quotas (`VOICE_RATE_LIMITS`) covering upload rate, concurrent processing, and total storage.
- Exposes management endpoints:
  - `POST /api/v1/audio/voices/upload`
  - `GET /api/v1/audio/voices/catalog` (aggregated provider voices, optional `provider` filter)
  - `GET /api/v1/audio/voices` + `GET/DELETE /api/v1/audio/voices/{voice_id}`
  - `POST /api/v1/audio/voices/{voice_id}/preview`
- Integrates with cloning-capable adapters (VibeVoice, Higgs, Chatterbox, Dia, IndexTTS2, NeuTTS, ElevenLabs). See `TTS-VOICE-CLONING.md` for detailed workflows.

## Configuration

`TTSConfigManager` merges sources in the order: environment variables → `Config_Files/config.txt` → `tts_providers_config.yaml` → defaults.

Example `tts_providers_config.yaml` excerpt:

```yaml
provider_priority:
  - openai
  - elevenlabs
  - kokoro
  - higgs
  - index_tts
  - neutts

providers:
  openai:
    enabled: true
    api_key: ${OPENAI_API_KEY}
    model: tts-1-hd

  kokoro:
    enabled: true
    model_path: ./models/kokoro-v0_19.onnx
    device: cpu

  index_tts:
    enabled: false
    model_dir: checkpoints/index_tts2
    cfg_path: checkpoints/index_tts2/config.yaml
    device: cuda
    interval_silence: 200

  neutts:
    enabled: false
    backbone_repo: neuphonic/neutts-air
    codec_repo: neuphonic/neucodec
    auto_download: true
    sample_rate: 24000

performance:
  max_concurrent_generations: 4
  stream_errors_as_audio: true
  connection_timeout: 30.0

fallback:
  enabled: true
  max_attempts: 3
  exclude_providers: []
```

Additional notes:

- `TTS_STREAM_ERRORS_AS_AUDIO` overrides the streaming error behavior at runtime.
- Provider configs support `${ENV_VAR}` references for secrets.
- `voice_mappings`, `format_preferences`, and logging settings can be customized per deployment.

## Runtime Behaviour

- **Provider selection & fallback**: `TTSServiceV2` maps OpenAI model names to adapters, applies circuit breaker checks, and iterates through `provider_priority` when a provider fails. Retryable errors use exponential backoff.
- **Concurrency control**: an async semaphore enforces `performance.max_concurrent_generations`; adapters layer on their own limits when necessary.
- **Resource management**: `tts_resource_manager` maintains HTTP clients, streaming sessions, and periodic cleanup of idle resources while tracking metrics per resource type.
- **Metrics & logging**: metrics such as `tts_requests_total`, `tts_request_duration_seconds`, `tts_text_length_characters`, `tts_audio_size_bytes`, and `tts_fallback_attempts` are registered with the global metrics registry. Logging levels follow configuration.
- **Validation & quotas**: `tts_validation` sanitizes text, enforces provider limits, and coordinates with API rate limiting and scope enforcement.

## API Endpoints

All endpoints live under `/api/v1/audio`:

- `POST /api/v1/audio/speech` - OpenAI-compatible speech synthesis (streaming or buffered).
- `GET /api/v1/audio/voices/catalog` - Aggregate voice catalog across providers.
- `POST /api/v1/audio/voices/upload` - Upload custom voice references.
- `GET /api/v1/audio/voices` - List a user’s custom voice assets.
- `GET /api/v1/audio/voices/{voice_id}` / `DELETE /api/v1/audio/voices/{voice_id}` - Manage stored voices.
- `POST /api/v1/audio/voices/{voice_id}/preview` - Generate preview audio via a stored voice.

See `tldw_Server_API/app/api/v1/endpoints/audio.py` for additional STT and quota-related endpoints co-located with the TTS routes.

## Usage Examples

```python
from tldw_Server_API.app.core.TTS.tts_service_v2 import get_tts_service_v2
from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest

async def synthesize():
    service = await get_tts_service_v2()
    request = OpenAISpeechRequest(
        input="Hello from the TLDW server.",
        model="tts-1-hd",
        voice="alloy",
        response_format="mp3",
        stream=True
    )

    async for chunk in service.generate_speech(request):
        process_audio(chunk)  # Your audio handling logic
```

List voices aggregated from all providers:

```python
tts_service = await get_tts_service_v2()
catalog = await tts_service.list_voices()
print(catalog["openai"]["voices"])  # Provider-specific voice metadata
```

## Testing

```bash
# Full TTS regression suite (legacy + v2)
python -m pytest tldw_Server_API/tests/TTS -v

# Property and integration tests for the new pipeline
python -m pytest tldw_Server_API/tests/TTS_NEW -v

# Targeted adapter tests
python -m pytest tldw_Server_API/tests/TTS/test_tts_adapters.py -k openai
```

## Adding a New Provider

1. **Create an adapter** inheriting from `TTSAdapter` under `adapters/your_adapter.py`. Implement `initialize`, `get_capabilities`, `generate`, and (optionally) streaming helpers.
2. **Register it** in `TTSProvider` and `DEFAULT_ADAPTERS` (via dotted path) inside `adapter_registry.py`.
3. **Add configuration** defaults to `tts_providers_config.yaml` and document required assets/dependencies.
4. **Provide tests** covering initialization, capability reporting, request validation, and audio generation.
5. **Update documentation** (this README and any relevant deployment guides).

## Additional References

- `TTS-DEPLOYMENT.md` - deployment checklist and environment validation.
- `TTS-VOICE-CLONING.md` - detailed cloning workflows and provider requirements.
- `Docs/STT-TTS/TTS-SETUP-GUIDE.md` - end-to-end setup for local and cloud engines.
- `Docs/Design/TTS_Module_PRD.md` - product requirements and roadmap.
