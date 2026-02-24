# Watchlists UX Review Group 05 - Error Prevention, Recovery, and Feedback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make failure handling and recovery pathways consistently actionable across source setup, monitor execution, and output delivery.

**Architecture:** Standardize prevention checks, error taxonomy mapping, and recovery affordances across all Watchlists mutation flows so users can diagnose and recover without backend knowledge.

**Tech Stack:** React, TypeScript, watchlists services/error mapping, run notification utilities, Ant Design alert/notification components, Vitest + integration tests.

---

## Scope

- UX dimensions covered: prevention, error messaging, recoverability, silent-failure detection.
- Primary surfaces:
  - `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/SourceFormModal.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/JobFormModal.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/RunsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/RunDetailDrawer.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/shared/watchlists-error.ts`
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Key outcomes:
  - Consistent actionable errors with next-step guidance.
  - Strong prevention before save/run.
  - Better reliability alerts for failed/stalled/undelivered work.

## Stage 1: Error Taxonomy and Message Contract
**Goal**: Define a unified error mapping and remediation contract for all Watchlists operations.
**Success Criteria**:
- Common error categories map to clear user actions in every tab.
- All user-visible errors include “what happened” and “what to do next.”
- Severity levels are applied consistently (info/warn/error).
**Tests**:
- Add unit tests for error-mapper outputs by representative backend failure strings.
- Add localization key coverage tests for error and remediation copy.
**Status**: Complete

## Stage 2: Prevention Before Commit
**Goal**: Ensure users can validate configurations before scheduled execution.
**Success Criteria**:
- Source and monitor preflight checks are available without forcing save-first flows.
- Validation blockers explain remediation paths inline.
- High-risk options (too frequent schedule, invalid recipients, malformed JSON) are prevented with explicit guidance.
**Tests**:
- Add tests for source test, monitor preview, and pre-save blockers.
- Add tests for edge-case validation messaging and retry actions.
**Status**: Complete

## Stage 3: Recovery and Undo Consistency
**Goal**: Make destructive action recovery behavior predictable and discoverable.
**Success Criteria**:
- Delete confirmation copy aligns with actual reversible-delete behavior.
- Undo windows are surfaced consistently for single and bulk actions.
- Partial restore failures provide next-step instructions and recovery options.
**Tests**:
- Add tests for undo notification timing, restore actions, and partial failure messaging.
- Add tests for delete dialogs under in-use and non-in-use conditions.
**Status**: Complete

## Stage 4: Reliability Signals and Escalation
**Goal**: Ensure failed/stalled runs and delivery failures are visible before user trust is impacted.
**Success Criteria**:
- Run and output reliability indicators are surfaced in overview and tab badges.
- Stalled/failure notifications include direct deep links to corrective actions.
- Delivery failures for reports/audio are clearly visible and filterable.
**Tests**:
- Add tests for run notification generation/grouping and deep-link actions.
- Add tests for output delivery status change announcements and filters.
**Status**: Complete

## Stage 5: Operational Recovery Runbook
**Goal**: Make incident response repeatable for support, QA, and developers.
**Success Criteria**:
- Recovery playbook documents top failure classes and UI recovery steps.
- QA scenario matrix covers source failure, run failure, template failure, and delivery failure.
- Monitoring checklist defines alert thresholds for recurring failures.
**Tests**:
- Run a fault-injection style manual test checklist on key flows.
- Validate all runbook paths against current UI and error copy.
**Status**: Complete

### Completion Note (2026-02-23)

- All Group 05 stages were executed and validated under the program coordination flow.
- Consolidated execution notes and validation evidence are tracked in:
  - `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_program_coordination_index_2026_02_23.md`
- Group 05 operational artifact:
  - `Docs/Plans/WATCHLISTS_RECOVERY_RUNBOOK_2026_02_23.md`
