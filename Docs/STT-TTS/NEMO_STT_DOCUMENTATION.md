# Nemo STT (Speech-to-Text) Documentation

## Overview

The tldw_server project includes comprehensive support for NVIDIA Nemo transcription models, providing high-performance speech-to-text capabilities through multiple model variants optimized for different hardware configurations.

## Supported Models

### 1. Parakeet TDT (Time-Domain Transducer)
- **Variants**: Standard (PyTorch), ONNX, MLX (Apple Silicon)
- **Speed**: 15-35x real-time depending on variant
- **Accuracy**: Very good for general transcription
- **Memory**: 1.5-2GB depending on variant
- **Best for**: Fast transcription with good accuracy

### 2. Canary-1B (Multilingual)
- **Languages**: English, Spanish, German, French
- **Speed**: 8-12x real-time
- **Accuracy**: Excellent, especially for multilingual content
- **Memory**: ~4GB
- **Best for**: Multilingual transcription needs

## Installation

### Prerequisites

```bash
# Core dependency
pip install nemo_toolkit[asr]

# For ONNX support
pip install onnxruntime  # or onnxruntime-gpu for CUDA

# For MLX support (Apple Silicon only)
pip install mlx parakeet-mlx

# Additional dependencies
pip install huggingface_hub librosa soundfile
```

### Model Downloads

Models are automatically downloaded on first use and cached locally. You can also pre-download:

```python
from huggingface_hub import snapshot_download

# Download Parakeet ONNX
snapshot_download(
    repo_id="istupakov/parakeet-tdt-0.6b-v3-onnx",
    local_dir="~/.cache/parakeet_onnx"
)
```

## Configuration

### config.txt Settings

```ini
[STT-Settings]
# Default transcription provider
default_transcriber = parakeet
# Options: faster-whisper, parakeet, canary, qwen2audio, external

# Nemo model variant for Parakeet
nemo_model_variant = mlx
# Options: standard (PyTorch), onnx (CPU optimized), mlx (Apple Silicon)

# Device for Nemo models
nemo_device = cpu
# Options: cpu, cuda (if available)

# Model cache directory
nemo_cache_dir = ./models/nemo

# Chunking for long audio (in seconds, 0 to disable)
nemo_chunk_duration = 120

# Overlap between chunks (in seconds)
nemo_overlap_duration = 15
```

## API Usage

### OpenAI-Compatible Endpoint

The Nemo models are accessible through the OpenAI-compatible transcription endpoint:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/api/v1",
    api_key="YOUR_API_TOKEN"
)

# Using Parakeet
with open("audio.wav", "rb") as f:
    transcript = client.audio.transcriptions.create(
        model="parakeet",  # or "canary" for multilingual
        file=f,
        response_format="json"  # Options: json, text, srt, vtt, verbose_json
    )
    print(transcript.text)
```

### Direct Python Usage

```python
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import (
    transcribe_with_parakeet,
    transcribe_with_canary
)

# Parakeet transcription
text = transcribe_with_parakeet(
    audio_data=audio_array,  # numpy array or file path
    sample_rate=16000,
    variant='mlx'  # Choose variant
)

# Canary multilingual transcription
text = transcribe_with_canary(
    audio_data=audio_array,
    sample_rate=16000,
    language='es'  # Specify language
)
```

### Chunked Transcription for Long Audio

For audio files longer than a few minutes, use chunking:

```python
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Parakeet_MLX import (
    transcribe_with_parakeet_mlx
)

def progress_callback(current_chunk, total_chunks):
    print(f"Processing chunk {current_chunk}/{total_chunks}")

result = transcribe_with_parakeet_mlx(
    "long_podcast.mp3",
    chunk_duration=120.0,  # 2-minute chunks
    overlap_duration=15.0,  # 15-second overlap
    chunk_callback=progress_callback
)
```

## Live Transcription

### Basic Live Transcription

```python
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Live_Transcription_Nemo import (
    create_live_transcriber
)

