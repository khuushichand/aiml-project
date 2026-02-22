# Implementation Plan: Flashcards H8 - Aesthetic and Minimalist Design

## Scope

Route/components: `tabs/ReviewTab.tsx`, `tabs/ImportExportTab.tsx`, shared layout primitives for flashcards panels  
Finding IDs: `H8-1` through `H8-2`

## Finding Coverage

- Review top bar competes with active study flow: `H8-1`
- Import/Export desktop layout feels sparse and under-structured: `H8-2`

## Stage 1: Review Flow Visual Priority Cleanup
**Goal**: Keep active study controls visually dominant and reduce competing actions.
**Success Criteria**:
- "Create card" CTA is contextual (empty states and secondary actions), not always primary in active review.
- Deck selector remains accessible but compressed into a low-noise control group.
- Review card and rating controls are the strongest visual focus in mid-session state.
**Tests**:
- Component tests for conditional CTA visibility based on session state.
- Visual regression tests for active review and empty review states.
- Accessibility tests ensuring controls remain keyboard-reachable after hierarchy changes.
**Status**: Complete

**Implementation Notes (2026-02-18)**:
- Updated review top bar hierarchy so create-card is contextual:
  - top-bar create CTA appears only when there is no active review card
  - while actively reviewing, top bar keeps scope/session controls but removes competing primary CTA
- Added subtle top-bar container styling during active review to de-emphasize chrome relative to card/rating loop.
- Kept create affordances in empty/caught-up states as primary/secondary actions inside the content state card.

**Validation Completed**:
- `ReviewTab.create-cta.test.tsx`:
  - create CTA visible when no active review card
  - create CTA hidden during active review
  - controls remain present/reachable while reviewing
- Flashcards regression suite:
  - `src/components/Flashcards/**/__tests__/*.test.tsx`
  - `src/utils/__tests__/flashcards-shortcut-hint-telemetry.test.ts`

## Stage 2: Import/Export Information Density Pass
**Goal**: Improve scanability and usefulness of import/export panels without adding clutter.
**Success Criteria**:
- Desktop layout adds compact summaries (supported formats, limits, last action result) to fill dead space.
- Import/export sections use consistent heading hierarchy and action grouping.
- Mobile stacked layout remains readable with no overflow/regression.
**Tests**:
- Visual regression tests for desktop and mobile breakpoints.
- Component tests for summary cards and result panel visibility.
- E2E import/export sanity tests to ensure layout changes do not break actions.
**Status**: Complete

**Implementation Notes (2026-02-18)**:
- Added a compact desktop/mobile-safe Transfer summary strip above the three panels with:
  - supported format summary
  - current import limits snapshot
  - session-scoped last action status (import/export/generate)
- Wired Import/Export/Generate panels to publish action outcomes (success/warning/error) into the summary strip.
- Added export success feedback + summary update after file generation.
- Preserved stacked mobile layout and existing per-panel workflows.

**Validation Completed**:
- `ImportExportTab.import-results.test.tsx`:
  - transfer summary cards render with formats/limits
  - summary last-action updates after import
  - existing import/export/generate and rollback coverage retained
- Flashcards regression suite:
  - `src/components/Flashcards/**/__tests__/*.test.tsx`
  - `src/utils/__tests__/flashcards-shortcut-hint-telemetry.test.ts`

## Stage 3: Design Guardrails for Future Iterations
**Goal**: Prevent recurring visual clutter as features are added.
**Success Criteria**:
- Flashcards layout guidance defines primary/secondary action placement per tab.
- New UI additions require explicit state priority mapping (empty, active, success, error).
- At least one screenshot baseline suite is established for core flashcards states.
**Tests**:
- Screenshot baseline tests for review active/complete, cards with selection, import result states.
- Lint or checklist enforcement for action hierarchy conventions.
- Regression checks for CTA count and placement thresholds in top bars.
**Status**: Complete

**Implementation Notes (2026-02-18)**:
- Added explicit Flashcards state-priority and action-placement contract in code:
  - `apps/packages/ui/src/components/Flashcards/constants/layout-guardrails.ts`
  - includes `empty/active/success/error` mappings for `review`, `manage`, and `transfer`.
- Added checklist/enforcement tests for guardrail completeness and CTA budgets:
  - `apps/packages/ui/src/components/Flashcards/constants/__tests__/layout-guardrails.test.ts`
- Added top-bar/selection test anchors and CTA budget assertions in tab tests:
  - `ReviewTab.tsx` (`flashcards-review-topbar`, active/empty card testids)
  - `ManageTab.tsx` (`flashcards-manage-topbar`, `flashcards-manage-selection-summary`)
  - `ImportExportTab.tsx` (`flashcards-import-last-result`)
- Added baseline snapshot coverage for core flashcards states:
  - Review active + caught-up completion
  - Cards with active selection
  - Import result + transfer summary state
- Documented the H8 guardrail policy in:
  - `Docs/Design/Flashcards.md`

**Validation Completed**:
- `apps/packages/ui/src/components/Flashcards/constants/__tests__/layout-guardrails.test.ts`
- `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx`
- `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx`
- `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx`

## Dependencies

- Stage 1 changes should align with H4 consistency decisions for CTA canonical placement.
- Stage 2 should consume H1 status/result surfaces rather than introducing duplicate widgets.
- Stage 3 guardrails should be referenced by future H7 feature additions.
