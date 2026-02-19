# Implementation Plan: Watchlists H5 - Error Prevention

## Scope

Route/components: `SourceFormModal`, `SourcesTab`, `SchedulePicker`, `GroupsTree`, `JobFormModal`  
Finding IDs: `H5.1` through `H5.5`

## Finding Coverage

- No pre-save source reachability validation: `H5.1`
- Missing dependency warnings before source deletion: `H5.2`
- Unsafe schedule and hierarchy configuration paths: `H5.3`, `H5.4`
- Missing field-level recipient validation: `H5.5`

## Stage 1: Form-Level Preflight Validation
**Goal**: Catch invalid input before submission.
**Success Criteria**:
- Source create/edit flow includes optional/inline "Test Source" preflight.
- Email recipient chips enforce basic email format with clear inline errors.
- Schedule picker warns or blocks high-frequency schedules beyond configured threshold.
**Tests**:
- Unit tests for email and schedule validation helpers.
- Component tests for source test action states (idle/running/success/failure).
- Integration tests for blocked invalid submissions.
**Status**: Complete

## Stage 2: Structural and Dependency Guardrails
**Goal**: Prevent operations that silently break running jobs or group trees.
**Success Criteria**:
- Deleting a source referenced by active jobs prompts with impacted job list.
- Group move/edit flow blocks circular parent relationships.
- Bulk delete path includes dependency summary count before execution.
**Tests**:
- Integration tests for source delete dependency warnings.
- Unit tests for group cycle detection algorithm.
- E2E test for dependency-gated destructive action confirmation.
**Status**: Complete

## Stage 3: Policy and Observability for Prevented Errors
**Goal**: Make prevention behavior transparent and supportable.
**Success Criteria**:
- Validation failures return specific, localized reasons with remediation guidance.
- Prevention events are captured in client telemetry/logging for UX quality tracking.
- Documentation of thresholds (frequency limits, validation rules) is published.
**Tests**:
- Contract tests for structured validation error payloads.
- Logging/telemetry tests for prevention event emission.
- Regression tests for localized message rendering.
**Status**: Complete

## Dependencies

- Source testing uses existing API endpoint (`POST /sources/{id}/test`) or equivalent pre-create probe.
- Dependency checks should share impact query utilities with H3 undo safety prompts.

## Progress Notes

- 2026-02-18: Added schedule-frequency guardrails in `SchedulePicker` and `JobFormModal`, with a minimum allowed cadence of every 5 minutes (`MIN_SCHEDULE_INTERVAL_MINUTES`).
- 2026-02-18: Added recipient validation helpers (`email-utils.ts`) and inline invalid-recipient feedback in `JobFormModal`; submission now blocks while invalid recipients are present.
- 2026-02-18: Added inline "Test Feed" action in `SourceFormModal` for saved feeds, wired to `POST /api/v1/watchlists/sources/{id}/test` via `testWatchlistSource`.
- 2026-02-18: Added source dependency warnings before destructive actions:
  - single-feed delete now lists active monitors directly referencing that feed;
  - bulk delete now includes active-monitor impact summary before confirmation.
- 2026-02-18: Added regression coverage:
  - `JobsTab/__tests__/schedule-frequency.test.ts`
  - `JobsTab/__tests__/email-utils.test.ts`
  - `SourcesTab/__tests__/SourceFormModal.test-source.test.tsx`
  - `SourcesTab/__tests__/source-usage.test.ts`
- 2026-02-18: Verified targeted Watchlists vitest suite passes (9 files, 18 tests).
- 2026-02-18: Added E2E scenario `feed delete warns when active monitors depend on the feed` in `apps/extension/tests/e2e/watchlists.spec.ts`; local execution is currently blocked by extension test harness timeouts in this environment.
- 2026-02-18: Added circular-hierarchy prevention for groups:
  - introduced group edit/reparent flow in `GroupsTree` via `updateWatchlistGroup`;
  - blocked invalid parent choices (self/descendants) in edit mode;
  - added submit-time cycle guard with localized remediation copy (`groups.parentCycleError`).
- 2026-02-18: Added unit coverage for group hierarchy guardrails in `SourcesTab/__tests__/group-hierarchy.test.ts`.
- 2026-02-18: Re-ran Watchlists component suite after hierarchy guard changes (`39` files, `121` tests passing).
- 2026-02-18: Added prevention telemetry utility `watchlists-prevention-telemetry` with local rollups by rule/surface and capped recent events.
- 2026-02-18: Instrumented prevention telemetry emissions at active guardrails:
  - `JobFormModal` scope-required, schedule-too-frequent, invalid-email-recipient blocks.
  - `SchedulePicker` advanced-cron frequency guard block.
  - `GroupsTree` cycle-prevention block on invalid parent assignment.
- 2026-02-18: Added telemetry regression tests in `utils/__tests__/watchlists-prevention-telemetry.test.ts`.
- 2026-02-18: Added `SchedulePicker.help.test.tsx` regression for localized too-frequent guidance plus prevention telemetry emission.
- 2026-02-18: Published threshold/remediation policy in `Docs/Monitoring/WATCHLISTS_ERROR_PREVENTION_POLICY_2026_02_18.md`.
- 2026-02-18: Added backend structured validation payloads (`watchlists_validation_error`) for monitor create/update scope, cadence, and recipient rules, with contract tests in `tldw_Server_API/tests/Watchlists/test_watchlists_api.py`.
- 2026-02-18: Propagated request error `detail` payloads through `bgRequest` and localized server-side remediation copy in `JobFormModal` using message/remediation translation keys.
- 2026-02-18: Added locale entries for `jobs.form.scopeRemediation`, `jobs.form.emailRecipientsRemediation`, and `schedule.tooFrequentRemediation` (assets + extension locale bundle) and regression coverage in `JobFormModal.live-summary.test.tsx`.
