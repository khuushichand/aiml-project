# Deep Research Synthesizing Slice Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a deterministic synthesizing phase that turns approved planning and collecting artifacts into outline, claims, report, and synthesis summary artifacts, then advances runs to outline review or packaging.

**Architecture:** A new `ResearchSynthesizer` reads plan plus collecting artifacts and returns deterministic synthesis outputs. The Jobs layer owns `synthesizing` execution and artifact persistence, while `ResearchService` keeps explicit checkpoint-to-phase mapping so `outline_review` advances to `packaging` without starting packaging execution yet.

**Tech Stack:** Python dataclasses, SQLite-backed `ResearchSessionsDB`, `ResearchArtifactStore`, core Jobs helpers, pytest, Bandit.

---

### Task 1: Add Synthesizer Models And Unit Tests

**Files:**
- Create: `tldw_Server_API/app/core/Research/synthesizer.py`
- Modify: `tldw_Server_API/app/core/Research/models.py`
- Modify: `tldw_Server_API/app/core/Research/__init__.py`
- Test: `tldw_Server_API/tests/Research/test_research_synthesizer.py`
**Status:** Complete

**Step 1: Write the failing test**

Add tests that verify:
- evidence notes are grouped into outline sections by focus area
- claims are emitted only with source IDs and citations
- unresolved questions propagate from collection gaps or missing evidence

**Step 2: Run test to verify it fails**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_synthesizer.py -v`
Expected: FAIL because `ResearchSynthesizer` and synthesis result models do not exist yet.

**Step 3: Write minimal implementation**

Add deterministic synthesis models and a `ResearchSynthesizer` that:
- accepts plan, source registry, evidence notes, and collection summary
- emits outline sections keyed by focus area
- builds claim objects with citations from source IDs
- builds deterministic markdown sections and a synthesis summary

**Step 4: Run test to verify it passes**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_synthesizer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/synthesizer.py tldw_Server_API/app/core/Research/models.py tldw_Server_API/app/core/Research/__init__.py tldw_Server_API/tests/Research/test_research_synthesizer.py
git commit -m "feat(research): add deterministic synthesizer"
```

### Task 2: Add Synthesizing Phase Execution In Jobs

**Files:**
- Modify: `tldw_Server_API/app/core/Research/artifact_store.py`
- Modify: `tldw_Server_API/app/core/Research/jobs.py`
- Test: `tldw_Server_API/tests/Research/test_research_jobs_worker.py`
**Status:** Complete

**Step 1: Write the failing test**

Extend worker tests to verify:
- a checkpointed `synthesizing` job writes `outline_v1.json`, `claims.json`, `report_v1.md`, and `synthesis_summary.json`
- checkpointed runs move to `awaiting_outline_review`
- autonomous runs move to `packaging`

**Step 2: Run test to verify it fails**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_worker.py -v`
Expected: FAIL because `handle_research_phase_job(...)` does not support `synthesizing`.

**Step 3: Write minimal implementation**

Update the artifact store and Jobs layer to:
- read `source_registry.json`
- read `evidence_notes.jsonl`
- load the effective plan
- call `ResearchSynthesizer`
- write synthesis artifacts
- create an `outline_review` checkpoint for checkpointed runs
- otherwise advance to `packaging`

**Step 4: Run test to verify it passes**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_worker.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/artifact_store.py tldw_Server_API/app/core/Research/jobs.py tldw_Server_API/tests/Research/test_research_jobs_worker.py
git commit -m "feat(research): add synthesizing jobs slice"
```

### Task 3: Advance Outline Review And Verify End-To-End

**Files:**
- Modify: `tldw_Server_API/app/core/Research/service.py`
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_service.py`
- Modify: `tldw_Server_API/tests/e2e/test_deep_research_runs.py`
**Status:** Complete

**Step 1: Write the failing test**

Add tests that verify:
- approving `outline_review` advances the session to `packaging`
- the e2e deep research run advances through `awaiting_outline_review`

**Step 2: Run test to verify it fails**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`
Expected: FAIL because the worker does not yet create outline review artifacts/checkpoints and the lifecycle does not reach that state.

**Step 3: Write minimal implementation**

Keep `outline_review -> packaging` explicit in `ResearchService`, then update e2e coverage to drive:
- planning
- collecting
- sources approval
- synthesizing
- outline review approval to `packaging`

**Step 4: Run test to verify it passes**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/service.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/e2e/test_deep_research_runs.py
git commit -m "test(research): verify synthesizing lifecycle"
```

### Task 4: Full Verification And Security Check

**Files:**
- Modify: `Docs/Plans/2026-03-07-deep-research-synthesizing-implementation-plan.md`
**Status:** Complete

**Step 1: Run targeted research suite**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_synthesizer.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_jobs_worker.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`
Expected: PASS

**Step 2: Run broader regression suite**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_broker.py tldw_Server_API/tests/Research/test_research_artifact_store.py tldw_Server_API/tests/Research/test_research_planner.py tldw_Server_API/tests/Research/test_research_limits.py tldw_Server_API/tests/Research/test_research_checkpoint_service.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_jobs_worker.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py tldw_Server_API/tests/Research/test_research_exporter.py tldw_Server_API/tests/Research/test_research_package_adapter.py tldw_Server_API/tests/DB_Management/test_research_db_paths.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`
Expected: PASS

**Step 3: Run Bandit on touched production scope**

Run: `source ../../.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Research tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py -f json -o /tmp/bandit_deep_research_synthesizing.json`
Expected: JSON report with `0` findings in production files touched by this slice.

**Step 4: Update plan status**

Mark all tasks complete in this plan file once verification passes.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-07-deep-research-synthesizing-implementation-plan.md
git commit -m "docs(research): record synthesizing verification"
```
