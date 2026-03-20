# Deep Research Replayable Events Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a persistent per-run research event log and extend the deep research SSE endpoint so reconnecting clients can replay missed events with an `after_id` cursor before resuming the live tail, using owner-scoped event reads, transaction-consistent write points, and explicit replay cursors exposed on the wire.

**Architecture:** Introduce an append-only `research_run_events` table in `ResearchSessionsDB`, persist research-native events at the real state-transition and artifact-registration points, and update the existing SSE endpoint to emit a live `snapshot` with `latest_event_id`, replay persisted rows where `id > after_id`, and then tail new persisted rows in cursor order. Keep replay single-run only, scope event reads by `owner_user_id` plus `session_id`, emit SSE `id:` and JSON `event_id` for replayable events, and keep checkpoint events metadata-only rather than embedding full review payloads.

**Tech Stack:** FastAPI, `StreamingResponse`, `SSEStream`, SQLite-backed `ResearchSessionsDB`, `ResearchService`, research jobs/artifact helpers, pytest, Bandit.

**Status:** Complete

**Verification:** `59/59` focused research/e2e tests passed and Bandit reported `0` findings / `0` errors in `/tmp/bandit_deep_research_replayable_events.json`.

**Residual Risk:** Replay remains single-run only, `snapshot` is live but not persisted, `after_id` is the only replay cursor in v1, and reconnecting after the stored terminal row may still rely on synthetic terminal emission.

---

### Task 1: Persist Research Run Events And Read Them By Cursor

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- Modify: `tldw_Server_API/tests/Research/test_research_sessions_db.py`

**Step 1: Write the failing tests**

Add DB tests that verify:

- `research_run_events` is created automatically
- appending a research event returns a stable row with a numeric `id`
- `list_research_run_events_after(owner_user_id, session_id, after_id)` returns only newer rows in ascending `id` order
- owner-scoped reads do not leak rows for another owner on a shared DB path

Example assertion shape:

```python
first = db.record_run_event(...)
second = db.record_run_event(...)
events = db.list_run_events_after(
    owner_user_id=session.owner_user_id,
    session_id=session.id,
    after_id=first.id,
)
assert [event.id for event in events] == [second.id]
assert events[0].event_type == "status"
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_sessions_db.py -v`

Expected: FAIL because the event table and helpers do not exist yet.

**Step 3: Write minimal implementation**

Implement in `ResearchSessionsDB`:

- `research_run_events` table creation in `_ensure_schema()`
- mandatory replay index on `(owner_user_id, session_id, id ASC)`
- dataclass row model for a research run event
- `record_run_event(...)`
- `list_run_events_after(owner_user_id, session_id, after_id, limit=...)`
- `get_latest_run_event(owner_user_id, session_id, event_type)` for later dedupe
- `get_latest_run_event_id(owner_user_id, session_id)` for the snapshot watermark

Keep payload storage as JSON text and use additive schema migration only.

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_sessions_db.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/tests/Research/test_research_sessions_db.py
git commit -m "feat(research): persist replayable run events"
```

### Task 2: Add A Deduping Research Event Writer And Transaction Helpers

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/app/core/Research/service.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_service.py`

**Step 1: Write the failing tests**

Add service tests that verify:

- writing a semantic event stores the expected compact payload
- writing the same event twice for the same session suppresses the duplicate
- a changed payload for the same event type still writes a new row
- checkpoint event payloads stay metadata-only and do not embed full proposed review payloads
- transaction-bound helpers do not commit session state if the paired event write fails

Example assertion shape:

```python
written = service.record_run_event(...)
duplicate = service.record_run_event(...)
assert written.id == 1
assert duplicate.id == 1
assert len(service.list_run_events_after(...)) == 1
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py -v`

Expected: FAIL because there is no domain-level event writer or dedupe logic yet.

**Step 3: Write minimal implementation**

Implement in `ResearchService`:

- compact event payload builders if needed
- `record_run_event(...)` that:
  - normalizes payload JSON deterministically
  - compares against the latest same-type event for the session
  - suppresses duplicate writes when phase, job_id, and payload hash match
- thin read helper for `list_run_events_after(...)` if helpful for the stream layer
- transaction-bound DB helpers for state-plus-event writes where the session/checkpoint update and event insert share one SQLite transaction

Do not instrument write points yet; just add the reusable writer.

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/service.py tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/tests/Research/test_research_jobs_service.py
git commit -m "feat(research): add transactional event writer"
```

### Task 3: Instrument Real Research Write Points

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/app/core/Research/jobs.py`
- Modify: `tldw_Server_API/app/core/Research/service.py`
- Modify: `tldw_Server_API/app/core/Research/artifact_store.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_worker.py`
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_service.py`

**Step 1: Write the failing tests**

Add tests that verify event rows are appended when:

- phase/status/progress transitions occur in `jobs.py`
- checkpoint review phases are entered
- pause/resume/cancel transitions occur in `service.py`
- new artifact versions are recorded
- terminal completion is reached
- artifact events and manifest rows stay aligned on version/phase metadata
- checkpoint events contain compact metadata instead of full review payloads

Example assertion shape:

```python
events = service.list_run_events_after(owner_user_id="1", session_id=session.id, after_id=0)
assert [event.event_type for event in events] == ["status", "progress", "checkpoint"]
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_worker.py tldw_Server_API/tests/Research/test_research_jobs_service.py -v`

Expected: FAIL because the write points are not instrumented yet.

**Step 3: Write minimal implementation**

Instrument:

- `jobs.py` for `status`, `progress`, `checkpoint`, and `terminal`
- `service.py` for pause/resume/cancel and checkpoint-approval transitions
- `artifact_store.py` for `artifact` event persistence when a new version is recorded
- the DB transaction helpers from Task 2 so session/checkpoint state and event rows commit together

Reuse the same compact payload shapes already used by the SSE contract. Keep event writes close to the actual state change and avoid transport-specific logic here. For artifacts, write the file first, then commit the manifest row and `artifact` event row together in one DB transaction.

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_worker.py tldw_Server_API/tests/Research/test_research_jobs_service.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/jobs.py tldw_Server_API/app/core/Research/service.py tldw_Server_API/app/core/Research/artifact_store.py tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/tests/Research/test_research_jobs_worker.py tldw_Server_API/tests/Research/test_research_jobs_service.py
git commit -m "feat(research): record run events at write points"
```

