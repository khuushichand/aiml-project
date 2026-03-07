# Deep Research Packaging Slice Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the packaging phase build `bundle.json` from synthesis artifacts and complete the research session without requiring a manual service call.

**Architecture:** The Jobs handler gains a `packaging` phase that reads plan plus synthesis artifacts, calls the existing package builder, writes `bundle.json`, and marks the session completed. `ResearchService` updates checkpoint approval so `outline_review` enqueues the packaging slice for checkpointed runs.

**Tech Stack:** Python dataclasses, SQLite-backed `ResearchSessionsDB`, `ResearchArtifactStore`, core Jobs helpers, pytest, Bandit.

---

### Task 1: Add Packaging Worker Tests

**Files:**
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_worker.py`
**Status:** Complete

**Step 1: Write the failing test**

Add tests that verify:
- a packaging job reads synthesis artifacts, writes `bundle.json`, and completes the session
- packaging fails when `claims.json` contains uncited claims

**Step 2: Run test to verify it fails**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_worker.py -v`
Expected: FAIL because `handle_research_phase_job(...)` does not support `packaging`.

**Step 3: Write minimal implementation**

No implementation in this task.

**Step 4: Run test to verify it still fails for the expected reason**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_worker.py -v`
Expected: FAIL on unsupported `packaging` phase.

**Step 5: Commit**

Do not commit yet.

### Task 2: Implement Packaging Phase In Jobs

**Files:**
- Modify: `tldw_Server_API/app/core/Research/jobs.py`
- Modify: `tldw_Server_API/app/core/Research/artifact_store.py` if additional read helpers are needed
- Modify: `tldw_Server_API/app/core/Research/exporter.py` only if small adapter logic is required
**Status:** Complete

**Step 1: Write minimal implementation**

Update the Jobs layer to:
- read the effective plan
- read `outline_v1.json`, `claims.json`, `report_v1.md`, `source_registry.json`, and `synthesis_summary.json`
- call `build_final_package(...)`
- write `bundle.json`
- transition the session to `completed`

**Step 2: Run targeted packaging worker tests**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_worker.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tldw_Server_API/app/core/Research/jobs.py tldw_Server_API/app/core/Research/artifact_store.py tldw_Server_API/app/core/Research/exporter.py tldw_Server_API/tests/Research/test_research_jobs_worker.py
git commit -m "feat(research): add packaging jobs slice"
```

### Task 3: Enqueue Packaging From Outline Review And Verify End-To-End

**Files:**
- Modify: `tldw_Server_API/app/core/Research/service.py`
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_service.py`
- Modify: `tldw_Server_API/tests/e2e/test_deep_research_runs.py`
**Status:** Complete

**Step 1: Write the failing test**

Add tests that verify:
- approving `outline_review` enqueues a packaging job
- the e2e run reaches `completed`
- export is driven by the generated `bundle.json`

**Step 2: Run test to verify it fails**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`
Expected: FAIL because `outline_review` currently does not enqueue packaging and the e2e run still uses `build_package(...)`.

**Step 3: Write minimal implementation**

Update `ResearchService` checkpoint mapping so `outline_review` resumes with packaging. Then update e2e coverage to:
- drive the full run lifecycle
- invoke packaging through the worker path
- read `bundle.json` for export assertions

**Step 4: Run test to verify it passes**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/service.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/e2e/test_deep_research_runs.py
git commit -m "test(research): verify packaging lifecycle"
```

### Task 4: Full Verification And Security Check

**Files:**
- Modify: `Docs/Plans/2026-03-07-deep-research-packaging-implementation-plan.md`
**Status:** Complete

**Step 1: Run targeted suite**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_worker.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`
Expected: PASS

**Step 2: Run broader regression suite**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_broker.py tldw_Server_API/tests/Research/test_research_artifact_store.py tldw_Server_API/tests/Research/test_research_planner.py tldw_Server_API/tests/Research/test_research_limits.py tldw_Server_API/tests/Research/test_research_checkpoint_service.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_jobs_worker.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py tldw_Server_API/tests/Research/test_research_exporter.py tldw_Server_API/tests/Research/test_research_package_adapter.py tldw_Server_API/tests/Research/test_research_synthesizer.py tldw_Server_API/tests/DB_Management/test_research_db_paths.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`
Expected: PASS

**Step 3: Run Bandit on touched production scope**

Run: `source ../../.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Research tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py -f json -o /tmp/bandit_deep_research_packaging.json`
Expected: JSON report with `0` findings in production files touched by this slice.

**Step 4: Update plan status**

Mark all tasks complete in this plan file once verification passes.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-07-deep-research-packaging-implementation-plan.md
git commit -m "docs(research): record packaging verification"
```
