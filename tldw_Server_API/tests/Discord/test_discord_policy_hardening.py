from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints import discord as discord_endpoint
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


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


def _make_test_signer() -> tuple[Ed25519PrivateKey, str]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private_key, public_key.hex()


def _sign(private_key: Ed25519PrivateKey, timestamp: int, body: bytes) -> str:
    return private_key.sign(str(timestamp).encode("utf-8") + body).hex()


@pytest.fixture()
def discord_policy_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Ed25519PrivateKey, _FakeJobManager]:
    signer, public_key_hex = _make_test_signer()
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", public_key_hex)
    monkeypatch.setenv("DISCORD_REPLAY_WINDOW_SECONDS", "300")
    monkeypatch.setenv("DISCORD_INGRESS_RATE_LIMIT_PER_MINUTE", "1000")
    discord_endpoint._reset_discord_state_for_tests()

    jm = _FakeJobManager()
    monkeypatch.setattr(discord_endpoint, "_get_job_manager", lambda: jm)

    app = FastAPI()
    app.include_router(discord_endpoint.router, prefix="/api/v1")
    app.dependency_overrides[get_request_user] = lambda: SimpleNamespace(id=1)
    return TestClient(app), signer, jm


def _post_interaction(
    client: TestClient,
    signer: Ed25519PrivateKey,
    *,
    interaction_id: str,
    guild_id: str,
    user_id: str,
    command_name: str,
    command_input: str = "",
) -> TestClient:
    payload = {
        "type": 2,
        "id": interaction_id,
        "application_id": "app-1",
        "guild_id": guild_id,
        "channel_id": "channel-1",
        "member": {"user": {"id": user_id}},
        "data": {
            "name": "tldw",
            "options": [{"name": command_name, "value": command_input}],
        },
    }
    body = json.dumps(payload).encode("utf-8")
    ts = int(time.time())
    headers = {
        "x-signature-timestamp": str(ts),
        "x-signature-ed25519": _sign(signer, ts, body),
        "content-type": "application/json",
    }
    return client.post("/api/v1/discord/interactions", data=body, headers=headers)


def test_discord_admin_policy_roundtrip(discord_policy_client: tuple[TestClient, Ed25519PrivateKey, _FakeJobManager]) -> None:
    client, _, _ = discord_policy_client

    baseline = client.get("/api/v1/discord/admin/policy", params={"guild_id": "G1"})
    assert baseline.status_code == 200
    assert "ask" in baseline.json()["policy"]["allowed_commands"]

    update = client.put(
        "/api/v1/discord/admin/policy",
        json={
            "guild_id": "G1",
            "allowed_commands": ["help", "status"],
            "strict_user_mapping": True,
            "user_mappings": {"U1": "local-1"},
            "status_scope": "guild_and_user",
            "default_response_mode": "channel",
        },
    )
    assert update.status_code == 200
    policy = update.json()["policy"]
    assert policy["allowed_commands"] == ["help", "status"]
    assert policy["strict_user_mapping"] is True
    assert policy["status_scope"] == "guild_and_user"


