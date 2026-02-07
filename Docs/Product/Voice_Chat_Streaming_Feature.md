# Voice Chat Streaming Feature Guide

End-to-end, low-latency voice chat over WebSocket: partial STT + streaming LLM deltas + streaming TTS audio. This guide covers what works today, how to enable it, and how to add more actions/tools.

## Capabilities
- `/api/v1/audio/chat/stream` WebSocket endpoint: send PCM base64 audio frames, receive partials/finals, LLM deltas, and streamed TTS bytes (mp3/opus/pcm). Auto-commit via Silero VAD is supported.
- LLM streaming via SSE parsing; deltas + final message delivered with usage + finish_reason.
- TTS streaming with backpressure and underrun/error counters; `voice_to_voice_seconds` records end-to-end latency.
- Action/tool execution (MCP modules) when hinted; results emitted as `action_result` and included in the assistant summary frame.
- Metrics: `stt_final_latency_seconds{endpoint="audio.chat.stream"}`, `voice_to_voice_seconds{route="audio.chat.stream"}`, `audio_stream_underruns_total`, `audio_stream_errors_total`, plus provider metrics.
- Quotas/limits: daily minutes + concurrent stream guard reuse `/audio/stream/transcribe` policies; configurable close code (`AUDIO_WS_QUOTA_CLOSE_1008`).

## Prereqs & Setup
1. Install deps: `pip install -e .[dev]` (ffmpeg required for audio).
2. Auth: set API key or JWT; WS auth follows `_audio_ws_authenticate`.
3. Enable actions (optional):
   - `AUDIO_CHAT_ENABLE_ACTIONS=1`
   - `AUDIO_CHAT_ALLOWED_ACTIONS=tool1,tool2` (optional allowlist)
4. TTS/STT defaults (optional):
   - `AUDIO_CHAT_DEFAULT_LLM_MODEL` for LLM
   - VAD: `AUDIO_WS_IDLE_TIMEOUT_S`, `AUDIO_WS_QUOTA_CLOSE_1008` for policy tuning
5. Start server: `python -m uvicorn tldw_Server_API.app.main:app --reload`

### .env example
```
AUTH_MODE=single_user
SINGLE_USER_API_KEY=sk-your-key
OPENAI_API_KEY=sk-openai
ANTHROPIC_API_KEY=sk-anthropic
AUDIO_CHAT_ENABLE_ACTIONS=1
AUDIO_CHAT_ALLOWED_ACTIONS=tool1,tool2
AUDIO_CHAT_DEFAULT_LLM_MODEL=gpt-4o-mini
AUDIO_WS_IDLE_TIMEOUT_S=120
AUDIO_WS_QUOTA_CLOSE_1008=1
```

### config.txt snippet (legacy support)
```
[OPENAI]
api_key = sk-openai
default_model = gpt-4o-mini

[AUDIO]
audio_chat_default_llm_model = gpt-4o-mini
audio_ws_idle_timeout_s = 120
audio_ws_quota_close_1008 = 1

[ACTIONS]
audio_chat_enable_actions = 1
audio_chat_allowed_actions = tool1,tool2
```

### Docker Compose note
- Add envs above to your service section:
```
  tldw:
    image: tldw_server:latest
    environment:
      - AUTH_MODE=single_user
      - SINGLE_USER_API_KEY=sk-your-key
      - OPENAI_API_KEY=sk-openai
      - AUDIO_CHAT_ENABLE_ACTIONS=1
      - AUDIO_CHAT_ALLOWED_ACTIONS=tool1,tool2
      - AUDIO_CHAT_DEFAULT_LLM_MODEL=gpt-4o-mini
      - AUDIO_WS_IDLE_TIMEOUT_S=120
      - AUDIO_WS_QUOTA_CLOSE_1008=1
    ports:
      - "8000:8000"
```

## Using the WS Protocol
- Connect to `ws://<host>/api/v1/audio/chat/stream`.
- First frame (required): `{"type":"config","stt":{...},"llm":{...},"tts":{...},"session_id":"optional","metadata":{"action":"my_tool"}}`
- Send audio frames: `{"type":"audio","data":"<base64 PCM 16k mono>"}` (multiple frames).
- Commit turn: `{"type":"commit"}` (or rely on VAD auto-commit).
- Stop session: `{"type":"stop"}` to close cleanly.
- Client handling:
  - JSON frames: `partial`, `full_transcript`, `llm_delta`, `llm_message`, `assistant_summary`, `tts_start`, `tts_done`, `action_result`, `warning`, `error`.
  - Binary frames: TTS audio chunks.
