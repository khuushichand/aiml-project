# Deep Research Run Controls Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add pause, resume, cancel, and polling-based progress reporting to deep research runs while preserving the existing Jobs/session architecture and phase-boundary safety.

**Architecture:** Extend `research_sessions` with session-local control and progress fields, make `ResearchService` the authority for control transitions, and have `jobs.py` honor pause/cancel intent only at safe phase boundaries. Expose the new fields and control actions through the existing research run API, treat session progress as the primary polling source, and use active-job progress only as optional read-path enrichment.

**Tech Stack:** FastAPI, Pydantic, SQLite-backed `ResearchSessionsDB`, Jobs `JobManager`, pytest, Bandit.

---

### Task 1: Persist Run Control And Progress Fields

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py`
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_service.py`

**Step 1: Write the failing tests**

Add tests that verify:
- new sessions default to `control_state == "running"`
- new sessions default `progress_percent` and `progress_message` to `None`
- an existing `research_sessions` table created before this slice is migrated safely when opened
- `ResearchRunResponse` accepts the new fields when returned from service or endpoints

Example assertion shape:

```python
session = db.create_session(...)
assert session.control_state == "running"
assert session.progress_percent is None
assert session.progress_message is None
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py -v`

Expected: FAIL because the session row/schema do not yet include control/progress fields.

**Step 3: Write minimal implementation**

Implement:
- `control_state`, `progress_percent`, and `progress_message` on `ResearchSessionRow`
- additive schema migration in `ResearchSessionsDB._ensure_schema()` using `PRAGMA table_info(...)` and `ALTER TABLE ... ADD COLUMN`
- defaults on session creation:
  - `control_state = "running"`
  - `progress_percent = NULL`
  - `progress_message = NULL`
- row hydration for the new fields
- `ResearchRunResponse` fields:
  - `control_state: str`
  - `progress_percent: float | None`
  - `progress_message: str | None`

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py tldw_Server_API/tests/Research/test_research_jobs_service.py
git commit -m "feat(research): persist run control state"
```

### Task 2: Add Service-Level Pause, Resume, Cancel, And Progress Reads

**Files:**
- Modify: `tldw_Server_API/app/core/Research/service.py`
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_service.py`

**Step 1: Write the failing tests**

Add tests that verify:
- `pause_run(...)`:
  - marks `pause_requested` for executable sessions with active work
  - marks `paused` immediately for `queued` sessions with no active job
  - marks `paused` immediately for `waiting_human` checkpoint sessions
- `resume_run(...)`:
  - only works from `paused`
  - re-enqueues executable phases when `active_job_id` is empty
  - restores `waiting_human` without enqueue for paused checkpoint phases
- `cancel_run(...)`:
  - marks `cancel_requested` for executable sessions with active work
  - terminalizes queued idle or checkpoint sessions immediately as `cancelled`
  - rejects future resume
- `approve_checkpoint(...)` rejects paused or cancellation-pending sessions
- `get_session(...)` returns persisted session progress and may enrich it from the active job when available

Example assertions:

```python
updated = service.pause_run(owner_user_id="1", session_id=session.id)
assert updated.control_state == "pause_requested"

updated = service.resume_run(owner_user_id="1", session_id=session.id)
assert updated.control_state == "running"
assert updated.active_job_id == "12"
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py -v`

Expected: FAIL because `ResearchService` has no pause/resume/cancel surface or progress composition yet.

**Step 3: Write minimal implementation**

Implement in `ResearchService`:
- `pause_run(...)`
- `resume_run(...)`
- `cancel_run(...)`
- control transition validation helpers for:
  - executable phases
  - checkpoint phases
  - terminal sessions
- checkpoint approval gating for paused or cancellation-pending sessions
- read-path composition in `get_session(...)`:
  - if `active_job_id` is numeric and a Jobs manager is available, call `get_job(...)`
  - preserve session `progress_percent` and `progress_message` as authoritative and only overlay non-null Jobs values as optional enrichment
- best-effort `cancel_job(...)` call on active Jobs cancellation

Keep rules:
- `pause` is reversible
- `cancel` is terminal
- active-work cancellation is requested first and becomes terminal at a safe boundary
- `resume` never double-enqueues when `active_job_id` already exists

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/service.py tldw_Server_API/tests/Research/test_research_jobs_service.py
git commit -m "feat(research): add run control service methods"
```

### Task 3: Expose Run Controls Through The API

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/research_runs.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py`
- Modify: `tldw_Server_API/tests/Research/test_research_runs_endpoint.py`

**Step 1: Write the failing tests**

Add endpoint tests that verify:
- `POST /api/v1/research/runs/{id}/pause`
- `POST /api/v1/research/runs/{id}/resume`
- `POST /api/v1/research/runs/{id}/cancel`
- `GET /api/v1/research/runs/{id}` returns:
  - `control_state`
  - `progress_percent`
  - `progress_message`
