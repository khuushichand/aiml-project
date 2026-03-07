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
    from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore
    from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job
    from tldw_Server_API.app.core.Research.models import (
        ResearchCollectionResult,
        ResearchEvidenceNote,
        ResearchSourceRecord,
    )
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

    class StubBroker:
        async def collect_focus_area(self, **kwargs):
            focus_area = kwargs["focus_area"]
            return ResearchCollectionResult(
                sources=[
                    ResearchSourceRecord(
                        source_id=f"src_{focus_area}",
                        focus_area=focus_area,
                        source_type="local_document",
                        provider="local_corpus",
                        title=f"Internal note for {focus_area}",
                        url=None,
                        snippet=f"Evidence for {focus_area}",
                        published_at=None,
                        retrieved_at="2026-03-07T00:00:00+00:00",
                        fingerprint=f"fp_{focus_area}",
                        trust_tier="internal",
                        metadata={},
                    )
                ],
                evidence_notes=[
                    ResearchEvidenceNote(
                        note_id=f"note_{focus_area}",
                        source_id=f"src_{focus_area}",
                        focus_area=focus_area,
                        kind="summary",
                        text=f"Evidence for {focus_area}",
                        citation_locator=None,
                        confidence=0.8,
                        metadata={},
                    )
                ],
                collection_metrics={"lane_counts": {"local": 1, "academic": 0, "web": 0}, "deduped_sources": 0},
                remaining_gaps=[],
            )

    asyncio.run(
        handle_research_phase_job(
            {
                "id": 12,
                "payload": {
                    "session_id": session_id,
                    "phase": "collecting",
                    "checkpoint_id": session.latest_checkpoint_id,
                    "policy_version": 1,
                },
            },
            research_db_path=research_db_path,
            outputs_dir=outputs_dir,
            broker=StubBroker(),
        )
    )

    session = db.get_session(session_id)
    assert session is not None
    assert session.phase == "awaiting_source_review"
    assert session.latest_checkpoint_id is not None
    assert (outputs_dir / "research" / session_id / "source_registry.json").exists()
    assert (outputs_dir / "research" / session_id / "evidence_notes.jsonl").exists()
    assert (outputs_dir / "research" / session_id / "collection_summary.json").exists()

    with TestClient(app) as client:
        approve_source_resp = client.post(
            f"/api/v1/research/runs/{session_id}/checkpoints/{session.latest_checkpoint_id}/patch-and-approve",
            json={},
        )
        assert approve_source_resp.status_code == 200
        assert approve_source_resp.json()["phase"] == "synthesizing"

    asyncio.run(
        handle_research_phase_job(
            {
                "id": 13,
                "payload": {
                    "session_id": session_id,
                    "phase": "synthesizing",
                    "checkpoint_id": session.latest_checkpoint_id,
                    "policy_version": 1,
                },
            },
            research_db_path=research_db_path,
            outputs_dir=outputs_dir,
        )
    )

    session = db.get_session(session_id)
    assert session is not None
    assert session.phase == "awaiting_outline_review"
    assert session.latest_checkpoint_id is not None
    assert (outputs_dir / "research" / session_id / "outline_v1.json").exists()
    assert (outputs_dir / "research" / session_id / "claims.json").exists()
    assert (outputs_dir / "research" / session_id / "report_v1.md").exists()
    assert (outputs_dir / "research" / session_id / "synthesis_summary.json").exists()

    with TestClient(app) as client:
        approve_outline_resp = client.post(
            f"/api/v1/research/runs/{session_id}/checkpoints/{session.latest_checkpoint_id}/patch-and-approve",
            json={},
        )
        assert approve_outline_resp.status_code == 200
        assert approve_outline_resp.json()["phase"] == "packaging"

    store = ResearchArtifactStore(base_dir=outputs_dir, db=db)
    asyncio.run(
        handle_research_phase_job(
            {
                "id": 14,
                "payload": {
                    "session_id": session_id,
                    "phase": "packaging",
                    "checkpoint_id": session.latest_checkpoint_id,
                    "policy_version": 1,
                },
            },
            research_db_path=research_db_path,
            outputs_dir=outputs_dir,
        )
    )

    session = db.get_session(session_id)
    assert session is not None
    assert session.phase == "completed"
    assert session.status == "completed"
    assert session.completed_at is not None

    package = store.read_json(session_id=session_id, artifact_name="bundle.json")
    assert package is not None

    with TestClient(app) as client:
        run_resp = client.get(f"/api/v1/research/runs/{session_id}")
        bundle_resp = client.get(f"/api/v1/research/runs/{session_id}/bundle")
        artifact_resp = client.get(f"/api/v1/research/runs/{session_id}/artifacts/report_v1.md")

        assert run_resp.status_code == 200
        assert run_resp.json()["phase"] == "completed"
        assert run_resp.json()["completed_at"] is not None
        assert bundle_resp.status_code == 200
        assert bundle_resp.json()["question"] == "Test deep research run"
        assert artifact_resp.status_code == 200
        assert artifact_resp.json()["artifact_name"] == "report_v1.md"
        assert artifact_resp.json()["content_type"] == "text/markdown"
        assert artifact_resp.json()["content"].startswith("# Research Report")

    adapter = FileAdapterRegistry().get_adapter("research_package")
    assert adapter is not None
    export = adapter.export(package, format="md")
    assert export.status == "ready"
    assert export.content.startswith(b"# Research Report")
    assert (outputs_dir / "research" / session_id / "bundle.json").exists()
