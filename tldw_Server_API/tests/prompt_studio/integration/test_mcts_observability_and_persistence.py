import asyncio
import math
import os
import pytest

from tldw_Server_API.app.core.Prompt_Management.prompt_studio.optimization_engine import OptimizationEngine
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.event_broadcaster import EventType


pytestmark = pytest.mark.integration


def _seed_minimal_prompt_and_case(db):
    project = db.create_project(name="MCTSProj", description="", user_id="tester")
    prompt = db.create_prompt(
        project_id=project["id"],
        name="MCTSPrompt",
        system_prompt="You are precise.",
        user_prompt="Echo: {text}",
    )
    case = db.create_test_case(
        project_id=project["id"],
        name="Case",
        inputs={"text": "hello"},
        expected_outputs={"response": "hello"},
    )
    return project, prompt, case


def test_mcts_ws_throttling_behavior(prompt_studio_dual_backend_db, monkeypatch):
    # Enable MCTS via env flag (default is off)
    monkeypatch.setenv("PROMPT_STUDIO_ENABLE_MCTS", "true")

    label, db = prompt_studio_dual_backend_db
    project, prompt, case = _seed_minimal_prompt_and_case(db)

    # Create optimization row
    n_sims = 12
    throttle_every = 5
    opt = db.create_optimization(
        project_id=project["id"],
        name="WS-Throttle",
        initial_prompt_id=prompt["id"],
        optimizer_type="mcts",
        optimization_config={
            "optimizer_type": "mcts",
            "target_metric": "accuracy",
            "strategy_params": {
                "mcts_simulations": n_sims,
                "mcts_max_depth": 2,
                "prompt_candidates_per_node": 1,
                "ws_throttle_every": throttle_every,
                "token_budget": 1000,
            },
        },
        max_iterations=n_sims,
        status="pending",
    )

    # Ensure engine can resolve test_case_ids/model_config like endpoint would
    import json as _json
    db.update_optimization(opt["id"], {
        "test_case_ids": [case["id"] for case in db.get_test_cases_by_ids([case["id"] for case in db.get_test_cases_by_ids([1])]) if False]  # placeholder no-op
    })
    # Minimal test set: empty list acceptable for engine code paths
    db.update_optimization(opt["id"], {"test_case_ids": []})

    # Patch EventBroadcaster to count iteration events
    events = {"iteration": 0, "started": 0, "completed": 0}

    async def _patched_broadcast_event(self, event_type, data, client_ids=None, project_id=None):
        et = (event_type.value if hasattr(event_type, "value") else str(event_type)).lower()
        if et == EventType.OPTIMIZATION_ITERATION.value:
            events["iteration"] += 1
        elif et == EventType.OPTIMIZATION_STARTED.value:
            events["started"] += 1
        elif et == EventType.OPTIMIZATION_COMPLETED.value:
            events["completed"] += 1
        return None

    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import event_broadcaster as eb_mod
    monkeypatch.setattr(eb_mod.EventBroadcaster, "broadcast_event", _patched_broadcast_event, raising=True)

    engine = OptimizationEngine(db)

    # Run MCTS synchronously in test loop
    asyncio.get_event_loop().run_until_complete(engine.optimize(opt["id"]))

    # With throttling, iteration events should be bounded
    # Base expectation: first + last + floor(n_sims / throttle_every)
    expected_upper = (n_sims // throttle_every) + 4  # allow small slack for improvements
    assert events["iteration"] <= expected_upper
    assert events["started"] == 1
    assert events["completed"] == 1


@pytest.mark.asyncio
async def test_mcts_cancellation_mid_run(prompt_studio_dual_backend_db, monkeypatch):
    # Enable MCTS
    monkeypatch.setenv("PROMPT_STUDIO_ENABLE_MCTS", "true")

    label, db = prompt_studio_dual_backend_db
    project, prompt, case = _seed_minimal_prompt_and_case(db)
    n_sims = 40
    opt = db.create_optimization(
        project_id=project["id"],
        name="Cancel-Run",
        initial_prompt_id=prompt["id"],
        optimizer_type="mcts",
        optimization_config={
            "optimizer_type": "mcts",
            "target_metric": "accuracy",
            "strategy_params": {
                "mcts_simulations": n_sims,
                "mcts_max_depth": 2,
                "prompt_candidates_per_node": 1,
                "ws_throttle_every": 1,
                "token_budget": 2000,
            },
        },
        max_iterations=n_sims,
        status="pending",
    )

    # Ensure engine has test cases field present
    db.update_optimization(opt["id"], {"test_case_ids": []})
    engine = OptimizationEngine(db)

    async def _cancel_soon():
        await asyncio.sleep(0.05)
        db.set_optimization_status(opt["id"], "cancelled", mark_completed=True)

    # Run optimize and cancellation concurrently
    task_opt = asyncio.create_task(engine.optimize(opt["id"]))
    task_cancel = asyncio.create_task(_cancel_soon())
    results = await task_opt
    await task_cancel

    # Should not complete all sims due to cancellation
    assert results["iterations"] < n_sims


def test_mcts_final_trace_persisted(prompt_studio_dual_backend_db, monkeypatch):
    monkeypatch.setenv("PROMPT_STUDIO_ENABLE_MCTS", "true")
    monkeypatch.setenv("PROMPT_STUDIO_MCTS_DEBUG_DECISIONS", "true")

    label, db = prompt_studio_dual_backend_db
    project, prompt, case = _seed_minimal_prompt_and_case(db)

    n_sims = 3
    opt = db.create_optimization(
        project_id=project["id"],
        name="Trace-Persist",
        initial_prompt_id=prompt["id"],
        optimizer_type="mcts",
        optimization_config={
            "optimizer_type": "mcts",
            "target_metric": "accuracy",
            "strategy_params": {
                "mcts_simulations": n_sims,
                "mcts_max_depth": 2,
                "prompt_candidates_per_node": 1,
                "trace_top_k": 2,
                "token_budget": 1000,
            },
        },
        max_iterations=n_sims,
        status="pending",
    )

    # Ensure engine has test cases field present
    db.update_optimization(opt["id"], {"test_case_ids": []})
    engine = OptimizationEngine(db)
    asyncio.get_event_loop().run_until_complete(engine.optimize(opt["id"]))

    row = db.get_optimization(opt["id"]) or {}
    fm = row.get("final_metrics") or {}
    assert isinstance(fm, dict)
    assert "trace" in fm and isinstance(fm["trace"], dict)
    tr = fm["trace"]
    assert "best_path" in tr and "top_candidates" in tr
    # When debug flag is on, include debug_top_scores_by_depth
    assert "debug_top_scores_by_depth" in tr
