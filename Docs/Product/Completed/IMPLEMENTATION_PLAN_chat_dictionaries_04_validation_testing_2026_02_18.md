# Implementation Plan: Chat Dictionaries - Validation and Testing Experience

## Scope

Components: validation and preview surfaces in `apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`, dictionary validation endpoints, preview transform UX, E2E validation journeys
Finding IDs: `4.1` through `4.6`

## Finding Coverage

- Validation discoverability and entry-point visibility: `4.1`
- Diagnostic actionability and row-level navigation: `4.2`
- Preview comparability and diff readability: `4.3`
- Preserve high-value existing behavior: `4.4`, `4.6`
- Test-case persistence for repetitive workflows: `4.5`

## Stage 1: Promote Validation and Preview to First-Class Actions
**Goal**: Make validation/testing features obvious and immediately accessible.
**Success Criteria**:
- Validation and preview controls move out of collapsed-only interaction.
- Entry manager header exposes clear validate and preview actions.
- Existing inline per-entry test popover remains intact and discoverable.
- Empty-entry guard behavior is preserved for full-dictionary validation.
**Tests**:
- Component tests for new action locations and enable/disable gating.
- Regression tests verifying inline entry test remains available.
- E2E tests for validate and preview flows without opening collapse panels.
**Status**: Complete
**Progress Notes (2026-02-18)**:
- Added an always-visible validation/preview action bar above the accordion panels inside entry management.
- Promoted strict-validation toggle and `Run validation`/`Run preview` controls out of collapse-only discovery path.
- Header actions now auto-open the relevant tools panel while executing validation/preview workflows.
- Preserved empty-entry validation guard with disabled validation action and visible guidance text.
- Added Stage 1 component tests covering action discoverability, guard behavior, and retention of inline per-entry test controls.

## Stage 2: Actionable Validation Output and Rich Preview Diff
**Goal**: Reduce debugging time by linking errors directly to editable content.
**Success Criteria**:
- Validation list items are clickable and scroll to matching entry row.
- Target row receives temporary highlight state when jumped to from results.
- Preview panel supports side-by-side or inline diff highlighting changed spans.
- Diff view remains performant for moderate input lengths.
**Tests**:
- Component tests for clickable validation item behavior.
- Integration tests for row highlight lifecycle after navigation.
- Snapshot/visual tests for diff rendering semantics.
**Status**: Complete
**Progress Notes (2026-02-18)**:
- Validation errors/warnings that reference `entries[n]` now render as actionable buttons.
- Clicking a validation item scrolls to the corresponding entry row and applies temporary row highlight styling.
- Added lightweight diff rendering in preview results with explicit original/processed panes and changed-span emphasis (insertions and removals).
- Diff rendering handles unchanged output with a clear "no differences" fallback state.
- Added component tests for clickable validation navigation, row highlight behavior, and diff preview rendering after transform runs.

## Stage 3: Persisted Test Inputs and Authoring Efficiency
**Goal**: Support repeated validation/testing loops without re-entry overhead.
**Success Criteria**:
- Last preview text persists across panel close/reopen (session scoped or local storage).
- Optional saved test cases can be named, selected, and deleted.
- Saved test-case model is dictionary-scoped to avoid cross-contamination.
**Tests**:
- Unit tests for persistence adapter and keying by dictionary ID.
- Integration tests for save/select/delete test-case lifecycle.
- E2E test for reopening entry manager and recovering previous preview text.
**Status**: Complete
**Progress Notes (2026-02-18)**:
- Added dictionary-scoped preview draft persistence via local storage (`preview-draft` key per dictionary ID).
- Added dictionary-scoped saved test-case management with named save/load/delete actions.
- Persisted saved test-case collections per dictionary using dedicated local-storage keys.
- Added component tests covering reopen draft recovery and saved test-case lifecycle operations.
- Existing validation/preview actions remain compatible with persisted draft and saved-case workflows.

## Dependencies

- Row-linking behavior depends on stable row keying in the entry table.
- Diff rendering implementation should align with responsive strategy in Category 9.
