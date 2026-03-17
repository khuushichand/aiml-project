# Knowledge Workspace Beta Readiness Audit Matrix

**Date:** 2026-03-16
**Worktree:** `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/knowledge-workspace-beta-audit`
**Branch:** `codex/knowledge-workspace-beta-audit`

## Classification Rules

- `Live-covered`: proven against the real backend with meaningful assertions
- `Mock-only`: covered only through interception, local storage injection, or store seeding
- `Misleading`: a green test exists but does not credibly prove the user workflow
- `Missing`: no meaningful E2E proof exists yet

## Environment Notes

- API preflight target: `http://127.0.0.1:8000`
- API key used by tests: `THIS-IS-A-SECURE-KEY-123-FAKE-KEY`
- Frontend base URL: `http://localhost:8080`
- Sandbox-local `curl` could not reach `127.0.0.1:8000`, but escalated `curl` succeeded
- Worktree required fresh `bun install` in `apps/`
- Live test data prefix: `e2e-knowledge-workspace-<generateTestId>`
- Cleanup mode for now: record created IDs/titles by default; live workspace paste-ingestion coverage now also verifies the delete path for the created media ID

## `/knowledge`

| Route | Feature | Existing Test(s) | Classification | Evidence | Follow-up |
| --- | --- | --- | --- | --- | --- |
| `/knowledge` | Search bar render and `/` focus | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Mock-only | UI assertions only, no backend proof | Reclassify after live baseline |
| `/knowledge` | Live search request and results | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Live-covered | Waits on `/api/v1/rag/search` and asserts request body | Validate actual stability in baseline run |
| `/knowledge` | Evidence panel after live search | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Live-covered | Uses live search and evidence panel expectations; citation/source identity is now covered separately by a deterministic route test | Keep paired with the separate citation/source coherence row |
| `/knowledge` | Progressive loading stages | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Mock-only | Intercepted flow now passes with stage text plus rendered answer/citation/evidence assertions | Keep as non-gating edge coverage; see resolved `KQ-001` |
| `/knowledge` | Whitespace answer handling | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Mock-only | Deterministic route test now stubs the KnowledgeQA bootstrap plus intercepted blank-answer payload and asserts the source-only state | Keep as edge-case non-gating unless live repro exists |
| `/knowledge` | Settings dialog open/preset/expert/apply flows | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Live-covered | Route-scoped selectors prove real drawer open, preset state, expert toggle, and applied request payload when the API is reachable; the suite now preflight-skips these checks instead of failing through a connection modal when the backend is down | Resolved `KQ-002`; candidate for beta gate once live preflight is healthy |
| `/knowledge` | Follow-up thread continuity | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Live-covered | Sends second query and checks conversation turn count | Verify reload continuity separately |
| `/knowledge` | History sidebar and restored prior searches | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Live-covered | Route-scoped sidebar open and `Cmd+K` reset passed in the earlier live run; the suite now preflight-skips these checks when the backend is unavailable instead of timing out behind the connection modal | Resolved `KQ-003`; add explicit reload-restore coverage separately |
| `/knowledge` | Error state when API fails | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Mock-only | Forces `500` via route interception | Keep as non-gating edge coverage |
| `/knowledge` | Workspace handoff from answer panel | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`, `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.workspace-handoff.test.tsx` | Mock-only | Route-level deterministic Playwright now proves answer-panel click, `/workspace-playground` navigation, source prefill selection, and imported note content | Promote to live once backend preflight is stable again |
| `/knowledge` | Export dialog and share-link management | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`, `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/ExportDialog.a11y.test.tsx` | Mock-only | Deterministic route test now proves export dialog open plus share-link create/revoke on a server-backed thread | Promote to live once backend preflight is stable again |
| `/knowledge` | Shared permalink hydration | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`, provider/component tests | Mock-only | Deterministic route test now proves `/knowledge/shared/:token` resolves into hydrated query/answer/results, and the missing Next deep-link pages were added so direct links no longer 404 before React mounts | Promote to live once backend preflight is stable again |
| `/knowledge` | Branch from conversation turn | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`, provider/component tests | Mock-only | Deterministic route test now proves `/knowledge/thread/:threadId` hydrates a multi-turn thread, exposes `Start Branch`, and creates a child thread seeded from the selected turn | Promote to live once backend preflight is stable again |
| `/knowledge` | Citation-to-source coherence | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Mock-only | Deterministic route test clicks `Jump to source 2`, then asserts the citation becomes current and focus transfers to `#source-card-1` while source 1 loses focus | Promote to live once backend preflight is stable again |

## `/workspace-playground`

