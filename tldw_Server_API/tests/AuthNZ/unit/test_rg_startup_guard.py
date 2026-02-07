from __future__ import annotations

from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.AuthNZ.rg_startup_guard import (
    AuthRGStartupGuardError,
    route_map_matches,
    validate_auth_rg_startup_guards,
)


class _Loader:
    def __init__(self, *, policies: dict, by_path: dict):
        self._snapshot = SimpleNamespace(
            policies=policies,
            route_map={"by_path": by_path, "by_tag": {}},
        )

    def get_snapshot(self):
        return self._snapshot


def _build_app(*, policies: dict, by_path: dict, with_governor: bool = True):
    class RGSimpleMiddleware:
        pass

    state = SimpleNamespace(
        rg_governor=object() if with_governor else None,
        rg_policy_loader=_Loader(policies=policies, by_path=by_path),
    )
    user_middleware = [SimpleNamespace(cls=RGSimpleMiddleware)] if with_governor else []
    return SimpleNamespace(state=state, user_middleware=user_middleware)


def _set_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("tldw_production", "true")
    monkeypatch.delenv("ENVIRONMENT", raising=False)


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("tldw_production", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ALLOW_AUTH_RG_GUARD_BYPASS", raising=False)


def test_route_map_matches_wildcard_and_exact():
    by_path = {"/api/v1/auth*": "authnz.default", "/api/v1/auth/login": "authnz.default"}
    assert route_map_matches("/api/v1/auth/login", by_path)
    assert route_map_matches("/api/v1/auth/refresh", by_path)
    assert not route_map_matches("/api/v1/chat/completions", by_path)


def test_validate_auth_rg_startup_guards_non_production_noop(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr("tldw_Server_API.app.core.config.rg_enabled", lambda _default=True: False)
    app = _build_app(policies={}, by_path={}, with_governor=False)
    validate_auth_rg_startup_guards(app)


def test_validate_auth_rg_startup_guards_allows_rg_disabled_in_production(monkeypatch):
    _set_production(monkeypatch)
    monkeypatch.setattr("tldw_Server_API.app.core.config.rg_enabled", lambda _default=True: False)
    app = _build_app(policies={}, by_path={}, with_governor=False)
    validate_auth_rg_startup_guards(app)


def test_validate_auth_rg_startup_guards_requires_governor_in_production(monkeypatch):
    _set_production(monkeypatch)
    monkeypatch.setattr("tldw_Server_API.app.core.config.rg_enabled", lambda _default=True: True)
    app = _build_app(policies={}, by_path={}, with_governor=False)
    # Keep middleware present so this assertion isolates the missing-governor path.
    app.user_middleware = [SimpleNamespace(cls=type("RGSimpleMiddleware", (), {}))]
    with pytest.raises(AuthRGStartupGuardError, match="not initialized"):
        validate_auth_rg_startup_guards(app)


def test_validate_auth_rg_startup_guards_requires_rg_middleware_in_production(monkeypatch):
    _set_production(monkeypatch)
    monkeypatch.setattr("tldw_Server_API.app.core.config.rg_enabled", lambda _default=True: True)
    app = _build_app(
        policies={"authnz.default": {"requests": {"rpm": 60}}},
        by_path={"/api/v1/auth*": "authnz.default"},
        with_governor=True,
    )
    app.user_middleware = []
    with pytest.raises(AuthRGStartupGuardError, match="RGSimpleMiddleware"):
        validate_auth_rg_startup_guards(app)


def test_validate_auth_rg_startup_guards_requires_policies_and_paths(monkeypatch):
    _set_production(monkeypatch)
    monkeypatch.setattr("tldw_Server_API.app.core.config.rg_enabled", lambda _default=True: True)
    app = _build_app(
        policies={"authnz.default": {"requests": {"rpm": 60}}},
        by_path={"/api/v1/auth*": "authnz.default"},
    )
    with pytest.raises(AuthRGStartupGuardError, match="Missing required auth RG policies"):
        validate_auth_rg_startup_guards(app)


def test_validate_auth_rg_startup_guards_allows_explicit_bypass(monkeypatch):
    _set_production(monkeypatch)
    monkeypatch.setenv("ALLOW_AUTH_RG_GUARD_BYPASS", "1")
    monkeypatch.setattr("tldw_Server_API.app.core.config.rg_enabled", lambda _default=True: True)
    app = _build_app(policies={}, by_path={}, with_governor=False)
    validate_auth_rg_startup_guards(app)


def test_validate_auth_rg_startup_guards_passes_when_requirements_met(monkeypatch):
    _set_production(monkeypatch)
    monkeypatch.setattr("tldw_Server_API.app.core.config.rg_enabled", lambda _default=True: True)
    app = _build_app(
        policies={
            "authnz.default": {"requests": {"rpm": 60}},
            "authnz.forgot_password": {"requests": {"rpm": 10}},
            "authnz.magic_link.request": {"requests": {"rpm": 10}},
            "authnz.magic_link.email": {"requests": {"rpm": 1}},
        },
        by_path={
            "/api/v1/auth/login": "authnz.default",
            "/api/v1/auth/refresh": "authnz.default",
            "/api/v1/auth/forgot-password": "authnz.forgot_password",
            "/api/v1/auth/magic-link/request": "authnz.magic_link.request",
        },
    )
    validate_auth_rg_startup_guards(app)
