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


def test_create_research_run_passes_provider_overrides():
    from tldw_Server_API.app.api.v1.endpoints import research_runs

    app = FastAPI()
    app.include_router(research_runs.router, prefix="/api/v1")
    app.dependency_overrides[get_request_user] = lambda: SimpleNamespace(id=1)

    class StubService:
        def create_session(self, **kwargs):
            assert kwargs["provider_overrides"]["web"]["engine"] == "duckduckgo"
            assert kwargs["provider_overrides"]["local"]["top_k"] == 4
            return {
                "id": "rs_2",
                "status": "queued",
                "phase": "drafting_plan",
                "active_job_id": "11",
                "latest_checkpoint_id": None,
            }

    app.dependency_overrides[research_runs.get_research_service] = lambda: StubService()

    with TestClient(app) as client:
        create_resp = client.post(
            "/api/v1/research/runs",
            json={
                "query": "Provider override test",
                "provider_overrides": {
                    "local": {"top_k": 4, "sources": ["media_db"]},
                    "web": {"engine": "duckduckgo", "result_count": 3},
                },
            },
        )
        assert create_resp.status_code == 200
        assert create_resp.json()["id"] == "rs_2"


def test_read_research_run_bundle_and_artifact():
    from tldw_Server_API.app.api.v1.endpoints import research_runs

    app = FastAPI()
    app.include_router(research_runs.router, prefix="/api/v1")
    app.dependency_overrides[get_request_user] = lambda: SimpleNamespace(id=1)

    class StubService:
        def get_session(self, **kwargs):
            assert kwargs["session_id"] == "rs_1"
            return {
                "id": "rs_1",
                "status": "completed",
                "phase": "completed",
                "active_job_id": None,
                "latest_checkpoint_id": "cp_1",
                "completed_at": "2026-03-07T00:00:00+00:00",
            }

        def get_bundle(self, **kwargs):
            assert kwargs["session_id"] == "rs_1"
            return {
                "question": "What changed?",
                "report_markdown": "# Report",
                "claims": [],
            }

        def get_artifact(self, **kwargs):
            assert kwargs["session_id"] == "rs_1"
            assert kwargs["artifact_name"] == "report_v1.md"
            return {
                "artifact_name": "report_v1.md",
                "content_type": "text/markdown",
                "content": "# Report",
            }

    app.dependency_overrides[research_runs.get_research_service] = lambda: StubService()

    with TestClient(app) as client:
        run_resp = client.get("/api/v1/research/runs/rs_1")
        bundle_resp = client.get("/api/v1/research/runs/rs_1/bundle")
        artifact_resp = client.get("/api/v1/research/runs/rs_1/artifacts/report_v1.md")

        assert run_resp.status_code == 200
        assert run_resp.json()["completed_at"] == "2026-03-07T00:00:00+00:00"
        assert bundle_resp.status_code == 200
        assert bundle_resp.json()["question"] == "What changed?"
        assert artifact_resp.status_code == 200
        assert artifact_resp.json()["content_type"] == "text/markdown"


def test_read_research_artifact_maps_not_found_and_disallowed_errors():
    from tldw_Server_API.app.api.v1.endpoints import research_runs

    app = FastAPI()
    app.include_router(research_runs.router, prefix="/api/v1")
    app.dependency_overrides[get_request_user] = lambda: SimpleNamespace(id=1)

    class StubService:
        def get_session(self, **kwargs):
            raise KeyError(kwargs["session_id"])

        def get_bundle(self, **kwargs):
            raise KeyError("bundle.json")

        def get_artifact(self, **kwargs):
            if kwargs["artifact_name"] == "bad.bin":
                raise ValueError("artifact_not_allowed")
            raise KeyError(kwargs["artifact_name"])

    app.dependency_overrides[research_runs.get_research_service] = lambda: StubService()

    with TestClient(app) as client:
        run_resp = client.get("/api/v1/research/runs/rs_missing")
        bundle_resp = client.get("/api/v1/research/runs/rs_1/bundle")
        bad_artifact_resp = client.get("/api/v1/research/runs/rs_1/artifacts/bad.bin")
        missing_artifact_resp = client.get("/api/v1/research/runs/rs_1/artifacts/report_v1.md")

        assert run_resp.status_code == 404
        assert bundle_resp.status_code == 404
        assert bad_artifact_resp.status_code == 400
        assert missing_artifact_resp.status_code == 404
