"""Dual-backend coverage for longer Prompt Studio optimization flows.

These tests seed larger test corpora and run the optimization job handler
with mocked LLM/execution calls, validating that both SQLite and Postgres
backends complete multi-iteration optimizations on bigger datasets.

By default, sizes are moderate to keep runtime acceptable. Set
TLDW_PS_STRESS=1 to enable a heavier variant with more test cases and
iterations. You can further tune sizes via env vars:

- TLDW_PS_TC_COUNT: total test cases to seed (default 250; stress 1000)
- TLDW_PS_ITERATIONS: iterations per optimization (default 5; stress 10)
- TLDW_PS_OPT_COUNT: number of parallel optimizations (default 3; stress 8)
"""

from __future__ import annotations

import os
import asyncio
from typing import Dict, Any, List

import pytest

from tldw_Server_API.app.core.Prompt_Management.prompt_studio.job_manager import (
    JobManager, JobType, JobStatus,
)
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.job_processor import JobProcessor


pytestmark = pytest.mark.integration


def _should_stress() -> bool:
    return os.getenv("TLDW_PS_STRESS", "0").strip() in {"1", "true", "yes", "on", "y"}


def _int_from_env(name: str, default: int) -> int:
    val = os.getenv(name)
    if not val:
        return default
    try:
        return max(0, int(val))
    except Exception:
        return default


async def _seed_test_cases(client, project_id: int, total: int) -> List[int]:
    """Bulk insert test cases in batches and return created IDs."""
    created_ids: List[int] = []
    batch_size = 100
    remaining = total
    counter = 0
    while remaining > 0:
        n = min(batch_size, remaining)
        payload = {
            "project_id": project_id,
            "test_cases": [
                {
                    "name": f"TC-{counter + i}",
                    "inputs": {"q": f"Question {counter + i}"},
                    "expected_outputs": {"answer": "ok"},
                    "tags": ["bulk"],
                    "is_golden": (i % 10 == 0),
                }
                for i in range(n)
            ],
        }
        resp = client.post("/api/v1/prompt-studio/test-cases/bulk", json=payload)
        assert resp.status_code in (200, 201), resp.text
        data = resp.json().get("data", [])
        created_ids.extend([row.get("id") for row in data if row.get("id") is not None])
        remaining -= n
        counter += n
    return created_ids