- See `Docs/Audio_Streaming_Protocol.md` for full frame catalog and error/limit semantics.

## Add More Actions/Tools
1. Implement a tool in an MCP module (see `tldw_Server_API/app/core/MCP_unified`); expose it via `execute_tool`.
2. Allowlist (optional): set `AUDIO_CHAT_ALLOWED_ACTIONS=tool_name`.
3. Client hint: include `metadata.action: "tool_name"` in the config frame (or `llm.extra_params.action`).
4. Server behavior:
   - Actions run after the final transcript; result is sent as `action_result` and echoed in `assistant_summary.action`.
   - When WS persistence is enabled, user/assistant/tool turns are also persisted to ChaChaNotes.
5. Logging: action failures are emitted as status payloads; they do not tear down the stream.

## WebUI Consumer
- `apps/tldw-frontend/pages/audio.tsx` has a “Voice Chat (WS)” tab that:
  - Connects to `/audio/chat/stream`
  - Streams mic audio, shows partials/LLM deltas, plays streaming TTS (mp3/opus/pcm)
  - Accepts optional `action` name in the config form and surfaces `action_result`
- Use as reference for other clients.

## Metrics, Quotas, Limits
- Metrics registry provides:
  - `stt_final_latency_seconds{endpoint="audio.chat.stream"}`
  - `voice_to_voice_seconds{route="audio.chat.stream"}`
  - `audio_stream_underruns_total{provider}` / `audio_stream_errors_total{provider}`
- Quotas: daily minutes via `check_daily_minutes_allow` + `add_daily_minutes`; concurrent streams via `can_start_stream`.
- Close code policy: default `4003`, or `1008` when `AUDIO_WS_QUOTA_CLOSE_1008=1`.

## Session Persistence (Stage 4)
- Optional WS persistence can be enabled via either:
  - server env `AUDIO_CHAT_WS_PERSISTENCE=1`, or
  - first config frame metadata: `"metadata": {"persist_history": true}`
- When enabled, the server resolves/creates a ChaChaNotes conversation and emits:
  - `{"type":"session","session_id":"..."}`
- Per committed turn, WS persists:
  - user transcript message
  - assistant text message
  - optional tool/action result message (`sender="tool"`)
- Conversation settings also store WS session context under `audio_chat_ws` (including action hint and metadata).
- Persistence is fail-soft: DB/setup failures emit a warning with `warning_type="persistence_unavailable"` and the stream continues.

## Testing & Verification
- Unit tests: `python -m pytest tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py tldw_Server_API/tests/Audio/test_ws_tts_endpoint.py`
- Manual: use the WebUI tab or a simple client to:
  - Send audio → observe partial/final/LLM deltas
  - Receive streaming TTS audio
  - Trigger `metadata.action` and validate `action_result`
  - Exceed quota in a test env to see `quota_exceeded` frame/close code
- Perf/latency: `Helper_Scripts/voice_latency_harness/run.py --short` (scrapes `voice_to_voice_seconds`).
- Stage 4 regression checks:
  - WS persistence success path (`session` frame + persisted user/assistant/tool turns).
  - WS persistence fail-soft path (warning emitted; stream still completes with TTS audio).

## Staged Implementation Tracker
- Stage 1 (WS Persistence Wiring): Complete
  - Opt-in persistence via env or config metadata.
  - ChaChaNotes session resolution + per-turn writes added.
- Stage 2 (Failure Isolation): Complete
  - Persistence setup/write failures emit `persistence_unavailable` warning and do not stop streaming.
- Stage 3 (Documentation Alignment): Complete
  - Stage 4 behavior and regression checks documented in this guide.
- Stage 4 (Verification And Closeout): Complete
  - Verified with:
    - `python -m pytest -q tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py tldw_Server_API/tests/Audio/test_ws_tts_endpoint.py tldw_Server_API/tests/Audio/test_audio_chat_endpoint.py`
  - Result: all tests passed.

## Troubleshooting
- No TTS audio: check format (`mp3|opus|pcm`) and provider keys; inspect `audio_stream_errors_total`.
- Premature close: inspect quota frames (`quota_exceeded`) and concurrent stream limits.
- VAD not firing: ensure Silero model available; warnings emit `vad_unavailable`.
- Actions not running: verify `AUDIO_CHAT_ENABLE_ACTIONS`, allowlist, and tool registration.
