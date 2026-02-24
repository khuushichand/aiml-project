from __future__ import annotations

import pytest

from tldw_Server_API.app.core.DB_Management.Meetings_DB import MeetingsDatabase
from tldw_Server_API.app.core.Meetings.artifact_service import MeetingArtifactService


pytestmark = pytest.mark.unit


@pytest.fixture()
def artifact_context(tmp_path):
    db = MeetingsDatabase(db_path=tmp_path / "Media_DB_v2.db", client_id="tester", user_id="1")
    session_id = db.create_session(title="Artifact Session", meeting_type="standup")
    service = MeetingArtifactService(db=db)
    try:
        yield service, session_id
    finally:
        db.close_connection()


def test_create_and_list_artifacts(artifact_context):
    service, session_id = artifact_context
    created = service.create_artifact(
        session_id=session_id,
        kind="summary",
        format="json",
        payload_json={"summary": "All blockers resolved."},
    )
    assert created["session_id"] == session_id
    assert created["kind"] == "summary"

    rows = service.list_artifacts(session_id=session_id)
    assert [row["id"] for row in rows] == [created["id"]]


def test_create_artifact_requires_existing_session(artifact_context):
    service, _session_id = artifact_context
    with pytest.raises(KeyError):
        service.create_artifact(
            session_id="sess_missing",
            kind="summary",
            format="json",
            payload_json={"summary": "none"},
        )


def test_extract_action_items_without_markers_returns_empty_list():
    items = MeetingArtifactService._extract_action_items(
        "Team reviewed architecture and aligned on timeline."
    )
    assert items == []
