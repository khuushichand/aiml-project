# Audio Streaming Backpressure Runbook

## Scope
This runbook covers WebSocket audio streaming pressure controls for:
- `WS /api/v1/audio/stream/tts`
- `WS /api/v1/audio/stream/tts/realtime`
- `WS /api/v1/audio/chat/stream` (shared TTS stream helper)

It focuses on queue depth tuning, slow-reader behavior, and quota/close-code behavior.

## Symptoms
- Rising `audio_stream_underruns_total{provider}`.
- Rising `audio_stream_errors_total{component="audio_tts_ws"|...}`.
- Elevated `tts_ttfb_seconds` or increased client-side stutter/drop reports.
- Frequent WS closures with quota/policy codes (`4003` or `1008`).

## Backpressure Model
- Streaming TTS uses a bounded producer/consumer queue.
- On queue overflow:
  - increment `audio_stream_underruns_total`
  - drop oldest queued chunk
  - enqueue the newest chunk (best effort)
- This favors recency and keeps live playback moving under pressure.

## Primary Tuning Knobs
- `AUDIO_TTS_WS_QUEUE_MAXSIZE` (preferred)
- `AUDIO_WS_TTS_QUEUE_MAXSIZE` (fallback alias)
- Behavior:
  - default `8`
  - clamped range `2..256`
  - larger queue reduces drops but increases buffering latency and memory

Related controls:
- `AUDIO_WS_IDLE_TIMEOUT_S` / `STREAM_IDLE_TIMEOUT_S`: idle session timeout.
- `AUDIO_WS_QUOTA_CLOSE_1008`: if enabled, quota closes use `1008` instead of `4003`.
- Audio quota settings (`[Audio-Quota]` / env overrides): govern concurrent stream limits.
- Realtime endpoint:
  - `TTS_REALTIME_AUTO_FLUSH_MS`
  - `TTS_REALTIME_AUTO_FLUSH_TOKENS`

## Tuning Procedure
1. Establish baseline over 15-30 minutes:
   - p50/p90 `tts_ttfb_seconds`
   - `audio_stream_underruns_total` rate
   - `audio_stream_errors_total` rate
2. If underruns are high and latency budget allows it:
   - Increase queue depth in small steps (for example `8 -> 12 -> 16`)
   - Re-test with representative slow-reader and normal-reader traffic
3. If latency regresses:
   - Reduce queue depth
   - Prefer client/network improvements over very large queues
4. If quota closes spike:
   - Validate user tier/concurrency limits and stream release behavior
   - Confirm disconnect cleanup paths are executing (`finish_stream` calls)

## Guardrails
- Avoid queue sizes > `64` unless measured need is clear.
- Treat persistent underruns with low queue depth as a signal to inspect:
  - provider throughput
  - client read cadence
  - network path stability
- Treat persistent underruns with high queue depth as a signal that the consumer path is unhealthy.

## Validation Checklist
- WS TTS happy-path test passes.
- Slow-reader/overflow test increments `audio_stream_underruns_total`.
- Disconnect mid-stream test releases stream slot and closes cleanly.
- No sustained growth in active stream counters after abrupt client exits.

## Rollback
If a tuning change causes regressions:
1. Restore previous queue depth value.
2. Restart API workers.
3. Confirm:
   - underrun/error rates return to baseline
   - p50/p90 `tts_ttfb_seconds` return to baseline

## References
- Protocol details: `Docs/Audio_Streaming_Protocol.md`
- Endpoint implementation: `tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py`
- Shared streaming helper: `tldw_Server_API/app/core/Audio/streaming_service.py`
- WS TTS tests: `tldw_Server_API/tests/Audio/test_ws_tts_endpoint.py`
