# Watchlists Recovery Runbook (Group 05)

Date: 2026-02-23
Owners: Robert (Assignee), Mike (Reviewer)
Scope: Sources, Monitors, Runs, Outputs, Templates

## Purpose

Provide repeatable triage and recovery steps for top Watchlists failure classes without requiring backend log analysis as a first step.

## Failure Classes and UI Recovery Paths

| Failure Class | Primary Surface | User Signal | First Recovery Action | Escalation Action |
|---|---|---|---|---|
| Source connectivity failure (DNS/TLS/network/timeout) | Feeds (`SourcesTab`, Source Form) | `Could not test feed preflight`, feed test hint, failed run hint | Run `Test Feed`, verify URL/type, retry while preserving draft values | Open Activity and inspect newest failed run details; lower schedule intensity if repeated |
| Monitor validation failure (scope/schedule/email/json) | Monitor Form (`JobFormModal`) | Inline/remediation error on save | Resolve blocker shown in form (scope, cadence, recipients, voice-map JSON) and retry | Use advanced mode to inspect hidden settings; confirm recurring delivery impacts before save |
| Run execution failure/stall | Activity (`RunsTab`, run notifications) | Reliability attention alert, failed/stalled grouped notifications | Open newest failed run from deep link, inspect remediation panel, retry run | Cancel stalled run, adjust monitor scope/schedule, re-run |
| Output delivery failure (email/chatbook/audio delivery metadata) | Reports (`OutputsTab`) | Delivery tags (`Failed`/`Partial`), live-region delivery change announcements | Filter Reports by delivery status and inspect affected outputs | Regenerate with adjusted template/delivery settings; verify latest run health |
| Undo/restore partial failure after delete | Feeds (`SourcesTab`) / Monitors (`JobsTab`) | Undo snackbar + partial restore error guidance | Retry undo immediately within window; refresh tab and retry | If window expires, recreate from list/export and record failure class in incident log |
| Template authoring failure | Templates (`TemplatesTab`) | Syntax/save errors in editor and save flow | Correct highlighted syntax issues, re-preview, save | Roll back to known-good template/version and regenerate impacted outputs |

## Incident Playbook (Operator Steps)

1. Confirm scope:
   - Count impacted entities (feeds/monitors/runs/outputs).
   - Identify if failure is isolated (single source) or systemic (multiple monitors/runs).
2. Use UI-first diagnostics:
   - Feeds: run `Test Feed` for failing sources.
   - Activity: open newest failed run from deep link.
   - Reports: apply delivery-status filter (`Failed`, `Partial`) to bound impact.
3. Execute lowest-risk recovery:
   - Retry operations that are idempotent (test/retry/regenerate).
   - Avoid destructive edits until a recovery baseline is captured.
4. Validate recovery:
   - Confirm status transition in Activity (failed/stalled -> completed).
   - Confirm delivery status in Reports changes from failed/partial to sent/stored.
5. Escalate when thresholds are exceeded (see Monitoring Checklist).

## QA Scenario Matrix

| Scenario ID | Scenario | Steps | Expected Result |
|---|---|---|---|
| QA-05-01 | Source preflight failure with remediation | Add/edit feed -> inject bad URL/source type -> `Test Feed` | Error + actionable hint + retry action shown |
| QA-05-02 | Monitor schedule validation blocker | Create monitor -> set `* * * * *` cadence -> save | Save blocked with minimum-cadence guidance |
| QA-05-03 | Invalid email recipients blocker | Edit monitor with invalid recipient -> save | Save blocked + invalid recipient remediation |
| QA-05-04 | Single delete undo messaging | Delete one feed | Confirmation and undo messaging explicitly mention undo window |
| QA-05-05 | Bulk delete partial restore | Delete multiple feeds -> force one restore failure in undo path | Partial restore message includes next-step instruction |
| QA-05-06 | Failed/stalled run reliability attention | Seed failed + long-running run | Activity attention alert appears with deep-link actions |
| QA-05-07 | Delivery failure filtering | Seed outputs with `failed`, `partial`, `sent` delivery statuses | Delivery filter narrows table to selected status |
| QA-05-08 | Template save failure | Introduce syntax error in template and save | Save blocked with syntax remediation guidance |

## Monitoring Checklist and Escalation Thresholds

Use these thresholds during release validation and post-release monitoring:

- Run failure rate:
  - Warn: `>= 5%` failed runs over rolling 24h.
  - Escalate: `>= 10%` failed runs over rolling 24h.
- Stalled runs:
  - Warn: `>= 3` stalled runs over rolling 60m.
  - Escalate: any stalled run exceeding 90 minutes.
- Delivery failures (reports/audio):
  - Warn: `>= 3` failed/partial deliveries over rolling 60m.
  - Escalate: `>= 10` failed/partial deliveries over rolling 24h.
- Validation blockers (authoring friction):
  - Warn: repeated same blocker (`scope_required`, `schedule_too_frequent`, `invalid_email_recipients`) > 20 events/day.
  - Escalate: > 50 events/day on one blocker indicates UX/config regression.

## Handoff Checklist

- Confirm all Group 05 automated tests pass in CI.
- Confirm runbook scenario IDs map to QA runs for release.
- Confirm on-call owner acknowledges thresholds and escalation routes.
- Confirm locale keys and remediation copy remain synchronized with UI behavior.
