# Watchlists UX Review Group 02 - First-Run Experience and Learnability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make first-use setup intuitive for non-developer analysts, with clear progressive disclosure from basic setup to advanced controls.

**Architecture:** Expand onboarding from a one-shot setup modal to a layered guidance system (wizard, guided tour, contextual teach points), while preserving power-user paths for direct configuration.

**Tech Stack:** React, TypeScript, Ant Design Modal/Steps, i18n copy system, onboarding telemetry hooks, Vitest + Testing Library.

---

## Scope

- UX dimensions covered: first-run experience, learnability, progressive disclosure.
- Primary surfaces:
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/OverviewTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/quick-setup.ts`
  - `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx`
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Key outcomes:
  - Lower concept load for UC1 and UC2 onboarding.
  - Better guided tour depth tied to real outcomes.
  - Smoother transition from basic setup into advanced features.

## Stage 1: Onboarding Path Definition
**Goal**: Define beginner and power onboarding tracks with explicit branch criteria.
**Success Criteria**:
- New users are offered a guided beginner path with no cron/template jargon.
- Advanced users can skip directly to detailed forms.
- Onboarding path choice is persisted and can be changed in settings.
**Tests**:
- Add tests for first-visit onboarding branch selection and persistence.
- Add tests for “skip onboarding” and resume behavior.
**Status**: Complete

## Stage 2: Quick Setup Expansion for Real UC2
**Goal**: Extend quick setup beyond a single source into practical briefing setup.
**Success Criteria**:
- Quick setup supports multi-feed import/add, schedule preset, and briefing mode defaults.
- Quick setup includes explicit audio briefing toggle and output destination hints.
- Completion routes users to the most relevant next surface based on chosen goal.
**Tests**:
- Add tests for multi-feed setup success/failure flows.
- Add tests for setup-goal routing (triage vs briefing vs briefing+run-now).
**Status**: Complete

## Stage 3: Guided Tour Coverage and Contextual Teach Points
**Goal**: Make guided tour explain key concepts users encounter later.
**Success Criteria**:
- Guided tour includes monitor-output-template relationships and audio discoverability.
- Contextual tips appear when users first encounter cron, filters, or templates.
- Help tooltip topics map to concrete user tasks, not only technical definitions.
**Tests**:
- Add tests for guided tour step content and progression state.
- Add tests for first-time teach-point visibility and dismissal persistence.
**Status**: Complete

### Stage 3 Execution Notes (2026-02-23)

- Expanded guided tour copy to explain monitor -> template -> output relationships and audio briefing discoverability:
  - `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx`
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Added first-time contextual teach-point system with dismissal persistence (`watchlists:teach-points:v1`):
  - Jobs tab: cron-first tip, then filters tip.
  - Templates tab: preset-first template tip.
  - Implemented in `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx`.
- Reframed help tooltip topic copy from technical definitions to task-oriented guidance:
  - `apps/packages/ui/src/components/Option/Watchlists/shared/WatchlistsHelpTooltip.tsx`
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Added/updated regression coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/shared/__tests__/WatchlistsHelpTooltip.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/shared/__tests__/__snapshots__/WatchlistsHelpTooltip.test.tsx.snap`

### Stage 3 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/shared/__tests__/WatchlistsHelpTooltip.test.tsx -u`
- `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/shared/__tests__/WatchlistsHelpTooltip.test.tsx src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts`
- `/tmp/bandit_watchlists_group02_stage3_frontend_scope_2026_02_23.json`

## Stage 4: Concept Burden Reduction in Copy
**Goal**: Reduce jargon and improve actionability of onboarding/UI copy.
**Success Criteria**:
- Beginner-facing copy avoids or explains cron/Jinja/regex terms at point of use.
- All setup actions have clear “what happens next” wording.
- Mixed terminology is removed from first-run surfaces.
**Tests**:
- Add snapshot tests for key onboarding copy blocks.
- Add copy contract tests for terminology consistency in first-run keys.
**Status**: Complete

### Stage 4 Execution Notes (2026-02-23)

- Refined first-run copy to reduce model-driven terms and improve action clarity:
  - onboarding feed step now uses feed language consistently (removed source noun),
  - guided-tour monitor step now uses “briefing format” wording (removed output noun),
  - review-step messaging now uses “expected briefing” wording (removed output noun).
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/OverviewTab.tsx`
- Added first-run terminology contract checks to guard against backend-model nouns on onboarding surfaces:
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/watchlists-first-run-copy-contract.test.ts`
- Added onboarding copy snapshot coverage for key first-run blocks (`overview.onboarding`, `guide`, `teachPoints`):
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.onboarding-copy.snapshot.test.ts`
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/__tests__/__snapshots__/OverviewTab.onboarding-copy.snapshot.test.ts.snap`

### Stage 4 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.onboarding-copy.snapshot.test.ts src/components/Option/Watchlists/__tests__/watchlists-first-run-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/shared/__tests__/WatchlistsHelpTooltip.test.tsx -u`
- `bun run test:watchlists:uc2`
- `/tmp/bandit_watchlists_group02_stage4_frontend_scope_2026_02_23.json`

## Stage 5: Onboarding Effectiveness Validation
**Goal**: Validate that users reach first successful run and first report faster.
**Success Criteria**:
- Telemetry captures setup start, setup completion, first run success, first output success.
- Time-to-first-value and drop-off metrics are defined and reviewed.
- QA runbook includes beginner-path and power-path verification.
**Tests**:
- Add telemetry schema tests for onboarding events.
- Run onboarding regression suite for happy path and interruption recovery.
**Status**: Complete

### Stage 5 Execution Notes (2026-02-23)

- Extended onboarding telemetry contract with explicit first-success milestones and rate/timing/drop-off snapshot metrics:
  - added events: `quick_setup_first_run_succeeded`, `quick_setup_first_output_succeeded`,
  - added counters: `first_run_success`, `first_output_success`,
  - added timing samples: setup completion, first run success, first output success,
  - added rates: first-run/output success + setup/run/output drop-off rates.
  - `apps/packages/ui/src/utils/watchlists-onboarding-telemetry.ts`
- Wired milestone telemetry emission across beginner and power paths:
  - Overview snapshot path (existing users/new outputs): `OverviewTab.tsx`,
  - Reports list load path (unfiltered outputs): `OutputsTab.tsx`,
  - Global run-status transition polling path: `WatchlistsPlaygroundPage.tsx`.
- Added and updated regression coverage:
  - telemetry schema/rate/timing contract:
    - `apps/packages/ui/src/utils/__tests__/watchlists-onboarding-telemetry.test.ts`
  - onboarding happy-path + interruption recovery flow validation (guided setup + preview failure):
    - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`
    - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/__tests__/quick-setup.test.ts`
  - milestone propagation on run completion and outputs availability:
    - `apps/packages/ui/src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.run-notifications.test.tsx`
    - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
- Added dedicated onboarding regression gate command:
  - `apps/packages/ui/package.json` -> `test:watchlists:onboarding`
- Published Stage 5 QA/KPI runbook:
  - `Docs/Plans/WATCHLISTS_ONBOARDING_EFFECTIVENESS_VALIDATION_RUNBOOK_2026_02_23.md`

### Stage 5 Validation Evidence

- `bun run test:watchlists:onboarding`
- `bun run test:watchlists:uc2`
- `bunx vitest run src/utils/__tests__/watchlists-onboarding-telemetry.test.ts src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.run-notifications.test.tsx`
- `/tmp/bandit_watchlists_group02_stage5_frontend_scope_2026_02_23.json`
