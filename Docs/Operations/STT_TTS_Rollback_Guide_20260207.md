# STT/TTS/WS Rollback Guide (2026-02-07)

## Purpose
Provide a single rollback playbook for STT/WS/TTS changes introduced across the STT module staged roadmap.

Related references:
- `Docs/Operations/Env_Vars.md`
- `Docs/Audio_Streaming_Protocol.md`
- `Docs/Operations/Audio_Streaming_Backpressure_Runbook.md`
- `Docs/Product/STT_Module_Known_Issues_20260207.md`

## Rollback Triggers
Initiate rollback when one or more conditions hold for a sustained window (for example 10-15 minutes):
- WS transcript latency or WS TTS latency is materially above baseline and affecting user experience.
- `audio_stream_errors_total` or `audio_stream_underruns_total` rises sharply after a deployment.
- Quota/policy closes spike unexpectedly (4003 or 1008).
- Critical client compatibility regressions appear on audio WS endpoints.

## Rollback Levels

### Level 1 - Streaming Framework Rollback (Fastest)
Use when regressions correlate to unified streaming behavior.

1. Set `STREAMS_UNIFIED=0`.
2. Restart API workers (or recreate containers).
3. Verify:
   - Audio WS endpoint behavior is restored to legacy streaming path.
   - Error/latency metrics begin returning toward baseline.

Notes:
- This is the primary fast rollback knob documented in `Docs/Operations/Env_Vars.md`.

### Level 2 - Audio WS Policy/Pressure Stabilization
Use when failures are quota-close-code or queue/backpressure related.

1. Restore prior values for:
   - `AUDIO_TTS_WS_QUEUE_MAXSIZE` (or `AUDIO_WS_TTS_QUEUE_MAXSIZE`)
   - `AUDIO_WS_IDLE_TIMEOUT_S` / `STREAM_IDLE_TIMEOUT_S`
   - `AUDIO_WS_QUOTA_CLOSE_1008`
2. Restart API workers.
3. Verify:
   - Quota close code behavior matches expected client handling.
   - Underrun/error rates return near baseline.
   - No active-stream leak after forced disconnect tests.

### Level 3 - Route-Level TTS Streaming Rollback
Use when WS TTS endpoints are unstable but STT and REST TTS remain healthy.

1. Temporarily disable external exposure of:
   - `/api/v1/audio/stream/tts`
   - `/api/v1/audio/stream/tts/realtime`
   (use gateway/ingress routing controls).
2. Route clients to REST fallback:
   - `POST /api/v1/audio/speech`
3. Verify:
   - Client failures are resolved.
   - REST TTS latency and error rates remain within acceptable bounds.

### Level 4 - STT Streaming Degradation Path
Use when WS STT is unstable but file-based STT is healthy.

1. Temporarily disable client use of `/api/v1/audio/stream/transcribe` at gateway/ingress.
2. Route clients to file-based fallback:
   - `POST /api/v1/audio/transcriptions`
3. Keep minute/quota accounting checks active for migrated flows.
4. Verify:
   - Transcription completion rate recovers.
   - Support volume drops for live-stream failures.

## Validation Checklist (Post-Rollback)
- Health endpoints and startup logs show expected config values.
- Audio WS smoke test passes for enabled endpoints.
- One REST STT call and one REST TTS call succeed.
- Key metrics trend toward pre-regression baseline:
  - `stt_final_latency_seconds`
  - `tts_ttfb_seconds`
  - `voice_to_voice_seconds`
  - `audio_stream_errors_total`
  - `audio_stream_underruns_total`

## Communication Checklist
- Open incident note with rollback level and timestamp.
- Record changed env vars/route toggles and restart scope.
- Post customer-facing status update when behavior changes (for example WS to REST fallback).
- Link follow-up work item in known issues list before closing incident.

