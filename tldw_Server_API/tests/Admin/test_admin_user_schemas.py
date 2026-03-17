import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    AdminPasswordResetRequest,
    AdminPrivilegedActionRequest,
    AdminPasswordResetResponse,
    UserUpdateRequest,
)


pytestmark = pytest.mark.unit


def test_user_update_request_accepts_backend_role_vocabulary() -> None:
    payload = UserUpdateRequest(role="user")

    assert payload.role == "user"


def test_user_update_request_rejects_legacy_member_role() -> None:
    with pytest.raises(ValidationError):
        UserUpdateRequest(role="member")


def test_admin_password_reset_response_omits_plaintext_password() -> None:
    payload = AdminPasswordResetResponse(
        user_id=42,
        force_password_change=True,
        message="Password reset successfully",
    )

    assert payload.model_dump() == {
        "user_id": 42,
        "force_password_change": True,
        "message": "Password reset successfully",
    }


def test_admin_password_reset_request_requires_temporary_password() -> None:
    with pytest.raises(ValidationError):
        AdminPasswordResetRequest(
            reason="Support case 123",
            admin_password="AdminPass123!",
        )


def test_admin_privileged_action_request_allows_blank_admin_password_for_single_user_mode() -> None:
    payload = AdminPrivilegedActionRequest(
        reason="Support case 123",
        admin_password="",
        admin_reauth_token="",
    )

    assert payload.admin_password is None
    assert payload.admin_reauth_token is None


def test_user_update_request_allows_blank_admin_password_for_single_user_mode() -> None:
    payload = UserUpdateRequest(
        is_active=False,
        reason="Support case 123",
        admin_password="",
    )

    assert payload.admin_password is None
