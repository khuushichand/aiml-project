import types
import pytest

from tldw_Server_API.app.core.AuthNZ.csrf_protection import CSRFTokenManager
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings


def _dummy_request(user_id: int | None):
    o = types.SimpleNamespace()
    o.state = types.SimpleNamespace()
    if user_id is not None:
        o.state.user_id = user_id
    return o


def test_csrf_binding_user_suffix_ok(monkeypatch):
    reset_settings()
    monkeypatch.setenv("CSRF_BIND_TO_USER", "true")
    mgr = CSRFTokenManager()
    req = _dummy_request(42)
    token = mgr.generate_token(req)
    # Correct user binding validates
    assert mgr.validate_token(token, token, user_id=42) is True
    # Wrong user id fails
    assert mgr.validate_token(token, token, user_id=43) is False


def test_csrf_no_binding(monkeypatch):
    reset_settings()
    monkeypatch.setenv("CSRF_BIND_TO_USER", "false")
    mgr = CSRFTokenManager()
    req = _dummy_request(None)
    token = mgr.generate_token(req)
    # No binding required, plain compare works
    assert mgr.validate_token(token, token, user_id=None) is True


def test_csrf_single_user_bearer_skips_protection(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "bearer-test-key-1234567890")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    reset_settings()

    mgr = CSRFTokenManager()
    request = types.SimpleNamespace(
        method="POST",
        headers={
            "Authorization": "Bearer bearer-test-key-1234567890",
            "content-type": "application/json",
        },
        url=types.SimpleNamespace(path="/api/v1/chat/completions"),
        state=types.SimpleNamespace(),
    )
    assert mgr.should_protect(request) is False

    # Cleanup env to avoid leakage
    for key in ("AUTH_MODE", "SINGLE_USER_API_KEY", "DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    reset_settings()
