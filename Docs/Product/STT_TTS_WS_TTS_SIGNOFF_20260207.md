# STT/TTS Stage 3 Sign-off Record (WS TTS)

Date: 2026-02-07

## Scope
- `WS /api/v1/audio/stream/tts`
- `WS /api/v1/audio/stream/tts/realtime`
- Shared helper: `tldw_Server_API/app/core/Audio/streaming_service.py`

## Owners
- STT PRD owner group: Core Voice & API Team
- TTS PRD owner group: Core Voice & API Team (TTS maintainers)

## Acceptance Evidence
- Endpoint present and wired with shared auth/quota handling:
  - `tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py`
- Backpressure behavior + underrun metric:
  - `tldw_Server_API/app/core/Audio/streaming_service.py`
- Coverage:
  - `tldw_Server_API/tests/Audio/test_ws_tts_endpoint.py`
  - `tldw_Server_API/tests/Audio/test_ws_tts_realtime_endpoint.py`
- Protocol docs:
  - `Docs/Audio_Streaming_Protocol.md`
- Ops runbook:
  - `Docs/Operations/Audio_Streaming_Backpressure_Runbook.md`

## Decision
Stage 3 WS TTS scope is approved for STT execution tracker closure, with ownership split acknowledged and protocol/ops documentation in place.

## Notes
- Default WS TTS output format remains PCM for low-latency clients.
- Queue-depth tuning is now explicitly controlled via `AUDIO_TTS_WS_QUEUE_MAXSIZE` (alias: `AUDIO_WS_TTS_QUEUE_MAXSIZE`).
