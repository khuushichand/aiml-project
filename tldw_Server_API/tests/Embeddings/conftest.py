import os
import pytest

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.tests.Embeddings.fakes import FakeAsyncRedisSummary
from fastapi.testclient import TestClient


@pytest.fixture
def disable_heavy_startup(monkeypatch):
    monkeypatch.setenv("DISABLE_HEAVY_STARTUP", "1")
    yield


@pytest.fixture
def admin_user():
    async def _admin():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=42, username="admin", email="a@x", is_active=True, is_admin=True)

    app.dependency_overrides[get_request_user] = _admin
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_request_user, None)


@pytest.fixture
def fake_redis(monkeypatch):
    import redis.asyncio as aioredis
    fake = FakeAsyncRedisSummary()

    async def fake_from_url(url, decode_responses=True):
        return fake

    monkeypatch.setattr(aioredis, "from_url", fake_from_url)
    return fake


# Lightweight app client + auth fixtures for property/unit tests in this package
@pytest.fixture
def test_client(disable_heavy_startup):
    """Minimal TestClient with CSRF and auth header set.

    Scope: function — keeps isolation across property-based runs.
    """
    # Build client
    client = TestClient(app, raise_server_exceptions=False)
    # Double-submit CSRF: cookie + header
    csrf = "test-csrf"
    client.cookies.set("csrf_token", csrf)
    client.headers["X-CSRF-Token"] = csrf
    # Accept Authorization in single-user mode
    client.headers["Authorization"] = "Bearer test-api-key"
    try:
        yield client
    finally:
        # Ensure dependency overrides do not leak across tests
        try:
            app.dependency_overrides.clear()
        except Exception:
            pass


@pytest.fixture
def auth_headers():
    csrf = "test-csrf"
    return {
        "Authorization": "Bearer test-api-key",
        "X-CSRF-Token": csrf,
        "Content-Type": "application/json",
    }


@pytest.fixture
def regular_user():
    return User(id=1, username="testuser", email="t@example.com", is_active=True, is_admin=False)


@pytest.fixture(autouse=True)
def _sanitize_jsonschema_module(monkeypatch):
    """Ensure sys.modules['jsonschema'] is a proper ModuleType when present.

    Some tests stub 'jsonschema' with a SimpleNamespace for targeted assertions.
    Hypothesis inspects sys.modules and expects hashable module objects; wrapping
    the stub in a ModuleType avoids TypeError from unhashable SimpleNamespace.
    """
    import sys as _sys
    import types as _types
    mod = _sys.modules.get("jsonschema")
    if mod is not None and not isinstance(mod, _types.ModuleType):
        wrapper = _types.ModuleType("jsonschema")
        # Carry over commonly used attributes if present
        for attr in ("validate",):
            try:
                setattr(wrapper, attr, getattr(mod, attr))
            except Exception:
                pass
        monkeypatch.setitem(_sys.modules, "jsonschema", wrapper)


@pytest.fixture(autouse=True)
def _patch_hypothesis_local_constants(monkeypatch):
    """Patch Hypothesis provider constants discovery to tolerate unhashable stubs.

    Some tests insert non-module stubs (e.g., SimpleNamespace) into sys.modules.
    Hypothesis scans sys.modules and assumes hashable values; guard this by
    attempting to sanitize and retry when a TypeError arises.
    """
    try:
        from hypothesis.internal.conjecture import providers as _providers  # type: ignore
    except Exception:
        return

    orig = getattr(_providers, "_get_local_constants", None)
    if not callable(orig):
        return

    def _safe_get_local_constants():  # type: ignore[return-type]
        try:
            return orig()
        except TypeError:
            # Sanitize sys.modules: wrap unhashable stubs with ModuleType
            import sys as _sys
            import types as _types
            for name, mod in list(_sys.modules.items()):
                try:
                    hash(mod)
                    continue
                except Exception:
                    pass
                if isinstance(mod, _types.SimpleNamespace):
                    wrapper = _types.ModuleType(name)
                    for attr in dir(mod):
                        if attr.startswith("__") and attr.endswith("__"):
                            continue
                        try:
                            setattr(wrapper, attr, getattr(mod, attr))
                        except Exception:
                            pass
                    _sys.modules[name] = wrapper
            try:
                return orig()
            except Exception:
                # Fallback to existing cached constants if available
                return getattr(_providers, "_local_constants", None)

    monkeypatch.setattr(_providers, "_get_local_constants", _safe_get_local_constants, raising=False)


# ---------------------------------------------------------------------------
# Optional PGVector fixtures — skip when not available in this environment
# ---------------------------------------------------------------------------

@pytest.fixture
def pgvector_dsn():  # pragma: no cover - test helper for environments without PG
    pytest.skip("pgvector DSN not available in this test run")


@pytest.fixture
def pgvector_temp_table(pgvector_dsn):  # pragma: no cover - test helper for environments without PG
    pytest.skip("pgvector temporary table not available in this test run")
