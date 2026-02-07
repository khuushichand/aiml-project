import importlib
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.evaluations import evaluations_unified as eval_unified
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User


def _build_eval_only_app(monkeypatch) -> FastAPI:
    app = FastAPI()
    app.include_router(eval_unified.router, prefix="/api/v1")

    async def _verify_api_key_override():
        return "user_1"

    async def _get_user_override():
        return User(id=1, username="tester", email=None, is_active=True)

    async def _rate_limit_dep_override():
        return None

    app.dependency_overrides[eval_unified.verify_api_key] = _verify_api_key_override
    app.dependency_overrides[eval_unified.get_eval_request_user] = _get_user_override
    app.dependency_overrides[eval_unified.check_evaluation_rate_limit] = _rate_limit_dep_override
    return app


def _reload_main_app(monkeypatch, *, minimal: bool):
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")
    monkeypatch.setenv("MINIMAL_TEST_APP", "1" if minimal else "0")

    # Ensure evaluations route toggles are consistent for reload-time gating.
    monkeypatch.setenv("ROUTES_ENABLE", "evaluations")
    monkeypatch.setenv("ROUTES_DISABLE", "research")

    from tldw_Server_API.app.core import config as config_mod

    config_mod._route_toggle_policy.cache_clear()

    from tldw_Server_API.app import main as app_main

    return importlib.reload(app_main).app


def test_main_mounts_evaluations_routes_in_minimal_startup(monkeypatch):
    app = _reload_main_app(monkeypatch, minimal=True)
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/api/v1/evaluations/geval" in paths
    assert "/api/v1/evaluations/rate-limits" in paths
    assert "/api/v1/evaluations/embeddings/abtest" in paths


def test_main_mounts_evaluations_routes_in_full_startup(monkeypatch):
    app = _reload_main_app(monkeypatch, minimal=False)
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/api/v1/evaluations/geval" in paths
    assert "/api/v1/evaluations/rag" in paths
    assert "/api/v1/evaluations/embeddings/abtest" in paths


def test_propositions_preserves_http_429_when_rate_limited(monkeypatch):
    app = _build_eval_only_app(monkeypatch)

    class _DenyLimiter:
        async def check_rate_limit(self, *_args, **_kwargs):
            return False, {"error": "rate limit exceeded", "retry_after": 7}

    monkeypatch.setattr(eval_unified, "get_user_rate_limiter_for_user", lambda _uid: _DenyLimiter())

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/evaluations/propositions",
            json={
                "extracted": ["Claim A"],
                "reference": ["Claim A"],
                "method": "semantic",
                "threshold": 0.7,
            },
        )

    assert response.status_code == 429
    assert response.headers.get("retry-after") == "7"


def test_history_preserves_http_403_for_non_admin_cross_user_request(monkeypatch):
    app = _build_eval_only_app(monkeypatch)

    class _DummyService:
        async def get_evaluation_history(self, **_kwargs):
            return []

        async def count_evaluations(self, **_kwargs):
            return 0

    async def _principal_override():
        return SimpleNamespace(is_admin=False, roles=[])

    monkeypatch.setattr(
        eval_unified,
        "get_unified_evaluation_service_for_user",
        lambda _user_id: _DummyService(),
    )
    app.dependency_overrides[eval_unified.get_auth_principal] = _principal_override

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/evaluations/history",
            json={"user_id": "user_2", "limit": 10, "offset": 0},
        )

    assert response.status_code == 403
    assert "Admin privileges required" in response.json()["detail"]
