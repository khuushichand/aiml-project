## Stage 1: Confirm Current Workflow Coverage
**Goal**: Identify which existing web e2e specs exercise real behavior versus route smoke or skip-heavy checks.
**Success Criteria**: Representative specs and real-server workflows have been inspected or run; stale assumptions are documented.
**Tests**: Read representative specs; run focused Playwright workflows against the live app.
**Status**: Complete

## Stage 2: Fix Stale Real-Server Workflow Assumptions
**Goal**: Update cross-feature Playwright workflows to match the current chat and quick-ingest UI contracts.
**Success Criteria**: Real-server helpers find the current Quick Ingest modal and Save to Notes action path, and they wait for durable assistant server IDs instead of racing post-stream persistence.
**Tests**: `bunx playwright test e2e/real-server-workflows.spec.ts --grep 'chat -> save to notes -> open linked conversation|quick ingest -> media review'`
**Status**: Complete

## Stage 3: Strengthen Weak Journey Coverage
**Goal**: Improve weak journey specs so they assert concrete outcomes instead of mostly page-load success.
**Success Criteria**: At least the clearly weak journey coverage has stronger assertions around created artifacts or API effects.
**Tests**: Focused Playwright runs for the strengthened journey specs.
**Status**: Complete

## Stage 4: Verify and Summarize Suite Quality
**Goal**: Re-run focused verification, capture residual gaps, and summarize which e2e areas are solid versus still shallow.
**Success Criteria**: Updated tests pass, Bandit on touched scope is clean, and the remaining gaps are explicitly called out.
**Tests**: Focused Playwright runs, focused Vitest if touched, Bandit on touched backend/frontend paths.
**Status**: Complete

## Audit Notes
- Added focused coverage for the `/documentation` route and the placeholder settings-CTA contract.
- The static/redirect route harness issue was traced to brittle `waitForLoadState("networkidle")` calls plus one stale `/privileges` redirect assumption. Focused packs for hosted placeholders, settings placeholders, `/documentation`, `/privileges`, and `/profile`/`/companion` now pass against a stable dev server on `8091`.
- `settings-full.spec.ts` was not catching app bugs; it was counting interactive elements before the settings shell finished hydrating. It now waits on `SettingsPage.waitForReady()` and asserts visible DOM controls instead of immediate role counts.
- `model-playground.spec.ts` and `skills.spec.ts` were also stale. The live pages rendered correctly in failure artifacts, but the specs were blocked by `networkidle`, global `aria-pressed` selectors, and an unconditional Skills API expectation on a server that intentionally resolves to the unsupported-state branch. Focused tier-5 reruns now pass.
- Existing e2e coverage quality improved materially in this pass, but there are still additional route/workspace specs with the same `networkidle` pattern in tier-1 and tier-5 that should be refreshed in follow-up work.
- Tier-5 specialized coverage is now grounded in the real routes and current UI. The stale `/osint`, `/researchers`, and `/journalists` 404 placeholders were replaced with assertions against the real public `/for/*` landing pages, and the lingering moderation status test was fixed to wait for the actual badge/guard state instead of sampling too early.
- The workflow harness was also corrected to seed the migration-complete state and extension storage shim in `e2e/utils/helpers.ts`, which removed a global false failure mode where unrelated routes could be blocked by the migration overlay.
- Chat workflow coverage is now aligned with the current chat surface instead of pre-redesign assumptions. The `ChatPage` object no longer waits on an empty assistant transcript, it auto-selects a model when chat opens in the valid "Select a model" state, and the refreshed chat spec now waits on durable visible transcript changes instead of a brittle `/chat/completions` transport assumption.
- Quick Ingest workflow coverage is now aligned with the wizard UI instead of the legacy modal contract. The e2e spec follows the current `Add -> Configure -> Review -> Processing -> Results` flow, asserts the `wizard-results-step`/completed-items surface instead of the removed `#quick-ingest-tab-results` and `quick-ingest-complete` selectors, and the close-during-processing coverage now targets the real `Processing is in progress` confirmation dialog (`Stay`, `Cancel All`, `Minimize to Background`) instead of the removed `Keep running` / `Cancel run` prompt.
- Search workflow coverage is now aligned with the current Knowledge page contract instead of pre-redesign result cards. The `SearchPage` object now treats `Search complete. 0 sources found.` / `No relevant context found.` as the modern no-results state, uses `Open in Workspace` as the current result-interaction fallback when traditional result cards are absent, and treats `New search` / `Start new topic` as the modern way back from answer context.
- The watchlist journey is now a real regression guard instead of a skip-heavy smoke test. `e2e/workflows/journeys/watchlist-ingest-notify.spec.ts` now seeds a feed and monitor, triggers the real `POST /api/v1/watchlists/jobs/:id/run` action, verifies the resulting Activity row, verifies the ingested Article, and verifies the Notifications inbox item through deterministic route mocks.
- Strengthening that journey exposed a real product bug in the watchlists UI: in progressive mode, the orientation and teach-point buttons (`Open Monitors`, `Open Activity`) were calling `setActiveTab(...)` directly, which changed the guidance copy but did not expand the inline secondary sections. `WatchlistsPlaygroundPage` now routes those actions through `navigateToTab(...)`, and the unit coverage in `WatchlistsPlaygroundPage.orientation-guidance.test.tsx` now pins the persisted `watchlists:secondary-expanded:v1` behavior for `monitors` and `activity`.
- Tier-1 `settings-core` is now aligned with the current app contract. `/settings/health`, `/settings/mcp-hub`, and `/settings/processed` are standalone pages, not shell-backed settings subsections, so the spec now checks their real headings instead of forcing the shared settings navigation sidebar.
- Tier-4 admin coverage uncovered another stale assumption cluster, not a product regression. `/admin/maintenance`, `/admin/orgs`, and `/admin/data-ops` are now real admin workspaces, so the tests and `AdminPage` object were updated to assert their actual headings and controls. The corresponding `settings-full` failures were the same standalone-settings issue already fixed in `settings-core`.
- Verification from this wave:
  - `bunx vitest -c vitest.config.ts run __tests__/e2e-static-route-specs.guard.test.ts` passed.
  - `bunx vitest -c vitest.config.ts run __tests__/e2e-page-object-contracts.guard.test.ts` passed after the chat/media harness refresh.
  - Focused Playwright reruns passed for the refreshed tier-5 route specs (`7/7`), the full tier-5 specialized pack (`19/19`), `settings-core` (`25/25`), the refreshed admin/settings slice (`41/42` followed by the single maintenance fix passing `3/3`), and the earlier route/admin packs noted above.
  - The refreshed workflow slice passed on `March 21, 2026` against `http://localhost:8091`: chat send/history/scroll/copy (`4/4`) plus the updated Quick Ingest completion/processing-confirmation cases (`2/2`).
  - The three stale Search workflow failures reran clean on `March 21, 2026` against `http://localhost:8091`: nonexistent-content empty-state handling plus the two result-interaction cases (`3/3`).
  - Bandit on the touched TypeScript/e2e scope reported `0` findings and only Python-AST parse errors on `.ts/.tsx` files, which is expected for Bandit's parser.
