# STT Non-Synthetic Latency Evidence Runbook (2026-02-07)

## Purpose
Define a consistent process for producing non-synthetic latency evidence for STT/WS/TTS rollout and promotion decisions.

This runbook addresses known issue `STT-KI-001`.

## When Required
Produce evidence for each promoted environment:
- pre-staging promotion
- pre-production promotion
- post-production rollout verification

## Minimum Evidence Set
For each environment, attach:
1. Full-mode harness run artifact (`--short` is not sufficient for closure).
2. Metrics scrape snapshot taken in the same window.
3. Endpoint smoke proof:
   - `WS /api/v1/audio/stream/transcribe`
   - `WS /api/v1/audio/stream/tts` or `WS /api/v1/audio/stream/tts/realtime`
4. Environment metadata (build SHA/version, host class, timestamp, auth mode).

## Commands

### 1) Run full-mode harness
```bash
python Helper_Scripts/voice_latency_harness/run.py \
  --out Docs/Performance/stt_nonsynthetic_<env>_latency_<yyyymmdd>.jsonc \
  --base-url http://127.0.0.1:8000 \
  --api-key "$SINGLE_USER_API_KEY" \
  --runs 5
```

### 2) Capture metrics scrape
```bash
curl -s http://127.0.0.1:8000/metrics \
  > Docs/Performance/stt_nonsynthetic_<env>_metrics_<yyyymmdd>.txt
```

### 3) Validate required metrics exist
Must include:
- `stt_final_latency_seconds`
- `tts_ttfb_seconds`
- `voice_to_voice_seconds`

## Artifact Contract
The harness artifact must contain:
- `run_id`
- `fixture`
- `runs`
- `metrics`
- non-empty p50/p90 values for all three required metrics above

## Evidence Matrix Template

| Environment | Date (UTC) | Harness Artifact | Metrics Snapshot | Owner | Result |
|---|---|---|---|---|---|
| dev | TBD | TBD | TBD | Core Voice & API Team | Pending |
| staging | TBD | TBD | TBD | Core Voice & API Team | Pending |
| production | TBD | TBD | TBD | Core Voice & API Team | Pending |

## Acceptance Gate
Promotion is blocked when any environment lacks a non-synthetic evidence set.

