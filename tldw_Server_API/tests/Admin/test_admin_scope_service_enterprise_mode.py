from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services import admin_scope_service


def test_single_user_principal_is_not_platform_admin_in_enterprise_mode(monkeypatch):
    monkeypatch.setenv("ADMIN_UI_ENTERPRISE_MODE", "true")

    principal = AuthPrincipal(
        kind="user",
        user_id=1,
        subject="single_user",
        roles=["admin"],
        is_admin=True,
    )

    assert admin_scope_service.is_platform_admin(principal) is False


def test_single_user_principal_remains_platform_admin_when_enterprise_mode_disabled(monkeypatch):
    monkeypatch.delenv("ADMIN_UI_ENTERPRISE_MODE", raising=False)

    principal = AuthPrincipal(
        kind="user",
        user_id=1,
        subject="single_user",
        roles=["admin"],
        is_admin=True,
    )

    assert admin_scope_service.is_platform_admin(principal) is True
