# TTS Module - Text-to-Speech Service

## Overview

The TTS module provides a production-ready, extensible Text-to-Speech service with support for multiple providers, voice cloning, and OpenAI-compatible API endpoints. Built with an adapter pattern architecture, it offers seamless fallback between providers, comprehensive error handling, and enterprise-grade features.

## Features

### Core Capabilities
- **Multi-Provider Support**: OpenAI, ElevenLabs, and 4 open-source models
- **Voice Cloning**: Support for voice reference audio with Higgs, Chatterbox, and VibeVoice
- **Streaming Audio**: Real-time audio streaming for all providers
- **Format Support**: MP3, WAV, OPUS, FLAC, PCM output formats
- **OpenAI Compatibility**: Drop-in replacement for OpenAI TTS API
- **Fault Tolerance**: Circuit breaker pattern with automatic failover
- **Performance Metrics**: Built-in monitoring and health checks
- **Transcription/Translation**: OpenAI-compatible speech-to-text endpoints

### Supported Providers

| Provider | Type | Languages | Voice Cloning | Key Features |
|----------|------|-----------|---------------|--------------|
| **OpenAI** | Commercial API | 50+ | ❌ | Industry standard, HD quality |
| **ElevenLabs** | Commercial API | 29 | ✅ (Pro) | Premium quality, emotion control |
| **Kokoro** | Local ONNX | EN | ❌ | Lightweight, CPU-friendly, offline |
| **Higgs** | Local PyTorch | 50+ | ✅ (3-10s) | Music generation, multi-lingual |
| **Chatterbox** | Local PyTorch | EN | ✅ (5-20s) | Emotion exaggeration control |
| **Dia** | Local PyTorch | EN | ❌ | Multi-speaker dialogue specialist |
| **VibeVoice** | Local PyTorch | 12 | ✅ (Any) | Long-form (90min), spontaneous music |
| **NeuTTS** | Local (Hybrid) | EN | ✅ (3–15s) | Instant voice cloning, GGUF streaming |

## Architecture

### V2 Adapter Pattern

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   API       │────▶│  TTS Service │────▶│  Adapter    │
│  Endpoint   │     │      V2      │     │  Registry   │
└─────────────┘     └──────────────┘     └─────────────┘
                            │                     │
                    ┌───────▼───────┐    ┌───────▼───────┐
                    │Circuit Breaker│    │   Provider    │
                    │   Manager     │    │   Adapters   │
                    └───────────────┘    └───────────────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    │                            │                            │
              ┌─────▼─────┐            ┌────────▼────────┐           ┌───────▼───────┐
              │  OpenAI   │            │   Local Models  │           │  Commercial   │
              │  Adapter  │            │   (Kokoro,etc)  │           │   (ElevenLabs)│
              └───────────┘            └─────────────────┘           └───────────────┘
