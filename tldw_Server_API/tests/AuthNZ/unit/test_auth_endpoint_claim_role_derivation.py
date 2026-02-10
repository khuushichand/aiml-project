import pytest

from tldw_Server_API.app.api.v1.endpoints import auth as auth_endpoints
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


pytestmark = pytest.mark.unit


def test_current_user_primary_role_ignores_boolean_is_admin_without_claims() -> None:
    user = {
        "id": 1,
        "role": "",
        "roles": ["user"],
        "permissions": [],
        "is_admin": True,
    }
    assert auth_endpoints._current_user_primary_role(user) == "user"


def test_principal_primary_role_uses_admin_permission_claim() -> None:
    principal = AuthPrincipal(
        kind="user",
        user_id=1,
        roles=["user"],
        permissions=["system.configure"],
        is_admin=False,
    )
    assert auth_endpoints._principal_primary_role(principal) == "admin"


def test_principal_primary_role_ignores_boolean_is_admin_without_claims() -> None:
    principal = AuthPrincipal(
        kind="user",
        user_id=1,
        roles=["user"],
        permissions=[],
        is_admin=True,
    )
    assert auth_endpoints._principal_primary_role(principal) == "user"
