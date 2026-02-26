# Watchlists UX Review Group 04 - Information Density and Cognitive Load Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Preserve Watchlists power-user capability while reducing overwhelm in dense interfaces, especially monitor authoring.

**Architecture:** Refactor high-density forms and tables into layered disclosure with explicit state summaries, confidence cues, and safe defaults, while keeping advanced controls available and transparent.

**Tech Stack:** React, TypeScript, Ant Design forms/collapse/table, watchlists form utilities, i18n copy, Vitest + component interaction tests.

---

## Scope

- UX dimensions covered: information density, cognitive load, complex form usability.
- Primary surfaces:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/JobFormModal.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/SchedulePicker.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/FilterBuilder.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/SourcesTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/RunsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputsTab.tsx`
- Key outcomes:
  - Lower cognitive load in monitor setup.
  - Clear visibility for hidden advanced settings.
  - Better default density profiles for list surfaces.

## Stage 1: Cognitive Load Audit and Disclosure Rules
**Goal**: Define explicit disclosure heuristics for basic vs advanced controls.
**Success Criteria**:
- Each monitor form section is tagged as core, optional, or expert.
- Hidden advanced settings state is always visible in summary when active.
- Form sections have ordering based on user decision sequence, not backend model grouping.
**Tests**:
- Add unit tests for advanced-state detection and summary generation.
- Add UI tests for disclosure state transitions.
**Status**: Complete

## Stage 2: Monitor Form Recomposition
**Goal**: Recompose monitor authoring into staged decision flow with safety cues.
**Success Criteria**:
- Basic mode exposes only required controls and explicit default assumptions.
- Advanced mode remains complete but grouped by intent (scope, timing, filtering, delivery, audio).
- “Configuration confidence” panel indicates readiness and unresolved risks.
**Tests**:
- Add tests for mode switch behavior and preservation/reset of advanced state.
- Add tests for readiness checks and blocked-save validation messages.
**Status**: Complete

## Stage 3: Dense List View Profiles
**Goal**: Improve readability and signal-to-noise in source/monitor/run/output tables.
**Success Criteria**:
- Core vs advanced column profiles are consistent across list tabs.
- Status and attention signals are prominent without visual overload.
- Empty and filtered states clearly explain how to recover useful data.
**Tests**:
- Add table profile tests for each tab (default columns vs advanced).
- Add visual regression checks for state badges and compact summaries.
**Status**: Complete

## Stage 4: Summary and Confirmation Enhancements
**Goal**: Reduce memory load by summarizing key choices before commit.
**Success Criteria**:
- Every complex form includes a persistent live summary block.
- Summary includes hidden advanced settings and delivery/audio consequences.
- Final confirmation step is explicit for destructive or expensive operations.
**Tests**:
- Add tests for summary accuracy across edit/create scenarios.
- Add tests for final confirmation content and validation gating.
**Status**: Complete

## Stage 5: Usability Validation at Scale
**Goal**: Confirm reduced cognitive load for typical and heavy configurations.
**Success Criteria**:
- Task-completion tests demonstrate fewer misconfigurations for beginner path.
- High-density usage remains efficient for advanced users.
- QA checklist includes 1-feed, 10-feed, and 50-feed setup scenarios.
**Tests**:
- Run focused usability regression tests for monitor configuration paths.
- Add benchmark tests for rendering with larger table datasets.
**Status**: Complete

## Execution Notes

### 2026-02-23 - Stage 1 and Stage 2 completion snapshot

- Stage 1 disclosure baseline validated in monitor authoring:
  - Basic vs advanced setup mode toggles with preserved hidden advanced settings notice.
  - Decision-sequence ordering present via basic step flow (`scope -> schedule -> output -> review`).
  - Disclosure transition and summary coverage validated in:
    - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx`
- Stage 2 monitor recomposition updated with configuration confidence surface:
  - Added persistent confidence panel with readiness status and unresolved risk cues in:
    - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/JobFormModal.tsx`
  - Added confidence-specific red/green tests:
    - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx`
- Validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/job-summaries.test.ts src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx`
  - `/tmp/bandit_watchlists_group04_stage2_2026_02_23.json`

### 2026-02-23 - Stage 3 increment (Sources list profile)

- Added core/advanced column profile toggle in Sources list:
  - Compact default now surfaces per-feed summary chips (`group/tag` counts).
  - Advanced mode reveals detailed tag column and persists disclosure preference.
  - Implemented in:
    - `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/SourcesTab.tsx`
- Added Stage 3 regression coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx`
- Stage 3 completion validation across list surfaces:
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
- Stage 3 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/job-summaries.test.ts src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
  - `bunx vitest run src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/job-summaries.test.ts src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx`
  - `/tmp/bandit_watchlists_group04_stage3_2026_02_23.json`

### 2026-02-23 - Stage 4 completion (summary + confirmation)

- Extended monitor live summary coverage with delivery/audio consequences and hidden-advanced-state visibility:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/JobFormModal.tsx`
- Added explicit recurring delivery confirmation gate before save/create when expensive operations are enabled:
  - Email delivery, chatbook delivery, and audio generation now require explicit confirmation before submit.
- Added Stage 4 test coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx`
  - New assertions cover:
    - delivery/audio consequence summaries
    - hidden advanced-state summary visibility
    - recurring delivery confirmation cancellation gate
- Stage 4 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/job-summaries.test.ts src/components/Option/Watchlists/JobsTab/__tests__/SchedulePicker.help.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.load-error-retry.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
  - `/tmp/bandit_watchlists_group04_stage4_2026_02_23.json`

### 2026-02-23 - Stage 5 completion (usability validation at scale)

- Added scale-path regression coverage for compact/advanced density behavior at 1/10/50 dataset sizes:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx`
- Published explicit QA matrix for 1-feed, 10-feed, and 50-feed validation:
  - `Docs/Plans/WATCHLISTS_MONITOR_DENSITY_SCALE_QA_CHECKLIST_2026_02_23.md`
- Stage 5 validation evidence:
  - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx src/components/Option/Watchlists/OverviewTab/__tests__/quick-setup.test.ts --maxWorkers=1 --no-file-parallelism`
