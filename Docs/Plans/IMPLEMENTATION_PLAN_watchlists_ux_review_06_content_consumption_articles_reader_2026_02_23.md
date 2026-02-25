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

---

## Execution Notes (2026-02-23)

- Stage 1 completed with explicit reader prioritization/sorting controls and persisted view support:
  - Added reader sort modes (`newest`, `oldest`, `unreadFirst`, `reviewedFirst`) in:
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx`
  - Extended saved-view contract to persist and restore sort mode:
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/items-utils.ts`
  - Added localization for sort labels/options:
    - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Stage 1 test coverage added/updated:
  - Sort helper and sort-mode normalization coverage:
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts`
  - Sort-change row ordering and smart-filter + saved-view persistence coverage:
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx`
  - Keyboard shortcut regression adjusted for deterministic newest-first baseline:
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
- Validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
  - `/tmp/bandit_watchlists_group06_stage1_frontend_scope_2026_02_23.json`

- Stage 2 completed with explicit scale/recovery batch-review coverage:
  - Added all-filtered scope confirmation and completion behavior coverage:
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx`
  - Added partial-failure reconciliation coverage (warning copy + retained failed selections):
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx`
- Stage 2 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
  - `/tmp/bandit_watchlists_group06_stage2_frontend_scope_2026_02_23.json`

- Stage 3 completed with shortcut discoverability/accessibility regression reinforcement:
  - Added explicit keyboard-behavior coverage ensuring list navigation shortcuts are blocked while shortcut help is open:
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
  - Existing coverage for hint visibility/dismiss/restore lifecycle and help-panel focus restoration remains active.
- Stage 3 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
  - `/tmp/bandit_watchlists_group06_stage3_frontend_scope_2026_02_23.json`

- Stage 4 completed with cross-action/statefulness reinforcement in reader:
  - Added include-in-briefing state-transition coverage (disabled for already-ingested items, enabled for eligible items, disabled after successful inclusion):
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx`
  - Existing cross-jump routing coverage (Monitor/Run/Reports) remains active.
- Stage 4 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
  - `/tmp/bandit_watchlists_group06_stage4_frontend_scope_2026_02_23.json`

- Stage 5 completed with mobile/high-volume validation coverage and QA checklist:
  - Added narrow-viewport operability regression for core panes and controls:
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
  - Added high-volume all-filtered batch regression coverage (240-item operation):
    - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx`
  - Added 5/50/200 profile QA checklist artifact:
    - `Docs/Plans/WATCHLISTS_ARTICLES_READER_SCALE_QA_CHECKLIST_2026_02_23.md`
- Stage 5 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
  - `/tmp/bandit_watchlists_group06_stage5_frontend_scope_2026_02_23.json`
