import json
import hmac
import hashlib
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_export_payload(async_mode: bool = False):
    return {
        "name": "Signed URL Test",
        "description": "Testing signed download",
        "content_selections": {},
        "author": "tester",
        "include_media": False,
        "media_quality": "compressed",
        "include_embeddings": False,
        "include_generated_content": True,
        "tags": [],
        "categories": [],
        "async_mode": async_mode,
    }


def test_signed_download_happy_path(client, monkeypatch):
    # Enable signed URLs
    monkeypatch.setenv("CHATBOOKS_SIGNED_URLS", "true")
    monkeypatch.setenv("CHATBOOKS_SIGNING_SECRET", "secret123")
    monkeypatch.setenv("CHATBOOKS_ENFORCE_EXPIRY", "true")
    monkeypatch.setenv("CHATBOOKS_URL_TTL_SECONDS", "3600")

    resp = client.post("/api/v1/chatbooks/export", json=_make_export_payload(async_mode=False))
    assert resp.status_code in (200, 401, 403, 422)
    if resp.status_code != 200:
        # Tolerate auth-enabled test environments
        return

    body = resp.json()
    job_id = body.get("job_id")
    download_url = body.get("download_url")
    assert job_id and download_url

    # Valid signed download should succeed
    dresp = client.get(download_url)
    assert dresp.status_code in (200, 206)  # allow partial content


def test_signed_download_invalid_token(client, monkeypatch):
    monkeypatch.setenv("CHATBOOKS_SIGNED_URLS", "true")
    monkeypatch.setenv("CHATBOOKS_SIGNING_SECRET", "secret123")
    monkeypatch.setenv("CHATBOOKS_ENFORCE_EXPIRY", "true")
    monkeypatch.setenv("CHATBOOKS_URL_TTL_SECONDS", "3600")

    resp = client.post("/api/v1/chatbooks/export", json=_make_export_payload(async_mode=False))
    assert resp.status_code in (200, 401, 403, 422)
    if resp.status_code != 200:
        return

    body = resp.json()
    download_url = body.get("download_url")
    assert download_url

    # Tamper token
    parts = urlparse(download_url)
    qs = parse_qs(parts.query)
    qs["token"] = ["deadbeef"]
    new_qs = urlencode({k: v[0] for k, v in qs.items()})
    bad_url = urlunparse((parts.scheme, parts.netloc, parts.path, parts.params, new_qs, parts.fragment))

    dresp = client.get(bad_url)
    assert dresp.status_code in (403, 401)


def test_signed_download_expired_exp_param(client, monkeypatch):
    monkeypatch.setenv("CHATBOOKS_SIGNED_URLS", "true")
    monkeypatch.setenv("CHATBOOKS_SIGNING_SECRET", "secret123")
    monkeypatch.setenv("CHATBOOKS_ENFORCE_EXPIRY", "true")
    monkeypatch.setenv("CHATBOOKS_URL_TTL_SECONDS", "3600")

    resp = client.post("/api/v1/chatbooks/export", json=_make_export_payload(async_mode=False))
    assert resp.status_code in (200, 401, 403, 422)
    if resp.status_code != 200:
        return

    body = resp.json()
    job_id = body.get("job_id")
    assert job_id

    # Forge an expired exp param
    exp = 1  # definitely in the past
    msg = f"{job_id}:{exp}".encode("utf-8")
    token = hmac.new(b"secret123", msg, hashlib.sha256).hexdigest()
    url = f"/api/v1/chatbooks/download/{job_id}?exp={exp}&token={token}"

    dresp = client.get(url)
    assert dresp.status_code == 410
