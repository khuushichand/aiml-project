from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


pytestmark = pytest.mark.unit


def test_create_and_approve_research_run():
    from tldw_Server_API.app.api.v1.endpoints import research_runs

    app = FastAPI()
    app.include_router(research_runs.router, prefix="/api/v1")
    app.dependency_overrides[get_request_user] = lambda: SimpleNamespace(id=1)

    class StubService:
        def create_session(self, **kwargs):
            assert kwargs["owner_user_id"] == "1"
            return {
                "id": "rs_1",
                "status": "queued",
                "phase": "drafting_plan",
                "active_job_id": "9",
                "latest_checkpoint_id": None,
            }

        def approve_checkpoint(self, **kwargs):
            assert kwargs["session_id"] == "rs_1"
            assert kwargs["checkpoint_id"] == "cp_1"
            return {
                "id": kwargs["session_id"],
                "phase": "collecting",
                "status": "queued",
                "active_job_id": "10",
                "latest_checkpoint_id": kwargs["checkpoint_id"],
            }

    app.dependency_overrides[research_runs.get_research_service] = lambda: StubService()

    with TestClient(app) as client:
        create_resp = client.post("/api/v1/research/runs", json={"query": "Test deep research run"})
        assert create_resp.status_code == 200
        assert create_resp.json()["id"] == "rs_1"

        approve_resp = client.post(
            "/api/v1/research/runs/rs_1/checkpoints/cp_1/patch-and-approve",
            json={"patch_payload": {"focus_areas": ["background", "counterevidence"]}},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["phase"] == "collecting"
