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

### KQ-008: Shared KnowledgeQA links 404 because the Next app did not serve the deep-link routes

- Status: Resolved in audit worktree
- Route: `/knowledge/shared/:shareToken`
- Feature: opening shared KnowledgeQA conversations from direct permalink URLs
- Reproduction:
  1. Open a direct browser URL like `/knowledge/shared/share-token-route`
  2. Observe that the Next app renders the route-not-found page before React can mount KnowledgeQA
- Evidence:
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:970`
  - `apps/tldw-frontend/test-results/workflows-knowledge-qa-Kno-bfcba--tokenized-knowledge-routes-chromium/error-context.md`
  - `apps/tldw-frontend/pages/knowledge.tsx`
  - `apps/packages/ui/src/routes/route-registry.tsx:672`
- Suspected layer: Next page routing missing deep-link entry points even though the shared UI route registry supports them
- Why it matters: beta users opening a shared KnowledgeQA link would land on a 404 page, which breaks the share feature outright
- Resolution:
  - Added Next page entry points for both `/knowledge/shared/[shareToken]` and `/knowledge/thread/[threadId]`, each dynamically mounting the KnowledgeQA route.
  - Added deterministic Playwright coverage that resolves a shared token into hydrated query, answer, and evidence state from the direct `/knowledge/shared/:token` URL.
  - Verification: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "hydrates shared conversations from tokenized knowledge routes" --reporter=line --workers=1` => `1 passed (8.8s)`

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

### KQ-007: Export/share route surface had no E2E proof despite being exposed in the results workflow

- Status: Resolved as test hardening
- Route: `/knowledge`
- Feature: export dialog open plus share-link create/revoke on a server-backed thread
- Reproduction:
  1. Open `/knowledge`
  2. Run a server-backed search flow that renders results and exposes the `Export` button
  3. Observe that the suite previously had only component tests for the dialog and no route-level proof that the results workflow could actually open it or manage share links
- Evidence:
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:764`
  - `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/ExportDialog.a11y.test.tsx`
- Suspected layer: audit gap rather than a confirmed product defect
- Why it matters: export/share is part of the beta-facing KnowledgeQA workflow, and component tests alone do not prove the route wires the dialog to a server-backed thread correctly
- Resolution:
  - Added a deterministic route-level Playwright case that hydrates a server-backed thread, opens the export dialog from the real results shell, creates a share link, asserts the request payload uses `permission: "view"`, and revokes the resulting link.
  - Verification: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "opens the export dialog and manages share links for a server-backed thread" --reporter=line --workers=1` => `1 passed (3.8s)`

### KQ-009: Branch-from-turn behavior had provider coverage but no route-level proof

- Status: Resolved as test hardening
- Route: `/knowledge/thread/:threadId`
- Feature: branching from a prior turn into a child KnowledgeQA thread
- Reproduction:
  1. Open a server-backed thread permalink containing at least two user turns
  2. Click `Start Branch` on the earlier turn
  3. Observe that the prior suite only had provider/component coverage and did not prove the route could hydrate the thread, expose the action, and seed the child branch correctly
- Evidence:
  - `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts:1074`
  - `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/ConversationThread.test.tsx`
  - `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.branch-share.test.tsx`
- Suspected layer: audit gap rather than a confirmed product defect
- Why it matters: branching is part of the current KnowledgeQA workflow, and component tests alone do not prove the permalink route and persistence wiring create the expected child thread state
- Resolution:
  - Added a deterministic route-level Playwright case that hydrates `/knowledge/thread/source-thread-1`, clicks `Start Branch`, asserts the child-thread creation payload includes `parent_conversation_id` and `forked_from_message_id`, and verifies the UI rehydrates to the seeded branch turn.
  - Verification: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "branches from a prior turn on the thread permalink route" --reporter=line --workers=1` => `1 passed (6.6s)`

### WP-002: Workspace offline E2E bypass flag was ignored, so non-critical bootstrap failures spawned blocking connection modals

- Status: Resolved as suite + layout hardening
- Route: `/workspace-playground`
- Feature: deterministic workspace coverage while the local backend is unavailable or only partially stubbed
- Reproduction:
  1. Seed auth through the workflow helpers, which set `__tldw_test_bypass=true`
  2. Open `/workspace-playground` without stubbing every secondary bootstrap endpoint
  3. Wait for a request like `/api/v1/llm/models/metadata`, `/api/v1/chat/commands`, or `/api/v1/audio/voices/catalog?provider=kokoro` to fail
  4. Observe that `Can't reach your tldw server` modal still appears and blocks the Add Sources button
- Evidence:
  - `apps/tldw-frontend/e2e/utils/helpers.ts:45`
  - `apps/tldw-frontend/components/layout/WebLayout.tsx:123`
  - `apps/tldw-frontend/e2e/utils/page-objects/WorkspacePlaygroundPage.ts:53`
  - `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts:13`
