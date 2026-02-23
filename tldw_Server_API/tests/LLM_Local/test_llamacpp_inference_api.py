from typing import Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import llamacpp as lp
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


def _admin_principal() -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=["admin"],
        permissions=[],
        is_admin=True,
        org_ids=[],
        team_ids=[],
    )


class _Logger:
    def error(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return


class _DefaultMgr:
    logger = _Logger()
    llamacpp = True

    async def get_server_status(self, backend: str):
        return {"backend": backend, "model": "mock.gguf"}

    async def run_inference(self, backend: str, model_name_or_path: str, prompt=None, **kwargs):
        _ = prompt
        return {
            "model": model_name_or_path,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}}],
            "kwargs": {"backend": backend, **kwargs},
        }


def _make_app_with_manager(manager) -> FastAPI:  # noqa: ANN001
    app = FastAPI()
    app.include_router(lp.router, prefix="/api/v1")
    app.state.llm_manager = manager

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        principal = _admin_principal()
        ip = request.client.host if getattr(request, "client", None) else None
        ua = request.headers.get("User-Agent") if getattr(request, "headers", None) else None
        request_id = request.headers.get("X-Request-ID") if getattr(request, "headers", None) else None
        request.state.auth = AuthContext(
            principal=principal,
            ip=ip,
            user_agent=ua,
            request_id=request_id,
        )
        return principal

    async def _fake_check_rate_limit() -> None:
        return

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    app.dependency_overrides[auth_deps.check_rate_limit] = _fake_check_rate_limit
    app.dependency_overrides[lp.check_rate_limit] = _fake_check_rate_limit
    return app


@pytest.fixture()
def llamacpp_client() -> Tuple[TestClient, dict]:
    app = _make_app_with_manager(_DefaultMgr())
    headers = {"Content-Type": "application/json"}
    client = TestClient(app)
    return client, headers


@pytest.mark.integration
def test_llamacpp_inference_happy_path(llamacpp_client, monkeypatch):
    client, headers = llamacpp_client

    # Patch llm_manager on the endpoint module
    class _Mgr:
        llamacpp = True
        logger = _Logger()

        async def get_server_status(self, backend: str):
            return {"backend": backend, "model": "mock.gguf"}

        async def run_inference(self, backend: str, model_name_or_path: str, prompt=None, **kwargs):
            # Echo a minimal OpenAI-style response
            return {
                "model": model_name_or_path,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}}],
                "kwargs": kwargs,
            }

    import tldw_Server_API.app.api.v1.endpoints.llamacpp as lp

    stub = _Mgr()
    monkeypatch.setattr(lp, "llm_manager", stub, raising=False)
    # Ensure dependency resolver sees the stub instead of app.state.llm_manager.
    monkeypatch.setattr(client.app.state, "llm_manager", stub, raising=False)

    payload = {
        "model": "ignored-by-server",
        "messages": [{"role": "user", "content": "Hello!"}],
        "temperature": 0.7,
    }
    r = client.post("/api/v1/llamacpp/inference", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["model"] == "mock.gguf"
    assert body["choices"][0]["message"]["content"] == "hi"
