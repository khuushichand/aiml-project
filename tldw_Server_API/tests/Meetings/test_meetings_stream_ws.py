from __future__ import annotations

import pytest


pytestmark = pytest.mark.unit


def _create_session(meetings_api_client) -> str:
    resp = meetings_api_client.post(
        "/api/v1/meetings/sessions",
        json={"title": "WS Session", "meeting_type": "standup"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_ws_stream_emits_snapshot_and_ping_pong(meetings_api_client):
    session_id = _create_session(meetings_api_client)

    with meetings_api_client.websocket_connect(f"/api/v1/meetings/sessions/{session_id}/stream") as websocket:
        snapshot = websocket.receive_json()
        assert snapshot["type"] == "session.status"
        assert snapshot["session_id"] == session_id

        websocket.send_json({"type": "ping"})
        pong = websocket.receive_json()
        assert pong["type"] == "pong"
        assert pong["session_id"] == session_id


def test_ws_stream_persists_final_events_only(meetings_api_client):
    session_id = _create_session(meetings_api_client)

    with meetings_api_client.websocket_connect(f"/api/v1/meetings/sessions/{session_id}/stream") as websocket:
        websocket.receive_json()  # snapshot

        websocket.send_json({"type": "transcript.partial", "text": "hello world"})
        partial = websocket.receive_json()
        assert partial["type"] == "transcript.partial"

        websocket.send_json({"type": "transcript.final", "text": "hello world"})
        final = websocket.receive_json()
        assert final["type"] == "transcript.final"

    events_resp = meetings_api_client.get(f"/api/v1/meetings/sessions/{session_id}/events")
    assert events_resp.status_code == 200
    body = events_resp.text
    assert "transcript.final" in body
    assert "transcript.partial" not in body