- Final host verification on `March 21, 2026` passed for the full `e2e/smoke/all-pages.spec.ts` pack against the stable dev server on `http://localhost:8091`: `233/233` passing in `32.8m`.
- The last blocking smoke failure was `/__debug__/sidepanel-chat`, which turned out to be route-local render churn from passing a fresh `createSafeStorage()` instance into `useStorage(...)` on every render. The route now reuses a stable ref-backed storage instance, and the regression is pinned by `src/routes/__tests__/sidepanel-chat.background-storage-stability.guard.test.ts`.
- With the blocking smoke regressions fixed, the remaining audit findings are non-blocking quality debt:
  - several older workflow specs outside the refreshed smoke/admin/tier-5 packs still rely on `waitForLoadState("networkidle")` and should be migrated to visible UI readiness markers
  - some routes still emit allowlisted Ant Design/react warnings in live smoke, including `/quiz`, `/kanban`, and `/characters`
  - the next weak workflow cluster is now centered on older live-data specs with conditional skips or `networkidle` waits, especially `tier-2-features/sources.spec.ts`, `world-books.spec.ts`, `notes-flashcards.spec.ts`, and the remaining generic `settings.spec.ts` / `chat.spec.ts` / `search.spec.ts` cleanup spots
- New route findings from the continued walkthrough:
  - `/integrations`, `/billing`, `/account`, `/signup`, `/auth/reset-password`, and `/privileges` were traced to a stale port-3000 Next dev process rather than missing source routes. A clean server on `8091` served all of them as `200`, and restarting the live `3000` server restored the same behavior.
  - `/notifications` showed the same stale-process symptom on the original `3000` server. After the restart it served the normal page HTML instead of the Next recovery shell.
  - The remaining e2e reliability gap is now narrower and has shifted mostly to broader smoke/page-object coverage outside the refreshed tier-1/tier-4/tier-5 route slices.
