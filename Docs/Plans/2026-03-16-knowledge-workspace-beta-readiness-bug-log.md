# Knowledge Workspace Beta Readiness Bug Log

**Date:** 2026-03-16
**Baseline command:** `bunx playwright test e2e/workflows/knowledge-qa.spec.ts e2e/workflows/workspace-playground.spec.ts e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line --workers=1`

## P1

### KQ-002: Knowledge settings flows time out in the live route

- Status: Resolved in audit worktree
- Route: `/knowledge`
- Feature: settings dialog open, preset switching, expert mode toggle, and apply-settings request flow
- Reproduction:
  1. Open `/knowledge`
  2. Trigger the settings flow from the current Playwright workflow
  3. Attempt to open the dialog or interact with its preset/toggle controls
- Evidence:
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:277`
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:299`
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:327`
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:357`
  - `test-results/workflows-knowledge-qa-Kno-b11ae--should-open-settings-panel-chromium/error-context.md`
  - `test-results/workflows-knowledge-qa-Kno-3044a-ould-switch-between-presets-chromium/error-context.md`
  - `test-results/workflows-knowledge-qa-Kno-ee2bd-s-should-toggle-expert-mode-chromium/error-context.md`
  - `test-results/workflows-knowledge-qa-Kno-6a781--settings-to-search-request-chromium/error-context.md`
- Suspected layer: route UI interaction, dialog wiring, or stale selector assumptions in `KnowledgeQAPage.openSettings()`
- Why it matters: this is a live user-facing configuration surface and currently blocks four separate route-level checks
- Resolution:
  - Replaced the stale generic `KnowledgeQAPage` selectors with route-scoped `/knowledge` shells and dialog helpers.
  - Hardened the four settings tests to assert the real drawer, preset radio state, expert-mode toggle state, and live request payload.
  - Verification: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "Settings & Presets|should switch between presets|should toggle expert mode|should apply settings to search request" --reporter=line --workers=1` => `4 passed (12.5s)`

### KQ-003: Knowledge history sidebar flow hangs after live searches

- Status: Resolved in audit worktree
- Route: `/knowledge`
- Feature: history sidebar open and restore interaction
- Reproduction:
  1. Open `/knowledge`
  2. Perform two live searches
  3. Open the history sidebar and reselect the latest query
- Evidence:
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:453`
  - `test-results/workflows-knowledge-qa-Kno-a160d-should-open-history-sidebar-chromium/error-context.md`
- Suspected layer: sidebar open control, history render timing, or route-state restore behavior
- Why it matters: search history is part of the current KnowledgeQA workflow surface and may be non-functional in the live route
- Resolution:
  - The same stale page-object selector drift was sending the workflow to the wrong layout controls.
  - Hardened the history checks to assert the actual history rail and `Cmd+K` reset behavior.
  - Verification: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "Search History|should open history sidebar|should start new search with Cmd+K" --reporter=line --workers=1` => `2 passed (4.5s)`

### WP-001: Workspace live interaction flow is blocked by a fixed overlay intercepting pane controls

- Route: `/workspace-playground`
- Feature: hide/show sources and related core workspace interactions
- Reproduction:
  1. Open `/workspace-playground`
  2. Run the real-backend interaction flow
  3. Attempt to click `Hide sources`
- Evidence:
  - `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts:165`
  - `apps/tldw-frontend/e2e/utils/page-objects/WorkspacePlaygroundPage.ts:52`
  - `test-results/workflows-workspace-playgr-4f79f-tions-with-live-API-context-chromium/error-context.md`
- Suspected layer: modal/backdrop cleanup, pointer-event interception, or brittle interaction helper logic in `WorkspacePlaygroundPage`
- Why it matters: this breaks the current real-backend interaction suite and suggests the route can wedge on leftover overlays

## P2

### KQ-001: Mocked delayed-loading test asserts on brittle answer text rather than stable route behavior

- Status: Resolved as test hardening
- Route: `/knowledge`
- Feature: progressive loading stages for delayed long-running searches
- Reproduction:
  1. Intercept `/api/v1/rag/search` and `/api/v1/rag/search/stream`
  2. Return the mocked delayed payload used by the current spec
  3. Wait for the test to assert on a literal delayed answer node
- Evidence:
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:159`
  - `test-results/workflows-knowledge-qa-Kno-eaedd-layed-long-running-searches-chromium/error-context.md`
- Suspected layer: test fragility, answer rendering expectations, or a mismatch between mocked payload shape and current UI rendering
- Why it matters: this is probably not a beta-blocking product bug, but it is a misleading failing test in the current suite
- Resolution:
  - Updated the test to assert the current rendered answer state: loading stages, answer panel content, citation button, and evidence-panel source heading.
  - Verification: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "delayed long-running searches" --reporter=line --workers=1` => `1 passed (10.6s)`

## Notes

- Baseline summary: `17 passed`, `7 failed`
- Current `/knowledge` summary after repairs: `17 passed`, `0 failed`
- Current `/knowledge` verification command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --reporter=line --workers=1`
- `/workspace-playground` live boot, grounding, compare-sources generation, and global search all passed in the same run
- `/knowledge` basic live search, follow-up, and no-results/error-state paths passed in the same run
