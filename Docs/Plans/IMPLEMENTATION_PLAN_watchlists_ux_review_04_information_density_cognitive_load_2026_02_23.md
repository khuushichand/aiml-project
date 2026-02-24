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

---

## Execution Notes (2026-02-23)

- Stage 1 completed with disclosure-state helper coverage and UI transition tests:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
- Stage 2 completed with Basic/Advanced monitor authoring flow guardrails and remediation coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx`
- Stage 3 completed with compact-vs-advanced list profile behavior in Monitors, Activity, and Reports:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
- Stage 4 completed with persistent live summaries and review-step confirmation on monitor setup:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx`
- Stage 5 completed with scale-path usability coverage and explicit QA checklist:
  - 1/10/50 feed setup validation in monitor Basic mode:
    - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx`
  - High-density list rendering regressions:
    - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx`
    - `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx`
    - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx`
    - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
  - QA checklist artifact:
    - `Docs/Plans/WATCHLISTS_MONITOR_DENSITY_SCALE_QA_CHECKLIST_2026_02_23.md`
  - Validation evidence:
    - `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
    - `/tmp/bandit_watchlists_group04_stage5_frontend_scope_2026_02_23.json`
