# Nemo STT Real-time Streaming Transcription Documentation

## Overview

The Nemo STT streaming module provides real-time speech-to-text transcription using NVIDIA's Nemo models through a WebSocket interface. It supports both Parakeet (fast, English) and Canary (multilingual) models with various optimization variants.

## Architecture

### Core Components

1. **Unified Streaming Handler** (`Audio_Streaming_Unified.py`)
   - Abstract base class `BaseStreamingTranscriber` for common functionality
   - `ParakeetStreamingTranscriber` for Parakeet model variants
   - `CanaryStreamingTranscriber` for multilingual transcription
   - `UnifiedStreamingTranscriber` factory for model selection

2. **WebSocket Endpoint** (`/api/v1/audio/stream/transcribe`)
   - Separate WebSocket router to avoid authentication conflicts
   - Token-based authentication via query parameter
   - Real-time bidirectional communication

3. **Model Support**
   - **Parakeet TDT**: Fast English transcription
     - Standard variant (PyTorch)
     - ONNX variant (CPU optimized)
     - MLX variant (Apple Silicon optimized)
   - **Canary-1B**: Multilingual support (English, Spanish, German, French)

## WebSocket API

### Endpoint
```
ws://localhost:8000/api/v1/audio/stream/transcribe?token=YOUR_API_KEY
```

### Authentication
- API key must be provided as query parameter `token`
- In single-user mode, a temporary key is generated at startup (check logs)
- Keys can be stored in browser localStorage for persistence

### Message Protocol

#### Client → Server Messages

1. **Configuration Message** (required first)
```json
{
  "type": "config",
  "model": "parakeet",  // or "canary"
  "variant": "standard", // for parakeet: "standard", "onnx", "mlx"
  "sample_rate": 16000,
  "language": "en",      // for canary: "en", "es", "de", "fr"
  "chunk_duration": 2.0,
  "enable_partial": true
}
```

2. **Audio Data Message**
```json
{
  "type": "audio",
  "data": "base64_encoded_audio_bytes"
}
```
Audio format: Float32 PCM, mono channel

3. **Control Messages**
```json
{"type": "commit"}  // Get full transcript
{"type": "reset"}   // Clear buffer and history
{"type": "stop"}    // Close connection
```

#### Server → Client Messages

1. **Status Messages**
```json
{
  "type": "status",
  "state": "ready",  // or "configured", "reset", "error"
  "model": "parakeet"
}
```

2. **Transcription Results**
```json
{
  "type": "partial",  // or "final"
  "text": "transcribed text",
  "timestamp": 1234567890.123,
  "is_final": false,
  "model": "parakeet-standard"
}
```

3. **Full Transcript**
```json
{
  "type": "full_transcript",
  "text": "complete transcript so far",
  "timestamp": 1234567890.123
}
```

4. **Error Messages**
```json
{
  "type": "error",
  "message": "Error description"
}
```

## Configuration

### Audio Buffer Settings
- `sample_rate`: Audio sample rate (default: 16000 Hz)
- `chunk_duration`: Duration of audio chunks for processing (default: 2.0 seconds)
- `overlap_duration`: Overlap between chunks (default: 0.5 seconds)
- `max_buffer_duration`: Maximum buffer size (default: 30 seconds)

### Streaming Settings
- `enable_partial`: Send partial results during processing
- `partial_interval`: Interval between partial results (default: 0.5 seconds)

## Implementation Details

### NumPy 2.0 Compatibility
The module includes a compatibility layer (`numpy_compat.py`) that patches NumPy 2.0 to work with older Nemo libraries that expect `np.sctypes`.

### JSON Serialization
Transcription results from Nemo models (Hypothesis objects) are automatically converted to strings for JSON serialization.

### Authentication Architecture
- WebSocket endpoints use a separate router to avoid conflicts with HTTP authentication middleware
- Token validation happens after WebSocket upgrade
- CSRF protection is bypassed for WebSocket connections
- See also `Docs/API-related/Audio_Transcription_API.md` for detailed auth flows, quota error frames, and close codes (4401/4403/4003/1008/1011). The `GET /api/v1/audio/stream/limits` endpoint provides per-user minutes remaining and active stream counts.

## Usage Examples

### Python Client Example
```python
import asyncio
import websockets
import json
import base64
import numpy as np

async def stream_audio():
    uri = "ws://localhost:8000/api/v1/audio/stream/transcribe?token=YOUR_API_KEY"

    async with websockets.connect(uri) as websocket:
        # Send configuration
        config = {
            "type": "config",
            "model": "parakeet",
            "variant": "standard",
            "sample_rate": 16000,
            "enable_partial": True
        }
        await websocket.send(json.dumps(config))

        # Wait for ready status
        response = await websocket.recv()
        print(f"Status: {response}")

        # Send audio chunks
        for i in range(10):
            # Generate or read audio data
            audio_data = np.random.randn(16000).astype(np.float32)  # 1 second
            audio_base64 = base64.b64encode(audio_data.tobytes()).decode()

            message = {
                "type": "audio",
                "data": audio_base64
            }
            await websocket.send(json.dumps(message))

            # Check for transcription results
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                data = json.loads(response)
                if data.get("type") in ["partial", "final"]:
                    print(f"Transcription: {data.get('text')}")
            except asyncio.TimeoutError:
                pass

            await asyncio.sleep(1)

        # Get final transcript
        await websocket.send(json.dumps({"type": "commit"}))
        response = await websocket.recv()
        print(f"Final: {response}")

asyncio.run(stream_audio())
```

