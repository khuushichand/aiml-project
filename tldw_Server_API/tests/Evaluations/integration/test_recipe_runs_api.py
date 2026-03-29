from __future__ import annotations

import os
from typing import Any

import pytest

from tldw_Server_API.app.api.v1.schemas.evaluation_schemas_unified import RunStatus
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_single_user_instance
from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase
from tldw_Server_API.app.core.Evaluations.recipe_runs_service import (
    RECIPE_RUN_REUSE_ENTITY_TYPE,
    RecipeRunsService,
)
from tldw_Server_API.app.core.Evaluations.recipes.dataset_snapshot import build_dataset_content_hash

pytestmark = [pytest.mark.integration]


def _inline_dataset() -> list[dict[str, Any]]:
    return [
        {
            "input": "Summarize the meeting notes.",
            "expected": "A concise summary of the meeting notes.",
        }
    ]


def _run_config() -> dict[str, Any]:
    return {
        "candidate_model_ids": [
            "openai:gpt-4.1-mini",
            "local:mistral-small",
        ],
        "judge_config": {
            "provider": "openai",
            "model": "gpt-4.1-mini",
        },
        "prompts": {
            "system": "Compare model outputs.",
        },
        "weights": {
            "quality": 0.8,
            "cost": 0.2,
        },
        "comparison_mode": "leaderboard",
        "source_normalization": {
            "strip_citations": True,
        },
        "context_policy": {
            "mode": "strict",
        },
        "execution_policy": {
            "max_parallel_candidates": 2,
        },
    }


@pytest.mark.asyncio
async def test_recipe_manifest_endpoints(async_api_client, auth_headers) -> None:
    list_response = await async_api_client.get(
        "/api/v1/evaluations/recipes",
        headers=auth_headers,
    )

    assert list_response.status_code == 200
    manifests = list_response.json()
    assert any(item["recipe_id"] == "summarization_quality" for item in manifests)

    detail_response = await async_api_client.get(
        "/api/v1/evaluations/recipes/summarization_quality",
        headers=auth_headers,
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["recipe_id"] == "summarization_quality"


@pytest.mark.asyncio
async def test_recipe_validate_dataset_endpoint_returns_errors(async_api_client, auth_headers) -> None:
    response = await async_api_client.post(
        "/api/v1/evaluations/recipes/summarization_quality/validate-dataset",
        json={
            "dataset": [
                {"input": "valid prompt", "expected": "summary"},
                {"input": "missing label partner"},
            ]
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["errors"]


@pytest.mark.asyncio
async def test_recipe_run_create_metadata_and_report_endpoints(async_api_client, auth_headers) -> None:
    payload = {
        "dataset": _inline_dataset(),
        "run_config": _run_config(),
    }

    create_response = await async_api_client.post(
        "/api/v1/evaluations/recipes/summarization_quality/runs",
        json=payload,
        headers=auth_headers,
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["status"] == "pending"
    assert created["metadata"]["run_config"] == payload["run_config"]

    run_id = created["run_id"]

    metadata_response = await async_api_client.get(
        f"/api/v1/evaluations/recipe-runs/{run_id}",
        headers=auth_headers,
    )

    assert metadata_response.status_code == 200
    assert metadata_response.json()["run_id"] == run_id

    report_response = await async_api_client.get(
        f"/api/v1/evaluations/recipe-runs/{run_id}/report",
        headers=auth_headers,
    )

    assert report_response.status_code == 200
    report = report_response.json()
    assert report["run"]["run_id"] == run_id
    assert set(report["recommendation_slots"]) == {
        "best_overall",
        "best_cheap",
        "best_local",
    }
    for slot in report["recommendation_slots"].values():
        assert slot["candidate_run_id"] is None
        assert slot["reason_code"] is not None


@pytest.mark.asyncio
async def test_recipe_run_endpoint_reuses_completed_run_unless_forced(async_api_client, auth_headers) -> None:
    db_path = os.environ["EVALUATIONS_TEST_DB_PATH"]
    db = EvaluationsDatabase(db_path)
    user_id = get_single_user_instance().id_str
    service = RecipeRunsService(db=db, user_id=user_id)
    dataset = _inline_dataset()
    run_config = _run_config()
    manifest = service.get_manifest("summarization_quality")
    reuse_hash = service.build_reuse_hash(
        "summarization_quality",
        dataset=dataset,
        run_config=run_config,
    )

    completed_run_id = db.create_recipe_run(
        recipe_id=manifest.recipe_id,
        recipe_version=manifest.recipe_version,
        status=RunStatus.COMPLETED,
        dataset_content_hash=build_dataset_content_hash(dataset),
        metadata={
            "run_config": run_config,
            "reuse_hash": reuse_hash,
        },
    )
    db.record_idempotency(
        RECIPE_RUN_REUSE_ENTITY_TYPE,
        reuse_hash,
        completed_run_id,
        user_id,
    )

    response = await async_api_client.post(
        "/api/v1/evaluations/recipes/summarization_quality/runs",
        json={
            "dataset": dataset,
            "run_config": run_config,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    reused = response.json()
    assert reused["run_id"] == completed_run_id
    assert reused["status"] == "completed"

    forced_response = await async_api_client.post(
        "/api/v1/evaluations/recipes/summarization_quality/runs",
        json={
            "dataset": dataset,
            "run_config": run_config,
            "force_rerun": True,
        },
        headers=auth_headers,
    )

    assert forced_response.status_code == 201
    forced = forced_response.json()
    assert forced["run_id"] != completed_run_id
    assert forced["status"] == "pending"
