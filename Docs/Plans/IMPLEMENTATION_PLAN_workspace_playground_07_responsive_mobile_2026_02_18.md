# Implementation Plan: Workspace Playground - Responsive and Mobile Experience

## Scope

Components: mobile tabs, source rows, drawers, modals, upload tab, Studio controls
Finding IDs: `7.1` through `7.8`

## Finding Coverage

- Keep strengths unchanged: `7.1`
- Critical touch/discoverability fixes: `7.2`, `7.3`, `7.5`
- Responsive layout behavior: `7.4`, `7.7`, `7.8`
- Mobile control ergonomics: `7.6`

## Stage 1: Touch-Critical Interaction Fixes
**Goal**: Ensure core source actions are visible and tappable on touch devices.
**Success Criteria**:
- Source checkbox hit area meets 44x44 minimum on mobile.
- Remove source button is visible on touch devices (`@media (hover: none)`) and on keyboard focus.
- Upload tab copy adapts to mobile (`Tap to select files`) and includes explicit browse button.
**Tests**:
- Responsive component tests with mobile viewport assertions for control visibility.
- Integration tests verifying remove action is discoverable on touch.
- Accessibility tests for touch target dimensions.
**Status**: Complete

## Stage 2: Modal and Drawer Responsiveness
**Goal**: Avoid mobile/tablet occlusion and improve reading/editing space.
**Success Criteria**:
- Add Source modal uses full-width/mobile-specific body height constraints.
- Generated output viewer opens fullscreen on mobile.
- Tablet drawer behavior avoids fully obscuring chat (push layout or `mask={false}` strategy).
**Tests**:
- Playwright mobile/tablet tests for modal and drawer behavior.
- Visual regression tests for fullscreen artifact viewer layout.
**Status**: Complete

## Stage 3: Mobile Studio Control Ergonomics
**Goal**: Make TTS and Studio controls accurate and comfortable on touch screens.
**Success Criteria**:
- Mobile variants use larger `Select` controls and thicker slider track.
- Control density adapts by breakpoint without breaking desktop compact mode.
- Existing good tabbed mobile IA is preserved.
**Tests**:
- Responsive tests for control size tokens.
- Accessibility tests for keyboard and touch operation parity.
- Regression tests to ensure mobile tab badge behavior remains intact.
**Status**: Complete

## Dependencies

- Remove button behavior should align with accessibility fixes in Category 11.

## Progress Notes (2026-02-18)

- Stage 1 completed:
  - Increased source selection touch hit areas for mobile/touch contexts (44px-class min target) in `SourcesPane`.
  - Updated source remove button visibility behavior:
    - visible on touch devices (`@media (hover: none)` class variant),
    - visible on keyboard focus (`focus-visible:opacity-100`),
    - retained desktop hover reveal behavior.
  - Updated Upload tab copy for mobile from drag language to tap language and added an explicit mobile `Browse files` button.
- Files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/AddSourceModal.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.mobile.test.tsx`
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.mobile.test.tsx --reporter=verbose`
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.mobile.test.tsx src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage4.test.tsx src/store/__tests__/workspace.test.ts`

- Stage 2 completed:
  - Updated Add Source modal to use responsive mobile sizing (`width=\"100%\"`) with mobile body max-height/scroll constraints.
  - Updated WorkspacePlayground tablet drawers to non-blocking behavior via `mask={false}` for both Sources and Studio drawers.
  - Updated Studio artifact view modals to use fullscreen-style mobile presentation (`width=\"100%\"`, top-aligned, `100dvh`-friendly body scroll area) while preserving desktop widths.
- Files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/AddSourceModal.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.mobile.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage2.responsive.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx`
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.mobile.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage2.responsive.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx --reporter=verbose`
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage2.responsive.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.mobile.test.tsx src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage4.test.tsx src/store/__tests__/workspace.test.ts`

- Stage 3 completed:
  - Updated Studio audio settings controls to use responsive sizing on mobile (`Select` and related actions now render with `size=\"large\"` on mobile and remain compact on desktop).
  - Increased mobile slider affordance with thicker rail/track and larger handle via responsive class tokens.
  - Kept mobile tab IA intact while improving touch ergonomics for TTS controls.
- Files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx`
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx --reporter=verbose`
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.mobile.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage2.responsive.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx --reporter=verbose`
