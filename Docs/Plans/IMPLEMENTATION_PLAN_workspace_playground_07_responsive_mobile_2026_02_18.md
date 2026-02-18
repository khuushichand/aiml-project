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
**Status**: Not Started

## Stage 2: Modal and Drawer Responsiveness
**Goal**: Avoid mobile/tablet occlusion and improve reading/editing space.
**Success Criteria**:
- Add Source modal uses full-width/mobile-specific body height constraints.
- Generated output viewer opens fullscreen on mobile.
- Tablet drawer behavior avoids fully obscuring chat (push layout or `mask={false}` strategy).
**Tests**:
- Playwright mobile/tablet tests for modal and drawer behavior.
- Visual regression tests for fullscreen artifact viewer layout.
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Remove button behavior should align with accessibility fixes in Category 11.
