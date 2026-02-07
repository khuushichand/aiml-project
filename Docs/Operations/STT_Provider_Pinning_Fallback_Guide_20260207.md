# STT Provider Pinning & Fallback Guide (2026-02-07)

## Purpose
Reduce transcript quality drift caused by provider fallback variability across environments.

This addresses known issue `STT-KI-005`.

## Operating Modes

### Mode A: Strict Reproducibility (Preferred for eval/regression)
- Pin provider and model explicitly per workflow/request.
- Treat fallback as disabled for reproducibility-sensitive runs.
- Fail fast when pinned provider is unavailable.

### Mode B: Availability-First (Preferred for user-facing uptime)
- Configure an explicit fallback chain.
- Record provider/model used per request in logs/metadata.
- Monitor quality and latency by provider label.

## Recommendations
- Use Mode A for:
  - benchmarks
  - acceptance tests
  - release validation
- Use Mode B for:
  - production user traffic
  - non-blocking ingestion pipelines

## Verification Checklist
- Provider/model labels appear in transcript metadata and metrics.
- Pinned-run artifacts explicitly document provider/model used.
- Fallback events are visible in logs and incident notes.
- Quality regressions are reviewed with provider attribution.

## Incident Handling
If transcript quality shifts after deployment:
1. Confirm whether fallback provider usage increased.
2. Reproduce with strict pinning to isolate provider drift.
3. If drift is confirmed, pin known-good provider/model temporarily.
4. Open follow-up to adjust fallback order or provider health gating.

## Exit Criteria for STT-KI-005
- Pinning vs fallback expectations are documented and operationalized.
- Release validation includes at least one strict-pinned run.
- Support/ops handoff references this guide for drift triage.

