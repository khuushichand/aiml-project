import pytest


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_planning_job_writes_plan_and_opens_checkpoint(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job

    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Test planning",
        source_policy="balanced",
        autonomy_mode="checkpointed",
        limits_json={},
    )

    result = await handle_research_phase_job(
        {
            "id": 5,
            "payload": {
                "session_id": session.id,
                "phase": "drafting_plan",
                "checkpoint_id": None,
                "policy_version": 1,
            },
        },
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
    )

    updated = db.get_session(session.id)
    assert updated is not None
    assert updated.phase == "awaiting_plan_review"
    assert updated.latest_checkpoint_id is not None
    assert result["phase"] == "awaiting_plan_review"
    assert result["artifacts_written"] >= 1
    assert (tmp_path / "outputs" / "research" / session.id / "plan.json").exists()
