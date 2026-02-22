import asyncio
import contextlib
import json

import pytest
from starlette.requests import Request

from tldw_Server_API.app.api.v1.endpoints.prompt_studio import prompt_studio_optimization as ps_opt_endpoints
from tldw_Server_API.app.api.v1.schemas.prompt_studio_optimization import OptimizationCreate
from tldw_Server_API.app.core.Prompt_Management.prompt_studio import job_processor as job_processor_mod
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.job_processor import JobProcessor
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.mcts_optimizer import MCTSOptimizer
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.services import jobs_worker
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.test_runner import TestRunner


pytestmark = pytest.mark.integration


def _seed_prompt_and_case(db):
    project = db.create_project(name="OptJobEngine", description="")
    prompt = db.create_prompt(
        project_id=project["id"],
        name="BasePrompt",
        system_prompt="You are precise and concise.",
        user_prompt="Echo: {text}",
    )
    case = db.create_test_case(
        project_id=project["id"],
        name="Case1",
        inputs={"text": "hello"},
        expected_outputs={"response": "hello"},
    )
    return project, prompt, case


def _get_job_by_id(job_id: str) -> dict:
    jm = jobs_worker._jobs_manager()
    job = None
    with contextlib.suppress(Exception):
        job = jm.get_job_by_uuid(str(job_id))
    if job is None and str(job_id).isdigit():
        with contextlib.suppress(Exception):
            job = jm.get_job(int(job_id))
    assert job is not None, f"job not found: {job_id}"
    return job


def _fake_request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [],
        }
    )


async def _create_optimization_via_endpoint(
    db,
    payload: dict,
) -> tuple[int, str, dict]:
    response = await ps_opt_endpoints.create_optimization(
        optimization_data=OptimizationCreate.model_validate(payload),
        request=_fake_request("/api/v1/prompt-studio/optimizations/create"),
        _=True,
        db=db,
        security_config={},
        user_context={"user_id": "test-user-123", "is_admin": True, "permissions": ["all"]},
        idempotency_key=None,
    )
    body = response.model_dump()
    assert body.get("success") is True, body
    data = body.get("data") or {}
    optimization = data.get("optimization") or {}
    return int(optimization.get("id")), str(data.get("job_id")), body


async def _cancel_optimization_via_endpoint(db, optimization_id: int) -> dict:
    response = await ps_opt_endpoints.cancel_optimization(
        request=_fake_request(f"/api/v1/prompt-studio/optimizations/cancel/{optimization_id}"),
        optimization_id=optimization_id,
        reason=None,
        db=db,
        user_context={"user_id": "test-user-123", "is_admin": True, "permissions": ["all"]},
    )
    body = response.model_dump()
    assert body.get("success") is True, body
    return body


@pytest.mark.asyncio
async def test_process_optimization_job_routes_mcts_to_engine_and_persists_runtime_inputs(
    prompt_studio_dual_backend_db,
    monkeypatch,
):
    _label, db = prompt_studio_dual_backend_db
    project, prompt, case = _seed_prompt_and_case(db)

    optimization_config = {
        "optimizer_type": "mcts",
        "target_metric": "accuracy",
        "strategy_params": {
            "mcts_simulations": 3,
            "mcts_max_depth": 2,
            "prompt_candidates_per_node": 1,
            "token_budget": 1000,
        },
    }
    optimization = db.create_optimization(
        project_id=project["id"],
        name="MCTS-Job-Wiring",
        initial_prompt_id=prompt["id"],
        optimizer_type="mcts",
        optimization_config=optimization_config,
        max_iterations=3,
        status="pending",
    )

    async def fake_run_single_test(self, *, prompt_id: int, test_case_id: int, model_config, metrics=None):
        row = self.db.get_prompt(prompt_id) or {}
        sys_text = row.get("system_prompt") or ""
        score = 0.9 if "Ensure outputs strictly follow" in sys_text else 0.2
        return {"success": True, "scores": {"aggregate_score": score}}

    async def fake_rephrase_segment(self, system_text: str, segment_text: str):
        return None

    monkeypatch.setattr(TestRunner, "run_single_test", fake_run_single_test, raising=True)
    monkeypatch.setattr(MCTSOptimizer, "_rephrase_segment", fake_rephrase_segment, raising=True)

    payload = {
        "optimization_id": optimization["id"],
        "optimizer_type": "mcts",
        "initial_prompt_id": prompt["id"],
        "test_case_ids": [case["id"]],
        "optimization_config": optimization_config,
    }

    processor = JobProcessor(db)
    result = await processor.process_optimization_job(payload, int(optimization["id"]))

    row = db.get_optimization(int(optimization["id"])) or {}
    assert row.get("status") == "completed"
    assert isinstance((row.get("final_metrics") or {}).get("trace"), dict)
    assert [int(x) for x in (row.get("test_case_ids") or [])] == [int(case["id"])]

    assert int(result.get("optimization_id")) == int(optimization["id"])
    assert int(result.get("iterations_completed") or 0) >= 1
    assert result.get("best_prompt_id") is not None


