import pytest


pytestmark = pytest.mark.unit


def test_write_json_artifact_records_manifest(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore

    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Test query",
        source_policy="balanced",
        autonomy_mode="autonomous",
        limits_json={},
    )
    store = ResearchArtifactStore(base_dir=tmp_path / "outputs", db=db)

    artifact = store.write_json(
        owner_user_id=1,
        session_id=session.id,
        artifact_name="plan.json",
        payload={"focus_areas": ["history", "market structure"]},
        phase="drafting_plan",
        job_id="123",
    )

    assert artifact.byte_size > 0
    manifest = db.list_artifacts(session.id)
    assert manifest[0].artifact_name == "plan.json"
    assert (tmp_path / "outputs" / "research" / session.id / "plan.json").exists()
