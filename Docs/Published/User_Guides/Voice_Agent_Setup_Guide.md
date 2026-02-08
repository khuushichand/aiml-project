# Voice Agent Setup Guide

This guide walks through setting up and testing the built-in voice agent in `tldw_server`.

Voice agent endpoints:
- REST: `POST /api/v1/voice/command`
- WebSocket: `WS /api/v1/voice/assistant`

If you want protocol/reference details, see [Voice Assistant API](../API/Voice_Assistant.md).

## 1) Prerequisites

1. Server is installed and starts successfully.
2. Authentication is configured:
   - Single-user: `AUTH_MODE=single_user` and `SINGLE_USER_API_KEY=<key>`
   - Multi-user: JWT auth configured and working
3. Audio dependencies are installed:
   - FFmpeg
   - At least one TTS provider if you want spoken responses (`include_tts=true`)
   - At least one STT backend if you want audio input over WebSocket
4. Optional for WebSocket smoke tests:
   ```bash
   python -m pip install websockets numpy
   ```

Related setup docs:
- [Authentication Setup](Authentication_Setup.md)
- [TTS Getting Started](TTS_Getting_Started.md)

## 2) Verify Voice Routes Are Enabled

Check whether voice routes are exposed:

```bash
curl -s http://127.0.0.1:8000/openapi.json \
  | jq -r '.paths | keys[]' \
  | grep '^/api/v1/voice'
```

Expected output includes:
- `/api/v1/voice/command`
- `/api/v1/voice/assistant` (WebSocket)

If routes are missing, check route toggles:

1. Ensure `ROUTES_DISABLE` does not include `voice-assistant` or `voice-assistant-ws`.
2. If you run strict route policy, force-enable both:
   ```bash
   export ROUTES_ENABLE="voice-assistant,voice-assistant-ws"
   ```
3. In `tldw_Server_API/Config_Files/config.txt`, add the same keys under `[API-Routes]` if you prefer config-file control.

## 3) REST Smoke Test (Text In, No TTS)

Use this first to verify command routing without requiring TTS output:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/voice/command \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "help",
    "include_tts": false
  }' | jq .
```

Success signals:
- `"success": true`
- non-empty `intent`
- non-empty `action_result.response_text`

## 4) REST Test With Spoken Output (TTS)

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/voice/command \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "what can you do",
    "include_tts": true,
    "tts_provider": "kokoro",
    "tts_voice": "af_heart",
    "tts_format": "mp3"
  }' > /tmp/voice_response.json
```

Decode returned base64 audio:

```bash
python -c 'import base64, json, pathlib; d=json.load(open("/tmp/voice_response.json")); pathlib.Path("voice_reply.mp3").write_bytes(base64.b64decode(d["output_audio"]))'
```

## 5) WebSocket Text Turn (Real-Time)

This tests the real-time session flow without microphone capture.

```python
import asyncio
import json
import os
import websockets

WS_URL = os.getenv("VOICE_WS_URL", "ws://127.0.0.1:8000/api/v1/voice/assistant")
TOKEN = os.getenv("VOICE_TOKEN") or os.getenv("SINGLE_USER_API_KEY")

if not TOKEN:
    raise RuntimeError("Set VOICE_TOKEN or SINGLE_USER_API_KEY")


async def main():
    async with websockets.connect(WS_URL, max_size=None) as ws:
        await ws.send(json.dumps({"type": "auth", "token": TOKEN}))
        print("AUTH:", await ws.recv())

        await ws.send(json.dumps({
            "type": "config",
            "stt_model": "parakeet",
            "tts_provider": "kokoro",
            "tts_voice": "af_heart",
            "tts_format": "mp3",
            "sample_rate": 16000
        }))
        print("CONFIG:", await ws.recv())

        await ws.send(json.dumps({"type": "text", "text": "show commands"}))

        while True:
            msg = json.loads(await ws.recv())
            print(msg)
            if msg.get("type") == "state_change" and msg.get("state") == "idle":
                break


asyncio.run(main())
```

Expected message sequence:
- `auth_ok`
- `config_ack`
- `intent`
- `action_start`
- `action_result`
- `tts_chunk` / `tts_end` (if TTS succeeds)
- `state_change` to `idle`

## 6) WebSocket Audio Turn (WAV File Input, Optional)

The voice WebSocket expects base64-encoded raw PCM `float32` frames for `audio` messages.
The script below reads a mono 16-bit PCM WAV file, converts it to `float32`, streams chunks, and sends `commit`.

```python
import asyncio
import base64
import json
import os
import wave

import numpy as np
import websockets

WS_URL = os.getenv("VOICE_WS_URL", "ws://127.0.0.1:8000/api/v1/voice/assistant")
TOKEN = os.getenv("VOICE_TOKEN") or os.getenv("SINGLE_USER_API_KEY")
WAV_PATH = os.getenv("VOICE_WAV_PATH", "utterance.wav")


def load_wav_as_float32(path):
    with wave.open(path, "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())

    if channels != 1 or sample_width != 2:
        raise ValueError("Use a mono 16-bit PCM WAV file")

    pcm16 = np.frombuffer(raw, dtype=np.int16)
    float32 = pcm16.astype(np.float32) / 32768.0
    return float32, sample_rate


async def main():
    audio, sample_rate = load_wav_as_float32(WAV_PATH)

    async with websockets.connect(WS_URL, max_size=None) as ws:
        await ws.send(json.dumps({"type": "auth", "token": TOKEN}))
        print("AUTH:", await ws.recv())

        await ws.send(json.dumps({
            "type": "config",
            "stt_model": "parakeet",
            "sample_rate": sample_rate,
            "tts_provider": "kokoro",
            "tts_voice": "af_heart",
            "tts_format": "mp3"
        }))
        print("CONFIG:", await ws.recv())

        chunk_samples = int(sample_rate * 0.1)  # 100 ms
        sequence = 0
        for start in range(0, len(audio), chunk_samples):
            sequence += 1
            chunk = audio[start:start + chunk_samples].astype(np.float32).tobytes()
            await ws.send(json.dumps({
                "type": "audio",
                "data": base64.b64encode(chunk).decode("ascii"),
                "sequence": sequence
            }))

        await ws.send(json.dumps({"type": "commit"}))

        while True:
            msg = json.loads(await ws.recv())
            print(msg)
            if msg.get("type") == "state_change" and msg.get("state") == "idle":
                break


asyncio.run(main())
```

