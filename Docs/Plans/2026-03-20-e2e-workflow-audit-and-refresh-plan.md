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
- Live route audit confirmed the docs fix and the placeholder CTA de-duplication in rendered snapshots, but the full Playwright harness still times out after rendering the fixed DOM.
- New route findings from the continued walkthrough:
  - `/integrations`, `/billing`, `/account`, `/signup`, `/auth/reset-password`, and `/privileges` were traced to a stale port-3000 Next dev process rather than missing source routes. A clean server on `8091` served all of them as `200`, and restarting the live `3000` server restored the same behavior.
  - `/notifications` showed the same stale-process symptom on the original `3000` server. After the restart it served the normal page HTML instead of the Next recovery shell.
  - The remaining e2e reliability gap is the Playwright harness itself: several route specs time out even after the expected DOM is already rendered in the failure artifacts.
