"""Covers background optimization spawn path (prod-like).

This test ensures that when TEST_MODE is not set to true, the
optimization create endpoint schedules a background task which runs
and completes the optimization.
"""

from __future__ import annotations

import os
import asyncio
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.api.v1.API_Deps.prompt_studio_deps import get_prompt_studio_db
from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import PromptStudioDatabase


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_background_optimization_spawn_and_complete(tmp_path, monkeypatch):
    # Ensure TEST_MODE is not true so endpoint schedules background tasks
    monkeypatch.setenv("TEST_MODE", "false")

    # Provide an isolated DB instance via dependency override
    db_path = tmp_path / "ps_bg.sqlite"
    db = PromptStudioDatabase(str(db_path), "bg-test")

    async def override_db():
        return db

    # Patch the async background runner to a fast stub that marks completion
    from tldw_Server_API.app.api.v1.endpoints import prompt_studio_optimization as opt_mod

    async def _fast_run_optimization(optimization_id: int, pdb: PromptStudioDatabase):
        # Minimal completion to simulate a successful background run
        pdb.complete_optimization(
            optimization_id,
            optimized_prompt_id=None,
            iterations_completed=1,
            initial_metrics={"accuracy": 0.5},
            final_metrics={"accuracy": 0.6},
            improvement_percentage=20.0,
            total_tokens=0,
            total_cost=0.0,
        )

    monkeypatch.setattr(opt_mod, "run_optimization_async", _fast_run_optimization)

    _app = fastapi_app
    _app.dependency_overrides[get_prompt_studio_db] = override_db

    try:
        with TestClient(_app) as client:
            # Create project
            project = client.post(
                "/api/v1/prompt-studio/projects/",
                json={"name": "BG Proj", "description": "", "status": "active", "metadata": {}},
            )
            assert project.status_code in (200, 201), project.text
            pid = project.json()["data"]["id"]

            # Create prompt
            prompt = client.post(
                "/api/v1/prompt-studio/prompts/create",
                json={"project_id": pid, "name": "BG Prompt", "system_prompt": "S", "user_prompt": "{{q}}"},
            )
            assert prompt.status_code in (200, 201), prompt.text
            prompt_id = prompt.json()["data"]["id"]

            # Create optimization - should schedule background task that uses our stub
            opt = client.post(
                "/api/v1/prompt-studio/optimizations/create",
                json={
                    "project_id": pid,
                    "initial_prompt_id": prompt_id,
                    "optimization_config": {"optimizer_type": "iterative", "max_iterations": 2, "target_metric": "accuracy"},
                    "test_case_ids": [],
                    "name": "BG Opt",
                },
            )
            assert opt.status_code in (200, 201), opt.text
            opt_id = opt.json()["data"]["optimization"]["id"]

            # BackgroundTasks in TestClient are executed after response;
            # still, give a small async pause to ensure DB commit
            await asyncio.sleep(0.01)

            # Verify completion
            st = client.get(f"/api/v1/prompt-studio/optimizations/get/{opt_id}")
            assert st.status_code == 200, st.text
            status_val = st.json()["data"]["status"]
            assert status_val == "completed"
    finally:
        _app.dependency_overrides.clear()
