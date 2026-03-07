# Deep Research Read APIs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add REST read endpoints for deep research run status, final bundle access, and allowlisted artifact access.

**Architecture:** `ResearchService` will provide typed session and artifact readers backed by `ResearchSessionsDB` and `ResearchArtifactStore`. The API layer will expose dedicated GET routes for run status, final bundle, and artifact reads with simple, explicit schemas.

**Tech Stack:** FastAPI, Pydantic, SQLite-backed `ResearchSessionsDB`, `ResearchArtifactStore`, pytest, Bandit.

---

### Task 1: Add Service Read Tests

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_service.py` or create a dedicated service-read test file

**Step 1: Write the failing test**

Add tests that verify:
- session lookup returns the stored run
- bundle lookup returns parsed `bundle.json`
- artifact lookup returns parsed JSON, parsed JSONL, and raw markdown/text
- disallowed artifact names raise a validation error

**Step 2: Run test to verify it fails**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py -v`
Expected: FAIL because `ResearchService` lacks the read methods.

**Step 3: Write minimal implementation**

No implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py -v`
Expected: FAIL on missing service methods.

**Step 5: Commit**

Do not commit yet.

### Task 2: Implement Service Read Helpers And API Schemas

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/app/core/Research/service.py`
- Modify: `tldw_Server_API/app/core/Research/artifact_store.py` if helper reuse is needed
- Modify: `tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py`

**Step 1: Write minimal implementation**

Add:
- `completed_at` to the run response schema
- service methods for session, bundle, and allowlisted artifact reads
- a small artifact response schema with `artifact_name`, `content_type`, and `content`

**Step 2: Run service tests**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tldw_Server_API/app/core/Research/service.py tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py tldw_Server_API/tests/Research/test_research_jobs_service.py
git commit -m "feat(research): add read service helpers"
```

### Task 3: Add Read Endpoints And API Tests

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/research_runs.py`
- Modify: `tldw_Server_API/tests/Research/test_research_runs_endpoint.py`

**Step 1: Write the failing test**

Add endpoint tests for:
- `GET /research/runs/{id}`
- `GET /research/runs/{id}/bundle`
- `GET /research/runs/{id}/artifacts/{name}`

Include `404` and `400` cases.

**Step 2: Run test to verify it fails**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_runs_endpoint.py -v`
Expected: FAIL because the GET routes do not exist yet.

**Step 3: Write minimal implementation**

Add the new routes and map service exceptions to `400`/`404`.

**Step 4: Run test to verify it passes**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_runs_endpoint.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/research_runs.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py
git commit -m "feat(research): add read endpoints"
```

### Task 4: Verify End-To-End Polling Flow

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/tests/e2e/test_deep_research_runs.py`
- Modify: `Docs/Plans/2026-03-07-deep-research-read-apis-implementation-plan.md`

**Step 1: Write the failing test**

Extend the e2e run to:
- fetch `GET /runs/{id}` after completion
- fetch `GET /runs/{id}/bundle`
- fetch `GET /runs/{id}/artifacts/report_v1.md`

**Step 2: Run test to verify it fails**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`
Expected: FAIL until the endpoints and service readers are in place.

**Step 3: Write minimal implementation**

Adjust any endpoint/service details needed so the e2e polling flow passes.

**Step 4: Run full verification**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_broker.py tldw_Server_API/tests/Research/test_research_artifact_store.py tldw_Server_API/tests/Research/test_research_planner.py tldw_Server_API/tests/Research/test_research_limits.py tldw_Server_API/tests/Research/test_research_checkpoint_service.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_jobs_worker.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py tldw_Server_API/tests/Research/test_research_exporter.py tldw_Server_API/tests/Research/test_research_package_adapter.py tldw_Server_API/tests/Research/test_research_synthesizer.py tldw_Server_API/tests/DB_Management/test_research_db_paths.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`
Expected: PASS

Run: `source ../../.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Research tldw_Server_API/app/api/v1/endpoints/research_runs.py tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py -f json -o /tmp/bandit_deep_research_read_apis.json`
Expected: JSON report with `0` findings in touched production files.

**Step 5: Update plan status and commit**

```bash
git add Docs/Plans/2026-03-07-deep-research-read-apis-implementation-plan.md tldw_Server_API/tests/e2e/test_deep_research_runs.py
git commit -m "test(research): verify read api polling flow"
```