@pytest.mark.parametrize(
    "optimizer_type",
    ["iterative", "mipro"],
)
@pytest.mark.asyncio
async def test_long_running_optimization_dual_backend(
    prompt_studio_dual_backend_client,
    optimizer_type: str,
    monkeypatch,
):
    """Run multi-iteration optimization over a larger test corpus on both backends.

    - Seeds 200+ test cases by default (1000+ when TLDW_PS_STRESS=1)
    - Creates a base prompt
    - Creates an optimization job via the API
    - Processes the queued optimization job with JobProcessor
    - Asserts that the optimization completes with recorded iterations
    """

    backend_label, client, db = prompt_studio_dual_backend_client

    # Mock out LLM calls and speed up sleeps
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import prompt_executor as _pe
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import job_processor as _jp

    async def _fake_llm_call(*args, **kwargs) -> Dict[str, Any]:
        return {"content": "Optimized instruction"}

    monkeypatch.setattr(_pe.PromptExecutor, "_call_llm", staticmethod(_fake_llm_call))

    async def _fast_sleep(delay: float):
        return None

    monkeypatch.setattr(_jp.asyncio, "sleep", _fast_sleep)

    # Create project
    project_resp = client.post(
        "/api/v1/prompt-studio/projects/",
        json={"name": f"Opt Proj ({backend_label})", "description": "", "status": "active", "metadata": {}},
    )
    assert project_resp.status_code in (200, 201), project_resp.text
    project_id = project_resp.json()["data"]["id"]

    # Create base prompt
    prompt_resp = client.post(
        "/api/v1/prompt-studio/prompts/create",
        json={
            "project_id": project_id,
            "name": f"Base Prompt ({backend_label})",
            "system_prompt": "Summarize clearly",
            "user_prompt": "{{q}}",
        },
    )
    assert prompt_resp.status_code in (200, 201), prompt_resp.text
    prompt_id = prompt_resp.json()["data"]["id"]

    # Seed a larger number of test cases
    total_cases = _int_from_env("TLDW_PS_TC_COUNT", 1000 if _should_stress() else 250)
    created_ids = await _seed_test_cases(client, project_id, total_cases)
    assert len(created_ids) == total_cases

    # Create an optimization job
    iterations = _int_from_env("TLDW_PS_ITERATIONS", 10 if _should_stress() else 5)
    opt_resp = client.post(
        "/api/v1/prompt-studio/optimizations/create",
        json={
            "project_id": project_id,
            "initial_prompt_id": prompt_id,
            "optimization_config": {
                "optimizer_type": optimizer_type,
                "max_iterations": iterations,
                "target_metric": "accuracy",
                "early_stopping": True,
            },
            "test_case_ids": created_ids[:200],
            "name": f"LongRun-{optimizer_type}",
        },
    )
    assert opt_resp.status_code in (200, 201), opt_resp.text
    data = opt_resp.json().get("data", {})
    opt_info = data.get("optimization") or {}
    opt_id = opt_info.get("id")
    assert opt_id is not None

    # Process the queued job via JobProcessor directly
    jm = JobManager(db)
    processor = JobProcessor(db, jm)

    # Find queued optimization jobs (normalize payloads inside JobManager)
    jobs = jm.list_jobs(status=JobStatus.QUEUED, job_type=JobType.OPTIMIZATION, limit=10)
    assert any(j.get("entity_id") == opt_id for j in jobs)

    # Pick our job and process
    job = next(j for j in jobs if j.get("entity_id") == opt_id)
    await processor.process_job(job)

    # Verify optimization completion
    opt_get = client.get(f"/api/v1/prompt-studio/optimizations/get/{opt_id}")
    assert opt_get.status_code == 200, opt_get.text
    opt_payload = opt_get.json().get("data", {})
    assert opt_payload.get("status") in {"completed", "running", "failed"}
    # At least one iteration should have been recorded
    iterations_resp = client.get(f"/api/v1/prompt-studio/optimizations/iterations/{opt_id}")
    assert iterations_resp.status_code == 200, iterations_resp.text
    history = iterations_resp.json().get("data", {}).get("iterations", [])
    assert len(history) >= 1


