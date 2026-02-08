import pytest

from tldw_Server_API.app.core.Prompt_Management.prompt_studio import job_processor as job_processor_mod
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.job_processor import JobProcessor
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.mcts_optimizer import MCTSOptimizer
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
