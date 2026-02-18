# Implementation Plan: Media Pages - Multi-Item Review (/media-multi)

## Scope

Pages/components: `MediaReviewPage.tsx`, selection toolbar, view-mode controls, multi-item actions
Finding IDs: `7.1` through `7.8`

## Finding Coverage

- Preserve strong existing multi-review flows: `7.1`, `7.2`, `7.3`, `7.6`, `7.7`, `7.8`
- Improve limit discoverability and selection feedback: `7.4`
- Add cross-item comparison action: `7.5`

## Stage 1: Selection Limit Clarity
**Goal**: Communicate selection constraints before users hit errors.
**Success Criteria**:
- Selection counter displays `X / 30 selected` from first selection.
- Warning/error thresholds remain but become progressive and predictable.
- Counter updates remain accurate with shift-click and keyboard selection flows.
**Tests**:
- Component tests for selection counter rendering and threshold states.
- Integration tests for shift-click range and counter correctness.
- Regression tests for existing warning/error messaging behavior.
**Status**: Not Started

## Stage 2: Cross-Item Content Diff
**Goal**: Enable direct comparison of content between two selected media items.
**Success Criteria**:
- "Compare content" action appears only when exactly two items are selected.
- Action opens `DiffViewModal` using selected item content as left/right inputs.
- Empty or failed-content states are handled with actionable errors.
**Tests**:
- Integration tests for action visibility and modal launch conditions.
- Component tests for diff rendering with two selected items.
- Error-state tests for missing/failed content payloads.
**Status**: Not Started

## Stage 3: Regression Hardening for Existing Strengths
**Goal**: Preserve current quality in view modes, onboarding help, and per-card actions.
**Success Criteria**:
- Existing spread/list/all mode auto-selection behavior remains intact.
- First-use help modal and keyboard shortcut behavior remain available.
- Per-card copy actions and retry-on-failure card behavior remain unchanged.
**Tests**:
- Regression tests for view-mode auto-switching thresholds.
- Component tests for help modal trigger and keyboard shortcut handling.
- Integration tests for copy confirmation and retry behavior.
**Status**: Not Started

## Dependencies

- Mobile layout tuning should align with Category 11 responsive changes.
