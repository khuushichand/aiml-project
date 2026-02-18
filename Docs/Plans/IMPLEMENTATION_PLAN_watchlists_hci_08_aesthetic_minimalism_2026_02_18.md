# Implementation Plan: Watchlists H8 - Aesthetic and Minimalist Design

## Scope

Route/components: `WatchlistsPlaygroundPage`, `RunsTab`, `SettingsTab`, high-density table toolbars/cards  
Finding IDs: `H8.1` through `H8.3`

## Finding Coverage

- Information architecture overload from seven top-level tabs: `H8.1`
- Redundant controls in dense toolbars: `H8.2`
- Internal-facing diagnostics exposed in end-user settings: `H8.3`

## Stage 1: Remove Internal Noise and Redundant UI
**Goal**: Eliminate obvious non-user-facing clutter first.
**Success Criteria**:
- "Phase 3 Readiness" card is removed or relocated to admin-only diagnostics.
- Runs export controls are simplified (single split button or equivalent concise control).
- Settings copy and cards show only user-actionable information.
**Tests**:
- Component tests for settings card visibility and role gating.
- Snapshot tests for runs toolbar layout simplification.
- Regression tests ensuring export behavior is unchanged.
**Status**: Not Started

## Stage 2: Progressive Disclosure in Dense Screens
**Goal**: Preserve capability while reducing default cognitive load.
**Success Criteria**:
- Advanced controls in Runs/Jobs/Outputs are hidden behind clear "advanced" affordances.
- Data-heavy status tags gain concise summaries with expandable details.
- Default table views prioritize top 3 decision-driving fields per row.
**Tests**:
- Visual regression tests for default vs advanced states.
- Component tests for disclosure state persistence.
- UX checklist validation for reduced first-screen control count.
**Status**: Not Started

## Stage 3: Navigation Simplification Experiment
**Goal**: Evaluate reduced-information-architecture model before permanent migration.
**Success Criteria**:
- Prototype and feature-flagged variant of merged tab model (for example 5-tab structure) is implemented.
- Comparative usability metrics collected (time-to-first-briefing, tab hops, error rate).
- Final IA recommendation documented with migration and fallback plan.
**Tests**:
- E2E coverage for both legacy and experimental tab maps behind flag.
- Analytics verification tests for tab-navigation instrumentation.
- QA route integrity tests for deep links/bookmarks during IA experiment.
**Status**: Not Started

## Dependencies

- Navigation experiments should coordinate with H2 terminology updates.
- Role-based diagnostics separation should align with admin UI conventions.
