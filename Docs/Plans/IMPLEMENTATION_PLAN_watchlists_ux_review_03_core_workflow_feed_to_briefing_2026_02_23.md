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

### Stage 1 Completion Notes (2026-02-23)

- Added pipeline draft schema and contract helpers in `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/pipeline-contract.ts`.
- Implemented validation, job payload mapping, output payload mapping, and review-summary generation for UC2 setup drafts.
- Added unit tests in `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/__tests__/pipeline-contract.test.ts` to verify:
  - Required-field validation behavior.
  - Mapping to `WatchlistJobCreate` and `WatchlistOutputCreate`.
  - Review summary artifact/delivery/schedule output.

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

### Stage 2 Completion Notes (2026-02-23)

- Added a dedicated pipeline-builder CTA in `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/OverviewTab.tsx` (`watchlists-overview-cta-pipeline-builder`) so UC2 setup is accessible directly from Overview.
- Implemented a three-step pipeline modal (Scope -> Briefing -> Review) with:
  - multi-feed selection via source checklist,
  - cadence/template/audio configuration,
  - review summary generated from `buildPipelineReviewSummary`.
- Wired Stage 1 contracts into execution:
  - `toPipelineJobCreatePayload` for monitor creation,
  - `toPipelineOutputCreatePayload` for first output creation after run trigger,
  - `validateBriefingPipelineDraft` for client-side validation gating.
- Added transactional recovery behavior:
  - if pipeline creation fails before run start, newly created monitor is rolled back via `deleteWatchlistJob`,
  - recovery messaging distinguishes rollback success, rollback failure, and post-run failures.
- Added completion routing behavior:
  - run-now success routes to Reports with run filter + output preview (`setOutputsRunFilter`, `openOutputPreview`),
  - non-run-now success routes to Monitors,
  - post-run failures route to Activity with run detail.
- Extended tests in `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`:
  - run-now pipeline success path to output preview,
  - partial creation failure path with rollback assertion.
- Verification evidence:
  - `bunx vitest run src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`
  - `bunx vitest run src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx src/components/Option/Watchlists/OverviewTab/__tests__/pipeline-contract.test.ts src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/SettingsTab/__tests__/SettingsTab.help.test.tsx src/components/Option/Watchlists/shared/__tests__/onboarding-path.test.ts`
  - `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/Watchlists/OverviewTab -f json -o /tmp/bandit_watchlists_group03_stage2_2026_02_23.json`

## Stage 3: Dependency Visibility Across Existing Tabs
**Goal**: Clarify entity relationships even outside the new builder.
**Success Criteria**:
- Monitor detail and run detail explicitly show source and output linkage.
- Output rows show upstream monitor/run with clear jump actions.
- Articles and Runs surfaces expose “included in briefing” and destination visibility.
**Tests**:
- Add UI tests for relationship labels and jump actions.
- Add integration tests for deep-linking between related entities.
**Status**: Not Started

## Stage 4: Preview Before Commit and First-Output Confidence
**Goal**: Let users see likely briefing outcomes before schedules run long-term.
**Success Criteria**:
- Users can preview monitor candidate impact and output template result before final save.
- Pipeline completion includes a “test generation” option with clear result handling.
- Audio/text outcome expectations are shown in review step.
**Tests**:
- Add tests for preview generation, preview failures, and fallback messaging.
- Add tests for test-run completion routing.
**Status**: Not Started

## Stage 5: Workflow KPI and Reliability Validation
**Goal**: Validate UC2 completion quality and reduce setup abandonment.
**Success Criteria**:
- UC2 funnel events exist for each major step and completion checkpoint.
- Dashboard or report tracks setup completion rate and first-success rate.
- Documentation includes UC2 runbook for QA and product demos.
**Tests**:
- Add telemetry event contract tests for pipeline milestones.
- Run end-to-end regression for pipeline setup on clean user state.
**Status**: Not Started
