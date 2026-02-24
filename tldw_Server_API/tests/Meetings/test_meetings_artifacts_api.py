from __future__ import annotations

import pytest


pytestmark = pytest.mark.unit


def _create_session(meetings_api_client) -> str:
    resp = meetings_api_client.post(
        "/api/v1/meetings/sessions",
        json={"title": "Artifact Session", "meeting_type": "standup"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_and_list_artifacts(meetings_api_client):
    session_id = _create_session(meetings_api_client)
    create_resp = meetings_api_client.post(
        f"/api/v1/meetings/sessions/{session_id}/artifacts",
        json={
            "kind": "summary",
            "format": "json",
            "payload_json": {"summary": "Resolved all blockers."},
            "version": 1,
        },
    )
    assert create_resp.status_code == 201
    artifact_id = create_resp.json()["id"]

    list_resp = meetings_api_client.get(f"/api/v1/meetings/sessions/{session_id}/artifacts")
    assert list_resp.status_code == 200
    ids = {row["id"] for row in list_resp.json()}
    assert artifact_id in ids


def test_create_artifact_for_missing_session_returns_404(meetings_api_client):
    create_resp = meetings_api_client.post(
        "/api/v1/meetings/sessions/sess_missing/artifacts",
        json={
            "kind": "summary",
            "format": "json",
            "payload_json": {"summary": "none"},
            "version": 1,
        },
    )
    assert create_resp.status_code == 404
