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
**Status**: In Progress

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
- New route findings from the continued walkthrough:
  - `/integrations`, `/billing`, `/account`, `/signup`, `/auth/reset-password`, and `/privileges` were traced to a stale port-3000 Next dev process rather than missing source routes. A clean server on `8091` served all of them as `200`, and restarting the live `3000` server restored the same behavior.
  - `/notifications` showed the same stale-process symptom on the original `3000` server. After the restart it served the normal page HTML instead of the Next recovery shell.
  - The remaining e2e reliability gap is now narrower: several unfixed tier-1 and tier-5 specs still rely on `networkidle` and loose page-load assertions, even though the pages themselves appear healthy.
