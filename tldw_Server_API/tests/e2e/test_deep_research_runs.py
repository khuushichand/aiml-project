import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


pytestmark = pytest.mark.critical


def test_deep_research_run_can_be_approved_and_exported(tmp_path):
    from tldw_Server_API.app.api.v1.endpoints import research_runs
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.File_Artifacts.adapter_registry import FileAdapterRegistry
    from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job
    from tldw_Server_API.app.core.Research.service import ResearchService

    class DummyJobs:
        def create_job(self, **kwargs):
            return {"id": 11, "uuid": "job-11", "status": "queued", **kwargs}

    research_db_path = tmp_path / "research.db"
    outputs_dir = tmp_path / "outputs"
    service = ResearchService(
        research_db_path=research_db_path,
        outputs_dir=outputs_dir,
        job_manager=DummyJobs(),
    )

    app = FastAPI()
    app.include_router(research_runs.router, prefix="/api/v1")
    app.dependency_overrides[get_request_user] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[research_runs.get_research_service] = lambda: service

    with TestClient(app) as client:
        create_resp = client.post("/api/v1/research/runs", json={"query": "Test deep research run"})
        assert create_resp.status_code == 200
        session_id = create_resp.json()["id"]

    asyncio.run(
        handle_research_phase_job(
            {
                "id": 11,
                "payload": {
                    "session_id": session_id,
                    "phase": "drafting_plan",
                    "checkpoint_id": None,
                    "policy_version": 1,
                },
            },
            research_db_path=research_db_path,
            outputs_dir=outputs_dir,
        )
    )

    db = ResearchSessionsDB(research_db_path)
    session = db.get_session(session_id)
    assert session is not None
    assert session.latest_checkpoint_id is not None

    with TestClient(app) as client:
        approve_resp = client.post(
            f"/api/v1/research/runs/{session_id}/checkpoints/{session.latest_checkpoint_id}/patch-and-approve",
            json={"patch_payload": {"focus_areas": ["background", "counterevidence"]}},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["phase"] == "collecting"

    package = service.build_package(
        owner_user_id="1",
        session_id=session_id,
        brief={"query": "Test deep research run"},
        outline={"sections": ["Overview"]},
        report_markdown="# Report\nAnswer",
        claims=[{"text": "Claim", "citations": [{"source_id": "src_1"}]}],
        source_inventory=[{"source_id": "src_1", "title": "Source 1"}],
    )
    adapter = FileAdapterRegistry().get_adapter("research_package")
    assert adapter is not None
    export = adapter.export(package, format="md")
    assert export.status == "ready"
    assert export.content == b"# Report\nAnswer"
    assert (outputs_dir / "research" / session_id / "bundle.json").exists()