| Route | Feature | Existing Test(s) | Classification | Evidence | Follow-up |
| --- | --- | --- | --- | --- | --- |
| `/workspace-playground` | Core pane render | `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts` | Mock-only | Baseline mocked suite passed; still not live proof | Use only as support coverage |
| `/workspace-playground` | Global search modal shortcut | `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts`, component tests | Mock-only | No real backend coupling | Reclassify as support coverage |
| `/workspace-playground` | Pane collapse/restore | `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts` | Mock-only | Pure UI exercise | Support coverage only |
| `/workspace-playground` | Add Sources modal open/close | `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts` | Mock-only | Modal shell interaction still has standalone coverage, and the same spec now also boots reliably offline because it stubs non-critical model/command metadata and the layout honors the test bypass flag for backend-unreachable modals | Keep as support coverage; live intake is tracked separately |
| `/workspace-playground` | Boot against live backend | `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts` | Live-covered | Baseline run passed boot/bootstrap health check | Candidate for beta gate |
| `/workspace-playground` | Live core interaction shell (workspace search, pane toggles, add-source modal open/close) | `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts` | Live-covered | Real-backend interaction flow now passes and the formerly flaky sequence is stable across `--repeat-each 5` | Resolved `WP-001`; candidate for beta gate |
| `/workspace-playground` | Source selection through Add Sources UI | `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts`, `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts` | Live-covered | The real-backend suite now ingests a pasted text source through the Add Sources modal, waits for the inserted row to reach `Ready`, selects it from the real sources pane, and asserts `1 selected`; deterministic `My Media` coverage remains as support proof for the ready-library path | Add separate live `My Media` coverage only if library-backed selection becomes beta-critical |
| `/workspace-playground` | Chat grounding on selected source | `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx` | Mock-only | Component coverage still exercises grounded-answer rendering, but the current route suites do not submit or verify a grounded chat turn against selected sources | Add deterministic or live route proof before treating grounded chat as beta-gated |
| `/workspace-playground` | Studio compare-sources generation | `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx` | Mock-only | Component coverage still exercises compare-sources generation and usage metrics, but no current route-level suite proves the full compare flow from selected sources | Add deterministic or live route proof before treating compare generation as beta-gated |
| `/workspace-playground` | Global search across live chat turns | `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts`, `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/workspace-global-search.test.ts`, `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx` | Mock-only | Route coverage currently proves only modal open/close, while component tests cover result selection; there is no current live route proof for searching across chat turns and opening the matched result | Add deterministic or live route proof for result-backed global search before beta |
| `/workspace-playground` | Add-source ingestion via Paste tab | `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts`, `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.ingestion.test.tsx`, `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage2.intake.test.tsx` | Live-covered | Real-backend Playwright now posts pasted text through the live Add Sources modal, proves `/api/v1/media/add` succeeds, asserts the inserted row is immediately usable, and cleans up the created media ID; component regressions now lock `media_type` on both paste and upload requests so the backend validation bug cannot silently return | Candidate for beta gate |
| `/workspace-playground` | Add-source ingestion via URL tab | `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts`, component tests | Mock-only | Deterministic route test now drives the real `URL` tab, intercepts `/api/v1/media/add`, verifies workspace keyword tagging, and asserts the inserted source renders in `Processing` state with selection disabled | Promote to live once the backend can reliably ingest and expose a stable test URL |
| `/workspace-playground` | Filters/sort/list-state persistence | `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts`, component tests | Mock-only | Deterministic Playwright now seeds mixed-status sources, applies `Status Ready` plus `Name (A-Z)`, hides and restores the sources pane, and proves both the rendered order and advanced-control values survive the remount | Promote only if a reliable live mixed-source fixture becomes available |
| `/workspace-playground` | Studio cancellation and reload recovery | `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts`, `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx`, `apps/packages/ui/src/store/__tests__/workspace.test.ts` | Mock-only | Deterministic Playwright now stalls summary source loading, proves the user can cancel an in-flight summary and see the failed artifact, then reloads mid-generation and verifies the interrupted artifact rehydrates as failed with the recovery message | Promote only if a stable live interrupt harness becomes available |
| `/workspace-playground` | Trust/status/telemetry surfaces | `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx`, docs | Mock-only | Component coverage exercises telemetry summaries and recovered-artifact counters, but no current route-level suite proves those trust/status surfaces end to end | Add targeted route checks when telemetry surfaces become release-gating |

## Baseline Run Notes

