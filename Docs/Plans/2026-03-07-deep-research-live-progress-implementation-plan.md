# Deep Research Live Progress SSE Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a research-native SSE endpoint that streams a fresh deep-research snapshot plus live status, progress, checkpoint, artifact, and terminal updates for a single research session.

**Architecture:** Keep the HTTP surface in `research_runs.py`, add a dedicated polling and diffing helper in `tldw_Server_API/app/core/Research/streaming.py`, and extend the research schemas/service read model so the stream can emit richer reconnect-safe snapshots. Session state remains authoritative for lifecycle, while the streaming helper may read the active Jobs row separately for fresher progress.

**Tech Stack:** FastAPI, `StreamingResponse`, `SSEStream`, Pydantic, `ResearchService`, `ResearchSessionsDB`, pytest, Bandit.

---

### Task 1: Add A Rich Research Stream Snapshot Model

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py`
- Modify: `tldw_Server_API/app/core/Research/service.py`
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_service.py`

**Step 1: Write the failing tests**

Add service/schema tests that verify a research stream snapshot can include:

- current run state
- current checkpoint summary when `latest_checkpoint_id` exists
- current artifact manifest summary from the latest artifact versions only

Example assertion shape:

```python
snapshot = service.get_stream_snapshot(owner_user_id="1", session_id=session.id)
assert snapshot.run.id == session.id
assert snapshot.checkpoint.checkpoint_id == checkpoint.id
assert {item.artifact_name for item in snapshot.artifacts} == {"plan.json", "provider_config.json"}
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py -v`

Expected: FAIL because no research stream snapshot helper or richer snapshot schema exists yet.

**Step 3: Write minimal implementation**

Implement:

- new schema models in `research_runs_schemas.py`:
  - `ResearchCheckpointSummary`
  - `ResearchArtifactManifestEntry`
  - `ResearchRunSnapshotResponse`
- a service helper in `service.py`:
  - `get_stream_snapshot(...)`
- snapshot composition rules:
  - load the session row
  - load the current checkpoint by `latest_checkpoint_id` when present
  - load artifacts with latest-version-only semantics per `artifact_name`
  - keep artifact payloads metadata-only

Do not change the existing polling endpoint contract yet beyond shared schema reuse.

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py tldw_Server_API/app/core/Research/service.py tldw_Server_API/tests/Research/test_research_jobs_service.py
git commit -m "feat(research): add stream snapshot read model"
```

### Task 2: Build The Research SSE Diffing Helper

**Files:**
- Create: `tldw_Server_API/app/core/Research/streaming.py`
- Modify: `tldw_Server_API/app/core/Research/service.py`
- Modify: `tldw_Server_API/tests/Research/test_research_streaming.py`

**Step 1: Write the failing tests**

Create `test_research_streaming.py` with focused tests for:

- initial snapshot shaping
- `status` emission when `status`, `phase`, `control_state`, or `active_job_id` changes
- `progress` emission when progress values change
- `checkpoint` emission when checkpoint metadata changes
- `artifact` emission only for new `(artifact_name, artifact_version)` observations after baseline
- `terminal` emission when the session reaches `completed`, `failed`, or `cancelled`

Example assertion shape:

```python
events = list(diff_stream_events(previous=old_snapshot, current=new_snapshot))
assert [event["event"] for event in events] == ["status", "progress", "artifact"]
assert events[-1]["data"]["artifact_name"] == "report_v1.md"
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_streaming.py -v`

Expected: FAIL because `streaming.py` and the diff helpers do not exist yet.

**Step 3: Write minimal implementation**

Implement in `streaming.py`:

- a polling snapshot type or dataclass built from:
  - `ResearchService.get_stream_snapshot(...)`
  - direct active-job lookups for fresher progress when available
- latest-artifact baseline tracking by `(artifact_name, artifact_version)`
- change-detection helpers for:
  - `status`
  - `progress`
  - `checkpoint`
  - `artifact`
  - `terminal`
- a stream-state helper that treats:
  - session lifecycle as authoritative
  - job progress as optional enrichment

If a job lookup fails, keep streaming from session state instead of erroring.

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_streaming.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/streaming.py tldw_Server_API/app/core/Research/service.py tldw_Server_API/tests/Research/test_research_streaming.py
git commit -m "feat(research): add live progress stream diffing"
```

