from __future__ import annotations

import hashlib
import hmac
import time
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.endpoints import slack as slack_endpoint
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


class _FakeJobManager:
    def __init__(self) -> None:
        self._next_id = 1
        self._jobs: dict[int, dict] = {}

    def create_job(
        self,
        *,
        domain: str,
        queue: str,
        job_type: str,
        payload: dict,
        owner_user_id: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        job_id = self._next_id
        self._next_id += 1
        job = {
            "id": job_id,
            "status": "queued",
            "domain": domain,
            "queue": queue,
            "job_type": job_type,
            "payload": dict(payload),
            "owner_user_id": owner_user_id,
            "request_id": request_id,
        }
        self._jobs[job_id] = job
        return dict(job)

    def get_job(self, job_id: int) -> dict | None:
        job = self._jobs.get(int(job_id))
        return dict(job) if job else None


def _sign(secret: str, timestamp: int, body: bytes) -> str:
    base = f"v0:{timestamp}:".encode("utf-8") + body
    digest = hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return f"v0={digest}"


@pytest.fixture()
def slack_policy_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, _FakeJobManager]:
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-signing-secret")
    monkeypatch.setenv("SLACK_REPLAY_WINDOW_SECONDS", "300")
    monkeypatch.setenv("SLACK_INGRESS_RATE_LIMIT_PER_MINUTE", "1000")
    slack_endpoint._reset_slack_state_for_tests()

    jm = _FakeJobManager()
    monkeypatch.setattr(slack_endpoint, "_get_job_manager", lambda: jm)

    app = FastAPI()
    app.include_router(slack_endpoint.router, prefix="/api/v1")
    app.dependency_overrides[get_request_user] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[get_auth_principal] = lambda: AuthPrincipal(
        kind="user",
        user_id=1,
        roles=["admin"],
        is_admin=True,
    )
    return TestClient(app), jm


def _post_command(
    client: TestClient,
    *,
    team_id: str,
    user_id: str,
    text: str,
    trigger_id: str,
    channel_id: str = "C1",
):
    form = urlencode(
        {
            "team_id": team_id,
            "user_id": user_id,
            "channel_id": channel_id,
            "command": "/tldw",
            "text": text,
            "trigger_id": trigger_id,
        }
    )
    body = form.encode("utf-8")
    ts = int(time.time())
    headers = {
        "x-slack-request-timestamp": str(ts),
        "x-slack-signature": _sign("test-signing-secret", ts, body),
        "content-type": "application/x-www-form-urlencoded",
    }
    return client.post("/api/v1/slack/commands", data=body, headers=headers)


def test_slack_admin_policy_roundtrip(slack_policy_client: tuple[TestClient, _FakeJobManager]) -> None:
    client, _ = slack_policy_client

    baseline = client.get("/api/v1/slack/admin/policy", params={"team_id": "T1"})
    assert baseline.status_code == 200
    assert "ask" in baseline.json()["policy"]["allowed_commands"]

    update = client.put(
        "/api/v1/slack/admin/policy",
        json={
            "team_id": "T1",
            "allowed_commands": ["help", "status"],
            "strict_user_mapping": True,
            "user_mappings": {"U1": "local-1"},
            "status_scope": "workspace_and_user",
            "default_response_mode": "thread",
        },
    )
    assert update.status_code == 200
    policy = update.json()["policy"]
    assert policy["allowed_commands"] == ["help", "status"]
    assert policy["strict_user_mapping"] is True
    assert policy["status_scope"] == "workspace_and_user"

    fetched = client.get("/api/v1/slack/admin/policy", params={"team_id": "T1"})
    assert fetched.status_code == 200
    assert fetched.json()["policy"]["default_response_mode"] == "thread"


def test_slack_admin_policy_requires_admin_role(slack_policy_client: tuple[TestClient, _FakeJobManager]) -> None:
    client, _ = slack_policy_client
    original_override = client.app.dependency_overrides[get_auth_principal]
    client.app.dependency_overrides[get_auth_principal] = lambda: AuthPrincipal(
        kind="user",
        user_id=2,
        roles=["member"],
        is_admin=False,
    )

    try:
        get_resp = client.get("/api/v1/slack/admin/policy", params={"team_id": "T1"})
        put_resp = client.put("/api/v1/slack/admin/policy", json={"team_id": "T1", "allowed_commands": ["help"]})
    finally:
        client.app.dependency_overrides[get_auth_principal] = original_override

    assert get_resp.status_code == 403
    assert put_resp.status_code == 403


