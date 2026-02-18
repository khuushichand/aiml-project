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
**Status**: Complete

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
**Status**: Complete

## Stage 3: Bridge Existing Lorebook Debug Panel Discoverability
**Goal**: Reuse existing diagnostics and reduce hidden-feature risk.
**Success Criteria**:
- Add discoverability link from world-books page to lorebook debug docs/panel entry point.
- Ensure simplified test UI and full debug panel share terminology and metric definitions.
- Add explicit handoff path from test panel to live-chat diagnostics when deeper analysis is needed.
**Tests**:
- Component tests for discoverability links and conditional rendering.
- Content regression test to keep metric labels consistent across both surfaces.
**Status**: Complete

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
**Status**: Complete

## Dependencies

- Stages 2 and 4 depend on stable diagnostic API contracts and response-size handling.
- Security review required before exposing detailed diagnostics outside existing debug contexts.

## Progress Notes (2026-02-18)

- Implemented Stage 1 character/world-book cross-navigation:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Characters/Manager.tsx`
    - parses route query context (`from`, `focusCharacterId`, `focusWorldBookId`) from URL.
    - auto-opens preview popup when `focusCharacterId` is present and character exists in loaded results.
    - fetches attached world books for previewed character and passes them into preview UI.
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Characters/CharacterPreviewPopup.tsx`
    - renders attached world-book links with deep links back into world-books workspace.
    - adds explicit back-link behavior when launched from world-books, preserving focused world-book context.
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`
    - adds character deep links in attached-character popover.
    - adds character deep links in quick-attach modal and matrix character headers.
- Added Stage 1 tests:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Characters/__tests__/Manager.crossFeatureStage1.test.tsx`
    - verifies focused-character route params open preview and render world-book deep links + back link.
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.crossFeatureStage1.test.tsx`
    - verifies popover/quick-attach character links target characters workspace with focus params.
- Validation run:
  - `bunx vitest run src/components/Option/Characters/__tests__/Manager.crossFeatureStage1.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.crossFeatureStage1.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.attachmentStage1.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.attachmentStage4.test.tsx`
  - result: **4 passed / 4 files**, **7 passed / 7 tests**.
- Implemented Stage 2 test-matching workflow in `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - added reusable `WorldBookTestMatchingModal` with:
    - world-book selection
    - sample text input
    - scan depth/token budget/recursive-scanning controls
    - `processWorldBookContext` execution + result rendering (summary, diagnostics, budget status)
    - iterative rerun support without leaving modal
  - exposed entry points from both:
    - world-books toolbar (`Test Matching`)
    - entries drawer context (`Test Keywords`)
  - includes inline error handling for API failures.
- Added Stage 2 tests:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.crossFeatureStage2.test.tsx`
    - verifies request payload shape and result rendering.
    - verifies iterative rerun with updated sample text.
    - verifies entries-drawer launch path and error-path UI.
- Validation run:
  - `bunx vitest run src/components/Option/WorldBooks/__tests__/WorldBooksManager.crossFeatureStage2.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.crossFeatureStage1.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.attachmentStage1.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.attachmentStage4.test.tsx src/components/Option/Characters/__tests__/Manager.crossFeatureStage1.test.tsx`
  - result: **5 passed / 5 files**, **9 passed / 9 tests**.
- Implemented Stage 3 discoverability + terminology alignment in `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - added world-books page discoverability callout linking to chat lorebook diagnostics entry point.
  - aligned Test Matching result terminology with Lorebook Debug metric labels:
    - Entries matched
    - Books used
    - Tokens used
    - Token budget
  - added explicit handoff block in Test Matching results with link to live chat diagnostics (`Open Chat Debug Panel`).
- Added Stage 3 tests:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.crossFeatureStage3.test.tsx`
    - verifies discoverability link visibility from world-books page.
    - verifies handoff link appears after test run.
    - regression-checks metric label consistency in Test Matching output.
- Validation run:
  - `bunx vitest run src/components/Option/WorldBooks/__tests__/WorldBooksManager.crossFeatureStage3.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.crossFeatureStage2.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.crossFeatureStage1.test.tsx src/components/Option/Characters/__tests__/Manager.crossFeatureStage1.test.tsx`
  - result: **4 passed / 4 files**, **6 passed / 6 tests**.
- Implemented Stage 4 per-turn lorebook activity surface in chat session UI:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx`
    - added `Lorebook Activity` panel in chat pane for active server-backed chats.
    - fetches recent per-turn lorebook diagnostics from `getChatLorebookDiagnostics`.
    - renders turn cards (`Turn N: X entries fired`) with assistant preview snippets.
    - includes refresh and export actions plus a `View Full Diagnostics` handoff link.
    - adds authorization-safe fallback message when diagnostics endpoint is forbidden.
    - caps rendered activity cards to page-size for long-session performance safety.
  - updated existing ChatPane test suites to mock diagnostics client calls:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx`
- Added Stage 4 tests:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage4.lorebook-activity.test.tsx`
    - turn-level activity rendering coverage
    - forbidden/authorization visibility coverage
    - long-session rendering cap/performance guard coverage
- Validation run:
  - `bunx vitest run src/components/Option/WorldBooks/__tests__/WorldBooksManager.crossFeatureStage1.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.crossFeatureStage2.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.crossFeatureStage3.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.attachmentStage1.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.attachmentStage4.test.tsx src/components/Option/Characters/__tests__/Manager.crossFeatureStage1.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage4.lorebook-activity.test.tsx`
  - result: **10 passed / 10 files**, **32 passed / 32 tests**.
