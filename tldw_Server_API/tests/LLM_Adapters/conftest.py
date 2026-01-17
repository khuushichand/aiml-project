"""Local conftest for LLM_Adapters tests.

Provides:
- Lightweight stub for app.main when real app import fails (unit-only cases)
- Access to shared chat fixtures (client, authenticated_client, auth headers)
  via project-level plugin registration in pyproject.toml
- Backward-compat fixture alias client_user_only used by some tests

Note on plugin discovery and subtree runs
- These tests rely on the Chat fixtures plugin declared in pyproject.toml.
- When running tests from this subtree (or individual files) and the runner
  doesn’t load project-level plugins (e.g., PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
  or non-root working directory), fixtures like `authenticated_client` may be
  missing. In those cases, explicitly importing the plugin at module level
  (as some tests already do) or adding a local pytest_plugins declaration will
  restore deterministic fixture availability.
"""

import sys
import types
import pytest

# If the real app.main is importable, leave it alone; otherwise, install a stub
try:  # pragma: no cover - defensive guard
    import tldw_Server_API.app.main as _real_main  # noqa: F401
except Exception:
    m = types.ModuleType("tldw_Server_API.app.main")
    # Provide a minimal 'app' attribute that parent conftests import but do not use
    class _StubApp:  # pragma: no cover - simple container
        def __init__(self):
            self.dependency_overrides = {}
            self.state = types.SimpleNamespace()

    m.app = _StubApp()
    sys.modules["tldw_Server_API.app.main"] = m

# Shared chat fixtures are registered at the repository root conftest.py
# However, when running this subtree in isolation or with plugin autoloading
# disabled, those fixtures may be unavailable. Provide lightweight fallbacks
# here to keep this package's tests runnable in isolation without requiring
# project-level plugin loading.


@pytest.fixture
def client_user_only(request):  # noqa: D401 - compatibility alias with fallback
    """Return an authenticated TestClient.

    Prefer the rich 'authenticated_client' fixture from chat_fixtures when
    available; otherwise fall back to the project-level client_with_single_user
    which already overrides authentication dependencies.
    """
    try:
        return request.getfixturevalue("authenticated_client")
    except Exception:
        try:
            client, _logger = request.getfixturevalue("client_with_single_user")
            return client
        except Exception:
            # Last resort: construct a minimal TestClient against the app
            from fastapi.testclient import TestClient
            from tldw_Server_API.app.main import app as fastapi_app
            return TestClient(fastapi_app)


@pytest.fixture
def client(client_user_only):
    """Provide a TestClient with a helper 'post_with_auth' used by some tests.

    This mirrors the helper from the chat_fixtures plugin but works with the
    local fallback client when plugins are not loaded.
    """
    test_client = client_user_only

    # Best-effort CSRF token discovery (the health endpoint sets it)
    try:
        resp = test_client.get("/api/v1/health")
        csrf_token = getattr(test_client, "csrf_token", None) or resp.cookies.get("csrf_token", "")
        setattr(test_client, "csrf_token", csrf_token)
    except Exception:
        csrf_token = ""

    def post_with_auth(url, auth_token, **kwargs):
        headers = kwargs.pop("headers", {}) or {}
        if csrf_token and "X-CSRF-Token" not in headers:
            headers["X-CSRF-Token"] = csrf_token
        # Attach an auth header if provided; most tests run with request-user
        # dependency overridden, so this is optional but harmless.
        try:
            from tldw_Server_API.app.core.AuthNZ.settings import get_settings
            settings = get_settings()
            if settings.AUTH_MODE == "multi_user":
                headers.setdefault("Authorization", auth_token)
            else:
                headers.setdefault("X-API-KEY", auth_token)
        except Exception:
            pass
        return test_client.post(url, headers=headers, **kwargs)

    setattr(test_client, "post_with_auth", post_with_auth)
    return test_client


@pytest.fixture
def authenticated_client(client_user_only):  # pragma: no cover - thin alias
    """Alias for compatibility with tests expecting authenticated_client."""
    return client_user_only


@pytest.fixture
def auth_token():  # pragma: no cover - simple token helper
    """Provide a plausible auth token for tests that include it in requests."""
    try:
        from tldw_Server_API.app.core.AuthNZ.settings import get_settings
        import os as _os
        settings = get_settings()
        if settings.AUTH_MODE == "multi_user":
            # Not generating a real JWT here; tests using this fixture don't validate it.
            return "Bearer test-token"
        return _os.environ.get("SINGLE_USER_API_KEY", "test-api-key")
    except Exception:
        return "test-api-key"
