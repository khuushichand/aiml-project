# Chat Page (Playground) Group 06 - Responsive Design and Device Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver feature parity and ergonomic consistency across desktop, tablet, and mobile chat experiences.

**Architecture:** Normalize pane behavior per breakpoint, then harden touch/gesture and keyboard-safe composer behavior with dedicated mobile/tablet contracts.

**Tech Stack:** React, TypeScript, responsive hooks/utilities, mobile layout components, Vitest + targeted Playwright checks.

---

## Scope

- Findings: `UX-031`, `UX-032`, `UX-033`
- Primary surfaces:
  - `apps/tldw-frontend/src/components/Option/Playground/Playground.tsx`
  - `apps/tldw-frontend/src/components/Option/Playground/PlaygroundForm.tsx`
  - `apps/tldw-frontend/src/components/Sidepanel/Chat/ArtifactsPanel.tsx`
  - `apps/tldw-frontend/src/components/Common/Playground/MessageActionsBar.tsx`

## Stage 1: Breakpoint Behavior Contracts
**Goal**: Define and enforce predictable pane behavior by device class.
**Success Criteria**:
- Tablet: sidebar and artifacts use consistent overlay/drawer mechanics.
- Mobile: one-column layout with explicit entry points for history and artifacts.
- No silent feature removal at smaller breakpoints.
**Tests**:
- Add responsive contract tests for each breakpoint.
- Add integration tests for panel open/close behavior persistence.
**Status**: Complete

## Stage 2: Keyboard-Safe Sticky Composer
**Goal**: Keep composer usable with mobile virtual keyboard active.
**Success Criteria**:
- Composer remains visible and actionable when keyboard opens.
- Message timeline retains enough visible context for follow-up.
- Advanced controls collapse contextually when keyboard space is constrained.
**Tests**:
- Add mobile viewport tests simulating keyboard open/close states.
- Add interaction tests for send/attach/voice while keyboard is open.
**Status**: Complete

## Stage 3: Touch and Gesture Reliability
**Goal**: Reduce accidental actions and gesture conflicts.
**Success Criteria**:
- Variant swipe zones are constrained to avoid vertical scroll interference.
- Message action targets meet minimum size guidance.
- Gesture-only actions have visible button alternatives.
**Tests**:
- Add touch-target and gesture conflict tests.
- Add regression tests for scroll/swipe interactions in long threads.
**Status**: Complete

## Stage 4: Artifacts and Compare Mobile Access
**Goal**: Ensure advanced features remain reachable on small screens.
**Success Criteria**:
- Artifacts panel is reachable via persistent bottom-sheet affordance.
- Compare mode has a mobile-optimized stacked/tabs presentation.
- Branch and source navigation remain available on mobile.
**Tests**:
- Add mobile tests for artifacts open/use/return flow.
- Add compare and branching parity tests on mobile breakpoints.
**Status**: Complete

## Stage 5: Device-Matrix Regression Gate
**Goal**: Prevent parity regressions during ongoing UX changes.
**Success Criteria**:
- Establish a maintained desktop/tablet/mobile smoke matrix.
- Add per-release parity checklist and ownership.
- Critical flows are validated for all device classes before merge.
**Tests**:
- Run targeted responsive suites and document baseline outputs.
- Add Playwright smoke flows for representative mobile/tablet paths.
**Status**: Complete

## Dependencies

- Depends on Groups 03 and 04 for stabilized flows/composer hierarchy.
- Group 05 compare behavior must supply mobile-compatible contracts.

## Exit Criteria

- No core chat capability is discoverable only on desktop.

## Progress Notes (2026-02-22)

- Validated breakpoint and mobile parity coverage with:
  - `Playground.responsive-parity.guard.test.ts`
  - `mobile-composer-layout.test.ts`
  - `useMobileComposerViewport.integration.test.tsx`
  - `form.mobile-toolbar.contract.test.ts`
  - `WorkspacePlayground.stage2.responsive.test.tsx`
  - `AddSourceModal.stage1.mobile.test.tsx`
- Stage 5 closure evidence:
  - Added ownership/checklist artifact: `Docs/Plans/CHAT_PLAYGROUND_DEVICE_MATRIX_CHECKLIST_2026_02_22.md`.
  - Added enforceable CI release gate: `.github/workflows/ui-playground-quality-gates.yml`.
  - Device matrix suite passes via `bun run test:playground:device-matrix --reporter=dot` (`6 files / 12 tests passed`).