### Task 3: Expose The Research SSE Endpoint

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/research_runs.py`
- Modify: `tldw_Server_API/tests/Research/test_research_runs_endpoint.py`

**Step 1: Write the failing tests**

Add endpoint tests that verify:

- `GET /api/v1/research/runs/{id}/events/stream` returns `text/event-stream`
- the first emitted event is `snapshot`
- a terminal session emits `snapshot`, then `terminal`, then closes
- missing sessions map to `404`

Example assertion shape:

```python
with TestClient(app) as client:
    with client.stream("GET", "/api/v1/research/runs/rs_1/events/stream") as resp:
        body = b"".join(resp.iter_bytes()).decode("utf-8")
assert "event: snapshot" in body
assert "event: terminal" in body
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_runs_endpoint.py -v`

Expected: FAIL because the SSE route does not exist yet.

**Step 3: Write minimal implementation**

Implement in `research_runs.py`:

- `GET /runs/{session_id}/events/stream`
- `StreamingResponse` with `media_type="text/event-stream"`
- reuse of `SSEStream`
- test-mode max duration using the same style as other SSE endpoints
- `snapshot` first, then live updates from the research streaming helper, then `terminal` on completion
- `404` mapping for missing sessions

Keep the route thin; all diffing and polling logic belongs in `streaming.py`.

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_runs_endpoint.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/research_runs.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py
git commit -m "feat(research): expose live progress sse endpoint"
```

### Task 4: Add End-To-End Coverage For Snapshot And Live Updates

**Files:**
- Modify: `tldw_Server_API/tests/e2e/test_deep_research_runs.py`

**Step 1: Write the failing test**

Add an e2e-style research run test that:

- creates a run
- connects to the SSE endpoint
- observes `snapshot`
- advances the session into at least one new state
- verifies a coarse event sequence such as:
  - `snapshot`
  - `status`
  - `checkpoint`
  - `terminal`

Keep the test deterministic by using the existing research stubs/test-mode behavior instead of real external providers.

**Step 2: Run test to verify it fails**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`

Expected: FAIL because the SSE flow is not exercised yet.

**Step 3: Write minimal implementation**

Adjust any endpoint/helper seams needed so the e2e test can:

- consume the stream deterministically
- avoid hanging in CI
- observe terminal closure for already-terminal or completed sessions

Do not add replay or persistent event logs in this step.

**Step 4: Run test to verify it passes**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/e2e/test_deep_research_runs.py
git commit -m "test(research): cover live progress sse flow"
```

### Task 5: Verify The Full Live Progress Slice

**Files:**
- Modify: `Docs/Plans/2026-03-07-deep-research-live-progress-implementation-plan.md`

**Step 1: Run the focused research test suite**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_streaming.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`

Expected: PASS for the full live-progress slice.

**Step 2: Run Bandit on the touched production scope**

Run: `source ../../.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Research/streaming.py tldw_Server_API/app/core/Research/service.py tldw_Server_API/app/api/v1/endpoints/research_runs.py tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py -f json -o /tmp/bandit_deep_research_live_progress.json`

Expected: JSON report written with `0` new findings in the touched code.

**Step 3: Update the plan status**

Mark every task in this plan complete and note any residual risk, especially:

- no replay support in v1
- status guaranteed, progress best-effort
- artifact events are metadata-only

**Step 4: Commit**

```bash
git add Docs/Plans/2026-03-07-deep-research-live-progress-implementation-plan.md
git commit -m "docs(research): finalize live progress implementation plan"
```

## Execution Status

- Task 1: Complete in `ffe9f0685` (`feat(research): add stream snapshot read model`)
- Task 2: Complete in `cf7f9c266` (`feat(research): add live progress stream diffing`)
- Task 3: Complete in `71ea579f9` (`feat(research): expose live progress sse endpoint`)
- Task 4: Complete in `bce49ac1e` (`test(research): cover live progress sse flow`)
- Task 5: Complete after verification on 2026-03-07

## Verification Summary

- Focused research suite: `32/32` passed
- Deep research e2e file: `3/3` passed
- Bandit report `/tmp/bandit_deep_research_live_progress.json`: `0` findings, `0` errors

## Residual Risk

- Replay support is still intentionally absent in v1; reconnect uses fresh snapshot plus live updates only.
- `status` is the guaranteed event class; `progress` remains best-effort and may skip very short-lived intermediate values.
- `artifact` events stream metadata only, not artifact contents.
- The e2e SSE harness uses a short settle delay before advancing the run because `TestClient` buffers early stream chunks inconsistently.
