# STT Module Known Issues (2026-02-07)

Status: Active follow-up list for Stage 5 release readiness.

## Issue Register

| ID | Severity | Issue | Impact | Workaround | Owner | Status | Mitigation Delivered |
|---|---|---|---|---|---|---|---|
| STT-KI-001 | Medium | Stage 1 WS latency evidence is synthetic (stub transcriber/turn detector) | Reported p50 values do not represent production provider latency by themselves | Use live harness runs (`Helper_Scripts/voice_latency_harness/run.py`) plus environment metrics before/after rollout | Core Voice & API Team | Mitigated (pending env evidence) | `Docs/Audio_STT_Module.md` |
| STT-KI-002 | Medium | Audio WS still exposes transitional `error_type` alias in compatibility flows | Long-term protocol cleanup is blocked until client migration completes | Use canonical `code`; keep alias only during migration window | Streaming/Platform | Mitigated (pending alias removal) | `AUDIO_WS_COMPAT_ERROR_TYPE` toggle + `Docs/Product/STT_WS_Error_Type_Deprecation_Plan_20260207.md` |
| STT-KI-003 | Medium | WS TTS queue depth tuning is environment-sensitive | Incorrect queue sizing can increase either underruns or end-user latency | Tune with `AUDIO_TTS_WS_QUEUE_MAXSIZE` (alias `AUDIO_WS_TTS_QUEUE_MAXSIZE`) and follow runbook baseline profiles/validation gates | Ops + Core Voice | Mitigated (pending prod validation) | Updated `Docs/Operations/Audio_Streaming_Backpressure_Runbook.md` |
| STT-KI-004 | Low | Reference fixture profile differs from real multi-speaker noisy audio | Benchmarks may under-report latency/accuracy variance | Use fixture matrix and scheduled refresh cadence for noisy/multi-speaker sets | QA + Core Voice | Mitigated (pending cycle adoption) | `Docs/Product/STT_Fixture_Refresh_Matrix_20260207.md` |
| STT-KI-005 | Low | Provider fallback chain can change quality profile between deployments | Same request may produce different transcript quality when preferred provider unavailable | Apply strict pinning for reproducibility paths; use explicit fallback mode for availability paths | Core Voice & API Team | Mitigated (pending operational adoption) | `Docs/Product/STT_Module_PRD.md` |

## Exit Criteria Per Issue

- STT-KI-001: Closed when at least one non-synthetic benchmark run is attached per promoted environment.
- STT-KI-002: Closed when client compatibility notice is issued and `error_type` alias removal is completed.
- STT-KI-003: Closed when queue-depth defaults are validated against production traffic profile.
- STT-KI-004: Closed when refreshed fixtures are documented and used in periodic validation.
- STT-KI-005: Closed when provider pinning and fallback expectations are documented for operations/support.
