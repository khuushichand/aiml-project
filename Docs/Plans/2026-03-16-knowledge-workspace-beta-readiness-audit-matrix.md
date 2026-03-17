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
- Cleanup mode for now: record created IDs/titles unless a reliable delete path is verified during audit

## `/knowledge`

| Route | Feature | Existing Test(s) | Classification | Evidence | Follow-up |
| --- | --- | --- | --- | --- | --- |
| `/knowledge` | Search bar render and `/` focus | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Mock-only | UI assertions only, no backend proof | Reclassify after live baseline |
| `/knowledge` | Live search request and results | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Live-covered | Waits on `/api/v1/rag/search` and asserts request body | Validate actual stability in baseline run |
| `/knowledge` | Evidence panel after live search | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Live-covered | Uses live search and evidence panel expectations | Check whether citations map coherently to source cards |
| `/knowledge` | Progressive loading stages | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Mock-only | Intercepted flow now passes with stage text plus rendered answer/citation/evidence assertions | Keep as non-gating edge coverage; see resolved `KQ-001` |
| `/knowledge` | Whitespace answer handling | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Mock-only | Intercepted API payload | Keep as edge-case non-gating unless live repro exists |
| `/knowledge` | Settings dialog open/preset/expert/apply flows | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Live-covered | Route-scoped selectors now prove real drawer open, preset state, expert toggle, and applied request payload | Resolved `KQ-002`; candidate for beta gate |
| `/knowledge` | Follow-up thread continuity | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Live-covered | Sends second query and checks conversation turn count | Verify reload continuity separately |
| `/knowledge` | History sidebar and restored prior searches | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Live-covered | Route-scoped sidebar open and `Cmd+K` reset now pass live; reload restoration is still unproven | Resolved `KQ-003`; add explicit reload-restore coverage separately |
| `/knowledge` | Error state when API fails | `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts` | Mock-only | Forces `500` via route interception | Keep as non-gating edge coverage |
| `/knowledge` | Workspace handoff from answer panel | `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.workspace-handoff.test.tsx` | Mock-only | Component test only, no real route transition or prefill proof | Add live Playwright |
| `/knowledge` | Share/export/branch flows | component tests only | Missing | No live E2E proof found yet | Baseline and add route coverage |
| `/knowledge` | Citation-to-source coherence | partial in `knowledge-qa.spec.ts` | Misleading | Shows panel opens, but not strong source/evidence identity proof | Add targeted live assertion |

## `/workspace-playground`

| Route | Feature | Existing Test(s) | Classification | Evidence | Follow-up |
| --- | --- | --- | --- | --- | --- |
| `/workspace-playground` | Core pane render | `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts` | Mock-only | Baseline mocked suite passed; still not live proof | Use only as support coverage |
| `/workspace-playground` | Global search modal shortcut | `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts`, component tests | Mock-only | No real backend coupling | Reclassify as support coverage |
| `/workspace-playground` | Pane collapse/restore | `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts` | Mock-only | Pure UI exercise | Support coverage only |
| `/workspace-playground` | Add Sources modal open/close | `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts` | Mock-only | Modal shell only, no ingestion | Add live intake/ingestion test |
| `/workspace-playground` | Boot against live backend | `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts` | Live-covered | Baseline run passed boot/bootstrap health check | Candidate for beta gate |
| `/workspace-playground` | Live core interaction shell (workspace search, pane toggles, add-source modal open/close) | `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts` | Live-covered | Real-backend interaction flow now passes and the formerly flaky sequence is stable across `--repeat-each 5` | Resolved `WP-001`; candidate for beta gate |
| `/workspace-playground` | Source selection with seeded store data | `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts`, real-backend spec | Misleading | The route is stable again, but source selection still depends on store seeding rather than a real ingestion flow | Replace with live add-source path; keep current checks as support coverage only |
| `/workspace-playground` | Chat grounding on selected source | `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts` | Live-covered | Baseline run passed grounding request assertions | Candidate for beta gate |
| `/workspace-playground` | Studio compare-sources generation | `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts` | Live-covered | Baseline run passed compare-sources generation | Add cancel/recovery coverage |
| `/workspace-playground` | Global search across live chat turns | `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts` | Live-covered | Baseline run passed live global-search flow | Candidate for broader live coverage |
| `/workspace-playground` | Real add-source ingestion | component tests only | Missing | No live E2E proof found yet | Add live Playwright |
| `/workspace-playground` | Filters/sort/list-state persistence | component tests only | Missing | No route-level live proof found yet | Add live Playwright |
| `/workspace-playground` | Studio cancellation and reload recovery | component tests only | Missing | No live route proof found yet | Add live Playwright |
| `/workspace-playground` | Trust/status/telemetry surfaces | docs + component tests | Missing | No explicit route-level live proof found yet | Add targeted live checks |

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
- `/knowledge` outcome after repairs: `17 passed`, `0 failed`, runtime about `59.3s`
- `/knowledge` net effect:
  - removed stale selector failures from settings and history flows
  - replaced brittle mocked delayed-answer text assertion with rendered citation/evidence assertions
  - upgraded settings/history checks from permissive smoke tests to route-scoped behavioral assertions
- `/workspace-playground` real-backend command: `bunx playwright test e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line --workers=1`
- `/workspace-playground` real-backend outcome after repairs: `2 passed`, `0 failed`, runtime about `6.0s`
- `/workspace-playground` stability verification:
  - `bunx playwright test e2e/workflows/workspace-playground.real-backend.spec.ts --grep "supports core workspace interactions with live API context" --repeat-each 5 --reporter=line --workers=1`
  - outcome: `5 passed`, `0 failed`, runtime about `22.3s`
- Original three-spec audit rerun:
  - command: `bunx playwright test e2e/workflows/knowledge-qa.spec.ts e2e/workflows/workspace-playground.spec.ts e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line --workers=1`
  - outcome: `24 passed`, `0 failed`, runtime about `1.1m`
