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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Stage 1 changes should align with H4 consistency decisions for CTA canonical placement.
- Stage 2 should consume H1 status/result surfaces rather than introducing duplicate widgets.
- Stage 3 guardrails should be referenced by future H7 feature additions.
