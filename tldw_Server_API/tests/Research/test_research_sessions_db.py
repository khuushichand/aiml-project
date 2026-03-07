import pytest


pytestmark = pytest.mark.unit


def test_create_session_and_checkpoint_round_trip(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB

    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="7",
        query="Compare local and external evidence on quantum networking",
        source_policy="balanced",
        autonomy_mode="checkpointed",
        limits_json={"max_searches": 25},
    )

    assert session.phase == "drafting_plan"
    stored = db.get_session(session.id)
    assert stored is not None
    assert stored.query.startswith("Compare")

    checkpoint = db.create_checkpoint(
        session_id=session.id,
        checkpoint_type="plan_review",
        proposed_payload={"focus_areas": ["background", "primary sources"]},
    )
    resolved = db.resolve_checkpoint(
        checkpoint.id,
        resolution="patched",
        user_patch_payload={"focus_areas": ["background", "contradictions"]},
    )

    assert resolved.status == "resolved"
    assert resolved.user_patch_payload["focus_areas"][1] == "contradictions"