## 7) Manage Voice Commands

List active system + user commands:

```bash
curl -sS http://127.0.0.1:8000/api/v1/voice/commands \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" | jq .
```

Create a user-specific command:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/voice/commands \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Summarize latest notes",
    "phrases": ["summarize my latest notes"],
    "action_type": "llm_chat",
    "action_config": {},
    "priority": 40,
    "enabled": true,
    "requires_confirmation": false,
    "description": "Custom note summarizer"
  }' | jq .
```

## 8) Full End-to-End Example (Single Script)

If you want one command that runs a complete flow (custom command setup + REST turn + WebSocket turn + saved audio files), use:

```bash
python3 Helper_Scripts/Examples/voice_agent_full_example.py \
  --base-url http://127.0.0.1:8000 \
  --token "$SINGLE_USER_API_KEY" \
  --custom-command-name "Example Status Command" \
  --custom-phrase "status report now" \
  --custom-action-type llm_chat \
  --custom-system-prompt "You are concise and factual." \
  --rest-text "status report now" \
  --ws-text "show commands" \
  --tts-provider kokoro \
  --tts-voice af_heart \
  --tts-format mp3 \
  --rest-audio-out voice_rest_example.mp3 \
  --ws-audio-out voice_ws_example.mp3
```

What this script does:
1. Checks/creates a user command with your phrase.
2. Calls `POST /api/v1/voice/command` and saves returned audio.
3. Opens `WS /api/v1/voice/assistant`, runs a text turn, and saves streamed TTS audio.

### Where the action is defined

The command action is defined by the script flags and sent directly to:
- `POST /api/v1/voice/commands`

Specifically:
- `--custom-action-type` -> `action_type`
- `--custom-system-prompt` / `--custom-tool-name` / `--custom-workflow-template` / `--custom-custom-action` -> `action_config`
- `--custom-action-config-json` -> merged into `action_config`

For the command above, the created payload is:

```json
{
  "name": "Example Status Command",
  "phrases": ["status report now"],
  "action_type": "llm_chat",
  "action_config": {
    "system_prompt": "You are concise and factual."
  },
  "priority": 40,
  "enabled": true,
  "requires_confirmation": false,
  "description": "Created by voice_agent_full_example.py"
}
```

This command is persisted in the voice command store (`voice_commands`) for your user, so future turns can match it by phrase.

### Action type quick examples

`llm_chat`:

```bash
python3 Helper_Scripts/Examples/voice_agent_full_example.py \
  --token "$SINGLE_USER_API_KEY" \
  --custom-action-type llm_chat \
  --custom-system-prompt "Be concise." \
  --custom-phrase "status report now" \
  --rest-text "status report now"
```

`mcp_tool`:

```bash
python3 Helper_Scripts/Examples/voice_agent_full_example.py \
  --token "$SINGLE_USER_API_KEY" \
  --custom-action-type mcp_tool \
  --custom-tool-name media.search \
  --custom-phrase "search media for" \
  --rest-text "search media for vector reranking"
```

`workflow`:

```bash
python3 Helper_Scripts/Examples/voice_agent_full_example.py \
  --token "$SINGLE_USER_API_KEY" \
  --custom-action-type workflow \
  --custom-workflow-template search_and_summarize \
  --custom-phrase "workflow summarize" \
  --rest-text "workflow summarize retrieval benchmarks"
```

`custom`:

```bash
python3 Helper_Scripts/Examples/voice_agent_full_example.py \
  --token "$SINGLE_USER_API_KEY" \
  --custom-action-type custom \
  --custom-custom-action help \
  --custom-phrase "assistant help now" \
  --rest-text "assistant help now"
```

Expected artifacts:
- `voice_rest_example.mp3`
- `voice_ws_example.mp3`

Notes:
- Install `websockets` first if needed: `python3 -m pip install websockets`
- For JWT mode, pass your JWT with `--token`; the script will automatically send `Authorization: Bearer <token>`.

## 9) Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `404` for `/api/v1/voice/*` | Route disabled by route policy | Enable `voice-assistant` and `voice-assistant-ws`; restart server |
| `auth_error` / WS close `4401` | Invalid API key/JWT | Verify token and auth mode |
| `Could not transcribe audio` | Audio payload is not raw `float32` PCM frames | Convert WAV/int16 to `float32` before base64 |
| `No audio data to process` after `commit` | `commit` sent before audio frames | Send at least one `audio` message before `commit` |
| Missing `output_audio` or TTS errors | TTS provider/voice not configured | Validate TTS provider with `GET /api/v1/audio/voices/catalog`; set `include_tts=false` while debugging |
