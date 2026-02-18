# Implementation Plan: Watchlists H4 - Consistency and Standards

## Scope

Route/components: cross-tab layout patterns, action placement, `SourceFormModal`, `RunDetailDrawer` i18n  
Finding IDs: `H4.1` through `H4.5`

## Finding Coverage

- Uneven layout and control placement patterns: `H4.1`, `H4.2`, `H4.3`
- Ambiguous disabled controls and missing rationale: `H4.4`
- Hardcoded copy outside localization system: `H4.5`

## Stage 1: Pattern Inventory and Target Standards
**Goal**: Define explicit page-level UI standards before refactor work.
**Success Criteria**:
- Documented standard for table action placement, icon-label usage, and empty states.
- Decision record for when 3-pane layouts are acceptable vs table layouts.
- Shared action bar/table utility usage plan across tabs.
**Tests**:
- Visual regression baseline snapshots for all watchlists tabs.
- Lint/style checks for prohibited ad hoc action button patterns (where feasible).
- QA checklist for consistency acceptance criteria.
**Status**: Not Started

## Stage 2: UI Convergence Pass
**Goal**: Apply the agreed standards to inconsistent tabs and controls.
**Success Criteria**:
- Action placement is normalized across Sources/Jobs/Runs/Outputs/Templates.
- Disabled "Forum" source type includes explanatory tooltip or inline rationale.
- Icon-only controls in dense tables gain accessible labels and consistent tooltip pattern.
**Tests**:
- Component tests asserting control visibility/placement per tab.
- Accessibility checks for icon buttons and disabled-state explanation.
- E2E smoke tests for critical actions after layout adjustments.
**Status**: Not Started

## Stage 3: Localization and Copy Consistency
**Goal**: Remove hardcoded strings and standardize wording.
**Success Criteria**:
- `RunDetailDrawer` labels use i18n keys only.
- New/updated labels follow approved terminology glossary from H2.
- Localization fallback behavior verified for missing keys.
**Tests**:
- Unit tests for i18n key resolution and fallback behavior.
- Snapshot tests for run detail drawer locale rendering.
- Regression tests for tab-level translation bundle loading.
**Status**: Not Started

## Dependencies

- Terminology source of truth should come from H2 plan before final copy freeze.
- Accessibility enforcement should align with the dedicated accessibility findings backlog.