- Status: Complete
- Command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts e2e/workflows/workspace-playground.spec.ts e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line --workers=1`
- Outcome: `17 passed`, `7 failed`, total runtime about `8.1m`
- Passed highlights:
  - `/knowledge` basic live search, follow-up, and no-results/error-state checks
  - `/workspace-playground` live boot, grounding, studio compare, and global search
  - mocked `/workspace-playground` shell interactions
- Failed highlights:
  - `/knowledge` mocked delayed-loading assertion
  - `/knowledge` settings open/preset/expert/apply flows
  - `/knowledge` history sidebar flow
  - `/workspace-playground` live core interaction flow blocked by fixed overlay intercepting pane toggle clicks
- Follow-up: create bug log entries for each failure cluster and convert them into targeted task work

## Current Route Verification

- `/knowledge` command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --reporter=line --workers=1`
- `/knowledge` current live-backed outcome: `22 passed`, `0 failed`, runtime about `1.2m`
- `/knowledge` net effect:
  - removed stale selector failures from settings and history flows
  - replaced brittle mocked delayed-answer text assertion with rendered citation/evidence assertions
  - added deterministic citation-to-source identity coverage
  - isolated the whitespace-only mock case from live bootstrap dependencies
  - added deterministic export/share route coverage for server-backed KnowledgeQA threads
  - fixed direct `/knowledge/shared/:token` deep links by wiring the missing Next page routes and added deterministic shared-permalink hydration coverage
  - added deterministic `/knowledge/thread/:threadId` branch coverage seeded from a multi-turn server thread
  - upgraded settings/history checks from permissive smoke tests to route-scoped behavioral assertions, with preflight skips when live backend is unavailable
- `/knowledge` targeted handoff command:
  - `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "should carry answer context into workspace route" --reporter=line --workers=1`
  - outcome: `1 passed`, runtime about `4.3s`
  - classification note: this handoff proof is deterministic route coverage, not live-backend coverage
- `/knowledge` targeted citation/source coherence command:
  - `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "keeps citation jumps aligned with the matching evidence card" --reporter=line --workers=1`
  - outcome: `1 passed`, runtime about `4.4s`
  - classification note: this is deterministic route coverage, not live-backend coverage
- `/knowledge` targeted export/share command:
  - `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "opens the export dialog and manages share links for a server-backed thread" --reporter=line --workers=1`
  - outcome: `1 passed`, runtime about `3.8s`
  - classification note: this is deterministic route coverage, not live-backend coverage
- `/knowledge` targeted shared-permalink command:
  - `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "hydrates shared conversations from tokenized knowledge routes" --reporter=line --workers=1`
  - outcome: `1 passed`, runtime about `8.8s`
  - classification note: this is deterministic route coverage, not live-backend coverage
- `/knowledge` targeted branch command:
  - `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "branches from a prior turn on the thread permalink route" --reporter=line --workers=1`
  - outcome: `1 passed`, runtime about `6.6s`
  - classification note: this is deterministic route coverage, not live-backend coverage
- `/workspace-playground` deterministic command: `bunx playwright test e2e/workflows/workspace-playground.spec.ts --reporter=line --workers=1`
- `/workspace-playground` deterministic outcome: `9 passed`, `0 failed`, runtime about `13.7s`
- `/workspace-playground` targeted add-source command:
  - `bunx playwright test e2e/workflows/workspace-playground.spec.ts --grep "URL tab|My Media" --reporter=line --workers=1`
  - outcome: `2 passed`, `0 failed`, runtime about `9.2s`
- `/workspace-playground` targeted filter/sort remount command:
  - `bunx playwright test e2e/workflows/workspace-playground.spec.ts --grep "preserves advanced source filters and temporary sort across sources pane remounts" --reporter=line --workers=1`
  - outcome: `1 passed`, `0 failed`, runtime about `4.8s`
- `/workspace-playground` targeted studio cancel/recovery command:
  - `bunx playwright test e2e/workflows/workspace-playground.spec.ts --grep "cancels in-flight summary generation|recovers interrupted summary generation" --reporter=line --workers=1`
  - outcome: `2 passed`, `0 failed`, runtime about `5.1s`
- `/workspace-playground` targeted live paste-intake command:
  - `bunx playwright test e2e/workflows/workspace-playground.real-backend.spec.ts --grep "ingests pasted text through the live add-source flow" --reporter=line --workers=1`
  - outcome: `1 passed`, `0 failed`, runtime about `7.8s`
- `/workspace-playground` real-backend command: `bunx playwright test e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line --workers=1`
- `/workspace-playground` real-backend outcome after repairs: `3 passed`, `0 failed`, runtime about `7.8s`
- `/workspace-playground` stability verification:
  - `bunx playwright test e2e/workflows/workspace-playground.real-backend.spec.ts --grep "supports core workspace interactions with live API context" --repeat-each 5 --reporter=line --workers=1`
  - outcome: `5 passed`, `0 failed`, runtime about `22.3s`
- Current three-spec audit rerun:
  - command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts e2e/workflows/workspace-playground.spec.ts e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line --workers=1`
  - outcome: `34 passed`, `0 failed`, runtime about `1.5m`
- Current live-backend note:
  - the local API listener dropped earlier in the session, but later verification recovered to a healthy live-backed state and the full three-spec audit passed without skips
- Current classification correction:
  - the present real-backend workspace suite covers boot health, shell interactions, and live pasted-source intake only; earlier audit notes that implied live grounding, compare generation, or result-backed global search coverage were overstated and have been reclassified above
