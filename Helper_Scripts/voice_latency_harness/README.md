# Voice Latency Harness (Stub)

Purpose: quick, reproducible measurements for STT final latency, TTS TTFB, and end‑to‑end voice‑to‑voice on a local reference setup.

Status: minimal stub with TTS TTFB measurement via REST streaming. Extend to WS STT and voice‑to‑voice as VAD lands.

Requirements:
- Python 3.11+
- Optional: `pip install httpx websockets sounddevice`

Usage examples:
- TTS TTFB p50/p90 over 5 runs:
  `python harness.py --mode tts --base http://127.0.0.1:8000 --token YOUR_TOKEN --text "Hello world" --runs 5`

Outputs:
- JSON summary to stdout: includes per‑run timings and p50/p90 for TTFB.

Notes:
- The WS TTS example client is provided under `examples/ws_tts_client.py` (server endpoint optional).
- The PCM client example is provided under `examples/pcm_stream_client.py`.
