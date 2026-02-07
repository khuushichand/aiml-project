"""RBAC effective permission helpers for AuthNZ.

This module centralizes read-only calculation of effective permissions and a
simple checker that builds on the configured UserDatabase implementation. It
aligns with AuthNZ/permissions.py which already exposes FastAPI dependencies
and now uses the AuthnzRbacRepo facade for database access.
"""

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.repos.rbac_repo import AuthnzRbacRepo
from tldw_Server_API.app.core.AuthNZ.settings import get_settings, get_settings_generation

_RBAC_REPO: AuthnzRbacRepo | None = None
_RBAC_SETTINGS_GEN: int = -1


def _get_rbac_repo() -> AuthnzRbacRepo:
    """Return an AuthnzRbacRepo instance tied to the current settings generation."""
    global _RBAC_REPO
    global _RBAC_SETTINGS_GEN
    try:
        gen = int(get_settings_generation() or 0)
    except Exception:
        gen = 0
    if _RBAC_REPO is None or gen != _RBAC_SETTINGS_GEN:
        _RBAC_REPO = AuthnzRbacRepo()
        _RBAC_SETTINGS_GEN = gen
    return _RBAC_REPO


class RBACError(Exception):
    """Exception raised when RBAC operations fail."""
    pass


def get_effective_permissions(user_id: int) -> list[str]:
    """Return the list of effective permissions for a user.

    Combines role-derived permissions with user overrides (allow/deny) using the
    existing UserDatabase logic.

    Raises:
        RBACError: If permissions cannot be computed (database error, etc.)

    Note:
        SECURITY: This function raises an exception on error instead of returning
        an empty list. Returning [] could cause inconsistent security behavior
        depending on how callers check permissions. By raising, callers must
        explicitly handle the error case.
    """
    try:
        return _get_rbac_repo().get_effective_permissions(user_id)
    except Exception as e:
        try:
            redact_logs = get_settings().PII_REDACT_LOGS
        except Exception:
            redact_logs = False
        if redact_logs:
            logger.error(f"RBAC: failed to compute effective permissions for authenticated user (details redacted): {e}")
        else:
            logger.error(f"RBAC: failed to compute effective permissions for user {user_id}: {e}")
        # SECURITY: Raise instead of returning [] to force callers to handle error
        raise RBACError(f"Failed to compute effective permissions: {e}") from e


def user_has_permission(user_id: int, permission: str) -> bool:
    """Check if a user has a given permission code.

    Raises:
        RBACError: If the permission check fails (database error, etc.)

    Note:
        SECURITY: This function raises an exception on error instead of returning
        False. Returning False could mask legitimate errors, making it appear
        the user simply doesn't have the permission when in fact the check failed.
        Callers must explicitly handle the error case.
    """
    try:
        return _get_rbac_repo().has_permission(user_id, permission)
    except Exception as e:
        try:
            redact_logs = get_settings().PII_REDACT_LOGS
        except Exception:
            redact_logs = False
        if redact_logs:
            logger.error(f"RBAC: permission check failed for authenticated user (details redacted), perm={permission}: {e}")
        else:
            logger.error(f"RBAC: permission check failed for user {user_id}, perm={permission}: {e}")
        # SECURITY: Raise instead of returning False to force callers to handle error
        raise RBACError(f"Failed to check permission {permission}: {e}") from e
