from __future__ import annotations

import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints import discord as discord_endpoint


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
def discord_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Ed25519PrivateKey]:
    private_key, public_key_hex = _make_test_signer()
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", public_key_hex)
    monkeypatch.setenv("DISCORD_REPLAY_WINDOW_SECONDS", "300")
    monkeypatch.setenv("DISCORD_INGRESS_RATE_LIMIT_PER_MINUTE", "1000")
    discord_endpoint._reset_discord_state_for_tests()

    app = FastAPI()
    app.include_router(discord_endpoint.router, prefix="/api/v1")
    return TestClient(app), private_key


def test_discord_ping_success(discord_client: tuple[TestClient, Ed25519PrivateKey]) -> None:
    client, signer = discord_client
    payload = {"type": 1}
    body = json.dumps(payload).encode("utf-8")
    ts = int(time.time())
    headers = {
        "x-signature-timestamp": str(ts),
        "x-signature-ed25519": _sign(signer, ts, body),
        "content-type": "application/json",
    }

    response = client.post("/api/v1/discord/interactions", data=body, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"type": 1}


def test_discord_rejects_invalid_signature(discord_client: tuple[TestClient, Ed25519PrivateKey]) -> None:
    client, signer = discord_client
    payload = {"type": 1}
    body = json.dumps(payload).encode("utf-8")
    ts = int(time.time())
    bad_signature = _sign(signer, ts, body)[:-2] + "ff"
    headers = {
        "x-signature-timestamp": str(ts),
        "x-signature-ed25519": bad_signature,
        "content-type": "application/json",
    }

    response = client.post("/api/v1/discord/interactions", data=body, headers=headers)
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_signature"


def test_discord_rejects_stale_timestamp(discord_client: tuple[TestClient, Ed25519PrivateKey]) -> None:
    client, signer = discord_client
    payload = {"type": 1}
    body = json.dumps(payload).encode("utf-8")
    ts = int(time.time()) - 301
    headers = {
        "x-signature-timestamp": str(ts),
        "x-signature-ed25519": _sign(signer, ts, body),
        "content-type": "application/json",
    }

    response = client.post("/api/v1/discord/interactions", data=body, headers=headers)
    assert response.status_code == 401
    assert response.json()["error"] == "stale_request"


def test_discord_dedupes_interaction(discord_client: tuple[TestClient, Ed25519PrivateKey]) -> None:
    client, signer = discord_client
    payload = {
        "type": 2,
        "id": "1234",
        "application_id": "app-1",
        "guild_id": "guild-1",
    }
    body = json.dumps(payload).encode("utf-8")
    ts = int(time.time())
    headers = {
        "x-signature-timestamp": str(ts),
        "x-signature-ed25519": _sign(signer, ts, body),
        "content-type": "application/json",
    }

    first = client.post("/api/v1/discord/interactions", data=body, headers=headers)
    second = client.post("/api/v1/discord/interactions", data=body, headers=headers)

    assert first.status_code == 200
    assert first.json()["status"] == "accepted"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
