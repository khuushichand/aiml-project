"""
Verify that the websearch endpoint offloads provider calls with asyncio.to_thread,
by checking that the patched generate_and_search runs without a running loop.
"""
import os
import threading
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

# Disable rate limiting before importing app (avoids slowapi decorator errors)
os.environ["TEST_MODE"] = "true"


def _mini_app_with_user():
    from tldw_Server_API.app.api.v1.endpoints import research as research_module
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user

    app = FastAPI()
    app.include_router(research_module.router, prefix="/api/v1/research")

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    app.dependency_overrides[get_request_user] = override_user
    return app


def test_generate_and_search_runs_in_thread(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import research as research_module

    observations = {}

    def fake_generate_and_search(question, params):
        import asyncio
        # Record whether a running loop exists in this context (thread pool should have none)
        has_loop = True
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            has_loop = False

        observations["has_loop"] = has_loop
        observations["thread_name"] = threading.current_thread().name

        return {
            "web_search_results_dict": {"results": [], "total_results_found": 0},
            "sub_query_dict": {"main_goal": question, "sub_questions": []},
        }

    monkeypatch.setattr(research_module, "generate_and_search", fake_generate_and_search)

    app = _mini_app_with_user()
    with TestClient(app) as client:
        payload = {"query": "ping", "engine": "duckduckgo", "result_count": 1, "aggregate": False}
        resp = client.post("/api/v1/research/websearch", json=payload)

    assert resp.status_code == 200
    assert observations.get("has_loop") is False
    # Should run under a different worker thread name
    assert "ThreadPoolExecutor" in observations.get("thread_name", "")
