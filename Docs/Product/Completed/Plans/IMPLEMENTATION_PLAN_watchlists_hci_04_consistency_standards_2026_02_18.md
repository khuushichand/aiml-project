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
**Status**: Complete

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
**Status**: Complete

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
**Status**: Complete

## Dependencies

- Terminology source of truth should come from H2 plan before final copy freeze.
- Accessibility enforcement should align with the dedicated accessibility findings backlog.

## Progress Notes

- 2026-02-18: Added explicit disabled-state rationale for `Forum` source type in `SourceFormModal` by relabeling it to `Forum (coming soon)` and adding form helper text.
- 2026-02-18: Added regression coverage for forum disabled rationale in `SourceFormModal.forum-help.test.tsx`.
- 2026-02-18: Removed hardcoded run-detail statistics/error/filter labels in `RunDetailDrawer` and moved them to i18n keys under `watchlists:runs.detail.*`.
- 2026-02-18: Added matching locale keys to both locale bundles:
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
  - `apps/packages/ui/src/public/_locales/en/watchlists.json`
- 2026-02-18: Normalized icon-only action controls with explicit `aria-label` + tooltip parity across Feeds/Monitors/Activity/Reports/Templates tabs and Groups panel.
- 2026-02-18: Aligned action-column widths across Sources/Jobs/Runs/Outputs/Templates tables to a consistent `140px` target for cross-tab visual rhythm.
- 2026-02-18: Added disabled `Run Now` rationale copy (`runNowDisabledHint`) so inactive monitor actions explain why execution is unavailable.
- 2026-02-18: Localized remaining `RunDetailDrawer` hardcoded copy:
  - run-details load error fallback now uses `watchlists:runs.detail.loadError`;
  - duration strings now resolve from `watchlists:runs.detail.duration.*`;
  - source-id fallback/tooltip copy now uses `watchlists:runs.detail.itemsSourceReference`.
- 2026-02-18: Added matching locale keys to both watchlists locale bundles for the above run-detail copy (`assets/locale` and `public/_locales`).
- 2026-02-18: Added run-detail i18n regression coverage in `RunDetailDrawer.source-column.test.tsx` for duration-key rendering and load-error fallback behavior.
- 2026-02-18: Verified Watchlists regression suite remains green after localization pass (`38` files, `116` tests).
- 2026-02-18: Completed Stage 1 standards artifacts:
  - pattern inventory and target standards: `WATCHLISTS_UI_CONSISTENCY_STANDARDS_2026_02_18.md`
  - layout decision record (3-pane vs table-first): `DECISION_RECORD_watchlists_layout_model_stage1_2026_02_18.md`
  - consistency QA acceptance checklist: `WATCHLISTS_CONSISTENCY_QA_CHECKLIST_2026_02_18.md`
