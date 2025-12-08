# permissions.py
# Description: Permission decorators and authorization checks for the AuthNZ system
#
# This module provides decorators and utilities for checking user permissions
# and roles in the tldw_server application.
#
########################################################################################################################

import functools
from typing import List, Optional, Union, Callable, Any
from loguru import logger

# Local imports
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.AuthNZ.db_config import get_configured_user_database
from tldw_Server_API.app.core.AuthNZ.settings import is_single_user_mode, get_settings

########################################################################################################################
# Database Instance Management
########################################################################################################################

def get_user_database():
    """
    Get or create the UserDatabase singleton instance using centralized configuration.

    Returns:
        UserDatabase: The user database instance
    """
    return get_configured_user_database(client_id="auth_service")

########################################################################################################################
# Permission Checking Functions
########################################################################################################################

def check_permission(user: User, permission: str) -> bool:
    """
    Check if a user has a specific permission.

    Args:
        user: User object
        permission: Permission string to check

    Returns:
        bool: True if user has permission
    """
    # Prefer permission claims already attached to the request user to avoid
    # re-querying the RBAC store and to ensure consistency with the token's
    # authenticated context (especially in tests where multiple DB pools may
    # exist). This applies in both single-user and multi-user modes.
    perms = getattr(user, "permissions", None)

    if isinstance(perms, (list, tuple, set)):
        # Claims are authoritative when present; if the permission is not listed,
        # treat it as absent without hitting the DB.
        return permission in perms

    # For caller contexts that do not provide claim lists at all (perms is None),
    # fall back to the UserDatabase for compatibility with older code paths.
    # If a non-list value is present (e.g., string, dict), treat that as an
    # explicitly unsupported shape and fail closed without reaching into the DB.
    if perms is not None:
        logger.debug(
            "check_permission: non-list permissions attribute encountered on user; "
            "treating as no permissions and skipping DB lookup"
        )
        return False

    try:
        user_db = get_user_database()
        return user_db.has_permission(user.id, permission)
    except Exception as e:
        try:
            redact = get_settings().PII_REDACT_LOGS
        except Exception as settings_err:
            logger.debug(
                f"check_permission: failed to read PII_REDACT_LOGS; defaulting to non-redacted logging: {settings_err}"
            )
            redact = False
        if redact:
            logger.error(f"Error checking permission {permission} for authenticated user (details redacted): {e}")
        else:
            logger.error(f"Error checking permission {permission} for user {user.id}: {e}")
        return False

def check_role(user: User, role: str) -> bool:
    """
    Check if a user has a specific role.

    Args:
        user: User object
        role: Role name to check

    Returns:
        bool: True if user has role
    """
    # Prefer role claims already attached to the request user for fast-path
    # checks and to avoid depending on a potentially stale UserDatabase
    # singleton that may point at a different backend during tests. This applies
    # in both single-user and multi-user modes.
    roles = getattr(user, "roles", None)

    if isinstance(roles, (list, tuple, set)):
        # Claims are authoritative when present; if the role is not listed,
        # treat it as absent without hitting the DB. An explicit "admin"
        # claim implies both admin- and user-level access regardless of
        # deployment mode so that RBAC semantics are driven purely by claims.
        if "admin" in roles and role in ["admin", "user"]:
            return True
        return role in roles

    # For caller contexts that do not provide claim lists at all (roles is None),
    # fall back to the UserDatabase for compatibility with older code paths.
    # If a non-list value is present, treat that as an explicit "no roles"
    # state and avoid hitting the DB.
    if roles is not None:
        logger.debug(
            "check_role: non-list roles attribute encountered on user; "
            "treating as no roles and skipping DB lookup"
        )
        return False

    try:
        user_db = get_user_database()
        return user_db.has_role(user.id, role)
    except Exception as e:
        try:
            redact = get_settings().PII_REDACT_LOGS
        except Exception as settings_err:
            logger.debug(
                f"check_role: failed to read PII_REDACT_LOGS; defaulting to non-redacted logging: {settings_err}"
            )
            redact = False
        if redact:
            logger.error(f"Error checking role {role} for authenticated user (details redacted): {e}")
        else:
            logger.error(f"Error checking role {role} for user {user.id}: {e}")
        return False

def check_any_permission(user: User, permissions: List[str]) -> bool:
    """
    Check if a user has any of the specified permissions.

    Args:
        user: User object
        permissions: List of permission strings

    Returns:
        bool: True if user has at least one permission
    """
    for permission in permissions:
        if check_permission(user, permission):
            return True
    return False

