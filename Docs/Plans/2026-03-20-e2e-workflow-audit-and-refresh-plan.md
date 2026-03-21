## Stage 1: Confirm Current Workflow Coverage
**Goal**: Identify which existing web e2e specs exercise real behavior versus route smoke or skip-heavy checks.
**Success Criteria**: Representative specs and real-server workflows have been inspected or run; stale assumptions are documented.
**Tests**: Read representative specs; run focused Playwright workflows against the live app.
**Status**: Complete

## Stage 2: Fix Stale Real-Server Workflow Assumptions
**Goal**: Update cross-feature Playwright workflows to match the current chat and quick-ingest UI contracts.
**Success Criteria**: Real-server helpers find the current Quick Ingest modal and Save to Notes action path, and they wait for durable assistant server IDs instead of racing post-stream persistence.
**Tests**: `bunx playwright test e2e/real-server-workflows.spec.ts --grep 'chat -> save to notes -> open linked conversation|quick ingest -> media review'`
**Status**: In Progress

## Stage 3: Strengthen Weak Journey Coverage
**Goal**: Improve weak journey specs so they assert concrete outcomes instead of mostly page-load success.
**Success Criteria**: At least the clearly weak journey coverage has stronger assertions around created artifacts or API effects.
**Tests**: Focused Playwright runs for the strengthened journey specs.
**Status**: Complete

## Stage 4: Verify and Summarize Suite Quality
**Goal**: Re-run focused verification, capture residual gaps, and summarize which e2e areas are solid versus still shallow.
**Success Criteria**: Updated tests pass, Bandit on touched scope is clean, and the remaining gaps are explicitly called out.
**Tests**: Focused Playwright runs, focused Vitest if touched, Bandit on touched backend/frontend paths.
**Status**: In Progress

## Audit Notes
- Added focused coverage for the `/documentation` route and the placeholder settings-CTA contract.
- The static/redirect route harness issue was traced to brittle `waitForLoadState("networkidle")` calls plus one stale `/privileges` redirect assumption. Focused packs for hosted placeholders, settings placeholders, `/documentation`, `/privileges`, and `/profile`/`/companion` now pass against a stable dev server on `8091`.
- `settings-full.spec.ts` was not catching app bugs; it was counting interactive elements before the settings shell finished hydrating. It now waits on `SettingsPage.waitForReady()` and asserts visible DOM controls instead of immediate role counts.
- `model-playground.spec.ts` and `skills.spec.ts` were also stale. The live pages rendered correctly in failure artifacts, but the specs were blocked by `networkidle`, global `aria-pressed` selectors, and an unconditional Skills API expectation on a server that intentionally resolves to the unsupported-state branch. Focused tier-5 reruns now pass.
- Existing e2e coverage quality improved materially in this pass, but there are still additional route/workspace specs with the same `networkidle` pattern in tier-1 and tier-5 that should be refreshed in follow-up work.
- Tier-5 specialized coverage is now grounded in the real routes and current UI. The stale `/osint`, `/researchers`, and `/journalists` 404 placeholders were replaced with assertions against the real public `/for/*` landing pages, and the lingering moderation status test was fixed to wait for the actual badge/guard state instead of sampling too early.
- The workflow harness was also corrected to seed the migration-complete state and extension storage shim in `e2e/utils/helpers.ts`, which removed a global false failure mode where unrelated routes could be blocked by the migration overlay.
- Tier-1 `settings-core` is now aligned with the current app contract. `/settings/health`, `/settings/mcp-hub`, and `/settings/processed` are standalone pages, not shell-backed settings subsections, so the spec now checks their real headings instead of forcing the shared settings navigation sidebar.
- Tier-4 admin coverage uncovered another stale assumption cluster, not a product regression. `/admin/maintenance`, `/admin/orgs`, and `/admin/data-ops` are now real admin workspaces, so the tests and `AdminPage` object were updated to assert their actual headings and controls. The corresponding `settings-full` failures were the same standalone-settings issue already fixed in `settings-core`.
- Verification from this wave:
  - `bunx vitest -c vitest.config.ts run __tests__/e2e-static-route-specs.guard.test.ts` passed.
  - Focused Playwright reruns passed for the refreshed tier-5 route specs (`7/7`), the full tier-5 specialized pack (`19/19`), `settings-core` (`25/25`), the refreshed admin/settings slice (`41/42` followed by the single maintenance fix passing `3/3`), and the earlier route/admin packs noted above.
  - Bandit on the touched TypeScript/e2e scope reported `0` findings and only Python-AST parse errors on `.ts/.tsx` files, which is expected for Bandit's parser.
- New route findings from the continued walkthrough:
  - `/integrations`, `/billing`, `/account`, `/signup`, `/auth/reset-password`, and `/privileges` were traced to a stale port-3000 Next dev process rather than missing source routes. A clean server on `8091` served all of them as `200`, and restarting the live `3000` server restored the same behavior.
  - `/notifications` showed the same stale-process symptom on the original `3000` server. After the restart it served the normal page HTML instead of the Next recovery shell.
  - The remaining e2e reliability gap is now narrower and has shifted mostly to broader smoke/page-object coverage outside the refreshed tier-1/tier-4/tier-5 route slices.
