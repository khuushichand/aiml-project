# Implementation Plan: World Books - Character Attachment Matrix

## Scope

Components: Relationship Matrix modal, per-book attach modal, attachment state mutations, and attachment metadata controls.
Finding IDs: `5.1` through `5.5`

## Finding Coverage

- Matrix scalability and mobile-readiness concerns: `5.1`
- Interaction clarity and feedback in-session: `5.2`, `5.5`
- Attachment metadata controls and parity: `5.3`
- IA simplification between quick and advanced attach flows: `5.4`

## Stage 1: Introduce Scalable Attachment Views
**Goal**: Keep attachment management usable as character count grows.
**Success Criteria**:
- Define threshold-based view switch (matrix for small sets, list/multi-select for large sets).
- Add pagination/grouping behavior for large character sets to avoid horizontal overflow.
- Preserve attach/detach parity and keyboard accessibility in both view modes.
**Tests**:
- Component tests for automatic view-mode switch by character count threshold.
- Integration tests for attach/detach operations in matrix mode and list mode.
- Responsive tests confirming usable layout on narrow viewports.
**Status**: Not Started

## Stage 2: Improve Toggle Feedback and Session Diff Visibility
**Goal**: Make attachment changes visible and confidence-inspiring before save/close.
**Success Criteria**:
- Distinguish newly attached and newly detached cells visually until modal close.
- Add success micro-feedback on toggle completion while preserving non-disruptive UX.
- Keep failure handling explicit with reverted checkbox state and error details.
**Tests**:
- Component tests for visual delta states (newly attached/detached).
- Integration tests for optimistic update -> API success and API failure rollback.
- UI tests verifying success feedback appears for matrix toggles.
**Status**: Not Started

## Stage 3: Expose Per-Attachment Priority and Enabled Controls
**Goal**: Support full `CharacterWorldBookAttachment` schema from matrix workflow.
**Success Criteria**:
- Add per-cell metadata edit affordance (popover/menu) for `priority` and `enabled`.
- Display compact priority indicator in attached cells where feasible.
- Persist metadata updates without requiring detach/reattach cycles.
**Tests**:
- Integration tests for metadata update payloads and persisted values.
- Component tests for metadata editor open/save/cancel behavior.
- Regression tests for compatibility with existing attach endpoint semantics.
**Status**: Not Started

## Stage 4: Clarify Quick-Attach vs Full-Matrix Paths
**Goal**: Reduce confusion from overlapping attachment workflows.
**Success Criteria**:
- Reframe per-book modal as `Quick attach` workflow.
- Add explicit navigation to `Open full matrix` for advanced bulk management.
- Align copy and action labels across both experiences.
**Tests**:
- Component tests for quick-attach labeling and full-matrix navigation CTA.
- UX regression tests ensuring no duplicated or contradictory actions remain.
**Status**: Not Started

## Dependencies

- Stage 3 may require endpoint support for patching attachment metadata independently of attach/detach operations.
