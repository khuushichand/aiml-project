# Deep Research Run Console Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dedicated `/research` web console that lets users create deep-research runs, browse recent runs, watch a selected run live, approve checkpoints, and read artifacts and bundles.

**Architecture:** Extend the research backend with one owner-scoped recent-runs list endpoint, then build a frontend research client around `apiClient` plus a structured SSE helper. The page itself should use React Query for list/detail reads, one replayable SSE subscription for the selected run, and lazy artifact/bundle reads to keep the UI responsive.

**Tech Stack:** FastAPI, SQLite-backed `ResearchSessionsDB`, `ResearchService`, React, Next.js pages router, `@tanstack/react-query`, Axios `apiClient`, fetch-based SSE, Vitest, pytest, Bandit.

---

### Task 1: Add The Research Run History List API

**Status:** Not Started

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- Modify: `tldw_Server_API/app/core/Research/service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/research_runs.py`
- Modify: `tldw_Server_API/tests/Research/test_research_sessions_db.py`
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_service.py`
- Modify: `tldw_Server_API/tests/Research/test_research_runs_endpoint.py`

**Step 1: Write the failing tests**

Add DB, service, and endpoint tests that verify:

- `ResearchSessionsDB.list_sessions(owner_user_id, limit=...)` returns newest-first rows
- owner-scoped reads do not leak sessions on a shared DB path
- `ResearchService.list_sessions(...)` returns `ResearchSessionRow` items suitable for `ResearchRunResponse`
- `GET /api/v1/research/runs` returns only the current user’s recent runs

Example assertion shape:

```python
runs = service.list_sessions(owner_user_id="1", limit=10)
assert [run.id for run in runs] == [newest.id, older.id]
assert all(run.owner_user_id == "1" for run in runs)
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_sessions_db.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py -v`

Expected: FAIL because there is no session list helper or list endpoint yet.

**Step 3: Write minimal implementation**

Implement:

- `ResearchSessionsDB.list_sessions(owner_user_id, limit=...)`
- `ResearchService.list_sessions(owner_user_id, limit=...)`
- `GET /api/v1/research/runs`
- a small bounded default limit in the endpoint, such as `25`

Keep the response shape as:

```python
list[ResearchRunResponse]
```

Do not add pagination in this slice.

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_sessions_db.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/app/core/Research/service.py tldw_Server_API/app/api/v1/endpoints/research_runs.py tldw_Server_API/tests/Research/test_research_sessions_db.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py
git commit -m "feat(research): add run history list api"
```

### Task 2: Generalize The Frontend SSE Helper For Replayable Events

**Status:** Not Started

**Files:**
- Modify: `apps/tldw-frontend/lib/sse.ts`
- Create: `apps/tldw-frontend/lib/__tests__/sse.test.ts`

**Step 1: Write the failing tests**

Add focused Vitest coverage for a structured SSE reader that verifies:

- `event:` lines are surfaced
- `id:` lines are parsed as event IDs
- multiple `data:` lines are joined correctly
- JSON payloads are parsed when valid
- plain text payloads still work
- `[DONE]` still triggers completion
- the existing delta-oriented `streamSSE(...)` behavior stays compatible

Example assertion shape:

```ts
expect(events).toEqual([
  { event: 'snapshot', id: 4, payload: { latest_event_id: 4 } },
  { event: 'terminal', id: 5, payload: { event_id: 5 } },
])
```

**Step 2: Run tests to verify they fail**

Run: `cd apps/tldw-frontend && bunx vitest run lib/__tests__/sse.test.ts`

Expected: FAIL because `lib/sse.ts` does not currently expose structured event parsing.

**Step 3: Write minimal implementation**

Implement in `lib/sse.ts`:

- a structured SSE frame reader, such as `streamStructuredSSE(...)`
- event objects containing:
  - `event`
  - `id`
  - `payload`
- compatibility-preserving behavior for the existing `streamSSE(...)` wrapper

Prefer one shared parser in this file rather than duplicating stream parsing logic inside the research page.

**Step 4: Run tests to verify they pass**

