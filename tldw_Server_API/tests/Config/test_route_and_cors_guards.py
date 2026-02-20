import importlib
import os

from fastapi import FastAPI
import pytest

# Keep this module importable even when local/dev env sets ALLOWED_ORIGINS='*'.
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"

from tldw_Server_API.app.core import config as config_mod

importlib.reload(config_mod)

from tldw_Server_API.app import main as app_main

app_main = importlib.reload(app_main)


def test_main_app_route_guard_passes_for_current_routes() -> None:
    app_main._fail_on_duplicate_route_method_pairs(app_main.app, context="unit-test")


def test_duplicate_route_guard_raises_for_duplicate_path_method_pairs() -> None:
    app = FastAPI()

    @app.get("/dup")
    async def dup_one() -> dict[str, str]:
        return {"ok": "1"}

    @app.get("/dup")
    async def dup_two() -> dict[str, str]:
        return {"ok": "2"}

    with pytest.raises(RuntimeError, match="Duplicate route registrations detected"):
        app_main._fail_on_duplicate_route_method_pairs(app, context="unit-test")


def test_duplicate_route_guard_allows_same_path_different_methods() -> None:
    app = FastAPI()

    @app.get("/item")
    async def get_item() -> dict[str, str]:
        return {"method": "get"}

    @app.post("/item")
    async def post_item() -> dict[str, str]:
        return {"method": "post"}

    app_main._fail_on_duplicate_route_method_pairs(app, context="unit-test")


def test_resolve_cors_origins_rejects_empty_values() -> None:
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS is empty"):
        app_main._resolve_cors_origins_or_raise([])

    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS is empty"):
        app_main._resolve_cors_origins_or_raise(["", "   "])


def test_resolve_cors_origins_normalizes_and_accepts_non_empty_values() -> None:
    assert app_main._resolve_cors_origins_or_raise([" http://localhost:3000 ", "https://example.com"]) == [
        "http://localhost:3000",
        "https://example.com",
    ]


def test_validate_cors_configuration_rejects_wildcard_with_credentials() -> None:
    with pytest.raises(RuntimeError, match="cannot include '\\*'"):
        app_main._validate_cors_configuration_or_raise(["*", "http://localhost:3000"], allow_credentials=True)


def test_validate_cors_configuration_allows_wildcard_without_credentials() -> None:
    app_main._validate_cors_configuration_or_raise(["*"], allow_credentials=False)


def test_should_allow_cors_credentials_defaults_false() -> None:
    prior_allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS")
    try:
        _restore_env("CORS_ALLOW_CREDENTIALS", None)
        reloaded_config = importlib.reload(config_mod)
        assert reloaded_config.should_allow_cors_credentials() is False
    finally:
        _restore_env("CORS_ALLOW_CREDENTIALS", prior_allow_credentials)
        importlib.reload(config_mod)


def test_should_allow_cors_credentials_env_override_true() -> None:
    prior_allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS")
    try:
        os.environ["CORS_ALLOW_CREDENTIALS"] = "true"
        reloaded_config = importlib.reload(config_mod)
        assert reloaded_config.should_allow_cors_credentials() is True
    finally:
        _restore_env("CORS_ALLOW_CREDENTIALS", prior_allow_credentials)
        importlib.reload(config_mod)


def test_get_cors_runtime_diagnostics_reports_env_sources() -> None:
    prior_disable_cors = os.getenv("DISABLE_CORS")
    prior_allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS")
    prior_allowed_origins = os.getenv("ALLOWED_ORIGINS")
    try:
        os.environ["DISABLE_CORS"] = "false"
        os.environ["CORS_ALLOW_CREDENTIALS"] = "true"
        os.environ["ALLOWED_ORIGINS"] = "http://127.0.0.1:8080,http://localhost:3000"
        reloaded_config = importlib.reload(config_mod)

        diagnostics = reloaded_config.get_cors_runtime_diagnostics()
        assert diagnostics["disable_cors"] is False
        assert diagnostics["disable_cors_source"] == "env"
        assert diagnostics["allow_credentials"] is True
        assert diagnostics["allow_credentials_source"] == "env"
        assert diagnostics["allowed_origins_source"] == "env"
        assert diagnostics["allowed_origins_count"] == 2
        assert diagnostics["allowed_origins"] == ["http://127.0.0.1:8080", "http://localhost:3000"]
        assert diagnostics["config_path"]
    finally:
        _restore_env("DISABLE_CORS", prior_disable_cors)
        _restore_env("CORS_ALLOW_CREDENTIALS", prior_allow_credentials)
        _restore_env("ALLOWED_ORIGINS", prior_allowed_origins)
        importlib.reload(config_mod)


def test_get_cors_runtime_diagnostics_marks_empty_origins_env_as_default() -> None:
    prior_allowed_origins = os.getenv("ALLOWED_ORIGINS")
    try:
        os.environ["ALLOWED_ORIGINS"] = ""
        reloaded_config = importlib.reload(config_mod)
        diagnostics = reloaded_config.get_cors_runtime_diagnostics()
        assert diagnostics["allowed_origins_source"] == "default(empty-env)"
        assert diagnostics["allowed_origins_count"] >= 1
    finally:
        _restore_env("ALLOWED_ORIGINS", prior_allowed_origins)
        importlib.reload(config_mod)


def test_compute_openapi_cors_allow_origin_echoes_allowed_explicit_origin() -> None:
    allow_origin = app_main._compute_openapi_cors_allow_origin(
        "http://localhost:3000",
        allow_all_origins=False,
        allow_credentials=True,
        allowed_openapi_origins={"http://localhost:3000"},
    )
    assert allow_origin == "http://localhost:3000"


