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

- Status: Resolved in audit worktree
- Route: `/workspace-playground`
- Feature: hide/show sources and related core workspace interactions
- Reproduction:
  1. Open `/workspace-playground`
  2. Run the real-backend interaction flow
  3. Attempt to click `Hide sources`
- Evidence:
  - `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts:165`
  - `apps/tldw-frontend/e2e/utils/page-objects/WorkspacePlaygroundPage.ts:52`
  - repeated repro of the same failure during `--repeat-each 5`
- Suspected layer: modal/backdrop cleanup, pointer-event interception, or brittle interaction helper logic in `WorkspacePlaygroundPage`
- Why it matters: this breaks the current real-backend interaction suite and suggests the route can wedge on leftover overlays
- Resolution:
  - Reproduced the flake repeatedly and confirmed that the workspace search modal and command-palette backdrops could remain active across shortcut flows.
  - Hardened `WorkspacePlaygroundPage` to wait for the actual workspace search input, clear leftover command-palette/modal backdrops, and avoid trial-clicking through active overlays.
  - Fixed a real route bug in `WorkspacePlayground` so pressing `Escape` inside the workspace search input closes the modal.
  - Verification:
    - `bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx` => `14 passed (14)`
    - `bunx playwright test e2e/workflows/workspace-playground.real-backend.spec.ts --grep "supports core workspace interactions with live API context" --repeat-each 5 --reporter=line --workers=1` => `5 passed (22.3s)`
    - `bunx playwright test e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line --workers=1` => `2 passed (6.0s)`

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

### KQ-004: Citation/source jump coverage was green without proving source identity

- Status: Resolved as test hardening
- Route: `/knowledge`
- Feature: citation buttons focusing the matching evidence card
- Reproduction:
  1. Open `/knowledge` with a deterministic mocked answer containing at least two citations and two source cards
  2. Click `Jump to source 2`
  3. Observe that the prior suite only proved the evidence panel rendered; it did not assert that the second citation became current or that the second source card took focus
- Evidence:
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:141`
  - `Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-matrix.md:39`
- Suspected layer: audit gap in route-level assertions rather than a confirmed product defect
- Why it matters: a citation/index mismatch could have shipped into beta while the route suite still passed, leaving users with misleading evidence jumps
- Resolution:
  - Added a deterministic route-level Playwright case that stubs two sources, clicks `Jump to source 2`, asserts the clicked citation gets `aria-current="true"`, and verifies the focus ring moves from `#source-card-0` to `#source-card-1`.
  - Verification: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "keeps citation jumps aligned with the matching evidence card" --reporter=line --workers=1` => `1 passed (4.4s)`

### KQ-005: Whitespace-answer mock coverage still depended on live KnowledgeQA bootstrap

- Status: Resolved as test hardening
- Route: `/knowledge`
- Feature: source-only state when the generated answer is blank or whitespace
- Reproduction:
  1. Stop the local API listener
  2. Run the whitespace-answer test with only `/api/v1/rag/search` and `/api/v1/rag/search/stream` intercepted
  3. Observe that the route never reaches the results shell because the chat/bootstrap requests still target the dead backend
- Evidence:
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:412`
  - `apps/tldw-frontend/test-results/workflows-knowledge-qa-Kno-c8b2f-wers-as-no-generated-answer-chromium/error-context.md`
- Suspected layer: test setup incompletely stubbing the KnowledgeQA bootstrap path
- Why it matters: this was classified as mock-only coverage, but it could still fail for unrelated backend reachability reasons and hide real regressions
- Resolution:
  - Stubbed the KnowledgeQA bootstrap endpoints used by deterministic search flows (`docs-info`, conversations, chat creation, message persistence, and rag-context) so the whitespace-answer case no longer depends on the live API.
  - Verification: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "treats whitespace-only answers as no generated answer" --reporter=line --workers=1` => `1 passed (3.7s as part of the failure-cluster rerun)`

### KQ-006: Live settings/history checks ran without backend preflight and produced false route failures

- Status: Resolved as suite hardening
- Route: `/knowledge`
- Feature: settings drawer, preset toggles, history sidebar, and `Cmd+K` new-search shortcut
- Reproduction:
  1. Stop the local API listener
  2. Run the full `/knowledge` Playwright file
  3. Observe that settings and history tests time out behind the `Can't reach your tldw server` modal even though the current problem is backend availability, not those route features themselves
- Evidence:
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:559`
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:576`
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:599`
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:718`
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:737`
  - `apps/tldw-frontend/test-results/workflows-knowledge-qa-Kno-b11ae--should-open-settings-panel-chromium/error-context.md`
  - `apps/tldw-frontend/test-results/workflows-knowledge-qa-Kno-a160d-should-open-history-sidebar-chromium/error-context.md`
  - `apps/tldw-frontend/test-results/workflows-knowledge-qa-Kno-ca096-start-new-search-with-Cmd-K-chromium/error-context.md`
- Suspected layer: missing server-availability gating on tests that are intended to be live-covered
- Why it matters: false negatives from a dead local API make the beta gate noisy and obscure whether a failure is a real route regression or just environment reachability
- Resolution:
  - Added `skipIfServerUnavailable(serverInfo)` guards to the live settings and history cases so they now skip cleanly when backend preflight fails instead of timing out through the connection modal.
  - Verification: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "treats whitespace-only answers as no generated answer|should open settings panel|should switch between presets|should toggle expert mode|should open history sidebar|should start new search with Cmd\\+K" --reporter=line --workers=1` => `1 passed`, `5 skipped`

## Notes

- Baseline summary: `17 passed`, `7 failed`
- Current `/knowledge` offline-protected summary after repairs: `6 passed`, `13 skipped`, `0 failed`
- Last full live-backed `/knowledge` summary before the API listener dropped: `17 passed`, `0 failed`
- Current `/knowledge` verification command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --reporter=line --workers=1`
- Current `/knowledge` failure-cluster verification command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "treats whitespace-only answers as no generated answer|should open settings panel|should switch between presets|should toggle expert mode|should open history sidebar|should start new search with Cmd\\+K" --reporter=line --workers=1`
- Current `/knowledge` failure-cluster verification summary: `1 passed`, `5 skipped`
- Current `/knowledge` handoff verification command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "should carry answer context into workspace route" --reporter=line --workers=1`
- Current `/knowledge` handoff verification summary: `1 passed`, `0 failed`
- Current `/knowledge` citation/source verification command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "keeps citation jumps aligned with the matching evidence card" --reporter=line --workers=1`
- Current `/knowledge` citation/source verification summary: `1 passed`, `0 failed`
- Current `/workspace-playground` real-backend summary after repairs: `2 passed`, `0 failed`
- Last three-spec audit rerun before the later `/knowledge` additions: `24 passed`, `0 failed`
- `/workspace-playground` live boot, grounding, compare-sources generation, and global search all passed in the same run
- `/knowledge` basic live search, follow-up, and no-results/error-state paths passed in the same run
- Live-backend caveat for the current session: the local API listener later dropped, and direct restart attempts in the worktree hit missing-env then OpenMP shared-memory startup failures; the handoff and citation additions were therefore verified deterministically, and the current full `/knowledge` rerun reflects offline-protected pass/skip behavior rather than a fresh live rerun
