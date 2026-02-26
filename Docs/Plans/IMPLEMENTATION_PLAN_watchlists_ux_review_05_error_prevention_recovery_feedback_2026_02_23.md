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

## Execution Notes

### 2026-02-23 - Stage 1 completion (taxonomy + locale contract)

- Extended Watchlists shared error taxonomy for actionable remediation consistency:
  - Added `validation` error kind classification.
  - Added explicit timeout classification for HTTP `408` and `504`.
  - Expanded auth detection for token-expiration strings.
  - Implemented in:
    - `apps/packages/ui/src/components/Option/Watchlists/shared/watchlists-error.ts`
- Added/updated Stage 1 tests:
  - `apps/packages/ui/src/components/Option/Watchlists/shared/__tests__/watchlists-error.test.ts`
  - `apps/packages/ui/src/components/Option/Watchlists/shared/__tests__/watchlists-error.locale-contract.test.ts`
- Added locale contract copy key for validation remediation:
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/shared/__tests__/watchlists-error.test.ts src/components/Option/Watchlists/shared/__tests__/watchlists-error.locale-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/job-summaries.test.ts src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
  - `/tmp/bandit_watchlists_group05_stage1_2026_02_23.json`

### 2026-02-23 - Stage 2 completion (prevention-before-commit coverage)

- Expanded monitor pre-save blocker coverage in:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx`
  - Added explicit tests for:
    - too-frequent schedule submit blocking with actionable guidance.
    - invalid email recipient submit blocking in edit mode with remediation prompt.
- Validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourceFormModal.test-source.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx`

### 2026-02-23 - Stage 3 completion (undo/recovery consistency)

- Completed reversible-delete copy alignment and undo discoverability updates:
  - `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/SourcesTab.tsx`
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Added delete/recovery behavior coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.delete-confirm.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts`
- Validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.delete-confirm.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/source-undo.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts`
  - `/tmp/bandit_watchlists_group05_stage2_stage3_2026_02_23.json`

### 2026-02-23 - Stage 4 completion (reliability signal filtering)

- Added delivery-status filtering for Reports to make delivery failures directly filterable in advanced mode:
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputsTab.tsx`
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Added/updated Stage 4 regression coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx`
- Validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/SourcesTab/__tests__/SourceFormModal.test-source.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.delete-confirm.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/source-undo.test.ts src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/shared/__tests__/watchlists-error.test.ts src/components/Option/Watchlists/shared/__tests__/watchlists-error.locale-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts`
  - `/tmp/bandit_watchlists_group05_stage4_2026_02_23.json`

### 2026-02-23 - Stage 5 completion (operational runbook + QA matrix)

- Added operational recovery runbook documenting:
  - top failure classes and UI-first recovery workflows,
  - QA scenario matrix across source/run/template/delivery failures,
  - monitoring thresholds and escalation checklist.
- Artifact:
  - `Docs/Plans/WATCHLISTS_RECOVERY_RUNBOOK_2026_02_23.md`
