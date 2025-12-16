import re
from types import SimpleNamespace

from tldw_Server_API.app.core.AuthNZ.principal_model import (
    AuthContext,
    AuthPrincipal,
    compute_principal_id,
    is_single_user_principal,
)


def test_compute_principal_id_is_stable_and_pseudonymous():
    kind = "user"
    subject = "user:123"

    first = compute_principal_id(kind, subject)
    second = compute_principal_id(kind, subject)

    assert first == second
    assert first.startswith(f"{kind}:")
    # Hex suffix of at least a few characters, no raw subject embedded
    suffix = first.split(":", 1)[1]
    assert re.fullmatch(r"[0-9a-f]{16}", suffix) is not None
    assert subject not in first


def test_auth_principal_derives_principal_id_from_user_id():
    principal = AuthPrincipal(kind="user", user_id=42, roles=["user"], permissions=[])

    expected = compute_principal_id("user", "user:42")
    assert principal.principal_id == expected


def test_auth_principal_derives_principal_id_from_api_key_id():
    principal = AuthPrincipal(kind="api_key", api_key_id=7)

    expected = compute_principal_id("api_key", "api_key:7")
    assert principal.principal_id == expected


def test_auth_principal_prefers_explicit_subject_for_principal_id():
    principal = AuthPrincipal(
        kind="service",
        subject="service:workflow-engine",
        user_id=None,
        api_key_id=None,
        roles=["service"],
    )

    expected = compute_principal_id("service", "service:workflow-engine")
    assert principal.principal_id == expected


def test_auth_context_wraps_principal_and_metadata():
    principal = AuthPrincipal(kind="anonymous")
    ctx = AuthContext(
        principal=principal,
        ip="127.0.0.1",
        user_agent="pytest-agent",
        request_id="req-123",
    )

    assert ctx.principal is principal
    assert ctx.ip == "127.0.0.1"
    assert ctx.user_agent == "pytest-agent"
    assert ctx.request_id == "req-123"


def test_is_single_user_principal_prefers_explicit_subject():
    principal = AuthPrincipal(kind="user", user_id=123, subject="single_user")
    assert is_single_user_principal(principal) is True


def test_is_single_user_principal_fixed_id_fallback_requires_single_user_mode(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ import settings as auth_settings

    monkeypatch.setattr(
        auth_settings,
        "get_settings",
        lambda: SimpleNamespace(AUTH_MODE="single_user", SINGLE_USER_FIXED_ID=99),
    )
    principal = AuthPrincipal(kind="user", user_id=99, subject=None)
    assert is_single_user_principal(principal) is True

    monkeypatch.setattr(
        auth_settings,
        "get_settings",
        lambda: SimpleNamespace(AUTH_MODE="multi_user", SINGLE_USER_FIXED_ID=99),
    )
    assert is_single_user_principal(principal) is False
