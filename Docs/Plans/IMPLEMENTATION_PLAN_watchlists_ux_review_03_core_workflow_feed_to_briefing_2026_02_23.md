# Watchlists UX Review Group 03 - Core Workflow (Feed Setup to Briefing Delivery) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make UC2 (“set sources, run on schedule, receive text+audio briefings”) coherent as a single user workflow.

**Architecture:** Introduce a pipeline-oriented orchestration flow that composes Sources, Monitors, Runs, Outputs, and Templates into one guided setup, while preserving existing modular tabs for experts.

**Tech Stack:** React, TypeScript, existing Watchlists services API, Ant Design workflow components, Zustand for transient flow state, Vitest + integration UI tests.

---

## Scope

- UX dimensions covered: UC2 end-to-end workflow coherence.
- Primary surfaces:
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/OverviewTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/JobFormModal.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/RunsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputsTab.tsx`
  - `apps/packages/ui/src/services/watchlists.ts`
- Key outcomes:
  - Single guided pipeline creation path for UC2.
  - Explicit dependency visibility (feeds -> monitor -> run -> outputs).
  - Reduced handoff confusion between activity and reports.

## Stage 1: Pipeline Flow Specification and Data Contract
**Goal**: Define the canonical UI contract for creating a briefing pipeline.
**Success Criteria**:
- Pipeline builder schema includes source set, cadence, template/audio mode, delivery options.
- Draft payload maps cleanly to existing source/job/output APIs.
- “Review and confirm” step explains generated artifacts and schedule.
**Tests**:
- Add unit tests for payload builders and schema validators.
- Add contract tests for source/job/output request mapping.
**Status**: Complete

## Stage 2: Pipeline Builder UI Implementation
**Goal**: Implement a dedicated UC2 setup flow available from Overview.
**Success Criteria**:
- Users can configure multi-feed + cadence + briefing options in one guided sequence.
- Builder can create required entities with transactional error handling and rollback messaging.
- Post-completion route points to active run or generated report preview.
**Tests**:
- Add flow tests for successful pipeline creation and run-now variants.
- Add failure-path tests for partial creation and recovery prompts.
**Status**: Complete

## Stage 3: Dependency Visibility Across Existing Tabs
**Goal**: Clarify entity relationships even outside the new builder.
**Success Criteria**:
- Monitor detail and run detail explicitly show source and output linkage.
- Output rows show upstream monitor/run with clear jump actions.
- Articles and Runs surfaces expose “included in briefing” and destination visibility.
**Tests**:
- Add UI tests for relationship labels and jump actions.
- Add integration tests for deep-linking between related entities.
**Status**: Complete

### Stage 3 Execution Notes (2026-02-23)

- Jobs list now surfaces per-monitor output linkage summaries (template + audio mode) so monitor intent is visible without opening each monitor modal:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/job-summaries.ts`
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/JobsTab.tsx`
- Reports rows now expose direct “jump to monitor” and “jump to run” actions to reduce cross-tab hunting:
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputsTab.tsx`
- Activity rows now include explicit “open reports” action that routes with run/job filters:
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/RunsTab.tsx`
- Run detail now shows linked report count plus dependency actions (`open monitor`, `open reports`) and clarifies item inclusion state using briefing-language statuses:
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/RunDetailDrawer.tsx`
- Localization and regression coverage were expanded for the new linkage actions/labels:
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.relationship-jumps.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.relationship-jumps.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.source-column.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.stream-lifecycle.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx`

### Stage 3 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.relationship-jumps.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.relationship-jumps.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.source-column.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.stream-lifecycle.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
- `bunx vitest run src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.scope-filter-summary.test.tsx src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.relationship-jumps.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.relationship-jumps.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.source-column.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunDetailDrawer.stream-lifecycle.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx`
- `/tmp/bandit_watchlists_group03_stage3_frontend_scope_2026_02_23.json`

## Stage 4: Preview Before Commit and First-Output Confidence
**Goal**: Let users see likely briefing outcomes before schedules run long-term.
**Success Criteria**:
- Users can preview monitor candidate impact and output template result before final save.
- Pipeline completion includes a “test generation” option with clear result handling.
- Audio/text outcome expectations are shown in review step.
**Tests**:
- Add tests for preview generation, preview failures, and fallback messaging.
- Add tests for test-run completion routing.
**Status**: Complete

### Stage 4 Execution Notes (2026-02-23)

- Extended quick-setup workflow model with explicit audio briefing toggle support and output payload mapping (`generate_audio`) for briefing goal paths:
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/quick-setup.ts`
- Upgraded Overview quick-setup review step to provide pre-commit confidence:
  - source candidate preview via `testWatchlistSourceDraft` with retry/error fallback handling,
  - template-style briefing preview text derived from monitor/feed selections and sample candidates,
  - explicit destination/result hints for test-run vs scheduled-only flows.
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/OverviewTab.tsx`
- Clarified completion behavior by promoting “run now” into explicit “test generation” language and dynamic submit CTA (`Create setup + run test`).
- Added localization coverage for candidate preview, template preview, outcome expectations, and destination hints:
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Added regression tests for preview success/failure and test-run destination routing:
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/__tests__/quick-setup.test.ts`

