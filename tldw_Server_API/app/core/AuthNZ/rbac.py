"""
RBAC effective permission helpers for AuthNZ.

This module centralizes read-only calculation of effective permissions and a simple
checker that builds on the configured UserDatabase implementation. It aligns with
AuthNZ/permissions.py which already exposes FastAPI dependencies.
"""

from typing import List
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.db_config import get_configured_user_database
from tldw_Server_API.app.core.AuthNZ.settings import get_settings


def _user_db():
    return get_configured_user_database(client_id="rbac_service")


def get_effective_permissions(user_id: int) -> List[str]:
    """Return the list of effective permissions for a user.

    Combines role-derived permissions with user overrides (allow/deny) using the
    existing UserDatabase logic.
    """
    try:
        db = _user_db()
        return db.get_user_permissions(user_id)
    except Exception as e:
        try:
            redact_logs = get_settings().PII_REDACT_LOGS
        except Exception:
            redact_logs = False
        if redact_logs:
            logger.error(f"RBAC: failed to compute effective permissions for authenticated user (details redacted): {e}")
        else:
            logger.error(f"RBAC: failed to compute effective permissions for user {user_id}: {e}")
        return []


def user_has_permission(user_id: int, permission: str) -> bool:
    """Check if a user has a given permission code."""
    try:
        db = _user_db()
        return db.has_permission(user_id, permission)
    except Exception as e:
        try:
            redact_logs = get_settings().PII_REDACT_LOGS
        except Exception:
            redact_logs = False
        if redact_logs:
            logger.error(f"RBAC: permission check failed for authenticated user (details redacted), perm={permission}: {e}")
        else:
            logger.error(f"RBAC: permission check failed for user {user_id}, perm={permission}: {e}")
        return False
