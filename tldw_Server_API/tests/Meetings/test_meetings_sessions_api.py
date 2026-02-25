from __future__ import annotations

import pytest


pytestmark = pytest.mark.unit


def test_create_session_returns_scheduled(meetings_api_client):
    resp = meetings_api_client.post(
        "/api/v1/meetings/sessions",
        json={"title": "Weekly", "meeting_type": "standup"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "scheduled"
    assert body["title"] == "Weekly"


def test_list_sessions_includes_created_session(meetings_api_client):
    created = meetings_api_client.post(
        "/api/v1/meetings/sessions",
        json={"title": "Roadmap", "meeting_type": "planning"},
    )
    assert created.status_code == 201
    session_id = created.json()["id"]

    listed = meetings_api_client.get("/api/v1/meetings/sessions")
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()}
    assert session_id in ids


def test_session_transition_rejects_invalid_edge(meetings_api_client):
    created = meetings_api_client.post(
        "/api/v1/meetings/sessions",
        json={"title": "Sync", "meeting_type": "sync"},
    )
    assert created.status_code == 201
    session_id = created.json()["id"]

    invalid = meetings_api_client.post(
        f"/api/v1/meetings/sessions/{session_id}/status",
        json={"status": "completed"},
    )
    assert invalid.status_code == 400
