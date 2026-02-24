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

### Stage 1 Execution Notes (2026-02-23)

- Canonical terminology contracts were established and validated for Watchlists tab/section nouns and plain-language helper copy:
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts`
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts`
- Canonical user-facing labels remain aligned for `Feeds`, `Monitors`, `Activity`, `Articles`, and `Reports` across tab and section surfaces.

### Stage 1 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts`

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

### Stage 2 Execution Notes (2026-02-23)

- Task-oriented shortcut navigation (`Collect`, `Review`, `Briefings` entry points via quick actions) and reduced-IA fallback behavior are now validated through interaction coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx`
- Experimental IA mode preserves one-click access to secondary/advanced views while keeping legacy routes reachable.

### Stage 2 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx`

## Stage 3: Cross-Surface Orientation and “Next Step” Guidance
**Goal**: Make current location and adjacent actions explicit in each tab.
**Success Criteria**:
- Each tab has contextual “what this is” and “what to do next” guidance.
- Cross-tab jump actions appear at key transition points (e.g., run -> reports, item -> monitor).
- Ambiguous destination actions are renamed to reflect expected outcome.
**Tests**:
- Add component tests for guidance banners and cross-navigation buttons.
- Add journey tests for Overview -> Feeds -> Monitors -> Activity -> Reports transitions.
**Status**: Complete

### Stage 3 Execution Notes (2026-02-23)

- Added cross-surface orientation guidance banner to Watchlists shell with per-tab:
  - “What this is” context
  - “What to do next” guidance
  - explicit cross-tab action buttons
  - `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx`
- Added explicit transition actions for key handoffs:
  - Activity (`runs`) -> Reports (`outputs`)
  - Articles (`items`) -> Monitors (`jobs`)
- Added localized copy contract for orientation guidance and destination-explicit action labels:
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
- Added Stage 3 regression coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.orientation-guidance.test.tsx`
  - includes journey path validation for `Overview -> Feeds -> Monitors -> Activity -> Reports`.

### Stage 3 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.orientation-guidance.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts`
- `/tmp/bandit_watchlists_group01_stage3_frontend_scope_2026_02_23.json`

## Stage 4: Experimental IA Rollout and Safety
**Goal**: Replace ad hoc IA experiment flags with a controlled rollout plan.
**Success Criteria**:
- Experimental IA and baseline IA behavior is feature-flagged with clear fallback behavior.
- Telemetry captures transitions and drop-off across nav variants.
- Product docs define go/no-go criteria for making reduced IA default.
**Tests**:
- Add tests for both flag states and secondary tab access.
- Add telemetry payload contract tests for IA transition events.
**Status**: Complete

### Stage 4 Execution Notes (2026-02-23)

- Replaced ad hoc IA variant resolution with a controlled rollout resolver:
  - `apps/packages/ui/src/utils/watchlists-ia-rollout.ts`
  - Supports prioritized controls:
    - runtime override (`window.__TLDW_WATCHLISTS_IA_EXPERIMENT__`)
    - persisted rollout assignment (`watchlists:ia-rollout:v1`)
    - forced env variant (`NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_VARIANT`)
    - percentage rollout (`NEXT_PUBLIC_WATCHLISTS_IA_EXPERIMENT_PERCENT`)
    - safe fallback to baseline.
- Wired Watchlists shell to use rollout variant resolution directly:
  - `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx`
- Added rollout safety regression coverage:
  - `apps/packages/ui/src/utils/__tests__/watchlists-ia-rollout.test.ts`
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx`
  - includes persisted assignment validation and secondary-tab access behavior under experimental mode.
- Added explicit IA telemetry payload contract coverage for backend ingest schema fields:
  - `apps/packages/ui/src/utils/__tests__/watchlists-ia-experiment-telemetry.test.ts`
- Published rollout go/no-go criteria and rollback procedure:
  - `Docs/Plans/WATCHLISTS_IA_EXPERIMENT_ROLLOUT_GONOGO_2026_02_23.md`

### Stage 4 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.orientation-guidance.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.run-notifications.test.tsx src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/utils/__tests__/watchlists-ia-experiment-telemetry.test.ts src/utils/__tests__/watchlists-ia-rollout.test.ts`
- `/tmp/bandit_watchlists_group01_stage4_frontend_scope_2026_02_23.json`

## Stage 5: Documentation and Adoption Validation
**Goal**: Ensure IA changes are operable by engineering, QA, and product stakeholders.
**Success Criteria**:
- Navigation map and vocabulary matrix are documented in `Docs`.
- QA checklist covers primary flows and terminology consistency.
- Adoption metrics baseline and post-change comparison are defined.
**Tests**:
- Run focused regression suite for navigation and tab behavior.
- Verify docs links and help topic routing against updated IA labels.
**Status**: Complete

### Stage 5 Execution Notes (2026-02-23)

- Published Group 01 IA adoption playbook with:
  - canonical navigation map (task -> surface -> next-step flow)
  - vocabulary matrix (internal nouns vs canonical user-facing labels)
  - QA checklist for journey, terminology, and help-link routing validation
  - adoption baseline + post-change comparison template tied to Stage 1 telemetry exports
  - `Docs/Plans/WATCHLISTS_IA_NAVIGATION_ADOPTION_PLAYBOOK_2026_02_23.md`
- Extended help-link routing regression coverage to verify all tab destinations and tab-aligned help labels:
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx`

### Stage 5 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/shared/__tests__/help-docs.test.ts src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.orientation-guidance.test.tsx src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts src/routes/__tests__/option-watchlists.route-state.test.tsx src/utils/__tests__/watchlists-ia-experiment-telemetry.test.ts src/utils/__tests__/watchlists-ia-rollout.test.ts`
- `bun run test:watchlists:help`
- `Docs/Plans/WATCHLISTS_IA_NAVIGATION_ADOPTION_PLAYBOOK_2026_02_23.md`
- `/tmp/bandit_watchlists_group01_stage5_frontend_scope_2026_02_23.json`
