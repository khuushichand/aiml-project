# Watchlists UC2 Text+Audio End-to-End Runbook (Group 07 Stage 5)

Date: 2026-02-23  
Owners: Robert (Assignee), Mike (Reviewer)  
Scope: UC2 setup -> run -> text report -> audio briefing task lifecycle

## Purpose

Define a repeatable validation path for UC2 ("10+ sources, scheduled runs, text + audio briefing outputs") and establish reliability metrics for audio enqueue, generation, and fallback behavior.

## Preconditions

- User has at least one active source and one monitor with valid scope.
- Monitor output preferences can include `generate_audio=true`.
- Reports and Activity tabs are available.
- Audio output endpoint is configured (`/api/v1/audio/speech`).

## End-to-End UC2 Scenario (Happy Path)

1. Create monitor:
   - In Monitors, create/edit a monitor with:
     - schedule configured
     - output template selected
     - audio briefing enabled (`generate_audio`)
2. Trigger run:
   - Use `Run Now` or wait for schedule.
3. Generate report output:
   - In Reports, verify new text output appears for run.
4. Validate audio enqueue:
   - Output metadata should include:
     - `audio_briefing_requested=true`
     - `audio_briefing_status=pending`
     - `audio_briefing_task_id=<task id>`
5. Validate consumption:
   - Open preview drawer and confirm provenance/delivery metadata.
   - Download text output.
   - Play/download audio artifact when available for run.

Expected result: A single run yields a text artifact and a pending/fulfilled audio briefing lifecycle with actionable status visibility.

## Reliability Metrics

| Metric ID | Metric | Definition | Source | Target |
|---|---|---|---|---|
| UC2-A1 | Audio enqueue success rate | `pending task_id count / audio requested count` | Outputs metadata + run stats | >= 95% |
| UC2-A2 | Audio enqueue failure rate | `enqueue_failed count / audio requested count` | Outputs metadata (`audio_briefing_status`) | <= 2% |
| UC2-A3 | No-item skip rate | `skipped count / audio requested count` | Outputs metadata (`audio_briefing_status=skipped`) | Track only (informational) |
| UC2-A4 | Audio completion yield | `runs with downloadable audio artifact / runs with pending enqueue` | Run audio endpoint + output artifacts | >= 90% |
| UC2-A5 | Fallback utilization | `single-voice fallback executions / multi-voice attempts` | Scheduler workflow telemetry | 0-20% expected, investigate spikes |

Baseline context from Stage 1 telemetry export:
- UC2-F2 text output success: 0.06% (2/3182 completed runs)
- UC2-F3 audio output success: 0.03% (1/3182 completed runs)

## QA Scenario Matrix

| Scenario ID | Scenario | Steps | Expected Result |
|---|---|---|---|
| UC2-07-01 | Text+audio happy path | Enable audio -> run monitor -> generate output | Output includes `audio_briefing_status=pending` + task id |
| UC2-07-02 | Audio skipped on no ingestable items | Trigger audio with no ingestable run items | Output metadata marks `audio_briefing_status=skipped` |
| UC2-07-03 | Audio enqueue failure path | Force workflow trigger exception | Output metadata marks `audio_briefing_status=enqueue_failed` + error |
| UC2-07-04 | Audio disabled path | Generate output with `generate_audio=false` | No audio briefing metadata/task id persisted |
| UC2-07-05 | Multi-voice fallback | Cause multi-voice step failure in workflow | Fallback single-voice TTS path executes; task still returns artifact or controlled failure signal |

## Automated Verification Commands

Run these to validate UC2 audio integration and fallback behavior:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_api.py -k "generate_audio_payload_triggers_workflow_and_updates_run_stats or generate_audio_false_does_not_trigger_workflow or generate_audio_trigger_returns_none_marks_skipped_metadata or generate_audio_trigger_failure_marks_enqueue_failed_metadata"
python -m pytest -q tldw_Server_API/tests/Watchlists/test_audio_briefing_workflow.py -k "trigger_enqueues_workflow or trigger_skips_when_no_items or trigger_handles_scheduler_failure"
```

UI contract checks used alongside API validation:

```bash
bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputPreviewDrawer.audio.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx
```

## Release Gate

Do not close Group 07 unless all are true:

- API integration tests pass for success + disabled + skipped + enqueue_failed paths.
- Workflow trigger tests pass for enqueue, no-item skip, scheduler failure handling.
- Reports UI exposes delivery issues with direct remediation actions.
- This runbook is attached to Stage 5 closure evidence.