@pytest.mark.asyncio
async def test_process_optimization_job_legacy_fallback_for_unsupported_strategy(
    prompt_studio_dual_backend_db,
    monkeypatch,
):
    _label, db = prompt_studio_dual_backend_db
    project, prompt, _case = _seed_prompt_and_case(db)

    optimization = db.create_optimization(
        project_id=project["id"],
        name="Legacy-Fallback",
        initial_prompt_id=prompt["id"],
        optimizer_type="iterative",
        optimization_config={"optimizer_type": "iterative", "target_metric": "accuracy"},
        max_iterations=3,
        status="pending",
    )

    async def fake_iteration(self, optimization_id: int, prompt_id: int, iteration: int):
        return {
            "iteration": iteration,
            "prompt_id": prompt_id,
            "metric": 0.55 + (iteration * 0.1),
            "tokens_used": 12,
            "cost": 0.0,
        }

    async def no_sleep(_seconds: float):
        return None

    monkeypatch.setattr(JobProcessor, "_run_optimization_iteration", fake_iteration, raising=True)
    monkeypatch.setattr(job_processor_mod.asyncio, "sleep", no_sleep, raising=True)

    payload = {
        "optimization_id": optimization["id"],
        "optimizer_type": "iterative",
        "initial_prompt_id": prompt["id"],
        "max_iterations": 3,
    }
    processor = JobProcessor(db)
    result = await processor.process_optimization_job(payload, int(optimization["id"]))

    row = db.get_optimization(int(optimization["id"])) or {}
    assert row.get("status") == "completed"
    assert int(row.get("iterations_completed") or 0) == 3
    assert result.get("status") == "completed"
    assert int(result.get("iterations_completed") or 0) == 3


@pytest.mark.asyncio
async def test_endpoint_created_mcts_job_executes_via_worker_path_and_persists_trace(
    prompt_studio_dual_backend_db,
    monkeypatch,
):
    monkeypatch.setenv("PROMPT_STUDIO_ENABLE_MCTS", "true")

    async def allow_project_write_access(*args, **kwargs):
        return None

    monkeypatch.setattr(
        ps_opt_endpoints,
        "require_project_write_access",
        allow_project_write_access,
        raising=True,
    )

    _label, db = prompt_studio_dual_backend_db
    project, prompt, case = _seed_prompt_and_case(db)

    async def fake_run_single_test(self, *, prompt_id: int, test_case_id: int, model_config, metrics=None):
        row = self.db.get_prompt(prompt_id) or {}
        sys_text = row.get("system_prompt") or ""
        score = 0.9 if "Ensure outputs strictly follow" in sys_text else 0.2
        return {"success": True, "scores": {"aggregate_score": score}}

    async def fake_rephrase_segment(self, system_text: str, segment_text: str):
        return None

    monkeypatch.setattr(TestRunner, "run_single_test", fake_run_single_test, raising=True)
    monkeypatch.setattr(MCTSOptimizer, "_rephrase_segment", fake_rephrase_segment, raising=True)
    monkeypatch.setattr(jobs_worker, "_get_processor", lambda _user_id: JobProcessor(db), raising=True)

    optimization_id, job_id, _body = await _create_optimization_via_endpoint(
        db,
        {
            "project_id": project["id"],
            "initial_prompt_id": prompt["id"],
            "optimization_config": {
                "optimizer_type": "mcts",
                "max_iterations": 6,
                "target_metric": "accuracy",
                "strategy_params": {
                    "mcts_simulations": 4,
                    "mcts_max_depth": 2,
                    "prompt_candidates_per_node": 1,
                    "token_budget": 1000,
                },
            },
            "test_case_ids": [case["id"]],
            "name": "MCTS Endpoint Worker",
        },
    )

    result = await jobs_worker._handle_job(_get_job_by_id(job_id))
    row = db.get_optimization(optimization_id) or {}

    assert row.get("status") == "completed"
    assert isinstance((row.get("final_metrics") or {}).get("trace"), dict)
    assert [int(x) for x in (row.get("test_case_ids") or [])] == [int(case["id"])]
    assert int(result.get("iterations") or 0) >= 1


