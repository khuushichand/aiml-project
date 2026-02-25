from __future__ import annotations

from types import SimpleNamespace

import pytest


pytestmark = pytest.mark.unit


def _create_session(meetings_api_client) -> str:
    resp = meetings_api_client.post(
        "/api/v1/meetings/sessions",
        json={"title": "Integrations Session", "meeting_type": "standup"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_summary_artifact(meetings_api_client, session_id: str) -> str:
    resp = meetings_api_client.post(
        f"/api/v1/meetings/sessions/{session_id}/artifacts",
        json={
            "kind": "summary",
            "format": "json",
            "payload_json": {"text": "Launch scope confirmed."},
            "version": 1,
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_share_to_slack_enqueues_dispatch(meetings_api_client, monkeypatch):
    from tldw_Server_API.app.core.Meetings import integration_service as integration_mod

    monkeypatch.setattr(
        integration_mod,
        "evaluate_url_policy",
        lambda *_args, **_kwargs: SimpleNamespace(allowed=True, reason=None),
        raising=True,
    )

    session_id = _create_session(meetings_api_client)
    artifact_id = _create_summary_artifact(meetings_api_client, session_id=session_id)

    resp = meetings_api_client.post(
        f"/api/v1/meetings/sessions/{session_id}/share/slack",
        json={"webhook_url": "https://hooks.slack.test/services/T000/B000/XXXX", "artifact_ids": [artifact_id]},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["session_id"] == session_id
    assert body["integration_type"] == "slack"
    assert body["status"] == "queued"
    assert int(body["dispatch_id"]) > 0


def test_share_to_webhook_enqueues_dispatch(meetings_api_client, monkeypatch):
    from tldw_Server_API.app.core.Meetings import integration_service as integration_mod

    monkeypatch.setattr(
        integration_mod,
        "evaluate_url_policy",
        lambda *_args, **_kwargs: SimpleNamespace(allowed=True, reason=None),
        raising=True,
    )

    session_id = _create_session(meetings_api_client)

    resp = meetings_api_client.post(
        f"/api/v1/meetings/sessions/{session_id}/share/webhook",
        json={"webhook_url": "https://webhooks.example.test/meetings"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["session_id"] == session_id
    assert body["integration_type"] == "webhook"
    assert body["status"] == "queued"
    assert int(body["dispatch_id"]) > 0


def test_share_rejects_egress_denied_destination(meetings_api_client, monkeypatch):
    from tldw_Server_API.app.core.Meetings import integration_service as integration_mod

    monkeypatch.setattr(
        integration_mod,
        "evaluate_url_policy",
        lambda *_args, **_kwargs: SimpleNamespace(allowed=False, reason="Host not in allowlist"),
        raising=True,
    )

    session_id = _create_session(meetings_api_client)
    resp = meetings_api_client.post(
        f"/api/v1/meetings/sessions/{session_id}/share/webhook",
        json={"webhook_url": "https://blocked.example.test/meetings"},
    )
    assert resp.status_code == 403