- Suspected layer: dead test-bypass wiring in the web layout plus deterministic suite bootstrap gaps
- Why it matters: the workspace mock suite could fail for unrelated connection-modal reasons before reaching the user flow under test, which made the Add Sources surface look less stable than it actually was
- Resolution:
  - Wired `WebLayout` to honor `__tldw_test_bypass` when backend-unreachable events fire.
  - Narrowed the workspace page-object backdrop wait to visible masks only.
  - Stubbed the workspace mock suite’s non-critical model/slash-command bootstrap endpoints so deterministic route tests stop depending on incidental backend availability.
  - Verification:
    - `bunx playwright test e2e/workflows/workspace-playground.spec.ts --reporter=line --workers=1` => `6 passed (12.8s)`
    - `bunx playwright test e2e/workflows/knowledge-qa.spec.ts e2e/workflows/workspace-playground.spec.ts e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line --workers=1` => `30 passed (1.5m)`

### WP-003: Workspace add-source coverage was green without exercising the Add Sources UI

- Status: Resolved as test hardening
- Route: `/workspace-playground`
- Feature: URL ingestion and ready-source selection from the Add Sources modal
- Reproduction:
  1. Review the prior workspace workflow coverage
  2. Observe that source-selection proof depended on `seedSources()` instead of adding sources through `URL` or `My Media`
  3. Notice that a green run therefore did not prove the modal tabs, tag updates, insertion state, or ready-source selection wiring
- Evidence:
  - `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts:132`
  - `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts:208`
  - `Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-matrix.md:53`
- Suspected layer: audit gap rather than a confirmed product defect
- Why it matters: beta readiness would have been overstated for one of the most obvious workspace entry paths, especially around source ingestion and grounded-source selection
- Resolution:
  - Added deterministic route-level Playwright coverage for the `URL` tab that intercepts `/api/v1/media/add`, verifies workspace keyword tagging, and asserts the inserted source renders in `Processing` state with selection disabled.
  - Added deterministic route-level Playwright coverage for the `My Media` tab that adds a ready source from the server list and selects it from the real workspace sources pane without store mutation.
  - Verification:
    - `bunx playwright test e2e/workflows/workspace-playground.spec.ts --grep "URL tab|My Media" --reporter=line --workers=1` => `2 passed (9.2s)`
    - `bunx playwright test e2e/workflows/workspace-playground.spec.ts --reporter=line --workers=1` => `6 passed (12.8s)`

## Notes

- Baseline summary: `17 passed`, `7 failed`
- Current `/knowledge` live-backed summary after repairs: `22 passed`, `0 failed`
- Current `/knowledge` verification command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --reporter=line --workers=1`
- Current `/knowledge` failure-cluster verification command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "treats whitespace-only answers as no generated answer|should open settings panel|should switch between presets|should toggle expert mode|should open history sidebar|should start new search with Cmd\\+K" --reporter=line --workers=1`
- Current `/knowledge` failure-cluster verification summary: `1 passed`, `5 skipped`
- Current `/knowledge` handoff verification command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "should carry answer context into workspace route" --reporter=line --workers=1`
- Current `/knowledge` handoff verification summary: `1 passed`, `0 failed`
- Current `/knowledge` citation/source verification command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "keeps citation jumps aligned with the matching evidence card" --reporter=line --workers=1`
- Current `/knowledge` citation/source verification summary: `1 passed`, `0 failed`
- Current `/knowledge` export/share verification command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "opens the export dialog and manages share links for a server-backed thread" --reporter=line --workers=1`
- Current `/knowledge` export/share verification summary: `1 passed`, `0 failed`
- Current `/knowledge` shared-permalink verification command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "hydrates shared conversations from tokenized knowledge routes" --reporter=line --workers=1`
- Current `/knowledge` shared-permalink verification summary: `1 passed`, `0 failed`
- Current `/knowledge` branch verification command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "branches from a prior turn on the thread permalink route" --reporter=line --workers=1`
- Current `/knowledge` branch verification summary: `1 passed`, `0 failed`
- Current `/workspace-playground` deterministic summary after repairs: `6 passed`, `0 failed`
- Current `/workspace-playground` targeted add-source verification command: `bunx playwright test e2e/workflows/workspace-playground.spec.ts --grep "URL tab|My Media" --reporter=line --workers=1`
- Current `/workspace-playground` targeted add-source verification summary: `2 passed`, `0 failed`
- Current `/workspace-playground` real-backend summary after repairs: `2 passed`, `0 failed`
- Current three-spec audit rerun: `30 passed`, `0 failed`
- `/workspace-playground` live boot, grounding, compare-sources generation, and global search all passed in the same run
- `/knowledge` basic live search, follow-up, and no-results/error-state paths passed in the same run
- Session note: the local API listener dropped earlier in the audit and direct restart attempts hit missing-env then OpenMP shared-memory startup failures, but later verification recovered to a healthy live-backed state and the full three-spec audit passed cleanly
