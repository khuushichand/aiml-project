## Stage 1: Pin The Regressions
**Goal**: Add focused tests for the broken `/companion` page shim and repeated missing-chat backlink lookups in Notes.
**Success Criteria**: A page-shim test fails for the self-redirect implementation, and a Notes test proves missing conversations are not re-requested after the first miss.
**Tests**:
- `bunx vitest -c vitest.config.ts run __tests__/pages/companion-route.test.tsx`
- `bunx vitest -c vitest.config.ts run src/components/Notes/__tests__/NotesManagerPage.stage26.backlink-labels.test.tsx`
**Status**: In Progress

## Stage 2: Fix Companion Route Hosting
**Goal**: Replace the self-redirect wrapper with the standard dynamic route shim used by other working option pages.
**Success Criteria**: `/companion` loads the shared companion route component instead of redirecting to itself.
**Tests**:
- `bunx vitest -c vitest.config.ts run __tests__/pages/companion-route.test.tsx`
**Status**: Not Started

## Stage 3: Suppress Repeated Missing Backlink Lookups
**Goal**: Cache missing conversation ids in Notes so stale backlinks do not repeatedly hit the chat endpoint.
**Success Criteria**: A missing conversation id is fetched at most once per page lifecycle while valid labels still resolve normally.
**Tests**:
- `bunx vitest -c vitest.config.ts run src/components/Notes/__tests__/NotesManagerPage.stage26.backlink-labels.test.tsx`
**Status**: Not Started

## Stage 4: Verify And Continue Audit
**Goal**: Re-run focused verification, then resume the Playwright walkthrough on the newly fixed pages and additional routes.
**Success Criteria**: Targeted tests pass, Bandit reports no new findings in touched Python scope, `/companion` and `/notes` are clean in the browser, and any new issues are documented.
**Tests**:
- `bunx vitest -c vitest.config.ts run __tests__/pages/companion-route.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage26.backlink-labels.test.tsx`
- `source .venv/bin/activate && python -m bandit -r apps/tldw-frontend/pages apps/packages/ui/src/components/Notes -f json -o /tmp/bandit_companion_notes_followup.json`
**Status**: Not Started
