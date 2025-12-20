import os

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_token_scope
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings


class _StubSessionManager:
    async def is_token_blacklisted(self, _token: str, _jti=None) -> bool:
        return False


def _build_app(with_scope_dep: bool) -> FastAPI:
    app = FastAPI()

    deps = []
    if with_scope_dep:
        deps.append(
            Depends(
                require_token_scope(
                    "workflows",
                    require_if_present=True,
                    endpoint_id="unit.scoped",
                )
            )
        )

    @app.get("/protected", dependencies=deps)
    async def protected(_user=Depends(get_request_user)):  # noqa: B008
        return {"ok": True}

    # Avoid touching the real AuthNZ database pool in unit tests.
    async def _fake_db_pool():
        return None

    app.dependency_overrides[auth_deps.get_db_pool] = _fake_db_pool
    return app


def _make_scoped_token() -> str:
    svc = JWTService(get_settings())
    return svc.create_access_token(
        user_id=1,
        username="tester",
        role="user",
        additional_claims={"scope": "workflows"},
    )


def test_scoped_token_requires_scope_dependency(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-secret-key-1234567890-abcdef")
    reset_settings()

    # Stub auth dependencies to avoid DB/Redis access.
    import tldw_Server_API.app.core.AuthNZ.User_DB_Handling as user_mod
    import tldw_Server_API.app.core.DB_Management.Users_DB as users_db

    async def _fake_get_user_by_id(_user_id: int):
        return {"id": 1, "username": "tester", "is_active": True}

    monkeypatch.setattr(users_db, "get_user_by_id", _fake_get_user_by_id)
    async def _fake_get_session_manager():
        return _StubSessionManager()

    monkeypatch.setattr(user_mod, "get_session_manager", _fake_get_session_manager)
    monkeypatch.setattr(user_mod, "_enrich_user_with_rbac", lambda *_args, **_kwargs: (["user"], [], False))

    token = _make_scoped_token()
    app = _build_app(with_scope_dep=False)
    client = TestClient(app)

    r = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    assert r.json().get("detail") == "Scoped token requires endpoint scope enforcement"


def test_scoped_token_allows_when_scope_dependency_present(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-secret-key-1234567890-abcdef")
    reset_settings()

    import tldw_Server_API.app.core.AuthNZ.User_DB_Handling as user_mod
    import tldw_Server_API.app.core.DB_Management.Users_DB as users_db

    async def _fake_get_user_by_id(_user_id: int):
        return {"id": 1, "username": "tester", "is_active": True}

    monkeypatch.setattr(users_db, "get_user_by_id", _fake_get_user_by_id)
    async def _fake_get_session_manager():
        return _StubSessionManager()

    monkeypatch.setattr(user_mod, "get_session_manager", _fake_get_session_manager)
    monkeypatch.setattr(user_mod, "_enrich_user_with_rbac", lambda *_args, **_kwargs: (["user"], [], False))

    token = _make_scoped_token()
    app = _build_app(with_scope_dep=True)
    client = TestClient(app)

    r = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
