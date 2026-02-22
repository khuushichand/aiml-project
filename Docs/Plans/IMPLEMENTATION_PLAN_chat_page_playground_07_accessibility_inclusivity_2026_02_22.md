# Chat Page (Playground) Group 07 - Accessibility and Inclusivity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure every core chat capability is keyboard and screen-reader operable with clear focus, announcements, and non-color semantics.

**Architecture:** Build an accessibility contract layer across message timeline, composer, compare clusters, and mode controls; enforce with automated a11y tests and explicit manual QA checklists.

**Tech Stack:** React, TypeScript, ARIA patterns, keyboard event handlers, Vitest + axe checks (where present).

---

## Scope

- Findings: `UX-034`, `UX-035`, `UX-036`
- Primary surfaces:
  - `apps/tldw-frontend/src/components/Common/Playground/Message.tsx`
  - `apps/tldw-frontend/src/components/Common/Playground/ActionInfo.tsx`
  - `apps/tldw-frontend/src/components/Option/Playground/PlaygroundForm.tsx`
  - `apps/tldw-frontend/src/components/Option/Playground/PlaygroundChat.tsx`

## Stage 1: Full Keyboard Navigation Matrix
**Goal**: Make all essential actions keyboard reachable with predictable order.
**Success Criteria**:
- Keyboard shortcuts and tab order cover send/edit/regenerate/variant/branch/compare actions.
- Action menus are operable via Enter/Space/Arrow/Escape.
- Shortcut discovery is available in-product.
**Tests**:
- Add keyboard interaction tests across timeline and composer.
- Add shortcut map guard tests.
**Status**: Complete

## Stage 2: Screen Reader Semantics for Dynamic Chat
**Goal**: Ensure dynamic updates are announced accurately.
**Success Criteria**:
- Streaming updates use appropriate live-region semantics.
- Compare clusters announce model identity and selected winner state.
- Message action controls have explicit ARIA labels.
**Tests**:
- Add accessibility tests for live-region announcements.
- Add compare semantics tests for screen reader labels.
**Status**: Complete

## Stage 3: Focus Management Contracts
**Goal**: Prevent focus loss during send, variant switch, branch creation, and panel toggles.
**Success Criteria**:
- Post-send focus target is deterministic.
- Modal open/close returns focus to initiating control.
- Variant and branch actions keep focus within active conversation context.
**Tests**:
- Add focus-return tests for modals and drawers.
- Add integration tests for focus behavior after high-frequency actions.
**Status**: Complete

## Stage 4: Inclusive Visual and Touch Semantics
**Goal**: Remove reliance on color-only communication and undersized hit targets.
**Success Criteria**:
- Model/error/mood states include text or iconography beyond color.
- Critical controls meet touch target size requirements.
- Contrast passes for labels, chips, badges, and inline controls.
**Tests**:
- Add contrast and non-color semantic checks for key controls.
- Add touch target assertions for message action buttons.
**Status**: Complete

## Stage 5: A11y Quality Gate and Manual Audit
**Goal**: Prevent regressions and codify inclusive behavior expectations.
**Success Criteria**:
- Accessibility smoke suite runs in CI for core chat flows.
- Manual audit checklist is maintained for SR + keyboard + touch.
- Release criteria require passing accessibility gate for chat page changes.
**Tests**:
- Run and document focused accessibility smoke suite.
- Add manual audit evidence for at least one desktop and one mobile path.
**Status**: Complete

## Dependencies

- Depends on Groups 01 through 06 for stabilized structures/interactions.

## Exit Criteria

- All core tasks are operable without mouse and without relying on visual color cues alone.

## Progress Notes (2026-02-22)

- Verified accessibility contract coverage through:
  - `ActionInfo.accessibility.test.tsx`
  - `Playground.accessibility-regression.test.tsx`
  - `Message.keyboard-shortcuts.guard.test.ts`
  - `Message.non-color-signals.guard.test.ts`
- Stage 5 closure evidence:
  - Added manual audit artifact: `Docs/Plans/CHAT_PLAYGROUND_A11Y_MANUAL_AUDIT_2026_02_22.md`.
  - Added CI enforcement step in `.github/workflows/ui-playground-quality-gates.yml` (`Run accessibility gate`).
  - Accessibility gate pass: `bun run test:playground:a11y --reporter=dot` (`10 files / 17 tests passed`).
