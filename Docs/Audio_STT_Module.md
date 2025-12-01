# Audio STT Module Overview

This note captures the current STT streaming defaults, VAD/auto-commit behavior, metrics, and hygiene so contributors can validate latency and avoid regressions while finishing Waves 1–3.

## Streaming STT defaults
- WebSocket endpoint: `/api/v1/audio/stream/transcribe` (unified path used by Parakeet/Whisper/Qwen2Audio adapters).
- VAD/auto-commit (server defaults): `enable_vad=true`, `vad_threshold=0.5`, `min_silence_ms=250`, `turn_stop_secs=0.2`, `min_utterance_secs=0.4`. Clients may request overrides inside the `config` frame, but the server clamps values to safe bounds.
- Behavior: VAD end-of-speech triggers a server-side finalize equivalent to a client `commit`, emitting a single `full_transcript` frame per turn with `auto_commit=true`.

## Fail-open behavior
- If Silero VAD is unavailable or fails to initialize, the server continues streaming without auto-commit and logs a warning once per session (`... continuing without auto-commit`). `auto_commit` will be absent/false in finals in this mode.
- No quotas or auth are relaxed in fail-open mode; only auto-commit is disabled.

## Metrics to watch
- `stt_final_latency_seconds{model,variant,endpoint="audio_unified_ws"}`: end-of-speech → final transcript emit.
- `voice_to_voice_seconds{provider,route}` and `tts_ttfb_seconds{provider,voice,format}` are surfaced when you run the voice harness or `/audio/chat`; include `X-Request-Id` to correlate logs.

## Latency validation (short path)
- Use the WS integration test with synthetic audio + pauses to assert a single `full_transcript` and latency budget.
- For manual checks, stream 10s of 16 kHz mono audio with ~250 ms trailing silence; expect p50 final latency <600 ms on the reference setup (8-core CPU, optional GPU, macOS 14/Ubuntu 22.04).

## Hygiene and limits
- Input validation: enforce MIME/size/duration caps before STT; `/api/v1/audio/chat` accepts JSON+base64 input_audio with format hints and size/duration validation.
- Logging: avoid logging raw audio or full transcripts; use request IDs and provider/model labels instead.
- Retention: store audio only when explicitly enabled; otherwise keep only transcripts and normalized artifacts in Media DB v2.
- Actions: `/audio/chat` can optionally execute an action/workflow (guarded by `AUDIO_CHAT_ENABLE_ACTIONS`) and returns `action_result`; when present, it’s also persisted as a tool message in the conversation.
- Limits & errors for `/audio/chat`: configurable via `AUDIO_CHAT_MAX_BYTES` (default 20MB) and `AUDIO_CHAT_MAX_DURATION_SEC` (default 120s); unsupported formats return 400, oversize returns 413, failed STT/LLM/TTS return structured 5xx. Validation runs before STT to avoid heavy work on bad inputs.
- Metrics: end-to-end `/audio/chat` latency recorded in `audio_chat_latency_seconds{stt_provider,llm_provider,tts_provider}`; STT/TTS/voice-to-voice metrics remain (`stt_final_latency_seconds`, `tts_ttfb_seconds`, `voice_to_voice_seconds`).
- Harness: run `python Helper_Scripts/voice_latency_harness/run.py --out out.json --short` to scrape metrics, or omit `--short` to perform a real `/audio/chat` turn. Provide `--api-key`/`--base-url` if needed. Short mode relies on metrics already emitted by other tests/fixtures.
- WebUI: surface server errors (e.g., oversize/unsupported formats) in the voice chat UI; transcripts and action results are persisted in conversation history for display/playback.