def test_discord_policy_blocks_unknown_mapping_and_command(
    discord_policy_client: tuple[TestClient, Ed25519PrivateKey, _FakeJobManager],
) -> None:
    client, signer, _ = discord_policy_client

    strict = client.put(
        "/api/v1/discord/admin/policy",
        json={"guild_id": "G1", "strict_user_mapping": True, "allowed_commands": ["ask"]},
    )
    assert strict.status_code == 200

    unknown_mapping = _post_interaction(
        client,
        signer,
        interaction_id="strict-1",
        guild_id="G1",
        user_id="U1",
        command_name="ask",
        command_input="hello",
    )
    assert unknown_mapping.status_code == 403
    assert unknown_mapping.json()["error"] == "unknown_user_mapping"

    restricted = client.put(
        "/api/v1/discord/admin/policy",
        json={
            "guild_id": "G1",
            "strict_user_mapping": True,
            "user_mappings": {"U1": "local-1"},
            "allowed_commands": ["help"],
        },
    )
    assert restricted.status_code == 200

    blocked = _post_interaction(
        client,
        signer,
        interaction_id="strict-2",
        guild_id="G1",
        user_id="U1",
        command_name="ask",
        command_input="still blocked",
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"] == "command_blocked_by_policy"


def test_discord_status_is_guild_scoped(discord_policy_client: tuple[TestClient, Ed25519PrivateKey, _FakeJobManager]) -> None:
    client, signer, _ = discord_policy_client

    queued = _post_interaction(
        client,
        signer,
        interaction_id="scope-1",
        guild_id="G1",
        user_id="U1",
        command_name="ask",
        command_input="queue this",
    )
    assert queued.status_code == 200
    job_id = queued.json()["job_id"]

    wrong_guild = _post_interaction(
        client,
        signer,
        interaction_id="scope-2",
        guild_id="G2",
        user_id="U1",
        command_name="status",
        command_input=str(job_id),
    )
    assert wrong_guild.status_code == 404
    assert wrong_guild.json()["error"] == "job_not_found"


def test_discord_status_can_be_scoped_to_guild_and_user(
    discord_policy_client: tuple[TestClient, Ed25519PrivateKey, _FakeJobManager],
) -> None:
    client, signer, _ = discord_policy_client

    set_scope = client.put(
        "/api/v1/discord/admin/policy",
        json={"guild_id": "G1", "status_scope": "guild_and_user"},
    )
    assert set_scope.status_code == 200

    queued = _post_interaction(
        client,
        signer,
        interaction_id="owner-1",
        guild_id="G1",
        user_id="U1",
        command_name="ask",
        command_input="queue this",
    )
    assert queued.status_code == 200
    job_id = queued.json()["job_id"]

    wrong_user = _post_interaction(
        client,
        signer,
        interaction_id="owner-2",
        guild_id="G1",
        user_id="U2",
        command_name="status",
        command_input=str(job_id),
    )
    assert wrong_user.status_code == 404

    owner = _post_interaction(
        client,
        signer,
        interaction_id="owner-3",
        guild_id="G1",
        user_id="U1",
        command_name="status",
        command_input=str(job_id),
    )
    assert owner.status_code == 200
    assert owner.json()["job"]["id"] == job_id


def test_discord_policy_user_quota_enforced(discord_policy_client: tuple[TestClient, Ed25519PrivateKey, _FakeJobManager]) -> None:
    client, signer, _ = discord_policy_client

    put_policy = client.put(
        "/api/v1/discord/admin/policy",
        json={
            "guild_id": "G1",
            "guild_quota_per_minute": 100,
            "user_quota_per_minute": 1,
        },
    )
    assert put_policy.status_code == 200

    first = _post_interaction(
        client,
        signer,
        interaction_id="quota-1",
        guild_id="G1",
        user_id="U1",
        command_name="help",
        command_input="",
    )
    second = _post_interaction(
        client,
        signer,
        interaction_id="quota-2",
        guild_id="G1",
        user_id="U1",
        command_name="help",
        command_input="",
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"] == "user_quota_exceeded"


def test_discord_signature_failure_emits_metric(
    discord_policy_client: tuple[TestClient, Ed25519PrivateKey, _FakeJobManager],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _, _ = discord_policy_client
    calls: list[tuple[str, dict]] = []

    def _capture(name: str, labels=None, value=1):
        calls.append((name, dict(labels or {})))

    monkeypatch.setattr(discord_endpoint, "log_counter", _capture)

    payload = {"type": 1}
    body = json.dumps(payload).encode("utf-8")
    ts = int(time.time())
    headers = {
        "x-signature-timestamp": str(ts),
        "x-signature-ed25519": "deadbeef",
        "content-type": "application/json",
    }
    response = client.post("/api/v1/discord/interactions", data=body, headers=headers)
    assert response.status_code == 401
    assert any(name == "discord_signature_failures_total" for name, _ in calls)
