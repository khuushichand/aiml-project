import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
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
