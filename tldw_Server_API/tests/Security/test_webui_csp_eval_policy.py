import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Security.webui_csp import WebUICSPMiddleware


def _make_app():


     app = FastAPI()
    app.add_middleware(WebUICSPMiddleware)

    @app.get("/webui/ping")
    async def webui_ping():
        return {"ok": True}

    @app.get("/setup/ping")
    async def setup_ping():
        return {"ok": True}

    return app


def _has(header_val: str, token: str) -> bool:
    return token in (header_val or "")


def _script_src(header_val: str) -> str:
    parts = [p.strip() for p in (header_val or "").split(";")]
    for p in parts:
        if p.startswith("script-src ") or p.startswith("script-src\t") or p.startswith("script-src\n") or p == "script-src":
            return p
    # Fallback: return empty when not found
    return ""


@pytest.mark.parametrize("truthy", ["1", "true", "TRUE", "Yes", "on", "Y"])  # accepted truthy values
def test_webui_csp_no_eval_env_truthy_disables_eval(monkeypatch, truthy):
     monkeypatch.setenv("TLDW_WEBUI_NO_EVAL", truthy)
    # ensure env default doesn't interfere
    for k in ("ENVIRONMENT", "APP_ENV", "ENV"):
        monkeypatch.delenv(k, raising=False)

    app = _make_app()
    client = TestClient(app)
    r = client.get("/webui/ping")
    csp = r.headers.get("Content-Security-Policy", "")
    scr = _script_src(csp)
    assert scr
    assert not _has(scr, "'unsafe-eval'")  # disabled via NO_EVAL truthy
    assert not _has(scr, "'unsafe-inline'")  # /webui disallows inline scripts


@pytest.mark.parametrize("falsy", ["0", "false", "False", "off", "n", "no"])  # common falsy inputs
def test_webui_csp_no_eval_env_falsy_enables_eval(monkeypatch, falsy):
     monkeypatch.setenv("TLDW_WEBUI_NO_EVAL", falsy)
    for k in ("ENVIRONMENT", "APP_ENV", "ENV"):
        monkeypatch.delenv(k, raising=False)

    app = _make_app()
    client = TestClient(app)
    r = client.get("/webui/ping")
    csp = r.headers.get("Content-Security-Policy", "")
    scr = _script_src(csp)
    assert scr
    assert _has(scr, "'unsafe-eval'")  # enabled via NO_EVAL falsy
    assert not _has(scr, "'unsafe-inline'")


def test_webui_csp_default_prod_disables_eval(monkeypatch):


     # Unset NO_EVAL; set prod env
    monkeypatch.delenv("TLDW_WEBUI_NO_EVAL", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    # Clear alternatives to avoid ambiguity
    for k in ("APP_ENV", "ENV"):
        monkeypatch.delenv(k, raising=False)

    app = _make_app()
    client = TestClient(app)
    r = client.get("/webui/ping")
    csp = r.headers.get("Content-Security-Policy", "")
    scr = _script_src(csp)
    assert not _has(scr, "'unsafe-eval'")
    assert not _has(scr, "'unsafe-inline'")


def test_webui_csp_default_dev_enables_eval(monkeypatch):


     # Unset NO_EVAL; set non-prod env
    monkeypatch.delenv("TLDW_WEBUI_NO_EVAL", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    for k in ("APP_ENV", "ENV"):
        monkeypatch.delenv(k, raising=False)

    app = _make_app()
    client = TestClient(app)
    r = client.get("/webui/ping")
    csp = r.headers.get("Content-Security-Policy", "")
    scr = _script_src(csp)
    assert _has(scr, "'unsafe-eval'")
    assert not _has(scr, "'unsafe-inline'")


def test_setup_csp_allows_inline_and_eval(monkeypatch):


     # Regardless of env, /setup should allow both
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("TLDW_WEBUI_NO_EVAL", "1")  # would disable eval for /webui, but /setup stays permissive

    app = _make_app()
    client = TestClient(app)
    r = client.get("/setup/ping")
    csp = r.headers.get("Content-Security-Policy", "")
    assert _has(csp, "'unsafe-inline'")
    assert _has(csp, "'unsafe-eval'")
