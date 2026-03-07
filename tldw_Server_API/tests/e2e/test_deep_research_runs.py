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
    from tldw_Server_API.app.core.Research.service import ResearchService
    from tldw_Server_API.app.core.Research.synthesizer import ResearchSynthesizer

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
        create_resp = client.post(
            "/api/v1/research/runs",
            json={
                "query": "Test deep research run",
                "provider_overrides": {
                    "local": {"top_k": 4, "sources": ["media_db"]},
                    "web": {"engine": "kagi", "result_count": 3},
                    "academic": {"providers": ["arxiv", "pubmed"], "max_results": 2},
                    "synthesis": {"provider": "openai", "model": "gpt-4.1-mini", "temperature": 0.2},
                },
            },
        )
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
        provider_config_resp = client.get(f"/api/v1/research/runs/{session_id}/artifacts/provider_config.json")
        approve_resp = client.post(
            f"/api/v1/research/runs/{session_id}/checkpoints/{session.latest_checkpoint_id}/patch-and-approve",
            json={"patch_payload": {"focus_areas": ["background", "counterevidence"]}},
        )
        assert provider_config_resp.status_code == 200
        assert provider_config_resp.json()["content"]["web"]["engine"] == "kagi"
        assert provider_config_resp.json()["content"]["academic"]["providers"] == ["arxiv", "pubmed"]
        assert approve_resp.status_code == 200
        assert approve_resp.json()["phase"] == "collecting"

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
        )
    )

    session = db.get_session(session_id)
    assert session is not None
    assert session.phase == "awaiting_source_review"
    assert session.latest_checkpoint_id is not None
    assert (outputs_dir / "research" / session_id / "source_registry.json").exists()
    assert (outputs_dir / "research" / session_id / "evidence_notes.jsonl").exists()
    assert (outputs_dir / "research" / session_id / "collection_summary.json").exists()
    source_registry = ResearchArtifactStore(base_dir=outputs_dir, db=db).read_json(
        session_id=session_id,
        artifact_name="source_registry.json",
    )
    assert source_registry is not None
    assert {"local_corpus", "arxiv", "pubmed", "kagi"} <= {
        item["provider"] for item in source_registry["sources"]
    }

    with TestClient(app) as client:
        approve_source_resp = client.post(
            f"/api/v1/research/runs/{session_id}/checkpoints/{session.latest_checkpoint_id}/patch-and-approve",
            json={},
        )
        assert approve_source_resp.status_code == 200
        assert approve_source_resp.json()["phase"] == "synthesizing"

    store = ResearchArtifactStore(base_dir=outputs_dir, db=db)
    source_registry = store.read_json(session_id=session_id, artifact_name="source_registry.json")
    evidence_notes = store.read_jsonl(session_id=session_id, artifact_name="evidence_notes.jsonl")
    assert source_registry is not None
    assert evidence_notes is not None
    first_source = source_registry["sources"][0]
    first_note = evidence_notes[0]

    class StubSynthesisProvider:
        async def summarize(self, **kwargs):
            assert kwargs["config"]["provider"] == "openai"
            assert kwargs["config"]["model"] == "gpt-4.1-mini"
            return {
                "outline_sections": [
                    {
                        "title": "Background",
                        "focus_area": first_source["focus_area"],
                        "source_ids": [first_source["source_id"]],
                        "note_ids": [first_note["note_id"]],
                    }
                ],
                "claims": [
                    {
                        "text": "Supported claim",
                        "focus_area": first_source["focus_area"],
                        "source_ids": [first_source["source_id"]],
                        "citations": [{"source_id": first_source["source_id"]}],
                        "confidence": 0.81,
                    }
                ],
                "report_sections": [
                    {
                        "title": "Background",
                        "markdown": "Evidence-backed section text.",
                    }
                ],
                "unresolved_questions": [],
                "summary": {"mode": "llm_backed"},
            }

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
            synthesizer=ResearchSynthesizer(synthesis_provider=StubSynthesisProvider()),
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
    synthesis_summary = store.read_json(session_id=session_id, artifact_name="synthesis_summary.json")
    assert synthesis_summary is not None
    assert synthesis_summary["mode"] == "llm_backed"

    with TestClient(app) as client:
        approve_outline_resp = client.post(
            f"/api/v1/research/runs/{session_id}/checkpoints/{session.latest_checkpoint_id}/patch-and-approve",
            json={},
        )
        assert approve_outline_resp.status_code == 200
        assert approve_outline_resp.json()["phase"] == "packaging"

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
