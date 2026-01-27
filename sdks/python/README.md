# tldw Voice Assistant SDK (Python)

Python SDK for connecting to tldw_server voice assistant with real-time audio streaming support.

## Installation

```bash
# Basic installation
pip install tldw-voice-assistant

# With audio support (sounddevice, numpy)
pip install tldw-voice-assistant[audio]

# With Porcupine wake word support
pip install tldw-voice-assistant[wakeword]

# With OpenWakeWord support (open source)
pip install tldw-voice-assistant[openwakeword]

# All features
pip install tldw-voice-assistant[audio,wakeword,openwakeword]
```

## Quick Start

### Basic Text Commands

```python
import asyncio
from tldw_voice_assistant import VoiceAssistantClient, VoiceAssistantConfig

async def main():
    config = VoiceAssistantConfig(
        ws_url="ws://localhost:8000/api/v1/voice/assistant",
        token="your-api-key",
    )

    client = VoiceAssistantClient(config)

    @client.on_action_result
    def on_result(result):
        print(f"Response: {result.response_text}")

    async with client:
        await client.send_text("search for machine learning")
        await asyncio.sleep(3)  # Wait for response

asyncio.run(main())
```

### Audio Streaming

```python
import asyncio
from tldw_voice_assistant import VoiceAssistantClient, VoiceAssistantConfig
from tldw_voice_assistant.audio import AudioCapture, AudioPlayer

async def main():
    config = VoiceAssistantConfig(
        ws_url="ws://localhost:8000/api/v1/voice/assistant",
        token="your-api-key",
    )

    client = VoiceAssistantClient(config)
    capture = AudioCapture(sample_rate=16000)
    player = AudioPlayer()

    # Handle TTS playback
    @client.on_tts_chunk
    def on_tts(chunk):
        player.add_chunk(chunk.data, format=chunk.format)

    @client.on_action_result
    def on_result(result):
        print(f"Response: {result.response_text}")

    # Stream audio to server
    @capture.on_data
    def on_audio(audio):
        if client.is_connected:
            asyncio.create_task(client.send_audio(audio))

    async with client:
        capture.start()
        print("Speak now... (Ctrl+C to stop)")

        try:
            await asyncio.sleep(10)  # Record for 10 seconds
        finally:
            capture.stop()
            await client.commit()  # Signal end of speech
            await asyncio.sleep(3)  # Wait for response

asyncio.run(main())
```

### Wake Word Detection

```python
import asyncio
import numpy as np
import openwakeword
from openwakeword.model import Model

from tldw_voice_assistant import VoiceAssistantClient, VoiceAssistantConfig
from tldw_voice_assistant.audio import AudioCapture

async def main():
    # Initialize wake word model
    openwakeword.utils.download_models()
    oww_model = Model()

    config = VoiceAssistantConfig(
        ws_url="ws://localhost:8000/api/v1/voice/assistant",
        token="your-api-key",
    )

    client = VoiceAssistantClient(config)
    capture = AudioCapture(sample_rate=16000)

    is_listening = False

    @capture.on_data
    def on_audio(audio):
        nonlocal is_listening

        if not is_listening:
            # Check for wake word
            predictions = oww_model.predict(audio)
            for scores in predictions.values():
                if any(s > 0.5 for s in scores):
                    print("Wake word detected!")
                    is_listening = True
                    break
        else:
            # Stream to server
            asyncio.create_task(client.send_audio(audio))

    async with client:
        capture.start()
        print("Listening for wake word...")

        try:
            while True:
                await asyncio.sleep(1)
        finally:
            capture.stop()

asyncio.run(main())
```

## API Reference

### VoiceAssistantConfig

