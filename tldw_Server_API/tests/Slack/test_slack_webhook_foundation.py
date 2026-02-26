from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints import slack as slack_endpoint


def _sign(secret: str, timestamp: int, body: bytes) -> str:
    base = f"v0:{timestamp}:".encode("utf-8") + body
    digest = hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return f"v0={digest}"


@pytest.fixture()
def slack_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-signing-secret")
    monkeypatch.setenv("SLACK_REPLAY_WINDOW_SECONDS", "300")
    monkeypatch.setenv("SLACK_INGRESS_RATE_LIMIT_PER_MINUTE", "1000")
    slack_endpoint._reset_slack_state_for_tests()

    app = FastAPI()
    app.include_router(slack_endpoint.router, prefix="/api/v1")
    return TestClient(app)


def test_slack_events_url_verification_success(slack_client: TestClient) -> None:
    payload = {"type": "url_verification", "challenge": "abc123"}
    body = json.dumps(payload).encode("utf-8")
    ts = int(time.time())
    headers = {
        "x-slack-request-timestamp": str(ts),
        "x-slack-signature": _sign("test-signing-secret", ts, body),
        "content-type": "application/json",
    }

    response = slack_client.post("/api/v1/slack/events", data=body, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"challenge": "abc123"}


def test_slack_events_reject_invalid_signature(slack_client: TestClient) -> None:
    payload = {"type": "url_verification", "challenge": "abc123"}
    body = json.dumps(payload).encode("utf-8")
    ts = int(time.time())
    headers = {
        "x-slack-request-timestamp": str(ts),
        "x-slack-signature": "v0=deadbeef",
        "content-type": "application/json",
    }

    response = slack_client.post("/api/v1/slack/events", data=body, headers=headers)
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_signature"


def test_slack_events_reject_stale_timestamp(slack_client: TestClient) -> None:
    payload = {"type": "url_verification", "challenge": "abc123"}
    body = json.dumps(payload).encode("utf-8")
    ts = int(time.time()) - 301
    headers = {
        "x-slack-request-timestamp": str(ts),
        "x-slack-signature": _sign("test-signing-secret", ts, body),
        "content-type": "application/json",
    }

    response = slack_client.post("/api/v1/slack/events", data=body, headers=headers)
    assert response.status_code == 401
    assert response.json()["error"] == "stale_request"


def test_slack_events_dedupes_event_callback(slack_client: TestClient) -> None:
    payload = {
        "type": "event_callback",
        "event_id": "Ev123",
        "event": {"type": "app_mention", "text": "hello"},
    }
    body = json.dumps(payload).encode("utf-8")
    ts = int(time.time())
    headers = {
        "x-slack-request-timestamp": str(ts),
        "x-slack-signature": _sign("test-signing-secret", ts, body),
        "content-type": "application/json",
    }

    first = slack_client.post("/api/v1/slack/events", data=body, headers=headers)
    second = slack_client.post("/api/v1/slack/events", data=body, headers=headers)

    assert first.status_code == 200
    assert first.json()["status"] == "accepted"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"


def test_slack_commands_ack_and_dedupe(slack_client: TestClient) -> None:
    form = urlencode(
        {
            "team_id": "T1",
            "user_id": "U1",
            "command": "/tldw",
            "text": "help",
            "trigger_id": "1337.42",
        }
    )
    body = form.encode("utf-8")
    ts = int(time.time())
    headers = {
        "x-slack-request-timestamp": str(ts),
        "x-slack-signature": _sign("test-signing-secret", ts, body),
        "content-type": "application/x-www-form-urlencoded",
    }

    first = slack_client.post("/api/v1/slack/commands", data=body, headers=headers)
    second = slack_client.post(
        "/api/v1/slack/commands",
        data=body,
        headers={**headers, "x-slack-retry-num": "1"},
    )

    assert first.status_code == 200
    assert first.json()["status"] == "accepted"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"

