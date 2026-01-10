"""Smoke test for IterativeRefinementOptimizer with mocked LLM and runner.

Validates that refinement produces a new prompt row using the correct schema
fields and increments version_number while preserving user_prompt.
"""

import asyncio
import os
from typing import Dict, Any, List

import pytest

from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import PromptStudioDatabase
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.optimization_strategies import (
    IterativeRefinementOptimizer,
)
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.optimization_engine import TestRunner


@pytest.fixture
def temp_ps_db(tmp_path) -> PromptStudioDatabase:
    os.environ.setdefault("TEST_MODE", "true")
    db_path = tmp_path / "ps_iter_smoke.db"
    return PromptStudioDatabase(str(db_path), client_id="iter-smoke")


def _seed_project_prompt(db: PromptStudioDatabase) -> Dict[str, int]:
    proj = db.create_project("Iter-Smoke", "desc")
    pid = int(proj["id"]) if isinstance(proj, dict) else int(proj)
    p = db.create_prompt(
        project_id=pid,
        name="Base-Iter",
        system_prompt="Follow policies",
        user_prompt="Provide answer for {q}",
        version_number=1,
    )
    return {"project_id": pid, "prompt_id": int(p["id"]) }


def _seed_test_cases(db: PromptStudioDatabase, project_id: int, n: int = 3) -> List[int]:
    ids: List[int] = []
    for i in range(n):
        tc = db.create_test_case(
            project_id=project_id,
            name=f"ITER-TC-{i}",
            inputs={"q": f"iter-q-{i}"},
            expected_outputs={"response": f"iter-a-{i}"},
            is_golden=False,
        )
        ids.append(int(tc["id"]))
    return ids


@pytest.mark.asyncio
async def test_iterative_refinement_optimizer_smoke(temp_ps_db, monkeypatch):
    ids = _seed_project_prompt(temp_ps_db)
    project_id = ids["project_id"]
    prompt_id = ids["prompt_id"]
    test_case_ids = _seed_test_cases(temp_ps_db, project_id, n=3)

    # Patch TestRunner.run_single_test to yield low score (<0.8) to trigger refinements
    async def _fake_run_single_test(self, prompt_id: int, test_case_id: int, model_config: Dict[str, Any]):
        return {
            "success": True,
            "test_case_id": test_case_id,
            "inputs": {"q": f"iter-q-{test_case_id}"},
            "expected_outputs": {"response": f"iter-a-{test_case_id}"},
            "actual_output": {"response": f"diff-{test_case_id}"},
            "scores": {"aggregate_score": 0.6},
        }

    monkeypatch.setattr(TestRunner, "run_single_test", _fake_run_single_test)

    # Patch LLM helper to return refinement text
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import prompt_executor as _pe

    async def _fake_call_llm(*args, **kwargs) -> Dict[str, Any]:
        return {"content": "Refined instruction for clarity"}

    monkeypatch.setattr(_pe.PromptExecutor, "_call_llm", staticmethod(_fake_call_llm))

    # Speed up sleeps
    async def _fast_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", _fast_sleep)

    runner = TestRunner(temp_ps_db)
    it = IterativeRefinementOptimizer(temp_ps_db, runner)
    result = await it.optimize(
        prompt_id=prompt_id,
        test_case_ids=test_case_ids,
        model_config={"model": "dummy"},
        max_iterations=1,
        optimization_id=123,
    )

    assert result["optimized_prompt_id"]
    new_id = int(result["optimized_prompt_id"])
    new_prompt = temp_ps_db.get_prompt(new_id)
    assert new_prompt is not None
    # system_prompt should contain the refinement
    assert "Refined instruction" in new_prompt.get("system_prompt", "")
    # user_prompt should be preserved
    assert new_prompt.get("user_prompt", "").startswith("Provide answer for")
    # version number incremented
    assert int(new_prompt.get("version_number", 0)) >= 2
    # Iteration history contains at least one entry and improvement metric exists
    assert "iteration_history" in result and isinstance(result["iteration_history"], list)
    assert len(result["iteration_history"]) >= 1
    assert "iterations" in result and int(result["iterations"]) >= 1
    assert "initial_score" in result and "final_score" in result and "improvement" in result
    assert isinstance(result["improvement"], (int, float))
