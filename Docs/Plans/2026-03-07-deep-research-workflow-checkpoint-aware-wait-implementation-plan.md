# Deep Research Workflow Checkpoint-Aware Wait Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `deep_research_wait` pause workflows cleanly when linked research runs enter human-review checkpoints, then auto-resume the same wait step after the checkpoint is resolved in `/research`.

**Architecture:** Keep `deep_research_wait` as a normal polling adapter, but let it return a structured `waiting_human` payload for research checkpoints. Add first-class engine handling for adapter-returned wait states, a durable `workflow_research_waits` linkage table, active-poll-only timeout accounting, and a narrow async bridge that resumes paused workflows back into the same wait step after research approval.

**Tech Stack:** FastAPI, existing workflow engine and DB layer, `ResearchService`, Pydantic, asyncio, pytest.

---

### Task 1: Add Red Tests For Checkpoint-Aware Wait Behavior

**Status:** Not Started

**Files:**
- Modify: `tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py`
- Modify: `tldw_Server_API/tests/Workflows/test_engine_scheduler.py`
- Modify: `tldw_Server_API/tests/Workflows/test_workflows_api.py`
- Modify: `tldw_Server_API/tests/Research/test_research_runs_endpoint.py`
- Modify: `tldw_Server_API/tests/Workflows/test_workflows_db.py`

**Step 1: Add adapter-level failing tests**

In `test_research_adapters.py`, add failing coverage for:

- `deep_research_wait` returning:

```python
{
    "__status__": "waiting_human",
    "reason": "research_checkpoint",
    "run_id": "research-session-1",
    "research_checkpoint_id": "checkpoint-1",
    "research_checkpoint_type": "sources_review",
    "active_poll_seconds": pytest.approx(0.2, rel=0.5),
}
```

when `ResearchService.get_session(...)` reports:

- `status == "waiting_human"`
- `phase == "awaiting_source_review"`

Also add a failing test that reruns the adapter with:

```python
context = {"prev": {"active_poll_seconds": 1.5}}
```

and asserts timeout accounting resumes from the prior elapsed polling time instead of restarting from zero.

**Step 2: Add workflow DB failing tests**

In `test_workflows_db.py`, add failing tests for:

- creating or updating a `workflow_research_waits` link
- claiming a link for resume exactly once
- ignoring stale second claims
- marking a link resumed

**Step 3: Add engine failing tests**

In `test_engine_scheduler.py`, add failing coverage for:

- an adapter-returned `waiting_human` updating the workflow run status to `waiting_human`
- the step run ending in `waiting_human`
- no wall-clock human timeout being scheduled when the wait payload has `reason == "research_checkpoint"`
- resuming the same `deep_research_wait` step with `next_step_id == step_id`

**Step 4: Add endpoint and workflow integration failing tests**

In `test_research_runs_endpoint.py` and `test_workflows_api.py`, add failing coverage for:

- a workflow chain:

```python
deep_research -> deep_research_wait -> prompt
```

that pauses on a research checkpoint, then resumes after `/api/v1/research/runs/{id}/checkpoints/{checkpoint_id}/patch-and-approve`
- the bridge only resuming linked paused workflow runs

**Step 5: Run focused tests to verify failure**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py \
  tldw_Server_API/tests/Workflows/test_engine_scheduler.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py \
  tldw_Server_API/tests/Workflows/test_workflows_db.py \
  tldw_Server_API/tests/Research/test_research_runs_endpoint.py \
  -q -k "deep_research_wait or research_checkpoint or workflow_research_wait"
```

Expected: FAIL for missing checkpoint-aware wait payloads, missing wait-link storage, missing engine wait handling, and missing auto-resume.

**Step 6: Commit the red tests**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py \
  tldw_Server_API/tests/Workflows/test_engine_scheduler.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py \
  tldw_Server_API/tests/Workflows/test_workflows_db.py \
  tldw_Server_API/tests/Research/test_research_runs_endpoint.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "test(workflows): cover checkpoint-aware research waits"
```

### Task 2: Add Durable Workflow↔Research Wait Storage