# Start live transcription from microphone
with create_live_transcriber(
    model='parakeet',
    variant='standard',
    mode='vad_based'  # Voice Activity Detection
) as transcriber:
    print("Listening... Press Ctrl+C to stop")
    time.sleep(30)  # Record for 30 seconds
```

### Streaming File Transcription

```python
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Parakeet import (
    ParakeetStreamingTranscriber, StreamingConfig
)

config = StreamingConfig(
    model_variant='onnx',
    chunk_duration=2.0,
    enable_partial=True
)

transcriber = ParakeetStreamingTranscriber(config)
transcriber.initialize()

# Process audio stream
with open("audio_stream.wav", "rb") as f:
    while True:
        chunk = f.read(32000)  # Read 2 seconds at 16kHz
        if not chunk:
            break

        result = transcriber.process_audio_chunk(chunk)
        if result:
            print(f"Partial: {result['text']}")
```

## Performance Comparison

| Model | Provider | Speed (RTF) | Accuracy | Memory | Hardware |
|-------|----------|------------|----------|---------|----------|
| Whisper large-v3 | OpenAI | 2-4x | Best | 10GB | GPU recommended |
| Parakeet standard | Nemo | 15-20x | Very Good | 2GB | CPU/GPU |
| Parakeet ONNX | Nemo | 20-30x | Very Good | 1.5GB | CPU optimized |
| Parakeet MLX | Nemo | 25-35x | Very Good | 1.5GB | Apple Silicon |
| Canary-1B | Nemo | 8-12x | Excellent | 4GB | CPU/GPU |

*RTF = Real-Time Factor (higher is faster)*

## Model Selection Guide

### Choose Parakeet when:
- Speed is critical
- Running on limited hardware
- English-only transcription
- Real-time applications

### Choose Canary when:
- Multilingual support needed
- Higher accuracy required
- Memory is available (4GB+)
- Processing non-English content

### Choose specific variants:
- **Standard**: Best compatibility, CUDA acceleration
- **ONNX**: CPU optimization, deployment flexibility
- **MLX**: Apple Silicon Macs (M1/M2/M3)

## Troubleshooting

### Common Issues

#### 1. Model Download Failures
```python
# Manually set cache directory
import os
os.environ['NEMO_CACHE_DIR'] = '/path/to/cache'
os.environ['HF_HOME'] = '/path/to/huggingface/cache'
```

#### 2. Memory Issues
```python
# Unload models when done
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import (
    unload_nemo_models
)
unload_nemo_models()
```

#### 3. ONNX Runtime Errors
```bash
# For CPU
pip install onnxruntime

# For CUDA 11.x
pip install onnxruntime-gpu

# Verify installation
python -c "import onnxruntime; print(onnxruntime.get_available_providers())"
```

#### 4. MLX Not Available
```bash
# Only works on Apple Silicon Macs
# Check if you have Apple Silicon
python -c "import platform; print(platform.processor())"
# Should show 'arm' for Apple Silicon

# Install MLX
pip install mlx
```

### Performance Optimization

#### 1. Enable GPU Acceleration
```ini
[STT-Settings]
nemo_device = cuda  # If CUDA available
```

#### 2. Optimize Chunk Size
```ini
# Larger chunks = better context but more memory
nemo_chunk_duration = 180  # 3 minutes
nemo_overlap_duration = 20  # More overlap for better accuracy
```

#### 3. Use Appropriate Variant
- CPU-only systems: Use ONNX variant
- NVIDIA GPU: Use standard variant with CUDA
- Apple Silicon: Use MLX variant
- Cloud deployment: ONNX for consistency

## API Examples

### cURL Example
```bash
curl -X POST http://localhost:8000/api/v1/audio/transcriptions \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -F "file=@audio.mp3" \
  -F "model=parakeet" \
  -F "response_format=json"
```

### Python Requests
```python
import requests

with open("audio.wav", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/v1/audio/transcriptions",
        headers={"Authorization": "Bearer YOUR_API_TOKEN"},
        files={"file": f},
        data={
            "model": "canary",
            "language": "es",
            "response_format": "srt"
        }
    )
    print(response.json())