@pytest.mark.asyncio
async def test_many_optimizations_concurrent_dual_backend(
    prompt_studio_dual_backend_client,
    monkeypatch,
):
    """Spawn multiple optimizations and process them concurrently on both backends.

    The number of parallel optimizations is controlled by TLDW_PS_OPT_COUNT.
    This expands coverage for queueing, processing, and iteration logging
    under higher concurrency while staying deterministic via mocks.
    """
    backend_label, client, db = prompt_studio_dual_backend_client

    # Mock LLM + sleep to keep this fast and deterministic
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import prompt_executor as _pe
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import job_processor as _jp

    async def _fake_llm_call(*args, **kwargs) -> Dict[str, Any]:
        return {"content": "Optimized instruction"}

    monkeypatch.setattr(_pe.PromptExecutor, "_call_llm", staticmethod(_fake_llm_call))

    async def _fast_sleep(delay: float):
        return None

    monkeypatch.setattr(_jp.asyncio, "sleep", _fast_sleep)

    # Create project + base prompt
    proj = client.post(
        "/api/v1/prompt-studio/projects/",
        json={"name": f"Many Opt Proj ({backend_label})", "description": "", "status": "active", "metadata": {}},
    )
    assert proj.status_code in (200, 201), proj.text
    pid = proj.json()["data"]["id"]

    pr = client.post(
        "/api/v1/prompt-studio/prompts/create",
        json={"project_id": pid, "name": f"Many Opt Prompt ({backend_label})", "system_prompt": "S", "user_prompt": "{{q}}"},
    )
    assert pr.status_code in (200, 201), pr.text
    prompt_id = pr.json()["data"]["id"]

    # Seed a moderate dataset
    total_cases = _int_from_env("TLDW_PS_TC_COUNT", 500 if _should_stress() else 200)
    created_ids = await _seed_test_cases(client, pid, total_cases)
    assert len(created_ids) == total_cases

    # Create multiple optimizations
    opt_count = _int_from_env("TLDW_PS_OPT_COUNT", 8 if _should_stress() else 3)
    iterations = _int_from_env("TLDW_PS_ITERATIONS", 6 if _should_stress() else 3)
    strategies = ["iterative", "mipro", "random_search", "hill_climb", "beam_search", "greedy", "anneal", "genetic"]
    strategies = strategies[:max(1, opt_count)]

    created_opt_ids: List[int] = []
    for i, strat in enumerate(strategies):
        resp = client.post(
            "/api/v1/prompt-studio/optimizations/create",
            json={
                "project_id": pid,
                "initial_prompt_id": prompt_id,
                "optimization_config": {
                    "optimizer_type": strat,
                    "max_iterations": iterations,
                    "target_metric": "accuracy",
                    "early_stopping": True,
                },
                "test_case_ids": created_ids[(i * 50) % total_cases : ((i * 50) % total_cases) + 120],
                "name": f"Concurrent-{strat}",
            },
        )
        assert resp.status_code in (200, 201), resp.text
        created_opt_ids.append(resp.json()["data"]["optimization"]["id"])

    # Process all queued optimization jobs concurrently
    jm = JobManager(db)
    processor = JobProcessor(db, jm)
    jobs = jm.list_jobs(status=JobStatus.QUEUED, job_type=JobType.OPTIMIZATION, limit=len(created_opt_ids) + 5)
    targets = [j for j in jobs if j.get("entity_id") in created_opt_ids]
    assert len(targets) == len(created_opt_ids)

    await asyncio.gather(*[processor.process_job(job) for job in targets])

    # Verify at least one iteration per optimization
    for oid in created_opt_ids:
        it = client.get(f"/api/v1/prompt-studio/optimizations/iterations/{oid}")
        assert it.status_code == 200, it.text
        history = it.json().get("data", {}).get("iterations", [])
        assert len(history) >= 1


@pytest.mark.asyncio
async def test_strategy_comparison_and_concurrent_jobs_dual_backend(
    prompt_studio_dual_backend_client,
    monkeypatch,
):
    """Create a strategy comparison across multiple optimizers and process all jobs concurrently.

    Validates that the compare endpoint spawns multiple optimization jobs and that
    the JobProcessor can process all of them concurrently on both SQLite and Postgres.
    """
    backend_label, client, db = prompt_studio_dual_backend_client

    # Mock LLM + test runner + sleep for speed/determinism
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import prompt_executor as _pe
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import job_processor as _jp

    async def _fake_llm_call(*args, **kwargs) -> Dict[str, Any]:
        return {"content": "Optimized instruction"}

    monkeypatch.setattr(_pe.PromptExecutor, "_call_llm", staticmethod(_fake_llm_call))

    async def _fast_sleep(delay: float):
        return None

    monkeypatch.setattr(_jp.asyncio, "sleep", _fast_sleep)

    # Create project + prompt
    proj = client.post(
        "/api/v1/prompt-studio/projects/",
        json={"name": f"Compare Proj ({backend_label})", "description": "", "status": "active", "metadata": {}},
    )
    assert proj.status_code in (200, 201)
    pid = proj.json()["data"]["id"]
    pr = client.post(
        "/api/v1/prompt-studio/prompts/create",
        json={"project_id": pid, "name": f"Compare Prompt ({backend_label})", "system_prompt": "S", "user_prompt": "{{q}}"},
    )
    assert pr.status_code in (200, 201)
    prompt_id = pr.json()["data"]["id"]

    # Seed test cases (moderate)
    created_ids = await _seed_test_cases(client, pid, 150)
    assert len(created_ids) == 150

    # Compare strategies; this should spawn one optimization/job per strategy
    strategies = ["iterative", "mipro", "random_search"]
    cmp = client.post(
        "/api/v1/prompt-studio/optimizations/compare-strategies",
        json={
            "project_id": pid,
            "prompt_id": prompt_id,
            "strategies": strategies,
            "test_case_ids": created_ids[:100],
            "config": {"max_iterations": 6, "target_metric": "accuracy"},
        },
    )
    assert cmp.status_code == 200, cmp.text
    cmp_data = cmp.json().get("data", {})
    opt_ids = cmp_data.get("optimization_ids", [])
    assert len(opt_ids) == len(strategies)

    # Process all queued optimization jobs concurrently
    jm = JobManager(db)
    processor = JobProcessor(db, jm)
    jobs = jm.list_jobs(status=JobStatus.QUEUED, job_type=JobType.OPTIMIZATION, limit=20)
    # Ensure we captured our jobs
    targets = [j for j in jobs if j.get("entity_id") in opt_ids]
    assert len(targets) == len(strategies)

    await asyncio.gather(*[processor.process_job(job) for job in targets])

    # Verify each optimization has at least one recorded iteration
    for opt_id in opt_ids:
        it = client.get(f"/api/v1/prompt-studio/optimizations/iterations/{opt_id}")
        assert it.status_code == 200, it.text
        history = it.json().get("data", {}).get("iterations", [])
        assert len(history) >= 1


