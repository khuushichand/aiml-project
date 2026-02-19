# Implementation Plan: Watchlists H7 - Flexibility and Efficiency of Use

## Scope

Route/components: `ItemsTab`, global watchlists keyboard handling, filter/search state management, quick-create path  
Finding IDs: `H7.1` through `H7.5`

## Finding Coverage

- Missing keyboard and power-user interactions: `H7.1`
- No batch triage in high-volume item review: `H7.2`
- No saved/pinned filters for recurring workflows: `H7.3`
- Missing higher-efficiency organization/creation paths: `H7.4`, `H7.5`

## Stage 1: Batch Triage and Throughput Controls
**Goal**: Reduce click cost for reviewing large item sets.
**Success Criteria**:
- Items list supports multi-select and batch "mark reviewed" action.
- "Mark page as reviewed" and "mark all filtered as reviewed" actions are available with confirmations.
- Items page size is user-configurable and persisted.
**Tests**:
- Component tests for selection model and batch action enable/disable states.
- Integration tests for batch reviewed count updates and pagination effects.
- E2E test for reviewing 50+ items with batch controls.
**Status**: Complete

### Stage 1 Implementation Notes (2026-02-18)
- Added batch triage controls in `ItemsTab`:
  - Multi-select rows with per-page select toggle.
  - `Mark selected`, `Mark page`, and `Mark all filtered` reviewed actions with confirmation.
  - Batched update execution with partial-failure messaging.
- Added configurable page size (`20/25/50/100`) with local persistence.
- Added i18n keys for batch actions and page-size labels in watchlists locale files.
- Added test coverage:
  - Unit: `items-utils` page-size persistence and normalization.
  - Component: `ItemsTab.batch-controls` for selection enablement, confirmation, and persistence behavior.
  - E2E: `watchlists.spec.ts` scenario for 50+ item triage throughput.
- Validation:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx` (pass)
  - `bunx playwright test tests/e2e/watchlists.spec.ts` (suite compiled; all tests skipped locally due extension launch constraints in current environment)

## Stage 2: Keyboard-First Navigation
**Goal**: Enable fast triage without mouse dependence.
**Success Criteria**:
- Shortcuts implemented: `j/k` navigation, `space` toggle reviewed, `o` open original, `r` refresh, `n` new flow.
- Shortcut help overlay is discoverable and conflict-safe with text inputs.
- Focus management supports shortcut actions in 3-pane reader layout.
**Tests**:
- Keyboard interaction tests for each shortcut path.
- Accessibility tests for focus-visible and keyboard trap avoidance.
- E2E test for end-to-end unread triage using keyboard only.
**Status**: Complete

### Stage 2 Implementation Notes (2026-02-18)
- Added keyboard shortcuts in `ItemsTab`:
  - `j` / `k` move selected article up/down.
  - `space` toggles reviewed state for selected article.
  - `o` opens selected original URL in a new tab.
  - `r` refreshes feeds, article list, and smart counts.
  - `n` starts create flow by switching to Feeds and opening Add Source.
  - `?` opens keyboard shortcut help panel.
- Added shortcut safety and conflict handling:
  - Shortcuts are ignored in editable targets (`input`, `textarea`, `select`, contenteditable).
  - Shortcut dispatch is suppressed while the help modal is open (except `Escape`).
- Added discoverable help affordance:
  - `Shortcuts` button + tooltip in `ItemsTab` header.
  - Keyboard help modal listing keys and actions.
- Added validation:
  - Component tests for keyboard navigation, action shortcuts, input-focus safety, and help panel entry points.
  - E2E scenario added for keyboard-only article triage (`j/k/space/o/r/n` path).
- Validation commands:
  - `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx` (pass)
  - `bunx playwright test tests/e2e/watchlists.spec.ts` (suite compiled; all tests skipped locally due extension launch constraints in current environment)

## Stage 3: Saved Views and Quick-Create Workflow
**Goal**: Make frequent workflows one-step operations.
**Success Criteria**:
- Users can save/pin filter presets at tab scope.
- Empty/first-run experience offers quick create flow for source + job + first run.
- Source grouping interactions support faster reassignment pattern (drag/drop or equivalent quick move control).
**Tests**:
- Integration tests for preset save/load/delete lifecycle.
- E2E test for quick create completion in <= 3 guided steps.
- Component tests for source move interaction and fallback controls.
**Status**: Complete

### Stage 3 Progress Notes (2026-02-18)
- Implemented saved/pinned filter presets in `ItemsTab`:
  - Save current filter set (source, smart feed, status, search query).
  - Apply preset from dropdown.
  - Update active preset in place.
  - Delete active preset with confirmation.
  - Persist presets to local storage.
- Added supporting persistence helpers in `items-utils` with validation/normalization.
- Added test coverage:
  - Utility tests for preset persistence load/save behavior.
  - Component test for preset save/apply/delete lifecycle.
- Implemented guided quick-create flow in `OverviewTab`:
  - Added a 3-step modal (`Feed -> Monitor -> Review`) launched from onboarding via `Guided setup`.
  - Wired single-flow creation for source + monitor + optional run-now trigger.
  - Added payload helpers in `OverviewTab/quick-setup.ts` and defensive normalization for unset fields.
- Implemented fast source reassignment in `SourcesTab`:
  - Added bulk action controls to move selected feeds to a chosen group (or clear group assignment).
  - Added confirmation messaging, partial-failure handling, and undo restore for previous `group_ids`.
- Expanded verification coverage:
  - Unit: `OverviewTab/__tests__/quick-setup.test.ts`
  - Component: `OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx`
  - Component: `SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx`
  - E2E: `apps/extension/tests/e2e/watchlists.spec.ts` now includes `guided quick setup creates feed and monitor in three steps`
- Stabilization update:
  - Fixed unstable `useTranslation` test mock in `SourcesTab.bulk-move` coverage so the reassignment harness runs deterministically and Stage 3 verification is complete.

## Dependencies

- Shortcut schema should be consistent with app-wide keyboard conventions.
- Quick-create flow should share onboarding state with H2 and help surfaces with H10.
