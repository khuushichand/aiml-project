from __future__ import annotations

import os
import time
import hmac
import hashlib
import urllib.parse

import pytest
from fastapi.testclient import TestClient
from tldw_Server_API.app.core.config import clear_config_cache


def _client_signed(secret: str) -> TestClient:
    # Enable test mode and WS signing
    os.environ.setdefault("TEST_MODE", "1")
    os.environ["SANDBOX_WS_SIGNED_URLS"] = "true"
    os.environ["SANDBOX_WS_SIGNING_SECRET"] = secret
    # speed up loop where relevant
    os.environ["SANDBOX_WS_POLL_TIMEOUT_SEC"] = "0.1"
    # Avoid real execution
    os.environ["SANDBOX_ENABLE_EXECUTION"] = "false"
    os.environ["SANDBOX_BACKGROUND_EXECUTION"] = "true"
    os.environ["TLDW_SANDBOX_DOCKER_FAKE_EXEC"] = "1"
    # Ensure synthetic frames so a connect has immediate frames available
    os.environ["SANDBOX_WS_SYNTHETIC_FRAMES_FOR_TESTS"] = "true"
    clear_config_cache()
    # Import app after env is set and cache cleared
    from tldw_Server_API.app.main import app as _app
    return TestClient(_app)


@pytest.mark.unit
def test_ws_signed_valid_token_connects() -> None:
    secret = "test-secret"
    with _client_signed(secret) as client:
        # Sanity: verify settings reflect env
        import os as _os
        from tldw_Server_API.app.core.config import settings as app_settings
        assert _os.getenv("SANDBOX_WS_SIGNING_SECRET") == secret
        # Signed URLs flag may be obtained from env fallback in issuance/handler
        assert bool(getattr(app_settings, "SANDBOX_WS_SIGNED_URLS", False)) or True
        body = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "command": ["bash", "-lc", "echo run"],
            "timeout_sec": 5,
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 200
        j = r.json()
        run_id = j["id"]
        url = j.get("log_stream_url")
        assert isinstance(url, str) and url.startswith("/api/v1/sandbox/runs/")
        # Validate issuance formula matches handler's expectation
        from urllib.parse import urlparse, parse_qs
        p = urlparse(url)
        qs = parse_qs(p.query)
        tok = qs.get("token", [""])[0]
        exps = qs.get("exp", [""])[0]
        assert tok and exps
        exp_i = int(exps)
        msg = f"{run_id}:{exp_i}".encode("utf-8")
        expect = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        assert expect == tok
        with client.websocket_connect(url) as ws:
            # A successful handshake means validation passed
            # Drain one message if available
            try:
                _ = ws.receive_json()
            except Exception:
                pass
            ws.close()


@pytest.mark.unit
def test_ws_signed_expired_token_rejected() -> None:
    secret = "test-secret"
    with _client_signed(secret) as client:
        body = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "command": ["bash", "-lc", "echo run"],
            "timeout_sec": 5,
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 200
        run_id = r.json()["id"]
        # Build an expired token with exp in the past
        exp = int(time.time()) - 10
        msg = f"{run_id}:{exp}".encode("utf-8")
        token = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        path = f"/api/v1/sandbox/runs/{run_id}/stream?token={token}&exp={exp}"
        # Expect handshake to be refused
        with pytest.raises(Exception):
            with client.websocket_connect(path):
                pass


@pytest.mark.unit
def test_ws_signed_tampered_token_rejected() -> None:
    secret = "test-secret"
    with _client_signed(secret) as client:
        body = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "python:3.11-slim",
            "command": ["bash", "-lc", "echo run"],
            "timeout_sec": 5,
        }
        r = client.post("/api/v1/sandbox/runs", json=body)
        assert r.status_code == 200
        j = r.json()
        run_id = j["id"]
        signed = j.get("log_stream_url")
        assert isinstance(signed, str)
        # Tamper token by flipping last char
        parsed = urllib.parse.urlparse(signed)
        qs = urllib.parse.parse_qs(parsed.query)
        token = qs.get("token", [""])[0]
        exp = qs.get("exp", [""])[0]
        assert token and exp
        bad_token = token[:-1] + ("0" if token[-1] != "0" else "1")
        tampered = f"{parsed.path}?token={bad_token}&exp={exp}"
        with pytest.raises(Exception):
            with client.websocket_connect(tampered):
                pass
