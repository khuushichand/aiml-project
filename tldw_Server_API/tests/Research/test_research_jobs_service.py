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
