from fastapi import FastAPI
from fastapi.testclient import TestClient

import tldw_Server_API.app.core.Security.webui_access_guard as guard
from tldw_Server_API.app.core.Security.webui_access_guard import WebUIAccessGuardMiddleware


def _make_app():


    app = FastAPI()
    app.add_middleware(WebUIAccessGuardMiddleware)

    @app.get("/webui/ping")
    async def webui_ping():
        return {"ok": True}

    @app.get("/setup/ping")
    async def setup_ping():
        return {"ok": True}

    return app


def _set_remote_ip(monkeypatch, ip: str):
    monkeypatch.setattr(WebUIAccessGuardMiddleware, "_resolve_client_ip", lambda self, request, proxies: ip)
    monkeypatch.setattr(guard, "_is_loopback", lambda _ip: False)


def test_webui_allowlist_blocks_when_remote_enabled(monkeypatch):


    monkeypatch.setenv("TLDW_WEBUI_ALLOW_REMOTE", "1")
    monkeypatch.setenv("TLDW_WEBUI_ALLOWLIST", "203.0.113.5")
    _set_remote_ip(monkeypatch, "198.51.100.20")

    client = TestClient(_make_app())
    resp = client.get("/webui/ping")
    assert resp.status_code == 403
    assert "allowlist" in resp.text.lower()


def test_webui_allowlist_allows_matching_ip(monkeypatch):


    monkeypatch.setenv("TLDW_WEBUI_ALLOW_REMOTE", "1")
    monkeypatch.setenv("TLDW_WEBUI_ALLOWLIST", "203.0.113.5")
    _set_remote_ip(monkeypatch, "203.0.113.5")

    client = TestClient(_make_app())
    resp = client.get("/webui/ping")
    assert resp.status_code == 200


def test_setup_prefix_guard_blocks_remote(monkeypatch):


    monkeypatch.delenv("TLDW_SETUP_ALLOW_REMOTE", raising=False)
    monkeypatch.delenv("TLDW_SETUP_ALLOWLIST", raising=False)
    _set_remote_ip(monkeypatch, "198.51.100.20")

    client = TestClient(_make_app())
    resp = client.get("/setup/ping")
    assert resp.status_code == 403