**Status:** Not Started

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Workflows_DB.py`
- Test: `tldw_Server_API/tests/Workflows/test_workflows_db.py`

**Step 1: Add schema support**

In `Workflows_DB.py`, add `workflow_research_waits` to both the Postgres schema string and the SQLite initialization path with:

```sql
CREATE TABLE IF NOT EXISTS workflow_research_waits (
    wait_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    research_run_id TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    checkpoint_type TEXT NOT NULL,
    wait_status TEXT NOT NULL,
    wait_payload_json TEXT NOT NULL,
    active_poll_seconds REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resumed_at TEXT
);
```

Also add:

- unique index on `(workflow_run_id, step_id)`
- lookup index on `(research_run_id, checkpoint_id, wait_status)`

**Step 2: Add DB helpers**

Implement minimal helpers:

- `upsert_research_wait_link(...)`
- `get_research_wait_link(...)`
- `claim_research_waits_for_resume(...)`
- `mark_research_wait_resumed(...)`
- `cancel_research_wait_links_for_run(...)`

Use the boring rule:

- `waiting -> resuming -> resumed`

and make `claim_research_waits_for_resume(...)` return only rows that were atomically moved out of `waiting`.

**Step 3: Re-run the DB tests**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Workflows/test_workflows_db.py -q -k "research_wait"
```

Expected: PASS

**Step 4: Commit the DB layer**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  tldw_Server_API/app/core/DB_Management/Workflows_DB.py \
  tldw_Server_API/tests/Workflows/test_workflows_db.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(workflows): persist research wait links"
```

### Task 3: Make Adapter-Returned Wait States First-Class In The Engine

**Status:** Not Started

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/engine.py`
- Test: `tldw_Server_API/tests/Workflows/test_engine_scheduler.py`

**Step 1: Add a shared helper**

Refactor the duplicated adapter-wait handling in `start_run(...)` and `continue_run(...)` into a helper with behavior like:

```python
def _handle_adapter_wait_state(..., wait_payload: dict[str, Any], step_id: str, step_run_id: str) -> bool:
    wait_status = "waiting_human" if wait_payload.get("__status__") == "waiting_human" else "waiting_approval"
    self.db.complete_step_run(step_run_id=step_run_id, status=wait_status, outputs=wait_payload)
    self.db.update_run_status(run_id, status=wait_status, status_reason=wait_payload.get("reason"))
    self._append_event(run_id, "run_waiting", {"step_id": step_id, "reason": wait_payload.get("reason")})
    ...
```

The helper should return `True` when it fully handled the pause so the caller can finalize early.

**Step 2: Skip wall-clock human timeout for research checkpoint waits**

When `wait_payload.get("reason") == "research_checkpoint"`:

- do not call `_schedule_human_timeout(...)`
- write or update the linkage record via `upsert_research_wait_link(...)`

For all other adapter-returned waits, keep the existing human-timeout behavior unchanged.

**Step 3: Support same-step resume**

Ensure the existing `continue_run(...)` path works cleanly when called with:

```python
next_step_id=step_id
last_outputs=stored_wait_payload
```

so the same `deep_research_wait` step reruns and can read `context["prev"]`.

**Step 4: Re-run focused engine tests**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Workflows/test_engine_scheduler.py -q -k "research_checkpoint or waiting_human"
```

Expected: PASS

**Step 5: Commit the engine changes**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  tldw_Server_API/app/core/Workflows/engine.py \
  tldw_Server_API/tests/Workflows/test_engine_scheduler.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(workflows): honor research checkpoint waits in engine"
```

### Task 4: Make `deep_research_wait` Checkpoint-Aware

**Status:** Not Started

**Files:**
- Modify: `tldw_Server_API/app/core/Workflows/adapters/research/wait.py`
- Modify: `tldw_Server_API/app/core/Workflows/adapters/research/_config.py`
- Test: `tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py`

**Step 1: Reuse prior elapsed polling time**

In `wait.py`, read:

```python
prev = context.get("prev") if isinstance(context.get("prev"), dict) else {}
elapsed_poll_seconds = float(prev.get("active_poll_seconds") or 0.0)
```

and continue timeout accounting from that value instead of always starting from zero.

**Step 2: Return a structured checkpoint wait payload**

When the linked research session reports:

- `status == "waiting_human"`
- `phase in {"awaiting_plan_review", "awaiting_source_review", "awaiting_outline_review"}`

return:

```python
{
    "__status__": "waiting_human",
    "reason": "research_checkpoint",
    "run_id": session.id,
    "research_phase": session.phase,
    "research_control_state": session.control_state,
    "research_checkpoint_id": session.latest_checkpoint_id,
    "research_checkpoint_type": checkpoint.type,
    "research_console_url": f"/research?run={session.id}",
    "active_poll_seconds": elapsed_poll_seconds,
}
```

Use the existing research service read path to resolve the checkpoint type instead of guessing from phase names alone.