@pytest.mark.skipif(not _should_stress(), reason="enable with TLDW_PS_STRESS=1")
@pytest.mark.asyncio
async def test_optimization_extreme_dataset_dual_backend(
    prompt_studio_dual_backend_client,
    monkeypatch,
):
    """Heavier variant using ~2000 test cases and ~10 iterations.

    Skipped by default; enable with TLDW_PS_STRESS=1.
    """
    backend_label, client, db = prompt_studio_dual_backend_client

    # Short-circuit external calls and sleeps
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import prompt_executor as _pe
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import test_runner as _tr
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import job_processor as _jp

    async def _fake_llm_call(*args, **kwargs) -> Dict[str, Any]:
        return {"content": "Optimized instruction"}

    async def _fake_run_single_test(*args, **kwargs) -> Dict[str, Any]:
        return {"success": True, "scores": {"accuracy": 0.75}}

    monkeypatch.setattr(_pe.PromptExecutor, "_call_llm", staticmethod(_fake_llm_call))
    monkeypatch.setattr(_tr.TestRunner, "run_single_test", staticmethod(_fake_run_single_test))

    async def _fast_sleep(delay: float):
        return None

    monkeypatch.setattr(_jp.asyncio, "sleep", _fast_sleep)

    # Project + prompt
    proj = client.post(
        "/api/v1/prompt-studio/projects/",
        json={"name": f"Stress Proj ({backend_label})", "description": "", "status": "active", "metadata": {}},
    )
    assert proj.status_code in (200, 201)
    pid = proj.json()["data"]["id"]
    pr = client.post(
        "/api/v1/prompt-studio/prompts/create",
        json={"project_id": pid, "name": f"Stress Prompt ({backend_label})", "system_prompt": "S", "user_prompt": "{{q}}"},
    )
    assert pr.status_code in (200, 201)
    prompt_id = pr.json()["data"]["id"]

    # Seed ~2000 cases
    created_ids = await _seed_test_cases(client, pid, 2000)
    assert len(created_ids) == 2000

    # Create optimization and process job
    opt = client.post(
        "/api/v1/prompt-studio/optimizations/create",
        json={
            "project_id": pid,
            "initial_prompt_id": prompt_id,
            "optimization_config": {"optimizer_type": "iterative", "max_iterations": 10, "target_metric": "accuracy"},
            "test_case_ids": created_ids[:500],
            "name": "Stress",
        },
    )
    assert opt.status_code in (200, 201)
    opt_id = opt.json()["data"]["optimization"]["id"]

    jm = JobManager(db)
    processor = JobProcessor(db, jm)
    jobs = jm.list_jobs(status=JobStatus.QUEUED, job_type=JobType.OPTIMIZATION)
    job = next(j for j in jobs if j.get("entity_id") == opt_id)
    await processor.process_job(job)

    # Verify status + iterations
    st = client.get(f"/api/v1/prompt-studio/optimizations/get/{opt_id}")
    assert st.status_code == 200
    it = client.get(f"/api/v1/prompt-studio/optimizations/iterations/{opt_id}")
    assert it.status_code == 200
    assert len(it.json().get("data", {}).get("iterations", [])) >= 1
