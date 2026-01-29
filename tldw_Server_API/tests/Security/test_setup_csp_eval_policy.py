import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Security.setup_csp import SetupCSPMiddleware


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SetupCSPMiddleware)

    @app.get("/setup/ping")
    async def setup_ping():
        return {"ok": True}

    return app


def _script_src(header_val: str) -> str:
    parts = [p.strip() for p in (header_val or "").split(";")]
    for part in parts:
        if part.startswith("script-src"):
            return part
    return ""


@pytest.mark.parametrize("truthy", ["1", "true", "TRUE", "Yes", "on", "Y"])
def test_setup_csp_no_eval_env_truthy_disables_eval(monkeypatch, truthy):
    monkeypatch.setenv("TLDW_SETUP_NO_EVAL", truthy)

    app = _make_app()
    client = TestClient(app)
    response = client.get("/setup/ping")
    script_src = _script_src(response.headers.get("Content-Security-Policy", ""))

    assert "'unsafe-inline'" in script_src
    assert "'unsafe-eval'" not in script_src


@pytest.mark.parametrize("falsy", ["0", "false", "False", "off", "n", "no"])
def test_setup_csp_no_eval_env_falsy_enables_eval(monkeypatch, falsy):
    monkeypatch.setenv("TLDW_SETUP_NO_EVAL", falsy)

    app = _make_app()
    client = TestClient(app)
    response = client.get("/setup/ping")
    script_src = _script_src(response.headers.get("Content-Security-Policy", ""))

    assert "'unsafe-inline'" in script_src
    assert "'unsafe-eval'" in script_src


def test_setup_csp_default_allows_eval(monkeypatch):
    monkeypatch.delenv("TLDW_SETUP_NO_EVAL", raising=False)

    app = _make_app()
    client = TestClient(app)
    response = client.get("/setup/ping")
    script_src = _script_src(response.headers.get("Content-Security-Policy", ""))

    assert "'unsafe-inline'" in script_src
    assert "'unsafe-eval'" in script_src
