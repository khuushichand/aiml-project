"""
Helpers for mapping profile update skip reasons to structured error responses.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import status

from tldw_Server_API.app.api.v1.schemas.user_profile_schemas import (
    UserProfileErrorDetail,
)

_FORBIDDEN_MESSAGES = {
    "forbidden",
    "forbidden_scope",
    "owner_required",
    "org_membership_required",
}

_UNKNOWN_MESSAGES = {
    "unknown_key",
    "unsupported_key",
    "unsupported_type",
}

_NOT_FOUND_MESSAGES = {
    "user_not_found",
}


def classify_profile_update_skips(
    skipped: Iterable[dict[str, str]],
) -> tuple[int, str, str, list[UserProfileErrorDetail]] | None:
    """Map per-key skip reasons into a single structured error response."""
    skipped_list = list(skipped)
    if not skipped_list:
        return None

    messages = {str(item.get("message") or "") for item in skipped_list}
    errors = [
        UserProfileErrorDetail(
            key=str(item.get("key") or ""),
            message=str(item.get("message") or ""),
        )
        for item in skipped_list
    ]

    if messages & _NOT_FOUND_MESSAGES:
        return (
            status.HTTP_404_NOT_FOUND,
            "profile_update_not_found",
            "Target user not found",
            errors,
        )
    if messages & _FORBIDDEN_MESSAGES:
        return (
            status.HTTP_403_FORBIDDEN,
            "profile_update_forbidden",
            "Caller cannot edit one or more fields",
            errors,
        )
    if messages & _UNKNOWN_MESSAGES:
        return (
            status.HTTP_400_BAD_REQUEST,
            "profile_update_unknown_key",
            "One or more keys are not recognized",
            errors,
        )

    return (
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "profile_update_invalid",
        "One or more updates failed validation",
        errors,
    )


__all__ = ["classify_profile_update_skips"]
