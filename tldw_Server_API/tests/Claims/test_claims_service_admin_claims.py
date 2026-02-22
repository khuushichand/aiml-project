from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.Claims_Extraction import claims_service


pytestmark = pytest.mark.unit


def test_legacy_user_admin_claims_rejects_boolean_only_shape() -> None:
    legacy_user = SimpleNamespace(role="user", roles=["user"], permissions=[], is_admin=True)
    assert claims_service._legacy_user_has_platform_admin_claims(legacy_user) is False


def test_legacy_user_admin_claims_accepts_system_configure_permission() -> None:
    legacy_user = SimpleNamespace(role="user", roles=["user"], permissions=["system.configure"], is_admin=False)
    assert claims_service._legacy_user_has_platform_admin_claims(legacy_user) is True


def test_principal_admin_claims_ignore_boolean_admin_flag_without_claims() -> None:
    principal = AuthPrincipal(
        kind="user",
        user_id=7,
        roles=["user"],
        permissions=[],
        is_admin=True,
    )
    assert claims_service._principal_has_platform_admin_claims(principal) is False