@pytest.mark.asyncio
async def test_history_endpoint_returns_progress_and_timeline_after_worker_run(
    prompt_studio_dual_backend_db,
    monkeypatch,
):
    monkeypatch.setenv("PROMPT_STUDIO_ENABLE_MCTS", "true")

    async def allow_project_write_access(*args, **kwargs):
        return None

    async def allow_project_access(*args, **kwargs):
        return None

    monkeypatch.setattr(
        ps_opt_endpoints,
        "require_project_write_access",
        allow_project_write_access,
        raising=True,
    )
    monkeypatch.setattr(
        ps_opt_endpoints,
        "require_project_access",
        allow_project_access,
        raising=True,
    )

    _label, db = prompt_studio_dual_backend_db
    project, prompt, case = _seed_prompt_and_case(db)

    async def fake_run_single_test(self, *, prompt_id: int, test_case_id: int, model_config, metrics=None):
        row = self.db.get_prompt(prompt_id) or {}
        sys_text = row.get("system_prompt") or ""
        score = 0.9 if "Ensure outputs strictly follow" in sys_text else 0.2
        return {"success": True, "scores": {"aggregate_score": score}}

    async def fake_rephrase_segment(self, system_text: str, segment_text: str):
        return None

    monkeypatch.setattr(TestRunner, "run_single_test", fake_run_single_test, raising=True)
    monkeypatch.setattr(MCTSOptimizer, "_rephrase_segment", fake_rephrase_segment, raising=True)
    monkeypatch.setattr(jobs_worker, "_get_processor", lambda _user_id: JobProcessor(db), raising=True)

    optimization_id, job_id, _body = await _create_optimization_via_endpoint(
        db,
        {
            "project_id": project["id"],
            "initial_prompt_id": prompt["id"],
            "optimization_config": {
                "optimizer_type": "mcts",
                "max_iterations": 6,
                "target_metric": "accuracy",
                "strategy_params": {
                    "mcts_simulations": 4,
                    "mcts_max_depth": 2,
                    "prompt_candidates_per_node": 1,
                    "token_budget": 1000,
                },
            },
            "test_case_ids": [case["id"]],
            "name": "MCTS History Worker",
        },
    )

    _result = await jobs_worker._handle_job(_get_job_by_id(job_id))

    history_response = await ps_opt_endpoints.get_optimization_history(
        optimization_id=optimization_id,
        db=db,
        user_context={"user_id": "test-user-123", "is_admin": True, "permissions": ["all"]},
    )
    body = history_response.model_dump()
    assert body.get("success") is True
    data = body.get("data") or {}
    progress = data.get("progress") or {}
    timeline = data.get("timeline") or []

    assert str(progress.get("status")).lower() == "completed"
    assert int(progress.get("iterations_completed") or 0) >= 1
    assert isinstance(timeline, list) and len(timeline) >= 1


@pytest.mark.asyncio
async def test_endpoint_created_non_mcts_job_uses_worker_legacy_fallback_path(
    prompt_studio_dual_backend_db,
    monkeypatch,
):
    async def allow_project_write_access(*args, **kwargs):
        return None

    monkeypatch.setattr(
        ps_opt_endpoints,
        "require_project_write_access",
        allow_project_write_access,
        raising=True,
    )

    _label, db = prompt_studio_dual_backend_db
    project, prompt, _case = _seed_prompt_and_case(db)

    async def fake_iteration(self, optimization_id: int, prompt_id: int, iteration: int):
        return {
            "iteration": iteration,
            "prompt_id": prompt_id,
            "metric": 0.55 + (iteration * 0.1),
            "tokens_used": 12,
            "cost": 0.0,
        }

    async def no_sleep(_seconds: float):
        return None

    monkeypatch.setattr(JobProcessor, "_run_optimization_iteration", fake_iteration, raising=True)
    monkeypatch.setattr(job_processor_mod.asyncio, "sleep", no_sleep, raising=True)
    monkeypatch.setattr(jobs_worker, "_get_processor", lambda _user_id: JobProcessor(db), raising=True)

    optimization_id, job_id, _body = await _create_optimization_via_endpoint(
        db,
        {
            "project_id": project["id"],
            "initial_prompt_id": prompt["id"],
            "optimization_config": {
                "optimizer_type": "iterative",
                "max_iterations": 3,
                "target_metric": "accuracy",
            },
            "test_case_ids": [],
            "name": "Iterative Endpoint Worker",
        },
    )

    result = await jobs_worker._handle_job(_get_job_by_id(job_id))
    row = db.get_optimization(optimization_id) or {}

    assert row.get("status") == "completed"
    assert int(row.get("iterations_completed") or 0) == 3
    assert result.get("status") == "completed"
    assert int(result.get("iterations_completed") or 0) == 3