### Stage 4 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/OverviewTab/__tests__/quick-setup.test.ts src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`
- `bunx vitest run src/components/Option/Watchlists/OverviewTab/__tests__/quick-setup.test.ts src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts`
- `/tmp/bandit_watchlists_group03_stage4_frontend_scope_2026_02_23.json`

## Stage 5: Workflow KPI and Reliability Validation
**Goal**: Validate UC2 completion quality and reduce setup abandonment.
**Success Criteria**:
- UC2 funnel events exist for each major step and completion checkpoint.
- Dashboard or report tracks setup completion rate and first-success rate.
- Documentation includes UC2 runbook for QA and product demos.
**Tests**:
- Add telemetry event contract tests for pipeline milestones.
- Run end-to-end regression for pipeline setup on clean user state.
**Status**: Complete

### Stage 5 Execution Notes (2026-02-23)

- Expanded onboarding telemetry contract for UC2 workflow milestones:
  - preview milestones (`quick_setup_preview_loaded`, `quick_setup_preview_failed`) for candidate/template confidence checks,
  - test-generation milestones (`quick_setup_test_run_triggered`, `quick_setup_test_run_failed`),
  - destination rollups (`completed_by_destination`) and UC2 snapshot rates.
  - `apps/packages/ui/src/utils/watchlists-onboarding-telemetry.ts`
- Added UC2 dashboard snapshot builder (`buildWatchlistsUc2FunnelDashboardSnapshot`) with completion and first-success proxy rate calculations.
- Wired quick-setup UI to emit new telemetry checkpoints:
  - candidate preview success/failure events,
  - template preview readiness event at review transition,
  - explicit test-run triggered/failed events around run kickoff.
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/OverviewTab.tsx`
- Added telemetry contract/regression coverage:
  - `apps/packages/ui/src/utils/__tests__/watchlists-onboarding-telemetry.test.ts`
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`
- Added dedicated UC2 regression gate command:
  - `apps/packages/ui/package.json` -> `test:watchlists:uc2`
- Published UC2 KPI runbook:
  - `Docs/Plans/WATCHLISTS_UC2_WORKFLOW_KPI_RUNBOOK_2026_02_23.md`

### Stage 5 Addendum (2026-02-23, Group 03 Continuation)

- Refreshed UC2 KPI runbook to include milestone-based onboarding outcomes introduced in shared telemetry:
  - added first-success milestones (`quick_setup_first_run_succeeded`, `quick_setup_first_output_succeeded`),
  - added explicit run/output success and drop-off rates,
  - added median timing metrics for setup/run/output first-success checkpoints,
  - aligned investigation thresholds to first-output success and timing regressions.
  - `Docs/Plans/WATCHLISTS_UC2_WORKFLOW_KPI_RUNBOOK_2026_02_23.md`

### Stage 5 Validation Evidence

- `bunx vitest run src/utils/__tests__/watchlists-onboarding-telemetry.test.ts src/components/Option/Watchlists/OverviewTab/__tests__/quick-setup.test.ts src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`
- `bun run test:watchlists:uc2`
- `bun run test:watchlists:onboarding`
- `/tmp/bandit_watchlists_group03_stage5_frontend_scope_2026_02_23.json`
