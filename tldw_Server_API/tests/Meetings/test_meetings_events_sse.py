from __future__ import annotations

import pytest


pytestmark = pytest.mark.unit


def _create_session(meetings_api_client) -> str:
    resp = meetings_api_client.post(
        "/api/v1/meetings/sessions",
        json={"title": "SSE Session", "meeting_type": "standup"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_sse_events_streams_structured_frames(meetings_api_client):
    session_id = _create_session(meetings_api_client)
    resp = meetings_api_client.get(f"/api/v1/meetings/sessions/{session_id}/events")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    assert "event:" in resp.text
    assert "\"session_id\"" in resp.text
