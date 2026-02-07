## Stage 1: Stage 3 Scope and Contract Audit
**Goal**: Confirm current Reading highlights/notes UX behavior and map PRD Stage 3 gaps to concrete UI/API changes.
**Success Criteria**: Required UI updates are identified and no incompatible API assumptions remain.
**Tests**: None (audit only).
**Status**: Complete

## Stage 2: Selection-Based Highlight Quick Actions
**Goal**: Add selection-driven highlight actions in reader content view with quick add/update/delete affordances.
**Success Criteria**: Selecting text in article content opens quick actions; users can create/update/delete highlights from the selection flow.
**Tests**: Targeted UI/unit tests for selection matching and quick-action state transitions.
**Status**: Complete

## Stage 3: Highlights Stale Badge + Filter/Search Validation
**Goal**: Ensure highlight list UX clearly surfaces stale highlights and keeps search/color filtering robust.
**Success Criteria**: Stale highlights render a visible badge and existing search/color filter behavior remains intact.
**Tests**: UI/unit tests for stale badge rendering and highlight filtering behavior.
**Status**: Complete

## Stage 4: Notes Autosave + Dirty State Protection
**Goal**: Add notes autosave and dirty-state safeguards to prevent losing edits when closing item detail.
**Success Criteria**: Dirty indicator appears during edits, autosave runs, and close/navigation attempts do not silently drop pending note changes.
**Tests**: Targeted UI tests for highlight/stale behavior (`HighlightCard.test.tsx`), manual QA run sheet (`Docs/Plans/QA_RUN_SHEET_watchlists_stage3.md`), and Playwright skeleton coverage (`apps/tldw-frontend/e2e/workflows/collections-stage3.spec.ts`).
**Status**: Complete

## Stage 3 Closeout Evidence (2026-02-07)
- Automated E2E: `bunx playwright test e2e/workflows/collections-stage3.spec.ts --reporter=line`
- Environment: `nvm use --lts`, `TLDW_WEB_URL=http://127.0.0.1:3000`, `TLDW_SERVER_URL=http://127.0.0.1:8000`
- Result: `3 passed`
