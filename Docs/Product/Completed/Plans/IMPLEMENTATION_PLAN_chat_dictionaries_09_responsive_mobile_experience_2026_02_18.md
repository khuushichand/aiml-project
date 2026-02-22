# Implementation Plan: Chat Dictionaries - Responsive and Mobile Experience

## Scope

Components: dictionary list actions, entry manager layout, preview controls in `apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`, mobile E2E viewport coverage
Finding IDs: `9.1` through `9.5`

## Finding Coverage

- Row action density and mobile interaction load: `9.1`
- Entry manager modal constraints and nested overlay issues: `9.2`
- Preserve existing touch-target and form-grid strengths: `9.3`, `9.4`
- Preview control layout behavior in constrained widths: `9.5`

## Stage 1: Mobile Action Density and Prioritization
**Goal**: Keep row interactions usable on narrow screens without losing capability.
**Success Criteria**:
- Mobile rows expose primary actions directly (Edit, Entries).
- Secondary actions move to overflow menu with clear labels/icons.
- Action menu remains keyboard and screen-reader accessible.
- Touch targets maintain minimum 44x44 px for actionable controls.
**Tests**:
- Component tests for breakpoint-based action rendering.
- Mobile viewport tests for overflow action menu usability.
- Accessibility tests for menu button semantics and keyboard activation.
**Status**: Complete
**Completion Notes (2026-02-18)**:
- Added mobile action compaction in dictionary rows:
  - primary actions remain directly visible (`Edit`, `Entries`),
  - secondary actions moved into an overflow menu (`Quick assign`, exports, stats, duplicate, delete).
- Added explicit overflow trigger semantics (`aria-haspopup="menu"`) and keyboard activation coverage.
- Preserved 44x44 touch-target sizing for all row action triggers in compact mode.
- Added regression coverage in `apps/packages/ui/src/components/Option/Dictionaries/__tests__/Manager.responsiveStage1.test.tsx`.

## Stage 2: Entry Manager Layout for Small Screens
**Goal**: Eliminate cramped nested modal interactions on mobile.
**Success Criteria**:
- Entry management uses full-screen drawer or route on mobile breakpoints.
- Nested modal pattern is removed for entry editing in mobile layouts.
- Form sections remain readable with progressive disclosure for advanced fields.
- Table/list representation degrades gracefully (stacked rows/cards if needed).
**Tests**:
- E2E tests at 375px and 768px for full entry lifecycle.
- Component tests for drawer open/close and focus behavior.
- Visual regression checks for entry manager layout snapshots.
**Status**: Complete
**Completion Notes (2026-02-18)**:
- Switched breakpoint detection in dictionary manager to the shared `useMobile()` hook for reactive viewport handling.
- Kept entry-management in a full-width drawer on mobile and replaced mobile entry editing modal with a dedicated full-width drawer panel.
- Preserved desktop behavior: entry editing still uses the modal flow in non-mobile breakpoints.
- Added responsive regression coverage in `apps/packages/ui/src/components/Option/Dictionaries/__tests__/Manager.responsiveStage2.test.tsx`.
- Verified no regressions in surrounding container flows via:
  - `Manager.responsiveStage1.test.tsx`
  - `Manager.responsiveStage2.test.tsx`
  - `Manager.entryStage4.test.tsx`
  - `Manager.entryStage2.test.tsx`

## Stage 3: Preview and Validation Controls Under Width Constraints
**Goal**: Keep validation/preview tools usable in constrained containers.
**Success Criteria**:
- Token budget and max-iteration controls stack vertically when width is limited.
- Preview controls avoid horizontal overflow in all supported breakpoints.
- Existing responsive add-entry grid behavior remains unchanged.
- Performance remains acceptable with diff/preview rendering enabled on mobile.
**Tests**:
- Component tests for responsive grid fallback behavior.
- Mobile viewport tests for preview panel layout integrity.
- Regression tests confirming add-entry grid still collapses correctly.
**Status**: Complete
**Completion Notes (2026-02-18)**:
- Updated preview saved-case controls to stack by default and align horizontally only from `sm` upward.
- Hardened preview settings layout to `grid-cols-1` with `md:grid-cols-2` and added `min-w-0` safeguards to avoid cramped horizontal overflow in narrow containers.
- Added explicit responsive test hooks (`data-testid`) for preview layout verification.
- Added coverage in `apps/packages/ui/src/components/Option/Dictionaries/__tests__/Manager.responsiveStage3.test.tsx`.
- Revalidated responsive workflow tests:
  - `Manager.responsiveStage1.test.tsx`
  - `Manager.responsiveStage2.test.tsx`
  - `Manager.responsiveStage3.test.tsx`
  - `Manager.entryStage4.test.tsx`

## Dependencies

- Mobile layout decisions should align with Category 2 Stage 4 (nested modal replacement).
- Accessibility validations should be executed together with Category 10 checks.
