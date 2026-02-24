# Watchlists UX Review Group 01 - Information Architecture and Navigation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align Watchlists navigation with user task mental models so users can move from intake to review to briefing without terminology friction.

**Architecture:** Introduce a task-oriented top-level navigation contract layered over existing watchlists entities, then standardize labels and cross-tab linking so each surface explains where the user is and what comes next.

**Tech Stack:** React, TypeScript, Ant Design Tabs/Buttons, i18n (`watchlists.json`), Zustand state routing, Vitest + Testing Library.

---

## Scope

- UX dimensions covered: IA and navigation clarity.
- Primary surfaces:
  - `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx`
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
  - `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/OverviewTab.tsx`
  - `apps/packages/ui/src/store/watchlists.tsx`
- Key outcomes:
  - Consistent user-facing terminology.
  - Task-forward navigation labels and entry points.
  - Reduced navigation ambiguity between Reports/Outputs, Feeds/Sources, Monitors/Jobs, Activity/Runs.

## Stage 1: IA Contract and Terminology Canonicalization
**Goal**: Define and lock the canonical user vocabulary and mapping to backend entities.
**Success Criteria**:
- A single terminology map exists and is referenced by all Watchlists tab labels and helper copy.
- Terms are consistent in tab labels, buttons, empty states, and call-to-action text.
- Internal naming remains unchanged in APIs/store while user-facing labels are unified.
**Tests**:
- Add i18n contract tests to validate expected tab labels and key aliases.
- Add UI tests that assert canonical labels in header tabs and quick actions.
**Status**: Complete

### Stage 1 Completion Notes (2026-02-23)

- Added canonical terminology map in `apps/packages/ui/src/assets/locale/en/watchlists.json` under `terminology.canonical` and `terminology.aliases`.
- Extended i18n contract coverage in `apps/packages/ui/src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts`.
- Added UI contract assertions for tab and task shortcut labels in `apps/packages/ui/src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx`.

## Stage 2: Task-Oriented Navigation Layer
**Goal**: Present primary user flows (Collect, Review, Briefings) without removing advanced capability.
**Success Criteria**:
- Primary navigation emphasizes user tasks and de-emphasizes implementation nouns.
- Secondary/advanced views remain available via explicit advanced controls.
- Users can reach Feeds, Articles, and Reports within one click from overview and global toolbar.
**Tests**:
- Add interaction tests for task-nav switching and fallback to detailed tab views.
- Add regression tests ensuring deep-link tab state still opens correct legacy surfaces.
**Status**: Complete

### Stage 2 Completion Notes (2026-02-23)

- Implemented task-view navigation strip (`Collect`, `Review`, `Briefings`) in `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx` behind the experimental IA flag.
- Added explicit task-to-tab routing and legacy-tab fallback mapping:
  - `collect -> sources` (also active for `jobs`)
  - `review -> items` (also active for `runs`)
  - `briefings -> outputs` (also active for `templates`)
- Updated reduced IA tab model so primary tabs align with outcomes (`overview`, `sources`, `items`, `outputs`, `settings`) while advanced implementation tabs are in `More views` (`jobs`, `runs`, `templates`).
- Extended interaction coverage in `apps/packages/ui/src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx`:
  - task-centered primary tab assertions
  - task-view click routing assertions
  - fallback highlighting assertions for deep-linked legacy tabs (`runs`, `templates`)
- Verification evidence:
  - `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx`
  - `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx src/components/Option/Watchlists/SettingsTab/__tests__/SettingsTab.help.test.tsx src/components/Option/Watchlists/shared/__tests__/onboarding-path.test.ts src/components/Option/Watchlists/OverviewTab/__tests__/pipeline-contract.test.ts`
  - `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/Watchlists -f json -o /tmp/bandit_watchlists_group01_stage2_2026_02_23.json`

## Stage 3: Cross-Surface Orientation and “Next Step” Guidance
**Goal**: Make current location and adjacent actions explicit in each tab.
**Success Criteria**:
- Each tab has contextual “what this is” and “what to do next” guidance.
- Cross-tab jump actions appear at key transition points (e.g., run -> reports, item -> monitor).
- Ambiguous destination actions are renamed to reflect expected outcome.
**Tests**:
- Add component tests for guidance banners and cross-navigation buttons.
- Add journey tests for Overview -> Feeds -> Monitors -> Activity -> Reports transitions.
**Status**: Not Started

## Stage 4: Experimental IA Rollout and Safety
**Goal**: Replace ad hoc IA experiment flags with a controlled rollout plan.
**Success Criteria**:
- Experimental IA and baseline IA behavior is feature-flagged with clear fallback behavior.
- Telemetry captures transitions and drop-off across nav variants.
- Product docs define go/no-go criteria for making reduced IA default.
**Tests**:
- Add tests for both flag states and secondary tab access.
- Add telemetry payload contract tests for IA transition events.
**Status**: Not Started

## Stage 5: Documentation and Adoption Validation
**Goal**: Ensure IA changes are operable by engineering, QA, and product stakeholders.
**Success Criteria**:
- Navigation map and vocabulary matrix are documented in `Docs`.
- QA checklist covers primary flows and terminology consistency.
- Adoption metrics baseline and post-change comparison are defined.
**Tests**:
- Run focused regression suite for navigation and tab behavior.
- Verify docs links and help topic routing against updated IA labels.
**Status**: Not Started