### Task 4: Extend The SSE Endpoint For Replay With `after_id`

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/app/core/Research/streaming.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/research_runs.py`
- Modify: `tldw_Server_API/app/core/Research/service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py`
- Modify: `tldw_Server_API/tests/Research/test_research_streaming.py`
- Modify: `tldw_Server_API/tests/Research/test_research_runs_endpoint.py`

**Step 1: Write the failing tests**

Add tests that verify:

- `after_id=0` emits `snapshot` and then live/persisted events
- `after_id=N` replays only newer persisted rows
- replay is ordered by numeric event ID
- replayed and live events emit SSE `id:` lines and JSON `event_id`
- replayed rows are marked `replayed: true`
- live-tail rows are marked `replayed: false`
- the opening `snapshot` includes `latest_event_id`
- a terminal run with remaining replay rows emits them, then `terminal`, then closes
- an `after_id` ahead of the latest event still returns `snapshot` and tails safely
- a terminal run with `after_id` already past the stored terminal row still emits `snapshot`, a synthetic `terminal`, and closes

Example assertion shape:

```python
with client.stream("GET", f"/api/v1/research/runs/{session.id}/events/stream?after_id={last_seen}") as resp:
    body = b"".join(resp.iter_bytes()).decode("utf-8")
assert "event: snapshot" in body
assert "\"event_type\": \"checkpoint\"" not in body
assert "\"event_type\": \"artifact\"" in body
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_streaming.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py -v`

Expected: FAIL because the stream currently ignores persisted event history and has no `after_id` contract.

**Step 3: Write minimal implementation**

Implement:

- `after_id: int = Query(0, ge=0)` on the SSE endpoint
- `latest_event_id` on the snapshot schema and snapshot read path
- replay helpers in `streaming.py` that:
  - fetch persisted rows after the cursor
  - emit them in ascending order
  - send SSE `id:` equal to the persisted row ID
  - include JSON `event_id` and `replayed`
  - continue tailing newer persisted rows
- keep the opening `snapshot`
- keep the stream single-run scoped

Use persisted event rows as the live tail source once replay begins. Do not reintroduce direct diff-based live event generation as the main path.

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_streaming.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/streaming.py tldw_Server_API/app/api/v1/endpoints/research_runs.py tldw_Server_API/app/core/Research/service.py tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py tldw_Server_API/tests/Research/test_research_streaming.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py
git commit -m "feat(research): replay persisted events in sse"
```

### Task 5: Add Reconnect End-To-End Coverage

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/tests/e2e/test_deep_research_runs.py`

**Step 1: Write the failing test**

Add an e2e reconnect test that:

- starts the research SSE stream
- captures the highest replayable event ID observed from SSE `id:` or JSON `event_id`
- disconnects
- advances the run through more transitions
- reconnects with `after_id=<last_seen>`
- verifies only missed events are replayed before the terminal close

Keep the scenario deterministic by using the existing deep-research test-mode execution path.

**Step 2: Run test to verify it fails**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`

Expected: FAIL because reconnect replay is not implemented yet.

**Step 3: Write minimal implementation**

Adjust any stream helper or test seams needed so the reconnect flow can:

- parse replayed events deterministically
- capture numeric event IDs cleanly from the wire contract
- reconnect without hanging

Do not add REST history endpoints or `Last-Event-ID` support in this step.

**Step 4: Run test to verify it passes**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/e2e/test_deep_research_runs.py
git commit -m "test(research): verify replayable sse reconnects"
```

### Task 6: Verify The Replayable Events Slice

**Status:** Complete

**Files:**
- Modify: `Docs/Plans/2026-03-07-deep-research-replayable-events-implementation-plan.md`

**Step 1: Run the focused research test suite**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_sessions_db.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_jobs_worker.py tldw_Server_API/tests/Research/test_research_streaming.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`

Expected: PASS for the full replayable-events slice.

**Step 2: Run Bandit on the touched production scope**

Run: `source ../../.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/app/core/Research/service.py tldw_Server_API/app/core/Research/jobs.py tldw_Server_API/app/core/Research/artifact_store.py tldw_Server_API/app/core/Research/streaming.py tldw_Server_API/app/api/v1/endpoints/research_runs.py -f json -o /tmp/bandit_deep_research_replayable_events.json`

Expected: JSON report written with `0` new findings in the touched code.

**Step 3: Update the plan status**

Mark every task in this plan complete and note residual risk, especially:

- replay remains single-run only
- `snapshot` is live but not persisted
- `after_id` is the only replay cursor in v1
- terminal reconnect still relies on synthetic terminal emission when the stored terminal row is already behind `after_id`

**Step 4: Commit**

```bash
git add Docs/Plans/2026-03-07-deep-research-replayable-events-implementation-plan.md
git commit -m "docs(research): finalize replayable events implementation plan"
```
