"""Integration tests for chat-loop endpoint basics."""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_chat_loop_start_then_replay_events(test_client, auth_headers) -> None:
    start = test_client.post(
        "/api/v1/chat/loop/start",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers=auth_headers,
    )
    assert start.status_code == 200
    run_id = start.json()["run_id"]
    assert run_id

    replay = test_client.get(
        f"/api/v1/chat/loop/{run_id}/events",
        params={"after_seq": 0},
        headers=auth_headers,
    )
    assert replay.status_code == 200
    payload = replay.json()
    assert payload["run_id"] == run_id
    assert len(payload["events"]) >= 1
    assert payload["events"][0]["event"] == "run_started"
    assert payload["events"][0]["seq"] == 1


@pytest.mark.integration
def test_chat_loop_replay_unknown_run_returns_404(test_client, auth_headers) -> None:
    replay = test_client.get(
        "/api/v1/chat/loop/run_missing/events",
        params={"after_seq": 0},
        headers=auth_headers,
    )
    assert replay.status_code == 404
