"""Regression tests for HTTP-layer security guards."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.MCP_unified.security import ip_filter
from tldw_Server_API.app.core.MCP_unified.security.request_guards import enforce_http_security


def _build_guarded_app() -> FastAPI:
    app = FastAPI()

    @app.post("/guarded")
    async def guarded_endpoint(
        _guard: None = Depends(enforce_http_security),  # pragma: no cover - dependency handles logic
    ):
        return {"status": "ok"}

    return app


def test_enforce_http_security_rejects_large_payload(monkeypatch):
    from types import SimpleNamespace

    cfg = SimpleNamespace(
        allowed_client_ips=[],
        blocked_client_ips=[],
        trust_x_forwarded_for=False,
        trusted_proxy_depth=0,
        trusted_proxy_ips=[],
        http_max_body_bytes=32,
        client_cert_required=False,
        client_cert_header=None,
        client_cert_header_value=None,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.MCP_unified.security.request_guards.get_config",
        lambda: cfg,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.MCP_unified.security.ip_filter.get_config",
        lambda: cfg,
    )
    try:
        ip_filter.get_ip_access_controller.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    client = TestClient(_build_guarded_app())
    try:
        # Small payload passes
        r_small = client.post("/guarded", json={"msg": "ok"})
        assert r_small.status_code == 200
        # Oversized payload rejected with 413
        big_value = "a" * 64
        r_big = client.post("/guarded", json={"msg": big_value})
        assert r_big.status_code == 413
    finally:
        client.close()


def test_enforce_http_security_requires_client_certificate(monkeypatch):
    from types import SimpleNamespace

    cfg = SimpleNamespace(
        allowed_client_ips=[],
        blocked_client_ips=[],
        trust_x_forwarded_for=False,
        trusted_proxy_depth=0,
        trusted_proxy_ips=[],
        http_max_body_bytes=524288,
        client_cert_required=True,
        client_cert_header="x-ssl-client-verify",
        # Stricter policy requires explicit expected value
        client_cert_header_value="success",
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.MCP_unified.security.request_guards.get_config",
        lambda: cfg,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.MCP_unified.security.ip_filter.get_config",
        lambda: cfg,
    )
    try:
        ip_filter.get_ip_access_controller.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    monkeypatch.setattr(
        ip_filter.IPAccessController,
        "_is_trusted_proxy",
        lambda self, ip: ip in {"testclient", "127.0.0.1"},
    )

    client = TestClient(_build_guarded_app())
    try:
        # Missing certificate header → 403
        r_missing = client.post("/guarded", json={"msg": "hello"})
        assert r_missing.status_code == 403
        # Valid header (default SUCCESS sentinel) → 200
        r_valid = client.post(
            "/guarded",
            json={"msg": "hello"},
            headers={"x-ssl-client-verify": "SUCCESS"},
        )
        assert r_valid.status_code == 200
        # Raw PEM payloads are rejected under strict policy (value must match expected)
        r_pem = client.post(
            "/guarded",
            json={"msg": "pem"},
            headers={"x-ssl-client-verify": "-----BEGIN CERTIFICATE-----\nMIIB..."},
        )
        assert r_pem.status_code == 403
    finally:
        client.close()


def test_ip_filter_ignores_untrusted_forwarded_header():
    controller = ip_filter.IPAccessController(
        allowed=[],
        blocked=[],
        trust_x_forwarded_for=True,
        trusted_proxy_depth=0,
        trusted_proxies=[],
    )
    # Public client tries to spoof XFF; remote peer is also public → ignore header
    resolved = controller.resolve_client_ip("198.51.100.10", "203.0.113.5", None)
    assert resolved == "198.51.100.10"


def test_enforce_http_security_rejects_invalid_cert_value(monkeypatch):
    from types import SimpleNamespace

    cfg = SimpleNamespace(
        allowed_client_ips=[],
        blocked_client_ips=[],
        trust_x_forwarded_for=False,
        trusted_proxy_depth=0,
        trusted_proxy_ips=[],
        http_max_body_bytes=524288,
        client_cert_required=True,
        client_cert_header="x-client-cert",
        client_cert_header_value="verified",
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.MCP_unified.security.request_guards.get_config",
        lambda: cfg,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.MCP_unified.security.ip_filter.get_config",
        lambda: cfg,
    )
    try:
        ip_filter.get_ip_access_controller.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass

    # Treat test client as coming via trusted proxy for header acceptance
    monkeypatch.setattr(
        ip_filter.IPAccessController,
        "_is_trusted_proxy",
        lambda self, ip: ip in {"testclient", "127.0.0.1"},
    )
    client = TestClient(_build_guarded_app())
    try:
        r_missing = client.post("/guarded", json={"msg": "bad"})
        assert r_missing.status_code == 403
        r_wrong = client.post(
            "/guarded",
            json={"msg": "bad"},
            headers={"x-client-cert": "denied"},
        )
        assert r_wrong.status_code == 403
        r_ok = client.post(
            "/guarded",
            json={"msg": "good"},
            headers={"x-client-cert": "verified"},
        )
        assert r_ok.status_code == 200
    finally:
        client.close()


def test_enforce_http_security_enforces_ip_allowlist(monkeypatch):
    from types import SimpleNamespace

    cfg = SimpleNamespace(
        allowed_client_ips=["10.0.0.1"],
        blocked_client_ips=[],
        trust_x_forwarded_for=True,
        trusted_proxy_depth=0,
        trusted_proxy_ips=["127.0.0.1/32"],
        http_max_body_bytes=524288,
        client_cert_required=False,
        client_cert_header=None,
        client_cert_header_value=None,
    )
    monkeypatch.setattr(
        ip_filter.IPAccessController,
        "_is_trusted_proxy",
        lambda self, ip: ip in {"testclient", "127.0.0.1"},
    )

    controller = ip_filter.IPAccessController(
        allowed=cfg.allowed_client_ips,
        blocked=cfg.blocked_client_ips,
        trust_x_forwarded_for=cfg.trust_x_forwarded_for,
        trusted_proxy_depth=cfg.trusted_proxy_depth,
        trusted_proxies=cfg.trusted_proxy_ips,
    )
    resolved = controller.resolve_client_ip("testclient", "10.0.0.1", None)
    assert resolved == "10.0.0.1"
    assert controller.is_allowed(resolved) is True
