# VibeVoice TTS Installation Guide

## Overview
This guide covers the installation of the enhanced VibeVoice TTS adapter with all performance improvements.

## Quick Installation

### Basic Installation (Required)
```bash
# Install VibeVoice TTS dependencies
pip install -e ".[TTS_vibevoice]"

# Clone and install VibeVoice library
git clone https://github.com/microsoft/VibeVoice.git libs/VibeVoice
cd libs/VibeVoice && pip install -e .
cd ../..
```

### Performance Enhancements (Recommended)

#### 1. Memory Optimization (4-bit Quantization)
```bash
# For CUDA users
pip install bitsandbytes

# For CPU/MPS users (limited support)
pip install bitsandbytes-cpu  # If available
```

#### 2. Flash Attention (CUDA only)
```bash
# Requires CUDA toolkit installed
pip install flash-attn --no-build-isolation

# Alternative if above fails
pip install ninja
pip install flash-attn
```

#### 3. SageAttention (Optional, when available)
```bash
# Currently not on PyPI, install from source if needed
git clone https://github.com/SageAttention/SageAttention.git
cd SageAttention && pip install -e .
```

## Platform-Specific Instructions

### NVIDIA GPU (CUDA)
```bash
# Full installation with all optimizations
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install -e ".[TTS_vibevoice]"
pip install bitsandbytes
pip install flash-attn --no-build-isolation

# Clone VibeVoice
git clone https://github.com/microsoft/VibeVoice.git libs/VibeVoice
cd libs/VibeVoice && pip install -e .
```

### Apple Silicon (MPS)
```bash
# MPS-optimized installation
pip install torch torchvision torchaudio
pip install -e ".[TTS_vibevoice]"

# Note: Flash Attention not supported on MPS, will use sdpa fallback
# Bitsandbytes has limited MPS support

# Clone VibeVoice
git clone https://github.com/microsoft/VibeVoice.git libs/VibeVoice
cd libs/VibeVoice && pip install -e .
```

### CPU-Only
```bash
# CPU installation
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[TTS_vibevoice]"

# Clone VibeVoice
git clone https://github.com/microsoft/VibeVoice.git libs/VibeVoice
cd libs/VibeVoice && pip install -e .
```

## Configuration

After installation, configure VibeVoice in `config.txt`:

```ini
[TTS-Settings]
# VibeVoice TTS Settings
vibevoice_variant = 1.5B              # Model size: 1.5B or 7B
vibevoice_device = auto                # auto, cuda, mps, or cpu
vibevoice_use_quantization = False     # Enable 4-bit quantization (requires bitsandbytes)
vibevoice_auto_cleanup = True          # Auto cleanup VRAM after generation
vibevoice_auto_download = True         # Auto download models from HuggingFace
vibevoice_attention_type = auto        # auto, flash_attention_2, sdpa, or eager
```

## Verify Installation

Test the installation:

```python
# Test script
from tldw_Server_API.app.core.TTS.adapters.vibevoice_adapter import VibeVoiceAdapter
from tldw_Server_API.app.core.TTS.adapters.base import TTSRequest, AudioFormat

async def test_vibevoice():
    # Initialize adapter
    adapter = VibeVoiceAdapter({
        "vibevoice_variant": "1.5B",
        "vibevoice_use_quantization": True,  # If bitsandbytes installed
        "vibevoice_auto_cleanup": True
    })
    
    # Initialize
    if await adapter.initialize():
        print("✓ VibeVoice initialized successfully")
        
        # Check capabilities
        caps = await adapter.get_capabilities()
        print(f"✓ Provider: {caps.provider_name}")
        print(f"✓ Max context: {caps.max_text_length} tokens")
        
        # Test generation
        request = TTSRequest(
            text="Hello, this is a test of the enhanced VibeVoice system.",
            voice="speaker_1",
            format=AudioFormat.WAV
        )
        
        response = await adapter.generate(request)
        print("✓ Audio generated successfully")
        
        # Check memory usage
        memory = adapter.get_memory_usage()
        print(f"✓ VRAM usage: {memory['current_vram_gb']:.2f} GB")
        if adapter.use_quantization:
            print(f"✓ Quantization savings: {memory['quantization_savings_gb']:.2f} GB")
    else:
        print("✗ Failed to initialize VibeVoice")

# Run test
import asyncio
asyncio.run(test_vibevoice())
```

## Performance Optimization Tips

### 1. Enable Quantization (Recommended for Limited VRAM)
```ini
vibevoice_use_quantization = True  # Saves 36-63% VRAM
```

### 2. Optimize Attention for Your Hardware
- **CUDA**: Will auto-select flash_attention_2 if available
- **MPS**: Will use sdpa (scaled dot-product attention)
- **CPU**: Will use eager attention

### 3. Configure Streaming
```ini
vibevoice_stream_chunk_size = 0.25  # Smaller = lower latency
vibevoice_stream_buffer_size = 4096  # Adjust based on network
```

### 4. Memory Management
```ini
vibevoice_auto_cleanup = True  # Clean VRAM after each generation
```

## Troubleshooting

### Issue: CUDA out of memory
**Solution**: Enable quantization
```ini
vibevoice_use_quantization = True
```

### Issue: Flash Attention installation fails
**Solution**: Install without build isolation
```bash
pip install ninja
pip install flash-attn --no-build-isolation
```

### Issue: Bitsandbytes not working on MPS/CPU
**Solution**: Disable quantization for non-CUDA platforms
```ini
vibevoice_use_quantization = False
```

### Issue: Model download fails
**Solution**: Manually download models
```bash
# Download 1.5B model
huggingface-cli download microsoft/VibeVoice-1.5B --local-dir ./models/vibevoice

# Or download 7B model
huggingface-cli download WestZhang/VibeVoice-Large-pt --local-dir ./models/vibevoice
```

## Voice Cloning Setup

1. Create voices directory:
```bash
mkdir -p ./voices
```

2. Add voice samples (3-10 seconds, WAV/MP3):
```bash
cp your_voice_sample.wav ./voices/custom_voice.wav
```

3. Voice will be auto-detected and available as "custom_voice"

## Memory Requirements

| Model | Original | With Quantization | Savings |
|-------|----------|-------------------|---------|
| 1.5B  | ~3 GB    | ~1.1 GB          | 63%     |
| 7B    | ~14 GB   | ~5 GB            | 64%     |

## Performance Benchmarks

| Configuration | Generation Speed | Quality |
|--------------|------------------|---------|
| CUDA + Flash Attention + Quantization | Fastest | Good |
| CUDA + Flash Attention | Fast | Best |
| MPS + SDPA | Moderate | Best |
| CPU + Eager | Slow | Best |

## Advanced Features

### Multi-Speaker Support
```python
text = "[1]: Hello, I'm speaker one. [2]: And I'm speaker two!"
```

### Zero-Shot Voice Cloning
```python
request = TTSRequest(
    text="Clone this voice",
    voice_reference=voice_audio_bytes,  # 3-10 second sample
    format=AudioFormat.WAV
)
```

### Generation Cancellation
```python
# Start generation
task = asyncio.create_task(adapter.generate(request))

# Cancel if needed
adapter.cancel_generation()
```

## Support

For issues or questions:
1. Check the [main documentation](README.md)
2. Review [Vibe-Voice-Improve-2.md](Vibe-Voice-Improve-2.md) for implementation details
3. Open an issue on GitHub with:
   - Your configuration
   - Error messages
   - Platform details (OS, GPU, Python version)