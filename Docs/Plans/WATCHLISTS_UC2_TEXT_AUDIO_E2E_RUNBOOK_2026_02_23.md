# Watchlists UC2 Text+Audio End-to-End Runbook (2026-02-23)

## Purpose

Validate the full UC2 path with audio enabled: setup -> run -> report generation -> audio artifact availability.

## Target Scenario

1. Create/confirm a monitor configured for briefing output with `generate_audio` enabled.
2. Trigger a run (run-now or scheduled).
3. Confirm text report output is generated.
4. Confirm audio briefing enqueue/result metadata is present.
5. Validate preview/download paths and fallback semantics for skipped/enqueue-failed audio states.

## Core Reliability Metrics

- `audio_enqueue_success_rate`
- `audio_generation_success_rate`
- `audio_fallback_rate` (`skipped`, `enqueue_failed`)
- `time_to_text_output`
- `time_to_audio_artifact`

## Validation Commands

Backend checks (repo root, venv activated):

```bash
python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_api.py -k "generate_audio_payload_triggers_workflow_and_updates_run_stats or generate_audio_false_does_not_trigger_workflow or generate_audio_trigger_returns_none_marks_skipped_metadata or generate_audio_trigger_failure_marks_enqueue_failed_metadata"
python -m pytest -q tldw_Server_API/tests/Watchlists/test_audio_briefing_workflow.py -k "trigger_enqueues_workflow or trigger_skips_when_no_items or trigger_handles_scheduler_failure"
```

Frontend checks (`apps/packages/ui`):

```bash
bun run test:watchlists:uc2
bun run test:watchlists:onboarding
```

## Failure Handling

- If text output succeeds and audio fails, verify fallback metadata is surfaced and user can regenerate.
- If both fail, route through recovery runbook:
  - `Docs/Plans/WATCHLISTS_RECOVERY_RUNBOOK_2026_02_23.md`

## Release Candidate Evidence

- Command outputs for backend + frontend checks.
- One successful text+audio run trace and one fallback trace.
- Any threshold breaches and remediation ticket links.
