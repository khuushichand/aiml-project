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
**Status**: Complete

### Stage 1 Implementation Notes (2026-02-18)
- Removed internal-facing readiness content from default `SettingsTab` surface:
  - Replaced the generic settings description with user-actionable copy focused on retention + cluster subscriptions.
  - Relocated internal diagnostics fields behind an explicit environment gate (`NEXT_PUBLIC_WATCHLISTS_SHOW_INTERNAL_DIAGNOSTICS=true`), hidden by default.
- Simplified `RunsTab` CSV export controls to a compact split action:
  - Main export action now includes current mode context in button text.
  - Mode selection moved into a compact dropdown options trigger that can export directly in one step.
  - Preserved existing CSV behavior for standard, per-run tallies, and global aggregate tallies modes.
- Added/updated regression coverage:
  - `RunsTab.export-csv-modes.test.tsx` validates aggregate + per-run export request payloads through the new split control.
  - `SettingsTab.help.test.tsx` validates diagnostics visibility gating (hidden by default, visible when explicitly enabled).

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
**Status**: Complete

### Stage 2 Implementation Notes (2026-02-18)
- Added progressive disclosure controls for dense toolbars:
  - `RunsTab` now uses a persisted `Show advanced filters` toggle (`watchlists:runs:advanced-filters:v1`).
  - `OutputsTab` now uses a persisted `Show advanced filters` toggle (`watchlists:outputs:advanced-filters:v1`).
- Added progressive disclosure controls for dense monitor table details:
  - `JobsTab` now uses a persisted `Show advanced details` toggle (`watchlists:jobs:advanced-columns:v1`).
- Reduced default cognitive load by prioritizing core table columns until advanced mode is opened:
  - `RunsTab`: default columns now focus on monitor/status/start time/actions.
  - `JobsTab`: default columns now focus on name/schedule/active/actions, with compact scope+filter summary in-row.
  - `OutputsTab`: default columns now focus on title/monitor/created/delivery/actions.
- Added dense delivery-status summarization for outputs:
  - Collapsed mode now shows one primary delivery status with `+N more` disclosure.
  - Overflow statuses are available through a tooltip details view (channel/status/detail).
  - Added helper `buildDeliveryDisclosureSummary` in `OutputsTab/outputMetadata.ts`.
- Added regression coverage:
  - `RunsTab.advanced-filters.test.tsx`
  - `JobsTab.advanced-details.test.tsx`
  - `OutputsTab.advanced-filters.test.tsx`
  - `OutputsTab/outputMetadata.test.ts` coverage for collapsed/expanded delivery disclosure summaries.
  - `apps/extension/tests/e2e/watchlists.spec.ts` smoke flow now asserts collapsed-default advanced controls and the reports `+N more` delivery summary path.

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
**Status**: Complete

### Stage 3 Implementation Notes (2026-02-18)
- Added a feature-flagged IA prototype in `WatchlistsPlaygroundPage`:
  - Flag: `NEXT_PUBLIC_WATCHLISTS_EXPERIMENTAL_IA=true`
  - Runtime override for QA/tests: `window.__TLDW_WATCHLISTS_IA_EXPERIMENT__`
  - Reduced default top-level tabs to 5: `Overview`, `Feeds`, `Activity`, `Reports`, `Settings`.
  - Added `More views` quick-access controls for `Monitors`, `Articles`, and `Templates`.
  - Preserved deep-link and guided-flow compatibility by injecting hidden tabs back into the rendered tab list when currently active.
- Added lightweight navigation telemetry persistence for experiment sessions:
  - localStorage key: `watchlists:ia-experiment:v1`
  - captures transition count and visited tab keys for comparative analysis.
- Added regression coverage:
  - `WatchlistsPlaygroundPage.experimental-ia.test.tsx`
  - legacy tab-map behavior when experiment is disabled
  - telemetry transition assertions for experimental sessions
  - hidden-tab route integrity assertions (`jobs`/`items`/`templates`)
- Added final IA recommendation + migration/fallback decision record:
  - `Docs/Plans/DECISION_RECORD_watchlists_h8_stage3_ia_experiment_2026_02_19.md`

## Dependencies

- Navigation experiments should coordinate with H2 terminology updates.
- Role-based diagnostics separation should align with admin UI conventions.