def test_slack_policy_blocks_unknown_mapping_and_disallowed_command(
    slack_policy_client: tuple[TestClient, _FakeJobManager],
) -> None:
    client, _ = slack_policy_client

    put_strict = client.put(
        "/api/v1/slack/admin/policy",
        json={
            "team_id": "T1",
            "strict_user_mapping": True,
            "allowed_commands": ["ask"],
        },
    )
    assert put_strict.status_code == 200

    unknown_mapping = _post_command(
        client,
        team_id="T1",
        user_id="U1",
        text="ask hello",
        trigger_id="strict-1",
    )
    assert unknown_mapping.status_code == 403
    assert unknown_mapping.json()["error"] == "unknown_user_mapping"

    put_restrict = client.put(
        "/api/v1/slack/admin/policy",
        json={
            "team_id": "T1",
            "strict_user_mapping": True,
            "user_mappings": {"U1": "local-1"},
            "allowed_commands": ["help"],
        },
    )
    assert put_restrict.status_code == 200

    blocked_command = _post_command(
        client,
        team_id="T1",
        user_id="U1",
        text="ask still blocked",
        trigger_id="strict-2",
    )
    assert blocked_command.status_code == 403
    assert blocked_command.json()["error"] == "command_blocked_by_policy"


def test_slack_status_is_workspace_scoped(slack_policy_client: tuple[TestClient, _FakeJobManager]) -> None:
    client, _ = slack_policy_client

    queued = _post_command(
        client,
        team_id="T1",
        user_id="U1",
        text="ask queued",
        trigger_id="scope-1",
    )
    assert queued.status_code == 200
    job_id = queued.json()["job_id"]

    wrong_workspace = _post_command(
        client,
        team_id="T2",
        user_id="U1",
        text=f"status {job_id}",
        trigger_id="scope-2",
    )
    assert wrong_workspace.status_code == 404
    assert wrong_workspace.json()["error"] == "job_not_found"


def test_slack_status_can_be_scoped_to_workspace_and_user(
    slack_policy_client: tuple[TestClient, _FakeJobManager],
) -> None:
    client, _ = slack_policy_client

    set_scope = client.put(
        "/api/v1/slack/admin/policy",
        json={"team_id": "T1", "status_scope": "workspace_and_user"},
    )
    assert set_scope.status_code == 200

    queued = _post_command(
        client,
        team_id="T1",
        user_id="U1",
        text="ask queued",
        trigger_id="owner-1",
    )
    assert queued.status_code == 200
    job_id = queued.json()["job_id"]

    wrong_user = _post_command(
        client,
        team_id="T1",
        user_id="U2",
        text=f"status {job_id}",
        trigger_id="owner-2",
    )
    assert wrong_user.status_code == 404

    owner = _post_command(
        client,
        team_id="T1",
        user_id="U1",
        text=f"status {job_id}",
        trigger_id="owner-3",
    )
    assert owner.status_code == 200
    assert owner.json()["job"]["id"] == job_id


def test_slack_policy_user_quota_enforced(slack_policy_client: tuple[TestClient, _FakeJobManager]) -> None:
    client, _ = slack_policy_client

    put_policy = client.put(
        "/api/v1/slack/admin/policy",
        json={
            "team_id": "T1",
            "workspace_quota_per_minute": 100,
            "user_quota_per_minute": 1,
        },
    )
    assert put_policy.status_code == 200

    first = _post_command(
        client,
        team_id="T1",
        user_id="U1",
        text="help",
        trigger_id="quota-1",
    )
    second = _post_command(
        client,
        team_id="T1",
        user_id="U1",
        text="help",
        trigger_id="quota-2",
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"] == "user_quota_exceeded"


def test_slack_signature_failure_emits_metric(
    slack_policy_client: tuple[TestClient, _FakeJobManager],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = slack_policy_client
    calls: list[tuple[str, dict]] = []

    def _capture(name: str, labels=None, value=1):
        calls.append((name, dict(labels or {})))

    monkeypatch.setattr(slack_endpoint, "log_counter", _capture)

    body = b'{"type":"url_verification","challenge":"abc"}'
    ts = int(time.time())
    headers = {
        "x-slack-request-timestamp": str(ts),
        "x-slack-signature": "v0=bad",
        "content-type": "application/json",
    }
    response = client.post("/api/v1/slack/events", data=body, headers=headers)
    assert response.status_code == 401
    assert any(name == "slack_signature_failures_total" for name, _ in calls)
