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
**Status**: Complete

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
**Status**: Complete

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
**Status**: Complete

## Stage 4: Clarify Quick-Attach vs Full-Matrix Paths
**Goal**: Reduce confusion from overlapping attachment workflows.
**Success Criteria**:
- Reframe per-book modal as `Quick attach` workflow.
- Add explicit navigation to `Open full matrix` for advanced bulk management.
- Align copy and action labels across both experiences.
**Tests**:
- Component tests for quick-attach labeling and full-matrix navigation CTA.
- UX regression tests ensuring no duplicated or contradictory actions remain.
**Status**: Complete

## Dependencies

- Stage 3 may require endpoint support for patching attachment metadata independently of attach/detach operations.

## Progress Notes (2026-02-18)

- Implemented Stage 1 scalable attachment views in `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - added automatic attachment view switch:
    - matrix mode for desktop with <= 10 filtered characters.
    - list/multi-select mode for mobile or larger character sets.
  - added list-mode table pagination (`8` world books per page) to keep large datasets manageable.
  - added list-mode per-book multi-select attachment control and `Detach all` action.
  - retained matrix-mode attach/detach checkboxes with explicit aria-labels.
- Added Stage 1 tests:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.attachmentStage1.test.tsx`
  - validates threshold-based mode switching, matrix attach/detach toggles, and mobile list-mode attach + detach-all.
- Validation run:
  - `bunx vitest run src/components/Option/WorldBooks/__tests__` (from `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui`)
  - result: **21 passed / 21 files**, **59 passed / 59 tests**.
- Implemented Stage 2 session-diff feedback in `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - added per-cell session delta states (`attached` / `detached`) that persist until modal close.
  - added subtle success pulse/highlight and inline micro-feedback status messages for toggle success.
  - added explicit inline failure feedback containing error details and reverted-state messaging.
  - added list-mode delta chips (`+new`, `-removed`) so session changes remain visible outside matrix mode.
- Added Stage 2 tests:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.attachmentStage2.test.tsx`
  - validates matrix delta visuals, success micro-feedback, failure/revert messaging, and list-mode delta chips.
- Validation run:
  - `bunx vitest run src/components/Option/WorldBooks/__tests__` (from `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui`)
  - result: **22 passed / 22 files**, **62 passed / 62 tests**.
- Implemented Stage 3 per-attachment metadata controls:
  - updated attach client integration to support optional attachment metadata payload (`enabled`, `priority`) while preserving existing toggle semantics.
  - added matrix-cell metadata editor popover for attached cells with:
    - inline `Enabled` switch.
    - inline `Priority` number input.
    - `Save` / `Cancel` actions and success/error micro-feedback.
  - added compact `P{priority}` indicator in matrix cells for attached relationships.
- Added Stage 3 tests:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.attachmentStage3.test.tsx`
  - validates metadata edit/save flow and attach payload parity with `enabled` and `priority`.
- Implemented Stage 4 quick-attach IA refinements:
  - re-labeled per-book link action to `Quick attach characters`.
  - re-labeled per-book modal to `Quick attach: <world book>`.
  - added explicit CTA in quick-attach modal: `Open full matrix` (`aria-label="Open full attachment matrix"`).
  - aligned quick-attach copy and labels (`Currently attached`, `Attach character`) to differentiate from matrix workflow while keeping semantics consistent.
- Added Stage 4 tests:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.attachmentStage4.test.tsx`
  - validates quick-attach labeling and full-matrix CTA navigation from quick-attach modal.
- Updated existing label-regression test:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.stage3.test.tsx`
  - now expects `Quick attach characters` action label.
- Validation run:
  - `bunx vitest run src/components/Option/WorldBooks/__tests__` (from `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui`)
  - result: **24 passed / 24 files**, **65 passed / 65 tests**.