```

### Key Components

1. **TTSServiceV2** (`tts_service_v2.py`)
   - Main service orchestrator
   - Handles provider selection and fallback
   - Integrates metrics and circuit breaker

2. **Adapter Registry** (`adapter_registry.py`)
   - Provider registration and management
   - Capability discovery
   - Dynamic adapter loading

3. **Base Adapter** (`adapters/base.py`)
   - Abstract interface for all providers
   - Standard request/response formats
   - Capability reporting

4. **Provider Adapters** (`adapters/*.py`)
   - Provider-specific implementations
   - Handle authentication and API calls
   - Audio generation and streaming

5. **Circuit Breaker** (`circuit_breaker.py`)
   - Fault tolerance and recovery
   - Automatic provider failover
   - Configurable thresholds

6. **Audio Utils** (`audio_utils.py`)
   - Voice reference processing
   - Format conversion
   - Audio validation

## Installation

### Prerequisites

```bash
# System dependencies
apt-get install ffmpeg espeak-ng  # Ubuntu/Debian
brew install ffmpeg espeak         # macOS

# Python dependencies
pip install -r requirements.txt
```

### Quick Start

1. **Configure API Keys**
```bash
# In config.txt
[API]
openai_api_key = sk-...
elevenlabs_api_key = xi-...
```

2. **Configure TTS Settings**
```yaml
# In tts_providers_config.yaml
provider_priority:
  - openai      # Primary provider
  - kokoro      # Fallback to local
  
providers:
  openai:
    enabled: true
    model: tts-1-hd
  
  kokoro:
    enabled: true
    model_path: ./models/kokoro-v0_19.onnx
```

3. **Start the Server**
```bash
python -m uvicorn tldw_Server_API.app.main:app --host 0.0.0.0 --port 8000
```

For NeuTTS installation and usage, see `Docs/STT-TTS/NEUTTS_TTS_SETUP.md`.

## API Usage

### Basic Text-to-Speech

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/audio/speech",
    headers={"Authorization": "Bearer your-token"},
    json={
        "model": "tts-1",  # or an ElevenLabs model like "eleven_multilingual_v2" / "eleven_turbo_v2"
        "input": "Hello, world!",
        "voice": "alloy",
        "response_format": "mp3"
    }
)

with open("output.mp3", "wb") as f:
    f.write(response.content)
```

### Voice Cloning

```python
import base64

# Prepare voice reference
with open("voice_sample.wav", "rb") as f:
    voice_ref = base64.b64encode(f.read()).decode()

response = requests.post(
    "http://localhost:8000/api/v1/audio/speech",
    json={
        "model": "higgs",  # or chatterbox, vibevoice
        "input": "This will sound like the reference voice.",
        "voice": "default",
        "voice_reference": voice_ref,  # Base64 encoded audio
        "response_format": "mp3"
    }
)
```

### Streaming Audio

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/v1/audio/speech",
        json={
            "model": "kokoro",  # ElevenLabs also supports streaming
            "input": "Streaming audio test.",
            "voice": "af_bella",
            "stream": True
        },
        timeout=30.0
    )
    
    with open("stream.mp3", "wb") as f:
        async for chunk in response.aiter_bytes():
            f.write(chunk)
```

### List Voices

List voices from all available providers, or filter by provider.

```bash
# All providers (catalog)
curl -s http://localhost:8000/api/v1/audio/voices/catalog | jq

# ElevenLabs only
curl -s "http://localhost:8000/api/v1/audio/voices/catalog?provider=elevenlabs" | jq
```

Example response (filtered):
```json
{
  "elevenlabs": [
    { "id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel", "gender": "female", "language": "en", "description": "American female voice" },
    { "id": "29vD33N1CtxCmqQRPOHJ", "name": "Drew",   "gender": "male",   "language": "en", "description": "American male voice" }
  ]
}
```

Notes
- ElevenLabs voices include your account’s user voices (cached on adapter init) plus defaults.
- Other providers expose their known/static voices where applicable.

### Bootstrap Kokoro Assets

Use the helper script to download Kokoro ONNX model and voices.json to your configured paths.

```bash
python Helper_Scripts/download_kokoro_assets.py \
  --onnx-url <KOKORO_ONNX_URL> \
  --voices-url <VOICES_JSON_URL> \
  --model-path tldw_Server_API/app/core/TTS/models/kokoro-v0_19.onnx \
  --voices-json tldw_Server_API/app/core/TTS/models/voices.json
```

Update `tts_providers_config.yaml` to point to your downloaded files. For GPU support, set `providers.kokoro.use_onnx: false` and provide a `.pth` model path (PyTorch backend requires a compatible Kokoro PyTorch implementation).

### Transcription (Speech-to-Text)

```python
# Transcribe audio file
with open("audio.mp3", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/v1/audio/transcriptions",
        headers={"Authorization": "Bearer your-token"},
        files={"file": f},
        data={
            "model": "whisper-1",
            "language": "en",
            "response_format": "json"
        }
    )
    
print(response.json()["text"])
```

## Configuration

### Provider Configuration (tts_providers_config.yaml)

```yaml
# Provider priority (fallback order)
provider_priority:
  - openai          # Try first
  - elevenlabs      # Try second
  - kokoro          # Local fallback

# Individual provider settings
providers:
  openai:
    enabled: true
    api_key: ${OPENAI_API_KEY}  # From environment
    model: tts-1-hd
    timeout: 30
    
  kokoro:
    enabled: true
    model_path: ./models/kokoro-v0_19.onnx
    device: cpu  # or cuda
    
  higgs:
    enabled: true
    model_path: bosonai/higgs-audio-v2-generation-3B-base
    device: cuda
    use_fp16: true
    
  chatterbox:
    enabled: true
    model_path: resemble-ai/chatterbox
    enable_watermark: true
    
  vibevoice:
    enabled: true
    variant: 1.5B  # or 7B
    device: cuda

# Fallback configuration
fallback:
  enabled: true
  max_attempts: 3
  retry_delay_ms: 1000

# Circuit breaker settings
circuit_breaker:
  failure_threshold: 5
  recovery_timeout: 60
  half_open_calls: 3

# Performance settings
performance:
  max_concurrent_generations: 4
  # When true, embed error messages into the audio stream (compat mode)
  # When false, raise errors so the API returns proper HTTP errors
  stream_errors_as_audio: true
  cache_enabled: false
```

#### Generic vs Provider-Prefixed Keys

The registry automatically aliases common, generic keys from your YAML to the provider-prefixed keys that some adapters expect. This keeps configuration consistent across providers while satisfying adapter expectations.

- OpenAI
  - Generic: `api_key`, `base_url`, `model`, `stability`, `similarity_boost`, `style`, `speaker_boost`
  - Aliased to: `openai_api_key`, `openai_base_url`, `openai_model`

- ElevenLabs
  - Generic: `api_key`, `base_url`, `model`, `stability`, `similarity_boost`, `style`, `speaker_boost`
  - Aliased to: `elevenlabs_api_key`, `elevenlabs_base_url`, `elevenlabs_model`, `elevenlabs_stability`, `elevenlabs_similarity_boost`, `elevenlabs_style`, `elevenlabs_speaker_boost`

- Kokoro
  - Generic: `device`, `use_onnx`, `model_path`, `voices_json`, `voice_dir`
  - Aliased to: `kokoro_device`, `kokoro_use_onnx`, `kokoro_model_path`, `kokoro_voices_json`, `kokoro_voice_dir`
  - Other Kokoro options are read generically (no alias needed): `sample_rate`, `normalize_text`, `sentence_splitting`

- Higgs
  - Generic: `model_path`, `tokenizer_path`, `device`, `use_fp16`, `batch_size`
  - Aliased to: `higgs_model_path`, `higgs_tokenizer_path`, `higgs_device`, `higgs_use_fp16`, `higgs_batch_size`

- Dia
  - Generic: `model_path`, `device`, `use_safetensors`, `use_bf16`, `sample_rate`, `auto_detect_speakers`, `max_speakers`
  - Aliased to: `dia_model_path`, `dia_device`, `dia_use_safetensors`, `dia_use_bf16`, `dia_sample_rate`, `dia_auto_detect_speakers`, `dia_max_speakers`

- Chatterbox
  - Generic: `device`, `use_multilingual`, `disable_watermark`, `sample_rate`, `target_latency_ms`
  - Aliased to: `chatterbox_device`, `chatterbox_use_multilingual`, `chatterbox_disable_watermark`, `chatterbox_target_latency_ms`

- VibeVoice
  - Generic: `device`, `sample_rate`, `variant`, `model_path`, `model_dir`, `cache_dir`, `voices_dir`, `background_music`, `enable_singing`, `use_quantization`, `auto_cleanup`, `auto_download`, `enable_sage`, `attention_type`, `cfg_scale`, `diffusion_steps`, `temperature`, `top_p`, `top_k`, `stream_chunk_size`, `stream_buffer_size`
  - Aliased to the corresponding `vibevoice_*` fields

Notes
- Environment variables still work and may override YAML (e.g., `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`).
- Adapters that already read generic names (e.g., Kokoro’s `sample_rate`) don’t require aliasing for those fields.
- If you add new provider options in YAML, prefer generic names; the registry can be extended to alias them.

#### Concurrency Control

The service (`TTSServiceV2`) reads `performance.max_concurrent_generations` and sets an internal semaphore to enforce this limit at runtime. This controls total concurrent TTS generations across providers. If not specified, it defaults to `4` and is clamped to a minimum of `1`.

#### Error Streaming Policy

Set `performance.stream_errors_as_audio` to control failure behavior during streaming:
- `true` (default for compatibility): embed `ERROR: ...` text chunks in the audio stream and return HTTP 200. Suitable for clients/tests that expect bytes regardless of outcome.
- `false` (recommended for production): raise provider/service errors instead. The API endpoint maps these to appropriate HTTP status codes (e.g., 400/402/429/5xx).

### Voice Cloning Requirements

| Provider | Min Duration | Max Duration | Format | Sample Rate |
|----------|-------------|--------------|--------|-------------|
| Higgs | 3s | 10s | WAV/MP3/FLAC | 24kHz |
| Chatterbox | 5s | 20s | WAV/MP3 | 24kHz+ |
| VibeVoice | 3s | 30s | WAV/MP3 | 22.05kHz |

## Monitoring

### Health Check
```bash
curl http://localhost:8000/api/v1/audio/health
```

Response:
```json
{
  "status": "healthy",
  "providers": {
    "total": 7,
    "available": 3,
    "details": {
      "openai": "available",
      "kokoro": "available",
      "higgs": "not_initialized"
    }
  },
  "circuit_breakers": {
    "openai": "closed",
    "kokoro": "closed"
  }
}
```

### List Providers
```bash
curl http://localhost:8000/api/v1/audio/providers
```

### Metrics
The service integrates with the application's metrics system:
- Request counts per provider
- Response times (p50, p95, p99)
- Error rates by category
- Active request gauges
- Audio generation sizes

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "Provider not available" | Check API keys and model files |
| "Voice reference validation failed" | Ensure audio meets duration/format requirements |
| "Circuit breaker open" | Provider temporarily disabled due to failures, will auto-recover |
| "Model not found" | Download required model files (see setup guide) |
| "Out of memory" | Reduce batch size or use smaller model variant |

### Debug Mode

Enable detailed logging:
```yaml
# In tts_providers_config.yaml
logging:
  level: DEBUG
  include_metrics: true
```

### Voice Cloning Issues

1. **Audio too short/long**: Check provider-specific duration requirements
2. **Poor quality clone**: Ensure clean audio, single speaker, no background noise
3. **Format not supported**: Convert to WAV 24kHz mono
4. **Memory error**: Voice cloning requires more VRAM, try CPU mode

## Development

### Adding a New Provider

1. Create adapter class in `adapters/`
```python
class MyProviderAdapter(TTSAdapter):
    async def initialize(self) -> bool:
        # Load models/setup API
        
    async def generate(self, request: TTSRequest) -> TTSResponse:
        # Generate audio
        
    async def get_capabilities(self) -> TTSCapabilities:
        # Return provider capabilities
```

2. Register in `adapter_registry.py`
```python
TTSProvider.MY_PROVIDER = "my_provider"
DEFAULT_ADAPTERS[TTSProvider.MY_PROVIDER] = MyProviderAdapter
```

3. Add configuration to YAML
```yaml
providers:
  my_provider:
    enabled: true
    # provider-specific settings
```

### Testing

```bash
# Run TTS tests
pytest tests/TTS/ -v

# Test specific provider
pytest tests/TTS/test_adapters.py::test_openai_adapter -v

# Test with coverage
pytest tests/TTS/ --cov=tldw_Server_API.app.core.TTS
```

## Security Considerations

### Voice Cloning Ethics
- Only clone voices with explicit consent
- Add watermarking when available (Chatterbox)
- Implement usage logging for audit trails
- Consider rate limiting voice cloning requests

### API Security
- Always use authentication in production
- Validate and sanitize all inputs
- Limit file upload sizes
- Use HTTPS for API endpoints
- Rotate API keys regularly

## Performance Optimization

### For API Providers
- Use connection pooling
- Implement response caching
- Batch requests when possible

### For Local Models
- Use GPU acceleration (CUDA)
- Enable mixed precision (FP16/BF16)
- Pre-load models at startup
- Use ONNX runtime for CPU inference

### Voice Cloning
- Cache processed voice references
- Limit reference audio duration
- Use efficient audio formats (WAV)
- Consider CPU/GPU memory limits

## License

The TTS module follows the main project's license:
- GNU General Public License v2.0

Individual model licenses:
- Kokoro: Apache 2.0
- Higgs: Custom research license
- Chatterbox: MIT
- VibeVoice: Microsoft research license

## Support

For issues or questions:
1. Check the [troubleshooting guide](#troubleshooting)
2. Review [API documentation](http://localhost:8000/docs)
3. Check logs in `logs/tldw_server.log`
4. Report issues with full error messages

---

*Last Updated: 2025-08-31*
*Version: 2.0.0*