### JavaScript Client Example
```javascript
class StreamingClient {
    constructor(apiKey) {
        this.apiKey = apiKey;
        this.ws = null;
    }

    async connect() {
        const wsUrl = `ws://localhost:8000/api/v1/audio/stream/transcribe?token=${this.apiKey}`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            // Send configuration
            this.ws.send(JSON.stringify({
                type: 'config',
                model: 'parakeet',
                variant: 'standard',
                sample_rate: 16000,
                enable_partial: true
            }));
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'partial' || data.type === 'final') {
                console.log('Transcription:', data.text);
            }
        };
    }

    sendAudio(audioData) {
        // Convert Float32Array to base64
        const base64 = btoa(String.fromCharCode(...new Uint8Array(audioData.buffer)));
        this.ws.send(JSON.stringify({
            type: 'audio',
            data: base64
        }));
    }
}
```

## WebUI Integration

The WebUI provides a user-friendly interface for streaming transcription:

1. **API Key Management**
   - Input field to enter API key
   - Save to localStorage for persistence
   - Show/hide toggle for security

2. **Model Selection**
   - Choose between Parakeet and Canary
   - Select model variants (ONNX, MLX for Parakeet)
   - Language selection for Canary

3. **Audio Visualization**
   - Real-time frequency spectrum display
   - Volume indicator
   - Recording duration tracker

4. **Transcript Display**
   - Live partial results
   - Final transcriptions
   - Full transcript history

## Performance Considerations

### Recommended Settings
- **Sample Rate**: 16000 Hz (optimal for speech)
- **Chunk Duration**: 2-3 seconds (balance between latency and accuracy)
- **Model Selection**:
  - Use Parakeet for English-only, low-latency requirements
  - Use ONNX variant for CPU-only deployments
  - Use MLX variant on Apple Silicon Macs
  - Use Canary for multilingual support

### Resource Usage
- **Memory**: ~2-4GB for model loading
- **CPU**: Moderate usage for standard variant
- **GPU**: Recommended for best performance (CUDA)
- **Network**: Low bandwidth (~32 kbps for 16kHz mono audio)

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Ensure API key is correct and included in WebSocket URL
   - Check server logs for the generated API key in single-user mode

2. **Connection Failures**
   - Verify server is running on correct port
   - Check CORS settings if connecting from different origin
   - Ensure WebSocket upgrade is allowed by reverse proxy (if used)

3. **No Transcription Output**
   - Verify audio format (Float32, correct sample rate)
   - Check audio volume/quality
   - Ensure model is loaded successfully (check server logs)

4. **NumPy Errors**
   - The numpy_compat.py module should handle NumPy 2.0 issues
   - If errors persist, consider downgrading to NumPy 1.x

### Debug Mode

Enable debug logging in the WebUI to see:
- WebSocket message flow
- Connection state changes
- Raw server responses

## Security Considerations

1. **API Key Protection**
   - Never commit API keys to version control
   - Use environment variables for production deployments
   - Rotate keys regularly

2. **WebSocket Security**
   - Use WSS (WebSocket Secure) in production
   - Implement rate limiting to prevent abuse
   - Validate audio data size to prevent memory exhaustion

3. **CORS Configuration**
   - Configure appropriate CORS headers for production
   - Restrict origins to trusted domains

## Future Enhancements

1. **Planned Features**
   - Voice Activity Detection (VAD)
   - Speaker diarization
   - Custom vocabulary support
   - Punctuation restoration
   - Real-time translation

2. **Performance Improvements**
   - Batched inference for multiple streams
   - Model quantization for reduced memory usage
   - Adaptive bitrate for audio transmission

## API Testing

### Using the Test Client
```bash
# Test with synthetic audio
python test_websocket_client.py \
  --model parakeet \
  --variant standard \
  --duration 5 \
  --token YOUR_API_KEY

# Test with real audio file
python test_websocket_client.py \
  --audio /path/to/audio.wav \
  --token YOUR_API_KEY
```

### Using cURL
```bash
# Note: cURL doesn't natively support WebSocket, use wscat instead
npm install -g wscat

wscat -c "ws://localhost:8000/api/v1/audio/stream/transcribe?token=YOUR_API_KEY"
> {"type": "config", "model": "parakeet", "sample_rate": 16000}
< {"type": "status", "state": "ready", "model": "parakeet"}
```

## License and Credits

- Nemo models are provided by NVIDIA under their respective licenses
- Parakeet and Canary models require acceptance of NVIDIA's model licenses
- This implementation is part of the tldw_server project (GPLv3)

## Support

For issues or questions:
1. Check server logs for detailed error messages
2. Verify all dependencies are installed correctly
3. Ensure models are downloaded and cached properly
4. Report issues with full error logs and configuration details

---

*Last updated: September 2024*
*Module version: 1.0.0*
