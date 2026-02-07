# STT Module Operations & Support Handoff (2026-02-07)

## Scope
This handoff covers production operations and support ownership for:
- `POST /api/v1/audio/transcriptions`
- `WS /api/v1/audio/stream/transcribe`
- `WS /api/v1/audio/stream/tts`
- `WS /api/v1/audio/stream/tts/realtime`
- `POST /api/v1/audio/speech` (fallback path for WS TTS incidents)

## Ownership
- Service owner: Core Voice & API Team
- Streaming/platform owner: Streaming/Platform
- First-response ops: Operations/On-call
- Support escalation: API Support + Core Voice

## Required Runbooks
- `Docs/Operations/STT_TTS_Rollback_Guide_20260207.md`
- `Docs/Operations/Audio_Streaming_Backpressure_Runbook.md`
- `Docs/Audio_Streaming_Protocol.md`
- `Docs/Product/STT_Module_Known_Issues_20260207.md`

## Primary SLO/Symptom Signals
Monitor and alert on:
- `stt_final_latency_seconds`
- `tts_ttfb_seconds`
- `voice_to_voice_seconds`
- `audio_stream_errors_total`
- `audio_stream_underruns_total`
- WS close-code distribution (4003/1008, auth, internal)

Operational symptoms that require response:
- Latency regression relative to established baseline.
- Error bursts on STT or TTS WS sessions.
- Underrun spikes after queue/config changes.
- Rising support tickets for dropped streams or missing finals.

## Triage Flow
1. Confirm incident scope (STT WS, TTS WS, REST fallback, or mixed).
2. Check last deployment/config changes (especially `STREAMS_UNIFIED`, WS queue/timeout/quota toggles).
3. Run endpoint smoke checks for affected and fallback paths.
4. If needed, execute rollback level from `STT_TTS_Rollback_Guide_20260207.md`.
5. Publish status update and open follow-up issue if not already tracked.

## Support Playbook (Common Cases)

### Case A: Clients report quota closes changing behavior
- Confirm `AUDIO_WS_QUOTA_CLOSE_1008` value.
- If unplanned, revert to prior value and restart workers.
- Validate client handling for 4003 vs 1008 close code.

### Case B: Choppy WS TTS playback / dropped chunks
- Inspect `audio_stream_underruns_total`.
- Apply queue-depth tuning steps from backpressure runbook.
- If unresolved, move affected clients to REST TTS temporarily.

### Case C: WS STT missing final transcripts
- Validate commit/turn-detection path in logs.
- Confirm no auth/quota denial pattern.
- If widespread, route users to REST transcriptions while investigating.

## Shift Handoff Template
- Incident/ticket IDs:
- Current endpoint status (STT WS, TTS WS, REST):
- Temporary mitigations in place:
- Env/route toggles changed:
- Next decision checkpoint time:
- Owner for next action:

## Open Follow-ups at Handoff Time
- Known issues are tracked in `Docs/Product/STT_Module_Known_Issues_20260207.md`.
- Any new incident-derived gap should be added there with severity, workaround, and owner.

