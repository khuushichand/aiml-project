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

