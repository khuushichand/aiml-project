# TTS Provider Setup Guide

This guide explains how to set up each TTS provider, especially the local models like Higgs, Kokoro, and VibeVoice.

## Table of Contents
- [Commercial Providers](#commercial-providers)
- [Local Model Providers](#local-model-providers)
- [Voice Cloning Setup](#voice-cloning-setup)
- [Setup Verification](#setup-verification)

## Commercial Providers

### OpenAI
```bash
# Add to config.txt or environment
OPENAI_API_KEY=your-api-key-here
```

### ElevenLabs
```bash
# Add to config.txt or environment
ELEVENLABS_API_KEY=your-api-key-here
```

## Local Model Providers

### Model Auto-Download Controls

Local providers (Kokoro, Higgs, Dia, Chatterbox, VibeVoice) can auto-download models the first time you use them. You can control this behavior globally or per provider.

Supported configuration sources (highest precedence last):
- YAML: `tts_providers_config.yaml` (per-provider `auto_download` flag)
- config.txt: `[TTS-Settings]` section (global and per-provider toggles)
- Environment variables

Defaults: auto-download is enabled unless overridden.

config.txt example (recommended for self-hosted setups):

```
[TTS-Settings]
# Global toggle for all local providers
auto_download_local_models = false

# Provider-specific overrides (optional)
vibevoice_auto_download = false
kokoro_auto_download = false
dia_auto_download = false
higgs_auto_download = false
chatterbox_auto_download = false
```

YAML example (per provider):

```yaml
providers:
  vibevoice:
    enabled: true
    auto_download: false
    model_path: microsoft/VibeVoice-1.5B  # or a local path
  higgs:
    enabled: true
    auto_download: true
    model_path: bosonai/higgs-audio-v2-generation-3B-base
```

Environment variables (override at runtime):
- Global: `TTS_AUTO_DOWNLOAD=0` (or `1`)
- Per provider: `VIBEVOICE_AUTO_DOWNLOAD`, `KOKORO_AUTO_DOWNLOAD`, `DIA_AUTO_DOWNLOAD`, `HIGGS_AUTO_DOWNLOAD`, `CHATTERBOX_AUTO_DOWNLOAD` (accept `0/1`, `true/false`, `yes/no`, `on/off`).

Behavior when disabled:
- VibeVoice: initialization returns unavailable if models are missing (no download).
- Dia: loads with `local_files_only` and fails fast if not cached.
- Chatterbox: runs in HF offline mode and fails if models are not local.
- Higgs: errors if a remote model path is specified while auto-download is disabled.
- Kokoro: does not auto-download; requires local files regardless of this flag.

Tip (CI/Dev): The test suite sets `TTS_AUTO_DOWNLOAD=0` to avoid network during tests.

### Kokoro Setup

Kokoro is a lightweight, high-quality TTS model that runs locally using ONNX runtime.

#### Installation
```bash
# Install dependencies
pip install onnxruntime kokoro-onnx phonemizer

# For GPU acceleration (optional)
pip install onnxruntime-gpu
```

#### Download Models
```bash
# Create model directory
mkdir -p models/kokoro

# Download ONNX model (Method 1: Using huggingface-cli)
pip install huggingface-hub
huggingface-cli download kokoro-82m kokoro-v0_19.onnx --local-dir models/kokoro/

# Method 2: Direct download
wget https://huggingface.co/kokoro-82m/resolve/main/kokoro-v0_19.onnx -O models/kokoro/kokoro-v0_19.onnx
wget https://huggingface.co/kokoro-82m/resolve/main/voices.json -O models/kokoro/voices.json
```

#### Configuration
```yaml
# In tts_providers_config.yaml
kokoro:
  enabled: true
  use_onnx: true
  model_path: ./models/kokoro/kokoro-v0_19.onnx
  voices_json: ./models/kokoro/voices.json
  device: cpu  # or cuda for GPU
  phonemizer_backend: espeak  # requires espeak-ng installed
```

#### System Requirements
- **Disk Space**: ~800MB for model
- **RAM**: 2GB minimum
- **Optional**: espeak-ng for phonemizer (`sudo apt-get install espeak-ng` on Ubuntu)

### Higgs Audio V2 Setup

Higgs is a powerful 3B parameter model supporting 50+ languages, music generation, and voice cloning.

#### Installation
```bash
# Install dependencies
pip install transformers torch torchaudio accelerate

# For optimized inference
pip install flash-attn --no-build-isolation  # Requires CUDA
```

#### Download Models
```bash
# Method 1: Automatic download (first run)
# The model will auto-download on first use (~3GB)

# Method 2: Pre-download
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "bosonai/higgs-audio-v2-generation-3B-base"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    device_map="auto"
)

# Save locally
model.save_pretrained("./models/higgs")
tokenizer.save_pretrained("./models/higgs")
```

#### Configuration
```yaml
# In tts_providers_config.yaml
higgs:
  enabled: true
  model_path: bosonai/higgs-audio-v2-generation-3B-base  # or ./models/higgs for local
  tokenizer_path: bosonai/higgs-audio-v2-tokenizer
  device: cuda  # Strongly recommended for 3B model
  use_fp16: true  # Reduces memory usage
  batch_size: 1
  # Voice cloning settings
  enable_voice_clone: true
  voice_clone_min_duration: 3.0  # seconds
  voice_clone_max_duration: 10.0  # seconds
```

#### System Requirements
- **Disk Space**: ~6GB for model
- **RAM**: 8GB minimum
- **VRAM**: 6GB+ for GPU inference (recommended)
- **CPU**: Can run on CPU but very slow
- **Voice Cloning**: Supports 3-10 second audio samples at 24kHz

### Chatterbox Setup

Chatterbox features unique emotion exaggeration control and voice cloning from Resemble AI.

#### Installation
```bash
# Install Chatterbox (when available)
pip install chatterbox-tts

# Or from source
git clone https://github.com/resemble-ai/chatterbox
cd chatterbox
pip install -e .
```

#### Download Models
```bash
# Download model
mkdir -p models/chatterbox
huggingface-cli download resemble-ai/chatterbox --local-dir models/chatterbox/
```

#### Configuration
```yaml
# In tts_providers_config.yaml
chatterbox:
  enabled: true
  model_path: ./models/chatterbox  # or resemble-ai/chatterbox
  device: cuda
  use_fp16: true
  enable_watermark: true  # Perth watermarking
  target_latency_ms: 200
  # Voice cloning settings
  enable_voice_clone: true
  voice_clone_min_duration: 5.0  # seconds
  voice_clone_max_duration: 20.0  # seconds
  voice_clone_sample_rate: 24000  # Hz
```

#### System Requirements
- **Disk Space**: ~3GB for model
- **RAM**: 6GB minimum
- **VRAM**: 4GB+ for GPU inference
- **Latency**: Sub-200ms on good GPU
- **Voice Cloning**: Supports 5-20 second audio samples, single speaker

### Dia Setup

Dia specializes in multi-speaker dialogue with nonverbal cues.

#### Installation
```bash
# Install dependencies
pip install transformers torch accelerate

# For dialogue processing
pip install nltk spacy
python -m spacy download en_core_web_sm
```

#### Download Models
```bash
# Download Dia model
mkdir -p models/dia
huggingface-cli download nari-labs/dia --local-dir models/dia/

# Or auto-download on first use
```

#### Configuration
```yaml
# In tts_providers_config.yaml
dia:
  enabled: true
  model_path: nari-labs/dia  # or ./models/dia for local
  device: cuda
  use_safetensors: true
  use_bf16: true  # Better than fp16 for this model
  auto_detect_speakers: true
  max_speakers: 5
```

#### System Requirements
- **Disk Space**: ~3.2GB for model
- **RAM**: 6GB minimum
- **VRAM**: 4GB+ for GPU inference
- **Best for**: Dialogue, conversations, storytelling

### VibeVoice Setup (Community Reference)

VibeVoice generates expressive, long-form, multi-speaker conversational audio with spontaneous background music and voice cloning support.

#### Installation
```bash
# Recommended: Use NVIDIA Deep Learning Container
sudo docker run --privileged --gpus all --rm -it nvcr.io/nvidia/pytorch:24.07-py3

# Install VibeVoice from GitHub (community reference)
git clone https://github.com/vibevoice-community/VibeVoice.git
cd VibeVoice/
pip install -e .
```

#### Models Available
- **VibeVoice-1.5B**: 64K context (~90 min generation)
- **VibeVoice-7B-Preview**: 32K context (~45 min generation)

Models will auto-download from HuggingFace on first use.

#### Test Installation
```bash
# Run Gradio demo for 1.5B model
python demo/gradio_demo.py --model_path microsoft/VibeVoice-1.5B --share

# Run Gradio demo for 7B model
python demo/gradio_demo.py --model_path WestZhang/VibeVoice-Large-pt --share

# File-based inference (single speaker)
python demo/inference_from_file.py \
  --model_path microsoft/VibeVoice-1.5B \
  --txt_path demo/text_examples/1p_abs.txt \
  --speaker_names Alice

# File-based inference (multiple speakers)
python demo/inference_from_file.py \
  --model_path microsoft/VibeVoice-1.5B \
  --txt_path demo/text_examples/2p_music.txt \
  --speaker_names Alice Frank
```

#### Adapter: Speaker Mapping via Config

You can define a default mapping between speakers in the script and voice samples so callers don’t need to pass it on each request. The adapter reads `vibevoice_speakers_to_voices` from its provider config.

- INI (config.txt) example (store JSON as a string):

```ini
[TTS-Settings]
vibevoice_speakers_to_voices = {"1": "en-Alice_woman", "2": "/abs/path/to/frank.wav"}
```

- YAML (tts_providers_config.yaml) example:

```yaml
providers:
  vibevoice:
    enabled: true
    model_path: vibevoice/VibeVoice-1.5B
    speakers_to_voices:
      "1": en-Alice_woman
      "2": /abs/path/to/frank.wav
```

At runtime, a request can still override the defaults by passing `extra_params["speakers_to_voices"]`.

#### Configuration
```yaml
# In tts_providers_config.yaml
vibevoice:
  enabled: true
  vibevoice_variant: "1.5B"  # or "7B"
  model_path: microsoft/VibeVoice-1.5B  # or WestZhang/VibeVoice-Large-pt
  device: cuda  # GPU strongly recommended
  use_fp16: true
  enable_music: true  # Spontaneous background music
  max_speakers: 4
  # Voice cloning settings
  enable_voice_clone: true
  voice_clone_min_duration: 3.0  # seconds
  voice_clone_max_duration: 30.0  # seconds
  voice_clone_sample_rate: 22050  # Hz
```

#### System Requirements
- **Disk Space**: ~3GB (1.5B) or ~14GB (7B)
- **RAM**: 8GB minimum (1.5B), 16GB (7B)
- **VRAM**: 4GB+ (1.5B), 16GB+ (7B)
- **Features**:
  - Long-form generation (up to 90 min)
  - Multi-speaker (up to 4 distinct voices)
  - Spontaneous background music
  - Emergent singing capability
  - Cross-lingual transfer
  - Voice cloning with any duration audio (3-30s recommended)

## Voice Cloning Setup

Voice cloning allows you to synthesize speech using a reference voice from an audio sample. Three providers support this feature: Higgs, Chatterbox, and VibeVoice.

### Preparing Voice Reference Audio

#### Audio Requirements by Provider

| Provider | Min Duration | Max Duration | Sample Rate | Format | Quality Requirements |
|----------|-------------|--------------|-------------|---------|---------------------|
| **Higgs** | 3 seconds | 10 seconds | 24kHz | WAV/MP3/FLAC | Clear speech, single speaker |
| **Chatterbox** | 5 seconds | 20 seconds | 24kHz | WAV/MP3 | No background noise/music |
| **VibeVoice** | 3 seconds | 30 seconds | 22.05kHz | WAV/MP3 | Can handle some background |

#### Preparing Audio Files

1. **Record or Select Clean Audio**:
   - Single speaker only
   - Clear speech without music
   - Minimal background noise
   - Natural speaking pace

2. **Convert Audio Format** (if needed):
```bash
# Convert to WAV with proper sample rate for Higgs/Chatterbox
ffmpeg -i input.mp3 -ar 24000 -ac 1 output.wav

# Convert for VibeVoice
ffmpeg -i input.mp3 -ar 22050 -ac 1 output.wav

# Trim audio to specific duration
ffmpeg -i input.wav -ss 0 -t 10 -ar 24000 output_10s.wav
```

3. **Validate Audio Quality**:
```python
import librosa
import numpy as np

# Load and check audio
audio, sr = librosa.load("voice_sample.wav", sr=None)
duration = len(audio) / sr

print(f"Duration: {duration:.2f} seconds")
print(f"Sample rate: {sr} Hz")
print(f"RMS energy: {np.sqrt(np.mean(audio**2)):.4f}")

# Check if too quiet or too loud
if np.max(np.abs(audio)) < 0.1:
    print("Warning: Audio may be too quiet")
elif np.max(np.abs(audio)) > 0.95:
    print("Warning: Audio may be clipping")
```

### Using Voice Cloning via API

#### Basic Voice Cloning Request

```python
import base64
import requests

# Prepare voice reference
with open("voice_sample.wav", "rb") as f:
    voice_data = base64.b64encode(f.read()).decode()

# Make TTS request with voice cloning
response = requests.post(
    "http://localhost:8000/api/v1/audio/speech",
    headers={"Authorization": "Bearer your-token"},
    json={
        "model": "higgs",  # or "chatterbox", "vibevoice"
        "input": "This text will be spoken in the cloned voice.",
        "voice": "clone",  # Use "clone" to indicate voice cloning
        "voice_reference": voice_data,  # Base64-encoded audio
        "response_format": "mp3"
    }
)

# Save the generated audio
with open("cloned_output.mp3", "wb") as f:
    f.write(response.content)
```

#### Advanced Voice Cloning with Parameters

```python
# Chatterbox with emotion control
response = requests.post(
    "http://localhost:8000/api/v1/audio/speech",
    json={
        "model": "chatterbox",
        "input": "I'm so excited about this feature!",
        "voice": "clone",
        "voice_reference": voice_data,
        "extra_params": {
            "emotion": "excited",
            "emotion_intensity": 1.5,
            "enable_watermark": True  # Add Perth watermark
        }
    }
)

# VibeVoice with vibe control
response = requests.post(
    "http://localhost:8000/api/v1/audio/speech",
    json={
        "model": "vibevoice",
        "input": "This is a professional presentation.",
        "voice": "clone",
        "voice_reference": voice_data,
        "extra_params": {
            "vibe": "professional",
            "vibe_intensity": 1.2,
            "enable_music": False  # Disable background music
        }
    }
)
```

### Voice Cloning via cURL

```bash
# Encode audio file to base64
base64 voice_sample.wav > voice_base64.txt

# Create JSON payload
cat > request.json <<EOF
{
  "model": "higgs",
  "input": "Hello, this is a voice cloning test.",
  "voice": "clone",
  "voice_reference": "$(cat voice_base64.txt)",
  "response_format": "mp3"
}
EOF

# Send request
curl -X POST http://localhost:8000/api/v1/audio/speech \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d @request.json \
  --output cloned.mp3
```

### Voice Cloning Best Practices

1. **Audio Quality**:
   - Use lossless formats when possible (WAV, FLAC)
   - Record in a quiet environment
   - Use a good microphone if recording
   - Normalize audio levels

2. **Speaker Consistency**:
   - Use consistent speaking style in reference
   - Avoid emotional extremes in reference
   - Match the tone you want in output

3. **Performance Optimization**:
   - Cache processed voice references
   - Pre-process audio to correct format
   - Use appropriate model for use case

4. **Ethical Considerations**:
   - Only clone voices with explicit consent
   - Use watermarking when available (Chatterbox)
   - Document voice sources
   - Implement usage logging

### Troubleshooting Voice Cloning

#### Common Issues and Solutions

1. **"Voice reference validation failed"**:
   - Check audio duration (must be within provider limits)
   - Verify audio format and sample rate
   - Ensure single speaker in audio
   - Check for silence or corruption

2. **"Poor voice quality in output"**:
   - Improve reference audio quality
   - Use longer reference (up to max duration)
   - Ensure clear speech in reference
   - Try different provider

3. **"Voice doesn't match reference"**:
   - Some providers better for certain voice types
   - Higgs: Best for multilingual
   - Chatterbox: Best for emotional expression
   - VibeVoice: Best for natural conversation

4. **"Memory error during cloning"**:
   - Reduce batch size in config
   - Enable FP16/BF16 in provider config
   - Use CPU offloading if available
   - Try smaller model variant

### Voice Cloning Configuration

Add to `tts_providers_config.yaml`:

```yaml
voice_cloning:
  # Global settings
  enabled: true
  max_reference_size_mb: 10
  cache_processed_references: true
  cache_ttl_hours: 24

  # Processing settings
  auto_normalize: true
  remove_silence: true
  denoise: false

  # Security settings
  require_consent: true
  log_usage: true
  watermark_when_available: true

# Provider-specific overrides
providers:
  higgs:
    voice_clone_settings:
      min_duration: 3.0
      max_duration: 10.0
      preferred_format: "wav"
      sample_rate: 24000

  chatterbox:
    voice_clone_settings:
      min_duration: 5.0
      max_duration: 20.0
      enable_perth_watermark: true

  vibevoice:
    voice_clone_settings:
      min_duration: 3.0
      max_duration: 30.0
      sample_rate: 22050
      enable_speaker_embeddings: true
```

## Setup Verification

### Test Installation

```python
# test_tts_setup.py
import asyncio
from tldw_Server_API.app.core.TTS.tts_service_v2 import get_tts_service_v2

async def test_providers():
    service = await get_tts_service_v2()

    # Check available providers
    status = service.get_status()
    print(f"Available providers: {status['available']}/{status['total_providers']}")

    # List capabilities
    caps = await service.get_capabilities()
    for provider, cap in caps.items():
        print(f"{provider}: {cap['status']}")
        if cap['status'] == 'available':
            print(f"  - Languages: {cap['languages']}")
            print(f"  - Formats: {cap['formats']}")

# Run test
asyncio.run(test_providers())
```

### Quick Test for Each Provider

```bash
# Test Kokoro
curl -X POST http://localhost:8000/api/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kokoro",
    "input": "Hello from Kokoro local TTS",
    "voice": "af_bella"
  }' --output kokoro_test.mp3

# Test Higgs
curl -X POST http://localhost:8000/api/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "higgs",
    "input": "Hello from Higgs multilingual TTS",
    "voice": "narrator"
  }' --output higgs_test.mp3

# Test Chatterbox with emotion
curl -X POST http://localhost:8000/api/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "chatterbox",
    "input": "I am so excited to test Chatterbox!",
    "voice": "energetic",
    "extra_params": {
      "emotion": "excited",
      "emotion_intensity": 1.5
    }
  }' --output chatterbox_test.mp3

# Test Dia with dialogue
curl -X POST http://localhost:8000/api/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "dia",
    "input": "Alice: Hello Bob! Bob: Hi Alice, how are you? Alice: Great, thanks!",
    "voice": "auto"
  }' --output dia_test.mp3

# Test VibeVoice with vibe control
curl -X POST http://localhost:8000/api/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vibevoice",
    "input": "This is a professional announcement with VibeVoice.",
    "voice": "aurora",
    "extra_params": {
      "vibe": "professional",
      "vibe_intensity": 1.2
    }
  }' --output vibevoice_test.mp3
```

## Performance Optimization

### GPU Acceleration

For best performance with local models:

1. **Install CUDA** (if using NVIDIA GPU):
```bash
# Check CUDA version
nvidia-smi

# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

2. **Use Mixed Precision**:
```yaml
# Enable in config
use_fp16: true  # or use_bf16 for newer GPUs
```

3. **Batch Processing**:
```yaml
# For multiple concurrent requests
batch_size: 4  # Adjust based on VRAM
```

### CPU Optimization

For CPU-only systems:

1. **Use ONNX models** (like Kokoro) when possible
2. **Enable multi-threading**:
```bash
export OMP_NUM_THREADS=4  # Adjust to CPU cores
```
3. **Use INT8 quantization** (if supported):
```yaml
use_int8: true  # Reduces model size and speeds up CPU inference
```

## Troubleshooting

### Common Issues

1. **Out of Memory (OOM)**:
   - Reduce batch size
   - Enable FP16/BF16
   - Use CPU offloading for large models
   - Close other applications

2. **Slow Generation**:
   - Ensure GPU is being used (`nvidia-smi` should show activity)
   - Check if model is using correct device in logs
   - Consider using smaller models or ONNX versions

3. **Model Download Fails**:
   - Check internet connection
   - Verify HuggingFace token if needed
   - Try manual download with wget/curl
   - Check disk space

4. **Audio Quality Issues**:
   - Verify sample rate matches model output
   - Check audio format compatibility
   - Ensure proper audio normalization

### Debug Mode

Enable detailed logging:
```yaml
# In tts_providers_config.yaml
logging:
  level: DEBUG
  include_metrics: true
```

### Health Check

```bash
# Check provider health
curl http://localhost:8000/api/v1/audio/health

# List available providers
curl http://localhost:8000/api/v1/audio/providers
```

## Resource Requirements Summary

| Provider | Model Size | Min RAM | Recommended VRAM | Latency (GPU) | Languages |
|----------|-----------|---------|------------------|---------------|-----------|
| Kokoro | 800MB | 2GB | Optional | ~100ms | EN |
| Higgs | 6GB | 8GB | 6GB+ | ~1s | 50+ |
| Chatterbox | 3GB | 6GB | 4GB+ | ~200ms | EN |
| Dia | 3.2GB | 6GB | 4GB+ | ~500ms | EN |
| VibeVoice | 2GB | 4GB | 3GB+ | ~150ms | 12 |

## Best Practices

1. **Start with Kokoro** for testing - it's lightweight and CPU-friendly
2. **Use GPU for Higgs/Chatterbox/Dia** - CPU inference is very slow
3. **Configure fallback chains** - Commercial → Local for reliability
4. **Monitor memory usage** - Local models can be memory-intensive
5. **Pre-download models** - Avoid download delays on first use
6. **Use circuit breakers** - Prevent cascading failures
7. **Enable metrics** - Track performance and errors

---

*For additional help, check the logs in DEBUG mode or open an issue on GitHub.*
