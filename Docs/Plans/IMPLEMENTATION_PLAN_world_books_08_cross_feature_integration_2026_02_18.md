# Implementation Plan: World Books - Cross-Feature Integration

## Scope

Components: Character detail pages, world-books page integration points, `processWorldBookContext` diagnostics UI, and chat-session lorebook activity surfaces.
Finding IDs: `8.1` through `8.4`

## Finding Coverage

- Navigation disconnect between character and world-book surfaces: `8.1`
- Missing in-place discovery of existing debug tooling: `8.2`
- Missing authoring-time test harness for matching quality: `8.3`
- Missing per-turn lorebook activity visibility in chat UX: `8.4`

## Stage 1: Add Character <-> World Book Cross-Navigation
**Goal**: Remove context switching friction between character and lore management.
**Success Criteria**:
- Add world-book section on character detail pages with attached-book links.
- Add character deep links from world-book attachment UIs.
- Preserve navigation context/back behavior when jumping between surfaces.
**Tests**:
- Integration tests for character page attached-book rendering and deep-link navigation.
- Integration tests for attachment-popover character links.
- Regression tests for route params and breadcrumb/title updates.
**Status**: Not Started

## Stage 2: Expose Test-Matching Workflow in World Books UI
**Goal**: Put the highest-impact diagnostic loop directly in authoring flow.
**Success Criteria**:
- Add `Test matching` / `Test keywords` panel from world-book management and entries drawer.
- Call `processWorldBookContext` with sample text and display matches, token usage, budget status.
- Support iterative runs without leaving the management screen.
**Tests**:
- Integration tests for request payload, response rendering, and error handling.
- Component tests for match list, token/budget summaries, and empty-result states.
- UX test verifying iterative rerun flow with updated sample text.
**Status**: Not Started

## Stage 3: Bridge Existing Lorebook Debug Panel Discoverability
**Goal**: Reuse existing diagnostics and reduce hidden-feature risk.
**Success Criteria**:
- Add discoverability link from world-books page to lorebook debug docs/panel entry point.
- Ensure simplified test UI and full debug panel share terminology and metric definitions.
- Add explicit handoff path from test panel to live-chat diagnostics when deeper analysis is needed.
**Tests**:
- Component tests for discoverability links and conditional rendering.
- Content regression test to keep metric labels consistent across both surfaces.
**Status**: Not Started

## Stage 4: Surface Per-Turn Lorebook Activity in Chat Session UI
**Goal**: Make runtime injection behavior visible without specialist tooling.
**Success Criteria**:
- Add chat-session lorebook activity section summarizing entries fired per turn.
- Provide export/view-more path to full diagnostics where available.
- Maintain privacy/security constraints for diagnostic visibility per user role.
**Tests**:
- Integration tests for turn-level activity rendering from diagnostics data.
- Authorization tests for diagnostic visibility in multi-user mode.
- Performance test for long chat sessions with many turns.
**Status**: Not Started

## Dependencies

- Stages 2 and 4 depend on stable diagnostic API contracts and response-size handling.
- Security review required before exposing detailed diagnostics outside existing debug contexts.
