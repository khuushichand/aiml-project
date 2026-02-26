# Watchlists Queue Workflow Follow-ups Implementation Plan

## Stage 1: Locale Coverage
**Goal**: Add queue-related Watchlists strings to non-English locale files used by WebUI/extension.
**Success Criteria**:
- Non-English locale directories include `watchlists.json` with queue-related keys.
- Queue keys include smart-feed label, queue action labels, queue status toasts, and queue generate-report labels.
**Tests**:
- JSON parse sanity via targeted Vitest or lint path check.
**Status**: Complete

## Stage 2: Queue -> Generate Report E2E
**Goal**: Add Playwright coverage for the user flow that queues an item and generates a run-specific report.
**Success Criteria**:
- Test queues an item from reader controls.
- Test switches to queued view and triggers report generation.
- Test asserts request payload includes `run_id` and explicit `item_ids`.
- Test asserts UI lands on Reports tab after generation.
**Tests**:
- `bunx playwright test apps/tldw-frontend/e2e/workflows/watchlists-items.spec.ts --reporter=line`
**Status**: In Progress

## Stage 3: User Guide Copy
**Goal**: Document the queue workflow in user-facing docs.
**Success Criteria**:
- User guide includes a concise section for queueing items and generating a run-specific report from queue.
- Published mirror doc updated to match source guide.
**Tests**:
- Manual doc consistency review of touched sections.
**Status**: Not Started