```

### JavaScript/Node.js
```javascript
const FormData = require('form-data');
const fs = require('fs');

const form = new FormData();
form.append('file', fs.createReadStream('audio.wav'));
form.append('model', 'parakeet');
form.append('response_format', 'vtt');

fetch('http://localhost:8000/api/v1/audio/transcriptions', {
    method: 'POST',
    headers: {
        'Authorization': 'Bearer YOUR_API_TOKEN',
        ...form.getHeaders()
    },
    body: form
})
.then(res => res.json())
.then(data => console.log(data));
```

## Advanced Usage

### Custom Processing Pipeline

```python
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import (
    Audio_Transcription_Nemo as nemo_stt,
    Audio_Transcription_Parakeet_ONNX as onnx_stt
)

class CustomTranscriptionPipeline:
    def __init__(self, primary_model='parakeet', fallback_model='whisper'):
        self.primary = primary_model
        self.fallback = fallback_model

    def transcribe(self, audio_path):
        try:
            # Try primary model
            if self.primary == 'parakeet':
                return onnx_stt.transcribe_with_parakeet_onnx(audio_path)
            elif self.primary == 'canary':
                return nemo_stt.transcribe_with_canary(audio_path)
        except Exception as e:
            print(f"Primary model failed: {e}")
            # Fallback to whisper
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (
                speech_to_text
            )
            segments = speech_to_text(audio_path, whisper_model='base')
            return ' '.join([s['text'] for s in segments])

# Use custom pipeline
pipeline = CustomTranscriptionPipeline()
text = pipeline.transcribe("audio.wav")
```

### Batch Processing

```python
import concurrent.futures
from pathlib import Path

def process_audio_file(file_path):
    """Process single audio file"""
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import (
        transcribe_with_parakeet
    )

    try:
        text = transcribe_with_parakeet(str(file_path), variant='onnx')
        output_path = file_path.with_suffix('.txt')
        output_path.write_text(text)
        return f"Success: {file_path.name}"
    except Exception as e:
        return f"Failed: {file_path.name} - {e}"

# Process multiple files in parallel
audio_dir = Path("audio_files")
audio_files = list(audio_dir.glob("*.wav"))

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    results = executor.map(process_audio_file, audio_files)
    for result in results:
        print(result)
```

## Limitations and Known Issues

### Current Limitations
1. **No WebSocket endpoint** - Streaming via WebSocket not yet implemented in API
2. **Canary model** - Requires manual model download for some configurations
3. **Language detection** - Not automatic, must specify language for Canary
4. **Diarization** - Speaker separation not integrated with Nemo models
5. **Custom vocabulary** - Not supported in current implementation

### Known Issues
1. **ONNX conversion** - Some Parakeet models require manual ONNX conversion
2. **Memory leaks** - Long-running processes should periodically unload models
3. **MLX compatibility** - Only works on Apple Silicon Macs
4. **Batch size** - Currently processes one file at a time

## Future Enhancements

### Planned Features
- [ ] WebSocket endpoint for real-time streaming
- [ ] Automatic language detection for Canary
- [ ] Speaker diarization integration
- [ ] Custom vocabulary support
- [ ] Batch processing API
- [ ] Model quantization options
- [ ] Fine-tuning interface

## Support and Resources

### Official Documentation
- [NVIDIA Nemo ASR](https://docs.nvidia.com/nemo/user-guide/docs/en/stable/asr/intro.html)
- [Parakeet Model Card](https://huggingface.co/nvidia/parakeet-tdt-1.1b)
- [Canary Model Card](https://huggingface.co/nvidia/canary-1b)

### Community Resources
- [tldw_server GitHub](https://github.com/tldw/tldw_server)
- [Nemo GitHub](https://github.com/NVIDIA/NeMo)
- [MLX Documentation](https://ml-explore.github.io/mlx/)

### Getting Help
1. Check this documentation
2. Review troubleshooting section
3. Search existing issues on GitHub
4. Create a new issue with:
   - System information
   - Configuration settings
   - Error messages
   - Steps to reproduce

---

*Last Updated: 2025-01-06*
*Version: 1.0.0*
