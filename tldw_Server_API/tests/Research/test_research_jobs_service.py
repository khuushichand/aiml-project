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
