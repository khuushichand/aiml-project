# Implementation Plan: Per-Page Active Tutorials + Quick Chat Tutorials Section

## Context

The WebUI already has a tutorial framework (`TutorialRunner`, `TutorialPrompt`, `PageHelpModal`, `tutorials/registry.ts`) and a separate Quick Chat helper mode with curated workflow Q&A cards (`browse_guides`).

Current gaps to close:

1. Tutorial coverage is effectively limited to Playground definitions and does not yet scale across core pages.
2. Existing tutorial route patterns use legacy path shapes (for example `/options/playground`) while current route definitions use canonical paths like `/chat`, `/media`, `/knowledge`, etc.
3. Quick Chat "Browse Guides" currently shows only Q&A workflow cards; it does not expose runnable per-page tutorials as a dedicated section.

## Goals

1. Enable active guided tutorials (Joyride) across priority pages.
2. Add a separate `Tutorials` section in Quick Chat Browse Guides, displayed above Q&A workflow cards and scoped to the current page.
3. Keep tutorial authoring maintainable with clear conventions, shared route matching rules, and documentation.

## Non-Goals (for this pass)

1. Full tutorial coverage for every experimental/admin route in one release.
2. Replacing workflow cards with tutorials (they serve different jobs).
3. Building backend telemetry pipelines for tutorial analytics.

## Stage 1: Route Alignment + Tutorial Discovery Baseline
**Goal**: Ensure tutorial route matching reflects real app routes and supports current navigation patterns.
**Success Criteria**:
- Tutorial definitions use canonical route paths (for example `/chat`, `/workspace-playground`, `/media`, `/knowledge`).
- Route matcher remains backward-safe for legacy aliases where needed.
- `getTutorialsForRoute()` returns expected tutorials for canonical paths.
- Add a page-priority matrix for first rollout (P0/P1 pages).
**Tests**:
- Unit tests for route matching exact/wildcard/legacy alias behavior.
- Unit tests for `getPrimaryTutorialForRoute()` on canonical paths.
- Manual smoke: opening `?` help modal on priority pages shows Tutorials tab with expected count.
**Status**: Complete

## Stage 2: Quick Chat "Tutorials" Section (Above Workflow Q&A Cards)
**Goal**: Extend Browse Guides UI with a dedicated per-page tutorials panel that can launch active tours.
**Success Criteria**:
- `QuickChatGuidesPanel` renders `Tutorials for this page` first, then existing workflow card list.
- Tutorial entries display title, short description, step count, and completion status.
- Buttons support `Start`/`Replay` and call tutorial store actions (`startTutorial`).
- Empty-state copy is shown when current page has no tutorials, without hiding workflow cards.
- Existing Q&A browse behavior remains unchanged.
**Tests**:
- Component test: renders tutorials section when route has tutorials.
- Component test: hides section body and shows empty-state when no per-page tutorials.
- Component test: clicking tutorial start triggers `startTutorial` and closes helper if expected UX requires it.
- Regression tests for workflow-card search/filtering and ask/open actions.
**Status**: Complete

## Stage 3: Per-Page Tutorial Content Rollout (P0 then P1)
**Goal**: Deliver useful tutorials on core pages with stable step targets.
**Success Criteria**:
- P0 tutorials shipped for: `/chat`, `/workspace-playground`, `/media`, `/knowledge`, `/characters`.
- Each page has at least one "basics" tutorial and optional follow-up workflow tutorial(s).
- Each step target uses stable `data-testid` anchors; missing anchors are added where required.
- Prerequisites/priority order used to guide progression (basics before advanced).
**Tests**:
- For each P0 page: unit/component assertion that required target selectors exist.
- Manual walkthrough test per tutorial: no hard break on missing target; graceful skip/end behavior works.
- Manual accessibility pass: keyboard navigation and Escape behavior in help modal + Joyride controls.
**Status**: Complete

## Stage 4: UX Reliability and Guardrails
**Goal**: Make tutorial runs robust during async rendering and route transitions.
**Success Criteria**:
- Add guardrails for delayed/mounted targets (retry/wait strategy before `TARGET_NOT_FOUND` skip).
- Prevent duplicate prompt spam across rapid route changes.
- Define stable fallback behavior when a tutorial target is hidden behind collapsed panels.
- Ensure sidepanel/options contexts do not cross-trigger incorrect tutorials.
**Tests**:
- Unit test(s) for target-not-found progression/fallback logic.
- Integration test for first-visit prompt show-once semantics by route.
- Manual regression across route transitions during active tutorial.
**Status**: Not Started

## Stage 5: Docs + Authoring Workflow
**Goal**: Make tutorial creation/editing self-serve for contributors.
**Success Criteria**:
- Update tutorial developer docs with canonical route table and "add a page tutorial" checklist.
- Add user-facing guide section describing where Tutorials appear (Help modal and Quick Chat Browse Guides).
- Document how to add/edit tutorial definitions and required `data-testid` anchors.
- Include a short QA checklist for validating new tutorials before merge.
**Tests**:
- Docs review pass for path accuracy against `route-registry.tsx`.
- Manual dry-run: create one new tutorial from docs only and confirm it appears/run.
**Status**: Complete

## Suggested Rollout Order

1. Stage 1 + Stage 2 together (foundation + visible feature value).
2. Stage 3 P0 page bundle.
3. Stage 4 hardening.
4. Stage 3 P1 expansion (`/prompts`, `/evaluations`, `/notes`, `/flashcards`, `/world-books`).
5. Stage 5 docs finalization.

## Key Risks and Mitigations

1. Risk: tutorial selectors become brittle when UI refactors.
   Mitigation: standardize tutorial-target `data-testid` contracts and add selector-existence tests.
2. Risk: route mismatch causes hidden tutorials.
   Mitigation: canonical-path-only definitions + matcher tests + route table in docs.
3. Risk: cluttered Quick Chat panel.
   Mitigation: keep tutorials section compact and collapsible if card count grows.

## Exit Criteria

1. Users can discover and launch page-specific active tutorials from both `?` Help and Quick Chat Browse Guides.
2. Priority pages each have at least one working tutorial with stable targets.
3. Contributor docs explain exactly how to add/modify tutorials and validate them.