@pytest.mark.asyncio
async def test_worker_path_respects_cancelled_optimization_for_queued_and_running_states(
    prompt_studio_dual_backend_db,
    monkeypatch,
):
    monkeypatch.setenv("PROMPT_STUDIO_ENABLE_MCTS", "true")

    async def allow_project_write_access(*args, **kwargs):
        return None

    monkeypatch.setattr(
        ps_opt_endpoints,
        "require_project_write_access",
        allow_project_write_access,
        raising=True,
    )

    _label, db = prompt_studio_dual_backend_db
    project, prompt, case = _seed_prompt_and_case(db)

    async def fake_run_single_test(self, *, prompt_id: int, test_case_id: int, model_config, metrics=None):
        await asyncio.sleep(0.01)
        return {"success": True, "scores": {"aggregate_score": 0.25}}

    async def fake_rephrase_segment(self, system_text: str, segment_text: str):
        return None

    monkeypatch.setattr(TestRunner, "run_single_test", fake_run_single_test, raising=True)
    monkeypatch.setattr(MCTSOptimizer, "_rephrase_segment", fake_rephrase_segment, raising=True)
    monkeypatch.setattr(jobs_worker, "_get_processor", lambda _user_id: JobProcessor(db), raising=True)

    # Queued cancellation: cancelling before worker handling should keep optimization cancelled.
    queued_opt_id, queued_job_id, _queued_body = await _create_optimization_via_endpoint(
        db,
        {
            "project_id": project["id"],
            "initial_prompt_id": prompt["id"],
            "optimization_config": {
                "optimizer_type": "mcts",
                "max_iterations": 12,
                "target_metric": "accuracy",
                "strategy_params": {
                    "mcts_simulations": 12,
                    "mcts_max_depth": 2,
                    "prompt_candidates_per_node": 1,
                    "token_budget": 1000,
                },
            },
            "test_case_ids": [case["id"]],
            "name": "Queued-Cancel",
        },
    )
    _cancelled = await _cancel_optimization_via_endpoint(db, queued_opt_id)

    queued_result = await jobs_worker._handle_job(_get_job_by_id(queued_job_id))
    queued_row = db.get_optimization(queued_opt_id) or {}
    assert queued_result.get("status") == "cancelled"
    assert str(queued_row.get("status")).lower() == "cancelled"

    # Running cancellation: cancel while worker path is executing.
    running_opt_id, running_job_id, _running_body = await _create_optimization_via_endpoint(
        db,
        {
            "project_id": project["id"],
            "initial_prompt_id": prompt["id"],
            "optimization_config": {
                "optimizer_type": "mcts",
                "max_iterations": 30,
                "target_metric": "accuracy",
                "strategy_params": {
                    "mcts_simulations": 30,
                    "mcts_max_depth": 2,
                    "prompt_candidates_per_node": 1,
                    "token_budget": 10000,
                },
            },
            "test_case_ids": [case["id"]],
            "name": "Running-Cancel",
        },
    )

    async def cancel_soon():
        await asyncio.sleep(0.03)
        db.set_optimization_status(
            running_opt_id,
            "cancelled",
            error_message="cancelled in test",
            mark_completed=True,
        )

    worker_task = asyncio.create_task(jobs_worker._handle_job(_get_job_by_id(running_job_id)))
    cancel_task = asyncio.create_task(cancel_soon())
    worker_result = await worker_task
    await cancel_task

    running_row = db.get_optimization(running_opt_id) or {}
    raw_cfg = running_row.get("optimization_config") or {}
    if isinstance(raw_cfg, str):
        with contextlib.suppress(Exception):
            raw_cfg = json.loads(raw_cfg)
    if not isinstance(raw_cfg, dict):
        raw_cfg = {}
    requested_sims = int(((raw_cfg.get("strategy_params") or {}).get("mcts_simulations")) or 30)
    assert str(running_row.get("status")).lower() == "cancelled"
    assert int(running_row.get("iterations_completed") or 0) < requested_sims
    assert isinstance((running_row.get("final_metrics") or {}).get("trace"), dict)
    assert int(worker_result.get("iterations") or 0) < requested_sims
