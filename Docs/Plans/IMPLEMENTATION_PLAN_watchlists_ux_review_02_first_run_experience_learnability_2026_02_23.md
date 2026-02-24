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

### Stage 1 Completion Notes (2026-02-23)

- Added persisted onboarding path helpers in `apps/packages/ui/src/components/Option/Watchlists/shared/onboarding-path.ts`.
- Added onboarding path branch controls in `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/OverviewTab.tsx` with beginner/advanced defaults and direct advanced CTA.
- Added onboarding path configuration control in `apps/packages/ui/src/components/Option/Watchlists/SettingsTab/SettingsTab.tsx`.
- Added test coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/shared/__tests__/onboarding-path.test.ts`
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/SettingsTab/__tests__/SettingsTab.help.test.tsx`

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

### Stage 2 Completion Notes (2026-02-23)

- Expanded quick-setup contract in `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/quick-setup.ts`:
  - added `extraSourceUrls` and `includeAudioBriefing`,
  - updated job payload builder to support multi-feed scopes and briefing audio defaults,
  - added `parseQuickSetupExtraSourceUrls` helper for newline/comma import strings.
- Extended quick-setup execution in `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/OverviewTab.tsx`:
  - creates additional feeds via `bulkCreateSources` when extra URLs are provided,
  - blocks setup on partial multi-feed creation failures,
  - includes explicit audio briefing toggle in monitor step,
  - surfaces destination hints in review step (Activity vs Reports vs Monitors).
- Added setup-goal routing coverage and multi-feed flow coverage in
  `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`:
  - multi-feed success scope mapping,
  - multi-feed partial-failure prevention,
  - briefing+run-now routing to Activity,
  - triage/no-run routing to Monitors,
  - existing briefing/no-run routing to Reports retained.
- Updated helper tests in `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/__tests__/quick-setup.test.ts` for new defaults and parser behavior.
- Verification evidence:
  - `bunx vitest run src/components/Option/Watchlists/OverviewTab/__tests__/quick-setup.test.ts src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`
  - `bunx vitest run src/components/Option/Watchlists/OverviewTab/__tests__/quick-setup.test.ts src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx src/components/Option/Watchlists/OverviewTab/__tests__/pipeline-contract.test.ts src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/SettingsTab/__tests__/SettingsTab.help.test.tsx src/components/Option/Watchlists/shared/__tests__/onboarding-path.test.ts`
  - `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/Watchlists/OverviewTab -f json -o /tmp/bandit_watchlists_group02_stage2_2026_02_23.json`

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

### Stage 3 Completion Notes (2026-02-24)

- Expanded guided-tour concept coverage in `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx`:
  - monitor step now explicitly covers schedule/filters/template-output relationship,
  - reports step now includes template/audio regeneration discoverability.
- Added first-time contextual teach points with dismissal persistence:
  - storage key: `watchlists:teach-points:v1`,
  - `jobs` teach point: cron + advanced filter progressive-disclosure guidance,
  - `templates` teach point: preset-first + regenerate comparison guidance.
- Updated help topic copy to task-oriented guidance in:
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`,
  - `apps/packages/ui/src/components/Option/Watchlists/shared/WatchlistsHelpTooltip.tsx`.
- Added/updated tests:
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/shared/__tests__/WatchlistsHelpTooltip.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/shared/__tests__/__snapshots__/WatchlistsHelpTooltip.test.tsx.snap`
- Verification evidence:
  - `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.orientation-guidance.test.tsx src/components/Option/Watchlists/shared/__tests__/WatchlistsHelpTooltip.test.tsx src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts`

## Stage 4: Concept Burden Reduction in Copy
**Goal**: Reduce jargon and improve actionability of onboarding/UI copy.
**Success Criteria**:
- Beginner-facing copy avoids or explains cron/Jinja/regex terms at point of use.
- All setup actions have clear “what happens next” wording.
- Mixed terminology is removed from first-run surfaces.
**Tests**:
- Add snapshot tests for key onboarding copy blocks.
- Add copy contract tests for terminology consistency in first-run keys.
**Status**: Not Started

## Stage 5: Onboarding Effectiveness Validation
**Goal**: Validate that users reach first successful run and first report faster.
**Success Criteria**:
- Telemetry captures setup start, setup completion, first run success, first output success.
- Time-to-first-value and drop-off metrics are defined and reviewed.
- QA runbook includes beginner-path and power-path verification.
**Tests**:
- Add telemetry schema tests for onboarding events.
- Run onboarding regression suite for happy path and interruption recovery.
**Status**: Not Started
