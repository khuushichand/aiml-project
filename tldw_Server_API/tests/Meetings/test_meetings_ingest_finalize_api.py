from __future__ import annotations

import pytest


pytestmark = pytest.mark.unit


def _create_session(meetings_api_client) -> str:
    resp = meetings_api_client.post(
        "/api/v1/meetings/sessions",
        json={"title": "Finalize Session", "meeting_type": "standup"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_finalize_session_generates_summary_and_actions(meetings_api_client):
    session_id = _create_session(meetings_api_client)
    transcript = (
        "Team discussed blockers. TODO: Alice will update the API docs. "
        "TODO: Bob will validate deployment checklist."
    )

    commit_resp = meetings_api_client.post(
        f"/api/v1/meetings/sessions/{session_id}/commit",
        json={"transcript_text": transcript},
    )
    assert commit_resp.status_code == 200

    body = commit_resp.json()
    artifacts_by_kind = {artifact["kind"]: artifact for artifact in body["artifacts"]}
    assert "summary" in artifacts_by_kind
    assert "action_items" in artifacts_by_kind
    assert "decisions" in artifacts_by_kind
    assert "speaker_stats" in artifacts_by_kind
    assert artifacts_by_kind["action_items"]["payload_json"]["items"] == [
        "Alice will update the API docs",
        "Bob will validate deployment checklist",
    ]
    assert artifacts_by_kind["decisions"]["payload_json"]["items"] == []
