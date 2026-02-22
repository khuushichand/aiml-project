# STT Fixture Refresh Matrix (2026-02-07)

## Purpose
Increase benchmark representativeness beyond the current reference fixture by introducing a repeatable refresh cadence and coverage matrix.

This addresses known issue `STT-KI-004`.

## Refresh Cadence
- Monthly: refresh at least one fixture per category below.
- Release candidate: run full validation on the latest approved matrix set.
- Incident-driven: add/refresh fixtures when production failures expose missing coverage.

## Coverage Matrix

| Fixture ID | Speakers | Noise | Accent/Style | Duration | Primary Use |
|---|---|---|---|---|---|
| FX-CLEAN-SINGLE-EN | 1 | low | neutral English | 10-30s | baseline latency regression checks |
| FX-NOISY-SINGLE-EN | 1 | medium/high | neutral English | 10-30s | robustness under background noise |
| FX-CLEAN-MULTI-EN | 2-3 | low | mixed English accents | 30-90s | diarization and segment boundary checks |
| FX-NOISY-MULTI-MIXED | 2-3 | medium/high | mixed accents/styles | 30-90s | production-like stress fixture |
| FX-LONGFORM-MONOLOGUE | 1 | low/medium | lecture/podcast style | 3-5m | long-form stability and chunking |

## Required Metadata Per Fixture
- source and license
- sample rate / channels / encoding
- speaker count (known or estimated)
- noise profile description
- language/accent tags
- date added and last refreshed date

## Validation Workflow
1. Select fixture set for target environment.
2. Run harness and endpoint smoke checks.
3. Compare against prior baseline for the same fixture family.
4. Record result and owner decision in release notes.

## Exit Criteria for STT-KI-004
- Matrix is documented and in use for periodic validation.
- At least one noisy multi-speaker fixture run is attached in each release cycle.