def check_all_permissions(user: User, permissions: List[str]) -> bool:
    """
    Check if a user has all specified permissions.

    Args:
        user: User object
        permissions: List of permission strings

    Returns:
        bool: True if user has all permissions
    """
    for permission in permissions:
        if not check_permission(user, permission):
            return False
    return True

########################################################################################################################
# Decorator Functions (for non-FastAPI use)
########################################################################################################################

def require_permission(permission: str):
    """
    Decorator to require a specific permission for a function.

    Args:
        permission: Required permission string

    Usage:
        @require_permission("media.delete")
        def delete_media(user: User, media_id: int):
            # Function implementation
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(user: User, *args, **kwargs):
            if not check_permission(user, permission):
                raise PermissionError(f"User {user.username} lacks permission: {permission}")
            return func(user, *args, **kwargs)
        return wrapper
    return decorator

def require_role(role: str):
    """
    Decorator to require a specific role for a function.

    Args:
        role: Required role name

    Usage:
        @require_role("admin")
        def admin_function(user: User):
            # Function implementation
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(user: User, *args, **kwargs):
            if not check_role(user, role):
                raise PermissionError(f"User {user.username} lacks role: {role}")
            return func(user, *args, **kwargs)
        return wrapper
    return decorator

def require_any_permission(permissions: List[str]):
    """
    Decorator to require at least one of the specified permissions.

    Args:
        permissions: List of permission strings

    Usage:
        @require_any_permission(["media.read", "media.update"])
        def access_media(user: User, media_id: int):
            # Function implementation
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(user: User, *args, **kwargs):
            if not check_any_permission(user, permissions):
                raise PermissionError(f"User {user.username} lacks any of: {permissions}")
            return func(user, *args, **kwargs)
        return wrapper
    return decorator

def require_all_permissions(permissions: List[str]):
    """
    Decorator to require all specified permissions.

    Args:
        permissions: List of permission strings

    Usage:
        @require_all_permissions(["system.configure", "system.maintenance"])
        def critical_operation(user: User):
            # Function implementation
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(user: User, *args, **kwargs):
            if not check_all_permissions(user, permissions):
                raise PermissionError(f"User {user.username} lacks all of: {permissions}")
            return func(user, *args, **kwargs)
        return wrapper
    return decorator

########################################################################################################################
# Permission Constants
########################################################################################################################

# Media permissions
MEDIA_CREATE = "media.create"
MEDIA_READ = "media.read"
MEDIA_UPDATE = "media.update"
MEDIA_DELETE = "media.delete"
MEDIA_TRANSCRIBE = "media.transcribe"
MEDIA_EXPORT = "media.export"

# User permissions
USERS_CREATE = "users.create"
USERS_READ = "users.read"
USERS_UPDATE = "users.update"
USERS_DELETE = "users.delete"
USERS_MANAGE_ROLES = "users.manage_roles"
USERS_INVITE = "users.invite"

# System permissions
SYSTEM_CONFIGURE = "system.configure"
SYSTEM_BACKUP = "system.backup"
SYSTEM_EXPORT = "system.export"
SYSTEM_LOGS = "system.logs"
SYSTEM_MAINTENANCE = "system.maintenance"

# API permissions
API_GENERATE_KEYS = "api.generate_keys"
API_MANAGE_WEBHOOKS = "api.manage_webhooks"
API_RATE_LIMIT_OVERRIDE = "api.rate_limit_override"

# Workflows permissions
WORKFLOWS_RUNS_READ = "workflows.runs.read"
WORKFLOWS_RUNS_CONTROL = "workflows.runs.control"
WORKFLOWS_ADMIN = "workflows.admin"

# Notes / graph permissions
NOTES_GRAPH_READ = "notes.graph.read"
NOTES_GRAPH_WRITE = "notes.graph.write"

# Evaluations permissions
EVALS_MANAGE = "evals.manage"
EVALS_READ = "evals.read"

# Flashcards permissions
FLASHCARDS_ADMIN = "flashcards.admin"

# Embeddings permissions
EMBEDDINGS_ADMIN = "embeddings.admin"

# Role names
ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLE_VIEWER = "viewer"
ROLE_CUSTOM = "custom"

#
# End of permissions.py
########################################################################################################################