def test_compute_openapi_cors_allow_origin_rejects_disallowed_origin() -> None:
    allow_origin = app_main._compute_openapi_cors_allow_origin(
        "http://evil.local",
        allow_all_origins=False,
        allow_credentials=True,
        allowed_openapi_origins={"http://localhost:3000"},
    )
    assert allow_origin is None


def test_compute_openapi_cors_allow_origin_supports_wildcard_when_credentials_disabled() -> None:
    allow_origin = app_main._compute_openapi_cors_allow_origin(
        "http://any.local",
        allow_all_origins=True,
        allow_credentials=False,
        allowed_openapi_origins=set(),
    )
    assert allow_origin == "*"


def test_main_import_fails_for_wildcard_origins_with_credentials() -> None:
    prior_allowed_origins = os.getenv("ALLOWED_ORIGINS")
    prior_allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS")
    prior_disable_cors = os.getenv("DISABLE_CORS")
    try:
        os.environ["DISABLE_CORS"] = "false"
        os.environ["ALLOWED_ORIGINS"] = "*"
        os.environ["CORS_ALLOW_CREDENTIALS"] = "true"
        importlib.reload(config_mod)
        with pytest.raises(RuntimeError, match="cannot include '\\*'"):
            importlib.reload(app_main)
    finally:
        _restore_env("DISABLE_CORS", prior_disable_cors)
        _restore_env("ALLOWED_ORIGINS", prior_allowed_origins)
        _restore_env("CORS_ALLOW_CREDENTIALS", prior_allow_credentials)
        importlib.reload(config_mod)
        importlib.reload(app_main)


def test_main_import_allows_wildcard_origins_when_credentials_disabled() -> None:
    prior_allowed_origins = os.getenv("ALLOWED_ORIGINS")
    prior_allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS")
    prior_disable_cors = os.getenv("DISABLE_CORS")
    try:
        os.environ["DISABLE_CORS"] = "false"
        os.environ["ALLOWED_ORIGINS"] = "*"
        os.environ["CORS_ALLOW_CREDENTIALS"] = "false"
        reloaded_config = importlib.reload(config_mod)
        reloaded_main = importlib.reload(app_main)

        assert reloaded_config.ALLOWED_ORIGINS == ["*"]
        assert reloaded_main._resolve_cors_origins_or_raise(reloaded_config.ALLOWED_ORIGINS) == ["*"]
    finally:
        _restore_env("DISABLE_CORS", prior_disable_cors)
        _restore_env("ALLOWED_ORIGINS", prior_allowed_origins)
        _restore_env("CORS_ALLOW_CREDENTIALS", prior_allow_credentials)
        importlib.reload(config_mod)
        importlib.reload(app_main)


def test_empty_string_allowed_origins_env_falls_back_to_defaults() -> None:
    prior_allowed_origins = os.getenv("ALLOWED_ORIGINS")
    try:
        os.environ["ALLOWED_ORIGINS"] = ""
        reloaded_config = importlib.reload(config_mod)
        reloaded_main = importlib.reload(app_main)

        assert "http://localhost:3000" in reloaded_config.ALLOWED_ORIGINS
        assert reloaded_main._resolve_cors_origins_or_raise(reloaded_config.ALLOWED_ORIGINS)
    finally:
        _restore_env("ALLOWED_ORIGINS", prior_allowed_origins)
        importlib.reload(config_mod)
        importlib.reload(app_main)


def test_main_import_fails_for_explicit_empty_allowed_origins_list() -> None:
    prior_allowed_origins = os.getenv("ALLOWED_ORIGINS")
    prior_disable_cors = os.getenv("DISABLE_CORS")
    try:
        os.environ["DISABLE_CORS"] = "false"
        os.environ["ALLOWED_ORIGINS"] = "[]"
        reloaded_config = importlib.reload(config_mod)
        assert reloaded_config.ALLOWED_ORIGINS == []
        with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS is empty"):
            importlib.reload(app_main)
    finally:
        _restore_env("DISABLE_CORS", prior_disable_cors)
        _restore_env("ALLOWED_ORIGINS", prior_allowed_origins)
        importlib.reload(config_mod)
        importlib.reload(app_main)


def _route_method_count(app: FastAPI, path: str, method: str) -> int:
    method_upper = method.upper()
    count = 0
    for route in app.routes:
        route_path = getattr(route, "path", None)
        route_methods = getattr(route, "methods", set()) or set()
        if route_path == path and method_upper in route_methods:
            count += 1
    return count


def _restore_env(key: str, prior_value: str | None) -> None:
    if prior_value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = prior_value


def test_ultra_minimal_uses_control_plane_health_routes_only() -> None:
    prior_ultra = os.getenv("ULTRA_MINIMAL_APP")
    prior_minimal = os.getenv("MINIMAL_TEST_APP")
    prior_test_mode = os.getenv("TEST_MODE")

    try:
        os.environ["TEST_MODE"] = "1"
        os.environ["ULTRA_MINIMAL_APP"] = "1"
        os.environ["MINIMAL_TEST_APP"] = "0"
        reloaded_main = importlib.reload(app_main)

        assert _route_method_count(reloaded_main.app, "/health", "GET") == 1
        assert _route_method_count(reloaded_main.app, "/ready", "GET") == 1
        assert _route_method_count(reloaded_main.app, "/health/ready", "GET") == 1
        assert _route_method_count(reloaded_main.app, "/api/v1/health", "GET") == 0
    finally:
        _restore_env("ULTRA_MINIMAL_APP", prior_ultra)
        _restore_env("MINIMAL_TEST_APP", prior_minimal)
        _restore_env("TEST_MODE", prior_test_mode)
        importlib.reload(app_main)