**Step 3: Keep terminal behavior unchanged**

Do not change:

- terminal `completed` handling
- `failed` / `cancelled` behavior
- optional bundle loading
- workflow cancellation short-circuiting

This slice is additive.

**Step 4: Re-run the adapter tests**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py -q -k "deep_research_wait"
```

Expected: PASS

**Step 5: Commit the adapter**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  tldw_Server_API/app/core/Workflows/adapters/research/wait.py \
  tldw_Server_API/app/core/Workflows/adapters/research/_config.py \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(workflows): pause deep research waits on checkpoints"
```

### Task 5: Add The Async Auto-Resume Bridge

**Status:** Not Started

**Files:**
- Add: `tldw_Server_API/app/core/Workflows/research_wait_bridge.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/research_runs.py`
- Test: `tldw_Server_API/tests/Research/test_research_runs_endpoint.py`
- Test: `tldw_Server_API/tests/Workflows/test_workflows_api.py`

**Step 1: Add the bridge helper**

Create `research_wait_bridge.py` with a helper shaped like:

```python
async def resume_workflows_waiting_on_research_checkpoint(
    *,
    research_run_id: str,
    checkpoint_id: str,
) -> int:
    db = WorkflowsDatabase(...)
    claimed = db.claim_research_waits_for_resume(research_run_id=research_run_id, checkpoint_id=checkpoint_id)
    engine = WorkflowEngine(db)
    for item in claimed:
        asyncio.create_task(
            engine.continue_run(
                item.workflow_run_id,
                after_step_id=item.step_id,
                last_outputs=item.wait_payload,
                next_step_id=item.step_id,
            )
        )
        db.mark_research_wait_resumed(item.wait_id)
    return len(claimed)
```

Keep this best-effort:

- log bridge failures
- never fail the research checkpoint approval because resume scheduling failed

**Step 2: Hook the bridge from the research endpoint**

In `research_runs.py`, after successful `service.approve_checkpoint(...)`, schedule:

```python
asyncio.create_task(
    resume_workflows_waiting_on_research_checkpoint(
        research_run_id=session_id,
        checkpoint_id=checkpoint_id,
    )
)
```

inside a `contextlib.suppress(...)` or equivalent best-effort guard.

**Step 3: Re-run the endpoint and integration tests**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Research/test_research_runs_endpoint.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py \
  -q -k "research_checkpoint or deep_research_wait"
```

Expected: PASS

**Step 4: Commit the bridge**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  tldw_Server_API/app/core/Workflows/research_wait_bridge.py \
  tldw_Server_API/app/api/v1/endpoints/research_runs.py \
  tldw_Server_API/tests/Research/test_research_runs_endpoint.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(research): auto-resume workflows after checkpoint approval"
```

### Task 6: Run Full Focused Verification And Security Checks

**Status:** Not Started

**Files:**
- Modify: `Docs/Plans/2026-03-07-deep-research-workflow-checkpoint-aware-wait-implementation-plan.md`

**Step 1: Run the full focused backend suite**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py \
  tldw_Server_API/tests/Workflows/test_engine_scheduler.py \
  tldw_Server_API/tests/Workflows/test_workflows_db.py \
  tldw_Server_API/tests/Workflows/test_workflows_api.py \
  tldw_Server_API/tests/Research/test_research_runs_endpoint.py \
  -q -k "deep_research_wait or research_checkpoint or workflow_research_wait"
```

Expected: PASS

**Step 2: Run Bandit on the touched backend scope**

Run:

```bash
source .venv/bin/activate
python -m bandit -r \
  tldw_Server_API/app/core/Workflows/adapters/research/wait.py \
  tldw_Server_API/app/core/Workflows/engine.py \
  tldw_Server_API/app/core/Workflows/research_wait_bridge.py \
  tldw_Server_API/app/core/DB_Management/Workflows_DB.py \
  tldw_Server_API/app/api/v1/endpoints/research_runs.py \
  -f json -o /tmp/bandit_deep_research_workflow_checkpoint_wait.json
```

Expected: `0` findings and `0` errors in `/tmp/bandit_deep_research_workflow_checkpoint_wait.json`

**Step 3: Mark the plan complete**

Update this file:

- set every task status to `Complete`
- add a short verification note at the bottom with the final test and Bandit results

**Step 4: Commit the completed plan**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  Docs/Plans/2026-03-07-deep-research-workflow-checkpoint-aware-wait-implementation-plan.md
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "docs(research): finalize checkpoint-aware wait plan"
```