Run: `cd apps/tldw-frontend && bunx vitest run lib/__tests__/sse.test.ts`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/tldw-frontend/lib/sse.ts apps/tldw-frontend/lib/__tests__/sse.test.ts
git commit -m "feat(frontend): add structured sse helper"
```

### Task 3: Add A Frontend Research Runs API Client

**Status:** Not Started

**Files:**
- Create: `apps/tldw-frontend/lib/api/researchRuns.ts`
- Create: `apps/tldw-frontend/lib/__tests__/researchRuns.test.ts`

**Step 1: Write the failing tests**

Add client tests that verify:

- `listResearchRuns()` calls `GET /research/runs`
- `createResearchRun(...)` calls `POST /research/runs`
- `getResearchRun(...)`, `pauseResearchRun(...)`, `resumeResearchRun(...)`, `cancelResearchRun(...)`
- `approveResearchCheckpoint(...)` posts an empty patch when requested
- `getResearchArtifact(...)` and `getResearchBundle(...)` use lazy read endpoints
- `subscribeResearchRunEvents(...)` reconnects with the latest `after_id`

Example assertion shape:

```ts
expect(apiClient.get).toHaveBeenCalledWith('/research/runs')
expect(streamUrl).toContain('/research/runs/rs_1/events/stream?after_id=5')
```

**Step 2: Run tests to verify they fail**

Run: `cd apps/tldw-frontend && bunx vitest run lib/__tests__/researchRuns.test.ts`

Expected: FAIL because the research frontend client module does not exist yet.

**Step 3: Write minimal implementation**

Implement:

- run types inside `lib/api/researchRuns.ts`
- API wrappers for:
  - list
  - create
  - get
  - pause
  - resume
  - cancel
  - approve checkpoint
  - read artifact
  - read bundle
- a `subscribeResearchRunEvents(...)` helper using:
  - `buildAuthHeaders(...)`
  - `getApiBaseUrl()`
  - the new structured SSE helper

The subscription helper should track the highest seen event ID and reconnect with:

```ts
after_id=<lastSeenId>
```

**Step 4: Run tests to verify they pass**

Run: `cd apps/tldw-frontend && bunx vitest run lib/__tests__/researchRuns.test.ts`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/tldw-frontend/lib/api/researchRuns.ts apps/tldw-frontend/lib/__tests__/researchRuns.test.ts
git commit -m "feat(frontend): add research run client"
```

### Task 4: Build The `/research` Run Console Page

**Status:** Not Started

**Files:**
- Create: `apps/tldw-frontend/pages/research/index.tsx`
- Create: `apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx`

**Step 1: Write the failing tests**

Add page tests that verify:

- the page loads a recent-runs list and selects a run
- creating a run prepends and selects the new run
- approving a checkpoint calls the correct API and refreshes state
- artifact contents load only when the artifact is opened
- bundle contents load only when the run is completed and the bundle section is opened
- incoming SSE `snapshot`, `status`, `progress`, `checkpoint`, `artifact`, and `terminal` events reduce correctly into selected-run state

Use mocked research client functions rather than a live backend in these tests.

Example assertion shape:

```tsx
await user.click(screen.getByRole('button', { name: /approve checkpoint/i }))
expect(approveResearchCheckpoint).toHaveBeenCalledWith('rs_1', 'cp_1', {})
expect(screen.getByText(/collecting sources/i)).toBeInTheDocument()
```

**Step 2: Run tests to verify they fail**

Run: `cd apps/tldw-frontend && bunx vitest run __tests__/pages/research-run-console.test.tsx`

Expected: FAIL because the page does not exist yet.

**Step 3: Write minimal implementation**

Implement a dedicated page that:

- renders a create-run form
- renders a recent-runs list
- keeps one selected run in local state
- uses React Query for:
  - recent runs
  - selected run detail
- uses `subscribeResearchRunEvents(...)` for live selected-run updates
- renders:
  - selected run status
  - run control buttons
  - read-only checkpoint details with approve
  - artifact list with lazy reads
  - bundle section for completed runs

Keep the page stacked and direct. Do not add a complex tab system or structured checkpoint editors in this slice.

**Step 4: Run tests to verify they pass**

Run: `cd apps/tldw-frontend && bunx vitest run __tests__/pages/research-run-console.test.tsx`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/tldw-frontend/pages/research/index.tsx apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx
git commit -m "feat(frontend): add research run console"
```

### Task 5: Verify The Run Console Slice

**Status:** Not Started

**Files:**
- Modify: `Docs/Plans/2026-03-07-deep-research-run-console-implementation-plan.md`

**Step 1: Run the focused backend research tests**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_sessions_db.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py -v`

Expected: PASS

**Step 2: Run the focused frontend tests**

Run: `cd apps/tldw-frontend && bunx vitest run lib/__tests__/sse.test.ts lib/__tests__/researchRuns.test.ts __tests__/pages/research-run-console.test.tsx`

Expected: PASS

**Step 3: Run Bandit on the touched backend scope**

Run: `source ../../.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/app/core/Research/service.py tldw_Server_API/app/api/v1/endpoints/research_runs.py -f json -o /tmp/bandit_deep_research_run_console.json`

Expected: JSON report written with `0` new findings in the touched backend code.

**Step 4: Update the plan status**

Mark every task in this plan complete and note residual risk, especially:

- run history remains a bounded recent list in v1
- checkpoint editing is still approve-only
- the selected-run detail is SSE-driven while the list remains polling-driven
- the page is accessible by direct route and does not yet add broader navigation changes

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-07-deep-research-run-console-implementation-plan.md
git commit -m "docs(research): finalize run console implementation plan"
```