```python
@dataclass
class VoiceAssistantConfig:
    ws_url: str              # WebSocket URL
    token: str               # Auth token (JWT or API key)
    stt_model: str = "parakeet"      # STT model
    stt_language: str = None         # Language code
    tts_provider: str = "kokoro"     # TTS provider
    tts_voice: str = "af_heart"      # TTS voice
    tts_format: str = "mp3"          # Audio format
    sample_rate: int = 16000         # Sample rate
    session_id: str = None           # Resume session
    auto_reconnect: bool = True      # Auto-reconnect
    max_reconnect_attempts: int = 5  # Max retries
    reconnect_delay: float = 1.0     # Reconnect delay
    debug: bool = False              # Debug logging
```

### VoiceAssistantClient

#### Methods

| Method | Description |
|--------|-------------|
| `connect()` | Connect to the server |
| `disconnect()` | Disconnect from the server |
| `send_audio(data)` | Send audio data (bytes or numpy array) |
| `commit()` | Signal end of utterance |
| `cancel()` | Cancel current operation |
| `send_text(text)` | Send text command |
| `subscribe_to_workflow(run_id)` | Subscribe to workflow |
| `cancel_workflow(run_id)` | Cancel workflow |

#### Event Decorators

| Decorator | Callback Signature |
|-----------|-------------------|
| `@on_connected` | `() -> None` |
| `@on_disconnected` | `(reason: str) -> None` |
| `@on_transcription` | `(result: TranscriptionResult) -> None` |
| `@on_intent` | `(result: IntentResult) -> None` |
| `@on_action_result` | `(result: ActionResult) -> None` |
| `@on_tts_chunk` | `(chunk: TTSChunk) -> None` |
| `@on_tts_end` | `() -> None` |
| `@on_state_change` | `(state, previous) -> None` |
| `@on_error` | `(error: VoiceError) -> None` |
| `@on_workflow_progress` | `(progress: WorkflowProgress) -> None` |
| `@on_workflow_complete` | `(complete: WorkflowComplete) -> None` |

### AudioCapture

```python
capture = AudioCapture(
    sample_rate=16000,
    channels=1,
    blocksize=4096,
    device=None,  # Use default
)

@capture.on_data
def on_audio(audio: np.ndarray):
    # Float32 audio samples
    pass

@capture.on_level
def on_level(level: float):
    # Audio level (0.0 - 1.0)
    pass

capture.start()
# ... later
capture.stop()

# List available devices
devices = AudioCapture.list_devices()
```

### AudioPlayer

```python
player = AudioPlayer(
    sample_rate=22050,
    device=None,  # Use default
)

@player.on_start
def on_start():
    print("Started playing")

@player.on_end
def on_end():
    print("Finished playing")

# Add streaming chunks
player.add_chunk(audio_bytes, format="mp3")

# Or play complete audio
player.play(audio_bytes, format="mp3", blocking=True)

# Volume control
player.set_volume(0.8)

player.stop()
```

## Raspberry Pi Setup

For optimal performance on Raspberry Pi:

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install python3-pip portaudio19-dev

# Install SDK with audio support
pip3 install tldw-voice-assistant[audio,openwakeword]
```

### Example systemd service

Create `/etc/systemd/system/voice-assistant.service`:

```ini
[Unit]
Description=tldw Voice Assistant
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
ExecStart=/usr/bin/python3 -m tldw_voice_assistant.examples.wake_word \
    --url ws://your-server:8000/api/v1/voice/assistant \
    --token YOUR_API_KEY \
    --engine openwakeword
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable voice-assistant
sudo systemctl start voice-assistant
```

## Wake Word Options

### Porcupine (Proprietary, Free Tier Available)

- Better accuracy
- Multiple languages
- Requires access key from [Picovoice Console](https://console.picovoice.ai/)

```bash
pip install pvporcupine
```

### OpenWakeWord (Open Source)

- Free and open source
- Good accuracy
- English only (currently)

```bash
pip install openwakeword
```

## Requirements

- Python 3.9+
- websockets
- For audio: sounddevice, numpy
- For wake word: pvporcupine or openwakeword

## License

MIT