- service `ValueError` for invalid transitions maps to `400`
- missing runs still map to `404`

Example stub return:

```python
{
    "id": "rs_1",
    "status": "queued",
    "phase": "collecting",
    "control_state": "pause_requested",
    "progress_percent": 45.0,
    "progress_message": "collecting sources",
    "active_job_id": "22",
    "latest_checkpoint_id": None,
    "completed_at": None,
}
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_runs_endpoint.py -v`

Expected: FAIL because the endpoints do not exist and the response schema is incomplete.

**Step 3: Write minimal implementation**

Implement:
- new route handlers:
  - `pause_research_run`
  - `resume_research_run`
  - `cancel_research_run`
- route-to-service calls:
  - `service.pause_run(...)`
  - `service.resume_run(...)`
  - `service.cancel_run(...)`
- error mapping:
  - `ValueError` -> `400`
  - `KeyError` -> `404`

Keep the response type as `ResearchRunResponse`.

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_runs_endpoint.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/research_runs.py tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py
git commit -m "feat(research): expose run control endpoints"
```

### Task 4: Honor Pause And Cancel At Worker Phase Boundaries

**Files:**
- Modify: `tldw_Server_API/app/core/Research/jobs.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_worker.py`

**Step 1: Write the failing tests**

Add worker tests that verify:
- phase start writes coarse progress values/messages
- `pause_requested` before a phase starts causes the phase to park the session in `paused`
- `pause_requested` after a phase completes prevents enqueue/advance and leaves the session `paused`
- `cancel_requested` before or after a phase prevents further advancement and leaves the session `cancelled`
- `completed` sessions end with `progress_percent == 100`

Example assertions:

```python
updated = db.get_session(session.id)
assert updated.control_state == "paused"
assert updated.progress_message == "collecting sources"
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_worker.py -v`

Expected: FAIL because `jobs.py` does not yet consult control state or persist progress.

**Step 3: Write minimal implementation**

Implement:
- DB helpers for updating control state and progress fields, for example:
  - `update_control_state(...)`
  - `update_progress(...)`
- in `jobs.py`, before each phase:
  - load session control state
  - short-circuit on `cancel_requested`
  - short-circuit to `paused` on `pause_requested`
- during each phase:
  - set coarse progress values/messages:
    - planning `10`
    - collecting `45`
    - synthesizing `75`
    - packaging `95`
- on successful completion:
  - if pause/cancel was requested, stop advancement
  - on final completion set progress to `100` and clear transient pause/cancel request state as appropriate

Do not implement mid-phase interruption.

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_worker.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/jobs.py tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/tests/Research/test_research_jobs_worker.py
git commit -m "feat(research): honor pause and cancel at phase boundaries"
```

### Task 5: Verify End-To-End Run Controls And Progress Polling

**Files:**
- Modify: `tldw_Server_API/tests/e2e/test_deep_research_runs.py`
- Modify: `Docs/Plans/2026-03-07-deep-research-run-controls-implementation-plan.md`

**Step 1: Write the failing test**

Extend the deep research e2e flow to verify:
- polling a run returns progress fields
- pause on a checkpoint session moves the session to `paused`
- resume restores checkpoint waiting state without enqueueing a job
- cancel on a nonterminal run is terminal and resume afterward is rejected

Example path:

1. create run
2. execute planning
3. pause at `awaiting_plan_review`
4. poll and assert `control_state == "paused"`
5. resume and assert `status == "waiting_human"`
6. cancel and assert future resume returns `400`
7. assert approving the checkpoint while paused or cancellation-pending is rejected

**Step 2: Run test to verify it fails**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`

Expected: FAIL until API and service run-controls are wired end to end.

**Step 3: Write minimal implementation**

Adjust any remaining service or endpoint details required for the full run-control lifecycle to pass.

**Step 4: Run full verification**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_provider_config.py tldw_Server_API/tests/Research/test_research_provider_adapters.py tldw_Server_API/tests/Research/test_research_broker.py tldw_Server_API/tests/Research/test_research_artifact_store.py tldw_Server_API/tests/Research/test_research_planner.py tldw_Server_API/tests/Research/test_research_limits.py tldw_Server_API/tests/Research/test_research_checkpoint_service.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_jobs_worker.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py tldw_Server_API/tests/Research/test_research_exporter.py tldw_Server_API/tests/Research/test_research_package_adapter.py tldw_Server_API/tests/Research/test_research_synthesizer.py tldw_Server_API/tests/DB_Management/test_research_db_paths.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`

Expected: PASS

Run: `source ../../.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Research tldw_Server_API/app/api/v1/endpoints/research_runs.py tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py -f json -o /tmp/bandit_deep_research_run_controls.json`

Expected: JSON report with `0` findings in the touched production paths.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-07-deep-research-run-controls-implementation-plan.md tldw_Server_API/tests/e2e/test_deep_research_runs.py
git commit -m "test(research): verify run controls end to end"
```
