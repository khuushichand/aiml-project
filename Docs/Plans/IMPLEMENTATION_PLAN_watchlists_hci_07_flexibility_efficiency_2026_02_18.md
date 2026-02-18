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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Shortcut schema should be consistent with app-wide keyboard conventions.
- Quick-create flow should share onboarding state with H2 and help surfaces with H10.
