# Watchlists UX Review Group 06 - Content Consumption (Articles Reader) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Articles tab a fast, scalable, and discoverable triage workspace for daily analyst usage.

**Architecture:** Build on the existing three-pane reader by adding stronger prioritization controls, scalable batch ergonomics, and improved mobile/readability behaviors while preserving keyboard-driven speed.

**Tech Stack:** React, TypeScript, Ant Design list/segmented/select/pagination, DOMPurify render path, watchlists item services, Vitest + UI interaction tests.

---

## Scope

- UX dimensions covered: reader ergonomics, review model, keyboard workflows, batch scale.
- Primary surfaces:
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/items-utils.ts`
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Key outcomes:
  - Faster triage at 100+ items.
  - Better discoverability of shortcuts and batch scope.
  - Stronger cross-surface handoff to monitor/run/report actions.

## Stage 1: Reader Workflow Baseline and Prioritization Model
**Goal**: Define core triage actions and ordering model for daily review sessions.
**Success Criteria**:
- Explicit sort modes and prioritization actions are available (e.g., newest, unread-first).
- Smart feeds and saved views align with high-frequency analyst tasks.
- Review status model remains clear with minimal toggling friction.
**Tests**:
- Add tests for sort changes, smart filter transitions, and view preset persistence.
- Add tests for review state rendering and state toggling.
**Status**: Complete

## Stage 2: Batch Review Scale and Feedback
**Goal**: Improve batch review safety and visibility for large item sets.
**Success Criteria**:
- Batch actions show scope, estimated impact, progress, and completion outcomes.
- Large-scope operations avoid UI freeze and provide clear partial-failure handling.
- Selection behavior is predictable across page and filtered scopes.
**Tests**:
- Add tests for selected/page/all-filtered batch flows and confirmations.
- Add tests for partial success/failure messaging and state reconciliation.
**Status**: Complete

## Stage 3: Shortcut Discoverability and Accessibility in Reader
**Goal**: Keep keyboard power while improving discoverability for new users.
**Success Criteria**:
- Shortcut hints are visible, dismissible, and restorable with clear entry points.
- Shortcut behavior avoids conflicts with form fields and assistive contexts.
- Reader actions remain accessible by both keyboard and pointer.
**Tests**:
- Add keyboard event tests for navigation/toggle/open/help flows.
- Add tests for shortcut modal focus management and dismissal behavior.
**Status**: Complete

## Stage 4: Reader Content Value and Cross-Action Flow
**Goal**: Improve in-pane value and reduce unnecessary context switching.
**Success Criteria**:
- Reader pane prioritizes actionable summary and source context.
- Cross-jump actions to Monitor/Run/Reports are clear and contextual.
- “Include in next briefing” behavior is understandable and stateful.
**Tests**:
- Add tests for reader header action buttons and target routing.
- Add tests for include-in-briefing action availability and feedback.
**Status**: Complete

## Stage 5: Mobile and High-Volume Reader Validation
**Goal**: Ensure reader usability on mobile and high-volume data scenarios.
**Success Criteria**:
- Responsive layout remains usable across pane collapses and narrow widths.
- Reader performance remains acceptable with thousands of matching items.
- QA checklist covers 5, 50, and 200 source profiles for reader interactions.
**Tests**:
- Run responsive tests for tablet/mobile breakpoints.
- Run performance-oriented tests for item rendering and selection operations.
**Status**: Complete

## Execution Notes

### 2026-02-23 - Stage 1 completion (reader prioritization baseline)

- Added explicit triage sort controls in Articles reader:
  - `newest`, `oldest`, and `unread-first`
  - persisted via local storage and included in saved view preset contracts
  - implemented in:
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx`
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/items-utils.ts`
- Added smart-feed transition coverage and reader sort transition coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts`
- Added localization copy for sort controls:
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Stage 1 validation evidence:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx --maxWorkers=1 --no-file-parallelism`

### 2026-02-23 - Stage 2 completion (batch scale and feedback)

- Added explicit scope/reconciliation regression coverage for batch flows:
  - selected/page/all-filtered confirmation scope assertions
  - partial success/failure warning and row-state reconciliation assertions
  - implemented in:
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx`
- Stage 2 validation evidence:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx --maxWorkers=1 --no-file-parallelism`

### 2026-02-23 - Stage 3 and Stage 4 validation snapshot

- Stage 3 (shortcut discoverability/accessibility) validated by:
  - shortcut hint dismiss/restore lifecycle
  - keyboard conflict guard for editable targets
  - shortcuts modal focus restore behavior
  - file: `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
- Stage 4 (content value and cross-action flow) validated by:
  - include-in-next-briefing action availability and feedback
  - monitor/run/reports cross-jump routing assertions
  - file: `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx`
- Stage 3/4 validation evidence:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts --maxWorkers=1 --no-file-parallelism`

### 2026-02-24 - Stage 5 completion (mobile + high-volume validation)

- Added source-list rendering window behavior to protect high-volume feed profiles:
  - initial render cap + scroll-driven expansion using source window helpers
  - explicit rendered-source hint for collapsed large lists
  - implemented in:
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx`
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/items-utils.ts`
- Added Stage 5 responsive/scale coverage:
  - new responsive + source-profile dataset tests (5, 50, 200 source contexts):
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.scale-responsive.test.tsx`
  - high-volume all-filtered pagination/throughput coverage (1200-item batch operation):
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx`
  - source render-window helper coverage:
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts`
- Added Stage 5 reader QA checklist:
  - `Docs/Plans/WATCHLISTS_READER_SCALE_MOBILE_QA_CHECKLIST_2026_02_24.md`
- Stage 5 validation evidence:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.scale-responsive.test.tsx --maxWorkers=1 --no-file-parallelism`
  - `/tmp/bandit_watchlists_group06_stage5_2026_02_24.json`
