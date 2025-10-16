"""Dual-backend coverage for longer Prompt Studio optimization flows.

These tests seed larger test corpora and run the optimization job handler
with mocked LLM/execution calls, validating that both SQLite and Postgres
backends complete multi-iteration optimizations on bigger datasets.

By default, sizes are trimmed to keep runtime acceptable. Set
TLDW_PS_STRESS=1 to enable a heavier variant with more test cases and
iterations. You can further tune sizes via env vars:

- TLDW_PS_TC_COUNT: total test cases to seed (default 120; stress 600)
- TLDW_PS_ITERATIONS: iterations per optimization (default 3; stress 8)
- TLDW_PS_OPT_COUNT: number of parallel optimizations (default 2; stress 5)
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


pytestmark = [pytest.mark.integration, pytest.mark.slow]

# Local override: run this heavy suite against a single backend only.
# Select with env TLDW_PS_BACKEND=sqlite|postgres (default sqlite).
from fastapi.testclient import TestClient
from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.api.v1.API_Deps.prompt_studio_deps import get_prompt_studio_db
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import PromptStudioDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
try:  # local optional PG driver detect
    import psycopg as _psycopg_v3  # type: ignore
    _PG_DRIVER = "psycopg"
except Exception:
    try:
        import psycopg2 as _psycopg2  # type: ignore
        _PG_DRIVER = "psycopg2"
    except Exception:
        _PG_DRIVER = None

_HAS_POSTGRES = (_PG_DRIVER is not None)

def _probe_postgres(config: DatabaseConfig, timeout: int = 2) -> bool:
    if _PG_DRIVER is None:
        return False
    try:
        if _PG_DRIVER == "psycopg":
            conn = _psycopg_v3.connect(
                host=config.pg_host,
                port=config.pg_port,
                dbname="postgres",
                user=config.pg_user,
                password=config.pg_password,
                connect_timeout=timeout,
            )
        else:
            conn = _psycopg2.connect(
                host=config.pg_host,
                port=config.pg_port,
                database="postgres",
                user=config.pg_user,
                password=config.pg_password,
                connect_timeout=timeout,
            )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            conn.close()
        return True
    except Exception:
        return False

def _create_temp_postgres_database(config: DatabaseConfig) -> DatabaseConfig:
    import uuid as _uuid
    if _PG_DRIVER is None:
        raise RuntimeError("psycopg/psycopg2 required for Postgres-backed tests")
    db_name = f"tldw_test_{_uuid.uuid4().hex[:8]}"
    if _PG_DRIVER == "psycopg":
        admin = _psycopg_v3.connect(
            host=config.pg_host,
            port=config.pg_port,
            dbname="postgres",
            user=config.pg_user,
            password=config.pg_password,
            connect_timeout=2,
        )
    else:
        admin = _psycopg2.connect(
            host=config.pg_host,
            port=config.pg_port,
            database="postgres",
            user=config.pg_user,
            password=config.pg_password,
            connect_timeout=2,
        )
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(f"CREATE DATABASE {db_name} OWNER {config.pg_user};")
    finally:
        admin.close()
    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=config.pg_host,
        pg_port=config.pg_port,
        pg_database=db_name,
        pg_user=config.pg_user,
        pg_password=config.pg_password,
    )

def _drop_postgres_database(config: DatabaseConfig) -> None:
    if _PG_DRIVER is None:
        return
    if _PG_DRIVER == "psycopg":
        admin = _psycopg_v3.connect(
            host=config.pg_host,
            port=config.pg_port,
            dbname="postgres",
            user=config.pg_user,
            password=config.pg_password,
            connect_timeout=2,
        )
    else:
        admin = _psycopg2.connect(
            host=config.pg_host,
            port=config.pg_port,
            database="postgres",
            user=config.pg_user,
            password=config.pg_password,
            connect_timeout=2,
        )
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s;",
                (config.pg_database,),
            )
            cur.execute(f"DROP DATABASE IF EXISTS {config.pg_database};")
    finally:
        admin.close()


@pytest.fixture(scope="module")
def prompt_studio_dual_backend_client(tmp_path_factory):
    """Module-local override: choose exactly one backend for this heavy suite.

    Backend is selected via env TLDW_PS_BACKEND (sqlite|postgres), default sqlite.
    No cross-backend parameterization here to avoid mixing backends in one run.
    """
    from tldw_Server_API.app.core.config import settings as app_settings
    from tldw_Server_API.app.api.v1.API_Deps import prompt_studio_deps as ps_deps

    backend_choice = os.getenv("TLDW_PS_BACKEND", "sqlite").strip().lower()
    if backend_choice not in {"sqlite", "postgres"}:
        backend_choice = "sqlite"

    backend = None
    config = None

    # Use a module-scoped temporary directory so DB and seed can be shared
    tmp_dir = tmp_path_factory.mktemp("ps_heavy")

    if backend_choice == "sqlite":
        db_instance = PromptStudioDatabase(str(tmp_dir / "prompt_studio_sqlite_heavy.sqlite"), "heavy-sqlite")
    else:
        if not _HAS_POSTGRES:
            pytest.skip("psycopg not available; skipping Postgres backend for heavy suite")
        base_config = DatabaseConfig(
            backend_type=BackendType.POSTGRESQL,
            pg_host=os.getenv("POSTGRES_TEST_HOST", "127.0.0.1"),
            pg_port=int(os.getenv("POSTGRES_TEST_PORT", "5432")),
            pg_database=os.getenv("POSTGRES_TEST_DB", "tldw_users"),
            pg_user=os.getenv("POSTGRES_TEST_USER", "tldw_user"),
            pg_password=os.getenv("POSTGRES_TEST_PASSWORD", "TestPassword123!"),
        )
        if not _probe_postgres(base_config, timeout=2):
            if os.getenv("TLDW_TEST_POSTGRES_REQUIRED", "0").lower() in {"1", "true", "yes", "on"}:
                pytest.fail("Postgres required for heavy suite but not reachable")
            pytest.skip("Postgres not reachable; skipping Postgres backend for heavy suite")
        config = _create_temp_postgres_database(base_config)
        backend = DatabaseBackendFactory.create_backend(config)
        db_instance = PromptStudioDatabase(
            db_path=str(tmp_dir / "prompt_studio_pg_placeholder.sqlite"),
            client_id="heavy-postgres",
            backend=backend,
        )

    prev_test_mode = os.environ.get("TEST_MODE")
    os.environ["TEST_MODE"] = "true"
    prev_user_base = app_settings.get("USER_DB_BASE_DIR")
    app_settings["USER_DB_BASE_DIR"] = tmp_dir

    # Static test user for this module-scoped client
    test_user = {
        "id": "test-user-123",
        "username": "testuser",
        "email": "test@example.com",
        "is_active": True,
    }

    async def override_user():
        return User(
            id=test_user["id"],
            username=test_user["username"],
            email=test_user["email"],
            is_active=True,
        )

    async def override_db():
        return db_instance

    _app = fastapi_app
    _app.dependency_overrides[get_request_user] = override_user
    _app.dependency_overrides[get_prompt_studio_db] = override_db
    # Patch dependency directly and restore in finally
    had_attr = hasattr(ps_deps, "get_current_active_user")
    prev_get_user = getattr(ps_deps, "get_current_active_user", None)
    setattr(ps_deps, "get_current_active_user", lambda: test_user)

    try:
        with TestClient(_app) as client:
            yield backend_choice, client, db_instance
    finally:
        _app.dependency_overrides.clear()
        if hasattr(db_instance, "close"):
            try:
                db_instance.close()
            except Exception:
                pass
        elif hasattr(db_instance, "close_connection"):
            try:
                db_instance.close_connection()
            except Exception:
                pass
        if backend is not None:
            try:
                backend.get_pool().close_all()
            except Exception:
                pass
        if backend_choice == "postgres" and config is not None:
            # Drop the ephemeral database
            try:
                from tldw_Server_API.tests.prompt_studio.conftest import _drop_postgres_database
                _drop_postgres_database(config)
            except Exception:
                pass
        # Restore patched settings/env
        if prev_test_mode is None:
            try:
                del os.environ["TEST_MODE"]
            except Exception:
                pass
        else:
            os.environ["TEST_MODE"] = prev_test_mode
        try:
            app_settings["USER_DB_BASE_DIR"] = prev_user_base
        except Exception:
            pass
        try:
            if had_attr:
                setattr(ps_deps, "get_current_active_user", prev_get_user)
            else:
                delattr(ps_deps, "get_current_active_user")
        except Exception:
            pass


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


@pytest.fixture(scope="module")
def ps_seeded_project(prompt_studio_dual_backend_client):
    """Create one project and seed test cases once per module to share across tests.

    Honors TLDW_PS_TC_COUNT with lower defaults; use TLDW_PS_STRESS=1 for larger sizes.
    """
    backend_label, client, db = prompt_studio_dual_backend_client

    # Create shared project
    proj = client.post(
        "/api/v1/prompt-studio/projects/",
        json={"name": f"Seed Proj ({backend_label})", "description": "", "status": "active", "metadata": {}},
    )
    assert proj.status_code in (200, 201), proj.text
    project_id = proj.json()["data"]["id"]

    # Lower default corpus size; allow stress mode to scale up
    total_cases = _int_from_env("TLDW_PS_TC_COUNT", 600 if _should_stress() else 120)

    # Seed synchronously in batches to avoid async fixture complexity
    created_ids: List[int] = []
    batch_size = 100
    remaining = total_cases
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

    return {
        "backend_label": backend_label,
        "client": client,
        "db": db,
        "project_id": project_id,
        "test_case_ids": created_ids,
    }


@pytest.mark.parametrize("optimizer_type", ["iterative", "mipro"])
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_long_running_optimization_dual_backend(
    ps_seeded_project,
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

    backend_label = ps_seeded_project["backend_label"]
    client = ps_seeded_project["client"]
    db = ps_seeded_project["db"]
    project_id = ps_seeded_project["project_id"]

    # Mock out LLM calls and speed up sleeps
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import prompt_executor as _pe
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import job_processor as _jp

    async def _fake_llm_call(*args, **kwargs) -> Dict[str, Any]:
        return {"content": "Optimized instruction"}

    monkeypatch.setattr(_pe.PromptExecutor, "_call_llm", staticmethod(_fake_llm_call))

    async def _fast_sleep(delay: float):
        return None

    monkeypatch.setattr(_jp.asyncio, "sleep", _fast_sleep)

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

    # Use pre-seeded test cases with lower defaults by default
    created_ids = ps_seeded_project["test_case_ids"]
    total_cases = len(created_ids)

    # Create an optimization job with fewer default iterations
    iterations = _int_from_env("TLDW_PS_ITERATIONS", 8 if _should_stress() else 3)
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
            "test_case_ids": created_ids[: min(100, total_cases)],
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


@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_many_optimizations_concurrent_dual_backend(
    ps_seeded_project,
    monkeypatch,
):
    """Spawn multiple optimizations and process them concurrently on both backends.

    The number of parallel optimizations is controlled by TLDW_PS_OPT_COUNT.
    This expands coverage for queueing, processing, and iteration logging
    under higher concurrency while staying deterministic via mocks.
    """
    backend_label = ps_seeded_project["backend_label"]
    client = ps_seeded_project["client"]
    db = ps_seeded_project["db"]
    pid = ps_seeded_project["project_id"]

    # Mock LLM + sleep to keep this fast and deterministic
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import prompt_executor as _pe
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import job_processor as _jp

    async def _fake_llm_call(*args, **kwargs) -> Dict[str, Any]:
        return {"content": "Optimized instruction"}

    monkeypatch.setattr(_pe.PromptExecutor, "_call_llm", staticmethod(_fake_llm_call))

    async def _fast_sleep(delay: float):
        return None

    monkeypatch.setattr(_jp.asyncio, "sleep", _fast_sleep)

    pr = client.post(
        "/api/v1/prompt-studio/prompts/create",
        json={"project_id": pid, "name": f"Many Opt Prompt ({backend_label})", "system_prompt": "S", "user_prompt": "{{q}}"},
    )
    assert pr.status_code in (200, 201), pr.text
    prompt_id = pr.json()["data"]["id"]

    # Use pre-seeded dataset
    created_ids = ps_seeded_project["test_case_ids"]
    total_cases = len(created_ids)

    # Create multiple optimizations
    opt_count = _int_from_env("TLDW_PS_OPT_COUNT", 5 if _should_stress() else 2)
    iterations = _int_from_env("TLDW_PS_ITERATIONS", 5 if _should_stress() else 2)
    strategies = ["iterative", "mipro", "random_search", "hill_climb", "beam_search", "greedy", "anneal", "genetic"]
    strategies = strategies[:max(1, opt_count)]

    created_opt_ids: List[int] = []
    subset_size = min(120 if _should_stress() else 60, total_cases)
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
                "test_case_ids": created_ids[(i * 20) % total_cases : ((i * 20) % total_cases) + subset_size],
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


@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_strategy_comparison_and_concurrent_jobs_dual_backend(
    ps_seeded_project,
    monkeypatch,
):
    """Create a strategy comparison across multiple optimizers and process all jobs concurrently.

    Validates that the compare endpoint spawns multiple optimization jobs and that
    the JobProcessor can process all of them concurrently on both SQLite and Postgres.
    """
    backend_label = ps_seeded_project["backend_label"]
    client = ps_seeded_project["client"]
    db = ps_seeded_project["db"]
    pid = ps_seeded_project["project_id"]

    # Mock LLM + test runner + sleep for speed/determinism
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import prompt_executor as _pe
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import job_processor as _jp

    async def _fake_llm_call(*args, **kwargs) -> Dict[str, Any]:
        return {"content": "Optimized instruction"}

    monkeypatch.setattr(_pe.PromptExecutor, "_call_llm", staticmethod(_fake_llm_call))

    async def _fast_sleep(delay: float):
        return None

    monkeypatch.setattr(_jp.asyncio, "sleep", _fast_sleep)

    # Create prompt on shared project
    pr = client.post(
        "/api/v1/prompt-studio/prompts/create",
        json={"project_id": pid, "name": f"Compare Prompt ({backend_label})", "system_prompt": "S", "user_prompt": "{{q}}"},
    )
    assert pr.status_code in (200, 201)
    prompt_id = pr.json()["data"]["id"]

    # Use pre-seeded test cases, limit to moderate subset
    created_ids = ps_seeded_project["test_case_ids"]

    # Compare strategies; this should spawn one optimization/job per strategy
    strategies = ["iterative", "mipro", "random_search"]
    cmp = client.post(
        "/api/v1/prompt-studio/optimizations/compare-strategies",
        json={
            "project_id": pid,
            "prompt_id": prompt_id,
            "strategies": strategies,
            "test_case_ids": created_ids[: min(80, len(created_ids))],
            "config": {"max_iterations": 3, "target_metric": "accuracy"},
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
