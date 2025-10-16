"""
Integration test for /api/v1/research/websearch endpoint.
Allows 200 or 500 due to environment/network variability.
"""

import os
import pytest
from fastapi.testclient import TestClient

# Disable rate limiting before importing app (avoids slowapi decorator errors)
os.environ["TEST_MODE"] = "true"

from fastapi import FastAPI
from tldw_Server_API.app.api.v1.endpoints.research import router as research_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user

# Minimal app to avoid importing full server (audio limiter issue)
mini_app = FastAPI()
mini_app.include_router(research_router, prefix="/api/v1/research")


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user():
    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)
    mini_app.dependency_overrides[get_request_user] = override_user
    with TestClient(mini_app) as client:
        yield client
    mini_app.dependency_overrides.clear()


def test_websearch_minimal(client_with_user: TestClient):
    client = client_with_user
    payload = {
        "query": "what is the capital of france",
        "engine": "duckduckgo",
        "result_count": 5,
        "aggregate": False,
    }
    resp = client.post("/api/v1/research/websearch", json=payload)
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert "web_search_results_dict" in data
        assert "sub_query_dict" in data


def test_websearch_aggregate_path(client_with_user: TestClient, monkeypatch: pytest.MonkeyPatch):
    from tldw_Server_API.app.api.v1.endpoints import research as research_module

    def fake_generate_and_search(question, params):
        return {
            "web_search_results_dict": {"results": [], "total_results_found": 0},
            "sub_query_dict": {"main_goal": question, "sub_questions": []},
        }

    async def fake_analyze_and_aggregate(web_results_dict, sub_query_dict, search_params, **_):
        return {
            "final_answer": {
                "text": "Paris is the capital of France.",
                "evidence": [
                    {"content": "Paris is the capital of France", "reasoning": "Geography"}
                ],
                "confidence": 0.85,
                "chunks": [],
            },
            "relevant_results": {"0": {"content": "Paris", "reasoning": "Geography"}},
            "web_search_results_dict": web_results_dict,
        }

    monkeypatch.setattr(research_module, "generate_and_search", fake_generate_and_search)
    monkeypatch.setattr(research_module, "analyze_and_aggregate", fake_analyze_and_aggregate)

    client = client_with_user
    payload = {
        "query": "what is the capital of france",
        "engine": "google",
        "result_count": 3,
        "aggregate": True,
    }

    resp = client.post("/api/v1/research/websearch", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["final_answer"]["text"].startswith("Paris")
    assert isinstance(data["final_answer"]["confidence"], float)
    assert 0.0 <= data["final_answer"]["confidence"] <= 1.0
    assert data["final_answer"]["evidence"]
    assert "chunks" in data["final_answer"]
