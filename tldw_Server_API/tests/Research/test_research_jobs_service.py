import pytest


pytestmark = pytest.mark.unit


def test_create_session_enqueues_planning_job(tmp_path):
    from tldw_Server_API.app.core.Research.service import ResearchService

    captured: dict[str, object] = {}

    class DummyJobs:
        def create_job(self, **kwargs):
            captured.update(kwargs)
            return {"id": 9, "uuid": "job-9", "status": "queued"}

    service = ResearchService(
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
        job_manager=DummyJobs(),
    )

    session = service.create_session(
        owner_user_id="1",
        query="Map evidence gaps between internal notes and public filings",
        source_policy="balanced",
        autonomy_mode="checkpointed",
    )

    assert session.phase == "drafting_plan"
    assert session.active_job_id == "9"
    assert captured["domain"] == "research"
    assert captured["job_type"] == "research_phase"
    assert captured["payload"]["session_id"] == session.id


def test_approve_plan_review_enqueues_collecting_job(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.service import ResearchService

    captured: dict[str, object] = {}

    class DummyJobs:
        def create_job(self, **kwargs):
            captured.update(kwargs)
            return {"id": 10, "uuid": "job-10", "status": "queued"}

    service = ResearchService(
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
        job_manager=DummyJobs(),
    )
    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Map evidence gaps",
        source_policy="balanced",
        autonomy_mode="checkpointed",
        limits_json={},
        phase="awaiting_plan_review",
        status="waiting_human",
    )
    checkpoint = db.create_checkpoint(
        session_id=session.id,
        checkpoint_type="plan_review",
        proposed_payload={
            "query": session.query,
            "focus_areas": ["evidence alignment"],
            "source_policy": session.source_policy,
            "autonomy_mode": session.autonomy_mode,
            "stop_criteria": {"min_cited_sections": 1},
        },
    )

    updated = service.approve_checkpoint(
        owner_user_id="1",
        session_id=session.id,
        checkpoint_id=checkpoint.id,
        patch_payload={"focus_areas": ["evidence alignment", "contradictions"]},
    )

    assert updated.phase == "collecting"
    assert updated.active_job_id == "10"
    assert captured["payload"]["phase"] == "collecting"
    assert captured["payload"]["session_id"] == session.id


def test_approve_sources_review_advances_to_synthesizing_without_requeue(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.service import ResearchService

    class DummyJobs:
        def create_job(self, **kwargs):
            raise AssertionError(f"unexpected job enqueue: {kwargs}")

    service = ResearchService(
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
        job_manager=DummyJobs(),
    )
    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Map evidence gaps",
        source_policy="balanced",
        autonomy_mode="checkpointed",
        limits_json={},
        phase="awaiting_source_review",
        status="waiting_human",
    )
    checkpoint = db.create_checkpoint(
        session_id=session.id,
        checkpoint_type="sources_review",
        proposed_payload={
            "query": session.query,
            "focus_areas": ["evidence alignment"],
            "source_inventory": [{"source_id": "src_1"}],
            "collection_summary": {"source_count": 1},
        },
    )

    updated = service.approve_checkpoint(
        owner_user_id="1",
        session_id=session.id,
        checkpoint_id=checkpoint.id,
    )

    assert updated.phase == "synthesizing"
    assert updated.active_job_id is None


def test_approve_outline_review_enqueues_packaging_job(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.service import ResearchService

    captured: dict[str, object] = {}

    class DummyJobs:
        def create_job(self, **kwargs):
            captured.update(kwargs)
            return {"id": 12, "uuid": "job-12", "status": "queued"}

    service = ResearchService(
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
        job_manager=DummyJobs(),
    )
    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Map evidence gaps",
        source_policy="balanced",
        autonomy_mode="checkpointed",
        limits_json={},
        phase="awaiting_outline_review",
        status="waiting_human",
    )
    checkpoint = db.create_checkpoint(
        session_id=session.id,
        checkpoint_type="outline_review",
        proposed_payload={
            "outline": {"sections": [{"title": "Background"}]},
            "claim_count": 1,
            "report_preview": "# Research Report",
        },
    )

    updated = service.approve_checkpoint(
        owner_user_id="1",
        session_id=session.id,
        checkpoint_id=checkpoint.id,
    )

    assert updated.phase == "packaging"
    assert updated.active_job_id == "12"
    assert captured["payload"]["phase"] == "packaging"
    assert captured["payload"]["session_id"] == session.id


def test_get_session_bundle_and_allowlisted_artifacts(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore
    from tldw_Server_API.app.core.Research.service import ResearchService

    service = ResearchService(
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
        job_manager=None,
    )
    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Read artifacts",
        source_policy="balanced",
        autonomy_mode="autonomous",
        limits_json={},
        phase="completed",
        status="completed",
    )
    store = ResearchArtifactStore(base_dir=tmp_path / "outputs", db=db)
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="bundle.json",
        payload={"question": session.query, "claims": []},
        phase="completed",
        job_id=None,
    )
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="claims.json",
        payload={"claims": [{"claim_id": "clm_1"}]},
        phase="completed",
        job_id=None,
    )
    store.write_jsonl(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="evidence_notes.jsonl",
        records=[{"note_id": "note_1", "text": "Evidence"}],
        phase="completed",
        job_id=None,
    )
    store.write_text(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="report_v1.md",
        content="# Research Report",
        phase="completed",
        job_id=None,
        content_type="text/markdown",
    )

    loaded_session = service.get_session(owner_user_id="1", session_id=session.id)
    bundle = service.get_bundle(owner_user_id="1", session_id=session.id)
    claims = service.get_artifact(owner_user_id="1", session_id=session.id, artifact_name="claims.json")
    notes = service.get_artifact(owner_user_id="1", session_id=session.id, artifact_name="evidence_notes.jsonl")
    report = service.get_artifact(owner_user_id="1", session_id=session.id, artifact_name="report_v1.md")

    assert loaded_session.id == session.id
    assert bundle["question"] == session.query
    assert claims["content"]["claims"][0]["claim_id"] == "clm_1"
    assert notes["content"][0]["note_id"] == "note_1"
    assert report["content"] == "# Research Report"
    assert report["content_type"] == "text/markdown"


def test_get_artifact_rejects_disallowed_name(tmp_path):
    from tldw_Server_API.app.core.Research.service import ResearchService

    service = ResearchService(
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
        job_manager=None,
    )

    with pytest.raises(ValueError, match="artifact_not_allowed"):
        service.get_artifact(
            owner_user_id="1",
            session_id="rs_missing",
            artifact_name="not_allowed.bin",
        )
