# Implementation Plan: Watchlists HCI Findings Remediation (2026-02-19)

## Context

This plan addresses the implementation gaps identified during plan-vs-code validation of:

- `IMPLEMENTATION_PLAN_watchlists_hci_01_visibility_status_2026_02_18.md`
- `IMPLEMENTATION_PLAN_watchlists_hci_03_user_control_freedom_2026_02_18.md`
- `IMPLEMENTATION_PLAN_watchlists_hci_04_consistency_standards_2026_02_18.md`
- `IMPLEMENTATION_PLAN_watchlists_hci_05_error_prevention_2026_02_18.md`
- `IMPLEMENTATION_PLAN_watchlists_hci_08_aesthetic_minimalism_2026_02_18.md`
- `IMPLEMENTATION_PLAN_watchlists_hci_09_error_recovery_2026_02_18.md`

## Findings Addressed

- `F1`: Undo flow is UX-level recreate, not backend soft-delete contract.
- `F2`: Source undo restore is lossy (`group_ids` not preserved).
- `F3`: Source preflight is unavailable in create flow (saved-only test action).
- `F4`: Run remediation hints are hardcoded English (not localized).
- `F5`: WebSocket/live-stream behavior lacks end-to-end verification depth.
- `F6`: IA experiment telemetry is local-only, limiting comparative analysis.

## Finding-to-Stage Mapping

- Stage 1 addresses: `F1`, `F2`
- Stage 2 addresses: `F3`
- Stage 3 addresses: `F4`
- Stage 4 addresses: `F5`
- Stage 5 addresses: `F6`

## Stage 1: Reversible Delete Contract and Restore Fidelity
**Goal**: Replace recreate-based undo with explicit backend reversible-delete semantics, preserving source/job fidelity.
**Success Criteria**:
- Sources/jobs delete operations expose a documented reversible window contract.
- Restore actions are served by explicit restore APIs rather than create-on-undo.
- Restored entities preserve original critical fields (including `group_ids` for sources).
- Undo expiration behavior is deterministic and observable in API responses.
**Tests**:
- API tests for delete -> restore within window and delete -> expired-restore rejection.
- Contract tests for restore payload fidelity (sources: groups/tags/settings; jobs: scope/filters/schedule/output prefs).
- Permission tests for delete/restore in authorized and unauthorized contexts.
**Status**: Complete

## Stage 2: Source Preflight in Create and Edit Flows
**Goal**: Allow source connectivity/content preflight before initial save, not only after persistence.
**Success Criteria**:
- Source form supports preflight in both create and edit modes.
- Create-mode preflight validates current draft URL/type without requiring source ID.
- Preflight failure states provide actionable, localized guidance inline.
- Submit path remains blocked only by true validation errors, not preflight optionality.
**Tests**:
- Component tests for create-mode preflight idle/running/success/failure states.
- Integration tests covering draft preflight request payloads and failure handling.
- Regression tests ensuring existing edit-mode preflight remains functional.
**Status**: Complete

## Stage 3: Localization Completion for Error Recovery Copy
**Goal**: Remove hardcoded remediation text and align error recovery messaging with i18n standards.
**Success Criteria**:
- `run-notifications` remediation hints resolve from i18n keys with sane fallback behavior.
- New/updated keys are added to both locale bundles used by UI and extension surfaces.
- Error recovery messaging remains severity-aware and context-specific.
**Tests**:
- Unit tests for key-based hint resolution and fallback.
- Snapshot/component tests validating localized copy appears in run notifications and run details.
- Regression tests for missing-key fallback behavior.
**Status**: Complete

## Stage 4: Streaming Visibility Verification Hardening
**Goal**: Add direct behavioral tests for stream lifecycle and bounded log buffering.
**Success Criteria**:
- `RunDetailDrawer` tests cover stream connect, reconnect, error, complete, and manual disable paths.
- Tests validate live log append and bounded buffer truncation behavior.
- Active run status transition is validated via stream updates without full-page reload.
**Tests**:
- Component/integration tests for WebSocket lifecycle transitions and state tags.
- Unit tests for stream payload handling and log truncation boundaries.
- E2E test for active run progression to terminal state with live updates.
**Status**: Complete

## Stage 5: IA Experiment Telemetry Operationalization
**Goal**: Upgrade IA experiment metrics from local-only storage to reportable comparative telemetry.
**Success Criteria**:
- IA experiment events are emitted to a queryable telemetry sink (with graceful local fallback).
- Baseline vs experiment comparison is documented using collected metrics.
- Rollout decision gates are defined from measured signals (tab transitions, traversal breadth, timing proxies).
**Tests**:
- Unit tests for telemetry payload shape and emission triggers.
- Integration tests for telemetry failure fallback (non-blocking UI behavior).
- QA validation of baseline/experiment data capture in staging.
**Status**: Complete

### Stage 5 Implementation Notes (2026-02-19)
- Added server-backed IA telemetry ingest + summary APIs:
  - `POST /api/v1/watchlists/telemetry/ia-experiment`
  - `GET /api/v1/watchlists/telemetry/ia-experiment/summary`
- Added persistent storage table in watchlists DB (`watchlist_ia_experiment_events`) with per-user variant/session snapshots.
- Updated UI telemetry flow to:
  - keep localStorage snapshot fallback (`watchlists:ia-experiment:v1`),
  - emit non-blocking telemetry to the server sink,
  - capture both `baseline` and `experimental` variants for direct comparison.
- Added automated verification:
  - frontend utility tests for payload + failure fallback,
  - Watchlists page regression tests for baseline/experimental telemetry behavior,
  - backend API test for ingest + summary aggregation.

## Dependencies and Sequencing

- Stage 1 should ship before broad UX messaging claims about reversibility are finalized.
- Stage 3 should complete before copy freeze updates to H4/H9 plan artifacts.
- Stage 4 can start in parallel with Stage 3, but should complete before closing H1 Stage 2 verification debt.
- Stage 5 should run after experimental IA behavior is stable and route integrity checks are passing.

## Exit Criteria

- All six findings (`F1`-`F6`) are resolved or explicitly deferred with rationale.
- Each resolved finding has corresponding automated test coverage at the declared level.
- Related watchlists HCI plan files are updated to reflect accurate implementation state.
