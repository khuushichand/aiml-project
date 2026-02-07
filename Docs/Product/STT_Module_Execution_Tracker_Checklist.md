# STT Module - Execution Tracker Checklist

Status: Tracker for the staged roadmap in `Docs/Product/STT_Module_PRD.md` (section: **Staged Implementation Plan (Execution Roadmap)**). Stages 1-5 are complete (19/19 items complete).

## Stage 1 - M1 Closure: WS Turn Detection Tuning + Compatibility

- [x] Update VAD tuning defaults table in docs (`vad_threshold`, `min_silence_ms`, `turn_stop_secs`) using reference-fixture measurements. (See `Docs/Performance/stt_stage1_vad_reference_fixture_20260207.jsonc`; tuning notes now in `Docs/Audio_STT_Module.md`.)
- [x] Produce and archive M1 evidence artifact (benchmark JSON with `warmup_runs=2`, `measured_runs=20`, p50/p90). (`Docs/Performance/stt_stage1_ws_latency_baseline_20260207.jsonc`)
- [x] Make WS compatibility test suite green in CI (pause/silence, duplicate-final prevention, fail-open path, auth/quota regressions). (Targeted run: `test_ws_vad_turn_detection.py`, `test_ws_quota.py`, `test_ws_quota_compat_and_close.py`, `test_ws_concurrent_streams.py`.)

## Stage 2 - M2 Build: Kokoro Phoneme/Lexicon Overrides

- [x] Define and commit override config spec (`Config_Files/tts_phonemes.{yaml,json}`) with precedence rules.
- [x] Wire override loading/validation and adapter application (`request > provider > global`).
- [x] Add/validate unit and integration test fixtures for boundary/case/overlap behavior and mapped-phrase output changes.
- [x] Publish user-facing docs for override setup, precedence, and constraints.

## Stage 3 - M3 Build: Optional WS TTS Endpoint

- [x] Implement `/api/v1/audio/stream/tts` handler with PCM streaming and auth/quota parity. (See `tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py`; verified with `tldw_Server_API/tests/Audio/test_ws_tts_endpoint.py` and `tldw_Server_API/tests/Audio/test_ws_tts_realtime_endpoint.py`.)
- [x] Document WS TTS protocol (frames, errors, close codes) and backpressure semantics. (`Docs/Audio_Streaming_Protocol.md`)
- [x] Add operational runbook for queue depth and backpressure tuning. (`Docs/Operations/Audio_Streaming_Backpressure_Runbook.md`)
- [x] Complete coordinated sign-off with TTS PRD owners. (`Docs/Product/STT_TTS_WS_TTS_SIGNOFF_20260207.md`)

## Stage 4 - M4 Build: Voice Latency Harness + Docs Refresh

- [x] Ship harness script(s) (including `--short`) and ensure expected CLI behavior. (`Helper_Scripts/voice_latency_harness/run.py`, validated by `tldw_Server_API/tests/Helper_Scripts/test_voice_latency_harness.py`)
- [x] Add a sample output JSON artifact with required schema (`run_id`, `fixture`, `runs`, `metrics`). (`Docs/Product/stt_stage4_voice_latency_harness_sample_20260207.jsonc`)
- [x] Publish execution/readme docs for running and interpreting harness results. (`Helper_Scripts/voice_latency_harness/README.md`, `Docs/Audio_STT_Module.md`, `Docs/API/Audio_Chat.md`)
- [x] Add troubleshooting guidance for common benchmark failures (server unavailable, auth errors, empty metrics). (`Helper_Scripts/voice_latency_harness/README.md`, `Docs/Audio_STT_Module.md`)

## Stage 5 - Production Hardening + Release Readiness

- [x] Produce final release report covering stage acceptance outcomes and residual risks. (`Docs/Product/STT_Module_Release_Report_20260207.md`)
- [x] Publish known-issues list with severity and workaround/owner fields. (`Docs/Product/STT_Module_Known_Issues_20260207.md`)
- [x] Document rollback guidance for STT/WS/TTS changes. (`Docs/Operations/STT_TTS_Rollback_Guide_20260207.md`)
- [x] Complete operations/support handoff notes. (`Docs/Operations/STT_Module_Ops_Support_Handoff_20260207.md`)
