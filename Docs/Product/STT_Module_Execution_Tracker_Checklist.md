# STT Module - Execution Tracker Checklist

Status: Tracker for the staged roadmap in `Docs/Product/STT_Module_PRD.md` (section: **Staged Implementation Plan (Execution Roadmap)**). Stage 1 is complete (3/3 items complete).

## Stage 1 - M1 Closure: WS Turn Detection Tuning + Compatibility

- [x] Update VAD tuning defaults table in docs (`vad_threshold`, `min_silence_ms`, `turn_stop_secs`) using reference-fixture measurements. (See `Docs/Performance/stt_stage1_vad_reference_fixture_20260207.jsonc`; tuning notes now in `Docs/Audio_STT_Module.md`.)
- [x] Produce and archive M1 evidence artifact (benchmark JSON with `warmup_runs=2`, `measured_runs=20`, p50/p90). (`Docs/Performance/stt_stage1_ws_latency_baseline_20260207.jsonc`)
- [x] Make WS compatibility test suite green in CI (pause/silence, duplicate-final prevention, fail-open path, auth/quota regressions). (Targeted run: `test_ws_vad_turn_detection.py`, `test_ws_quota.py`, `test_ws_quota_compat_and_close.py`, `test_ws_concurrent_streams.py`.)

## Stage 2 - M2 Build: Kokoro Phoneme/Lexicon Overrides

- [ ] Define and commit override config spec (`Config_Files/tts_phonemes.{yaml,json}`) with precedence rules.
- [ ] Wire override loading/validation and adapter application (`request > provider > global`).
- [ ] Add/validate unit and integration test fixtures for boundary/case/overlap behavior and mapped-phrase output changes.
- [ ] Publish user-facing docs for override setup, precedence, and constraints.

## Stage 3 - M3 Build: Optional WS TTS Endpoint

- [ ] Implement `/api/v1/audio/stream/tts` handler with PCM streaming and auth/quota parity.
- [ ] Document WS TTS protocol (frames, errors, close codes) and backpressure semantics.
- [ ] Add operational runbook for queue depth and backpressure tuning.
- [ ] Complete coordinated sign-off with TTS PRD owners.

## Stage 4 - M4 Build: Voice Latency Harness + Docs Refresh

- [ ] Ship harness script(s) (including `--short`) and ensure expected CLI behavior.
- [ ] Add a sample output JSON artifact with required schema (`run_id`, `fixture`, `runs`, `metrics`).
- [ ] Publish execution/readme docs for running and interpreting harness results.
- [ ] Add troubleshooting guidance for common benchmark failures (server unavailable, auth errors, empty metrics).

## Stage 5 - Production Hardening + Release Readiness

- [ ] Produce final release report covering stage acceptance outcomes and residual risks.
- [ ] Publish known-issues list with severity and workaround/owner fields.
- [ ] Document rollback guidance for STT/WS/TTS changes.
- [ ] Complete operations/support handoff notes.
