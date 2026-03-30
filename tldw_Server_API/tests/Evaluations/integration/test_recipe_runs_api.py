import os
from typing import Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def recipe_runs_client() -> Tuple[TestClient, dict]:
    os.environ.setdefault("AUTH_MODE", "single_user")
    os.environ.setdefault("TESTING", "true")
    os.environ.setdefault("TEST_MODE", "true")

    from tldw_Server_API.app.api.v1.endpoints.evaluations.evaluations_recipes import recipe_router
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    app = FastAPI()
    app.include_router(recipe_router, prefix="/api/v1/evaluations")

    api_key = get_settings().SINGLE_USER_API_KEY
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    client = TestClient(app)
    return client, headers


@pytest.mark.integration
def test_rag_retrieval_tuning_recipe_api_flow(recipe_runs_client, monkeypatch):
    client, headers = recipe_runs_client

    class _StubService:
        def list_recipes(self):
            return [
                {
                    "id": "rag_retrieval_tuning",
                    "version": "v1",
                    "display_name": "RAG Retrieval Tuning",
                    "description": "Tune retrieval settings against your own corpus.",
                    "status": "stable",
                }
            ]

        def get_recipe_manifest(self, recipe_id: str):
            return {
                "id": recipe_id,
                "version": "v1",
                "display_name": "RAG Retrieval Tuning",
                "description": "Tune retrieval settings against your own corpus.",
                "status": "stable",
            }

        def validate_recipe_dataset(self, recipe_id: str, payload: dict):
            if not payload.get("dataset_id"):
                return {"valid": False, "errors": ["dataset_id is required"]}
            if not payload.get("candidate_models"):
                return {"valid": False, "errors": ["candidate_models is required"]}
            return {"valid": True, "errors": []}

        def create_recipe_run(self, recipe_id: str, payload: dict, *, created_by: str | None = None):
            return {
                "id": "recipe_run_1",
                "object": "recipe_run",
                "recipe_id": recipe_id,
                "recipe_version": "v1",
                "dataset_id": payload["dataset_id"],
                "dataset_version": payload.get("dataset_version"),
                "candidate_models": payload["candidate_models"],
                "status": "pending",
                "review_state": "review_required",
                "config_hash": "sha256:abc123",
                "reused": False,
            }

        def get_recipe_run(self, run_id: str, *, created_by: str | None = None):
            return {
                "id": run_id,
                "object": "recipe_run",
                "recipe_id": "rag_retrieval_tuning",
                "recipe_version": "v1",
                "dataset_id": "dataset_1",
                "dataset_version": "v1",
                "candidate_models": ["m1", "m2"],
                "status": "completed",
                "review_state": "not_required",
                "config_hash": "sha256:abc123",
                "reused": False,
            }

        def get_recipe_report(self, run_id: str, *, created_by: str | None = None):
            return {
                "id": run_id,
                "object": "recipe_report",
                "recipe_id": "rag_retrieval_tuning",
                "best_overall": {"model": "m1"},
                "best_overall_reason_code": None,
                "best_cheap": {"model": "m2"},
                "best_cheap_reason_code": None,
                "best_local": None,
                "best_local_reason_code": "no_local_candidate",
                "review_state": "not_required",
                "confidence": {
                    "sample_count": 2,
                    "variance": 0.0,
                    "winner_margin": 0.12,
                    "judge_agreement": None,
                    "warning_codes": [],
                },
            }

    import tldw_Server_API.app.api.v1.endpoints.evaluations.evaluations_recipes as recipes

    monkeypatch.setattr(recipes, "get_recipe_runs_service_for_user", lambda user_id: _StubService())

    list_resp = client.get("/api/v1/evaluations/recipes", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["data"][0]["id"] == "rag_retrieval_tuning"

    manifest_resp = client.get("/api/v1/evaluations/recipes/rag_retrieval_tuning", headers=headers)
    assert manifest_resp.status_code == 200
    assert manifest_resp.json()["id"] == "rag_retrieval_tuning"

    validate_resp = client.post(
        "/api/v1/evaluations/recipes/rag_retrieval_tuning/validate-dataset",
        json={"dataset_id": "dataset_1"},
        headers=headers,
    )
    assert validate_resp.status_code == 200
    assert validate_resp.json()["valid"] is False

    create_resp = client.post(
        "/api/v1/evaluations/recipes/rag_retrieval_tuning/runs",
        json={
            "dataset_id": "dataset_1",
            "dataset_version": "v1",
            "candidate_models": ["m1", "m2"],
            "data_mode": "unlabeled",
            "run_config": {"retrieval_mode": "embedding_only"},
        },
        headers=headers,
    )
    assert create_resp.status_code == 202
    assert create_resp.json()["status"] == "pending"
    assert create_resp.json()["review_state"] == "review_required"

    run_resp = client.get("/api/v1/evaluations/recipe-runs/recipe_run_1", headers=headers)
    assert run_resp.status_code == 200
    assert run_resp.json()["status"] == "completed"

    report_resp = client.get("/api/v1/evaluations/recipe-runs/recipe_run_1/report", headers=headers)
    assert report_resp.status_code == 200
    report = report_resp.json()
    assert report["best_overall"]["model"] == "m1"
    assert report["best_overall_reason_code"] is None
    assert report["best_local"] is None
    assert report["confidence"]["sample_count"] == 2
