# permissions.py
# Description: Permission decorators and authorization checks for the AuthNZ system
#
# This module provides decorators and utilities for checking user permissions
# and roles in the tldw_server application.
#
########################################################################################################################

import functools
from typing import List, Optional, Union, Callable, Any
from fastapi import HTTPException, status, Depends
from loguru import logger

# Local imports
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
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
    # In single-user mode, always return True
    if is_single_user_mode():
        return True

    try:
        user_db = get_user_database()
        return user_db.has_permission(user.id, permission)
    except Exception as e:
        try:
            redact = get_settings().PII_REDACT_LOGS
        except Exception:
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
    # In single-user mode, treat as admin
    if is_single_user_mode():
        return role in ['admin', 'user']

    try:
        user_db = get_user_database()
        return user_db.has_role(user.id, role)
    except Exception as e:
        try:
            redact = get_settings().PII_REDACT_LOGS
        except Exception:
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
    # In single-user mode, always return True
    if is_single_user_mode():
        return True

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
    # In single-user mode, always return True
    if is_single_user_mode():
        return True

    for permission in permissions:
        if not check_permission(user, permission):
            return False
    return True

########################################################################################################################
# FastAPI Dependency Functions
########################################################################################################################

class PermissionChecker:
    """
    FastAPI dependency for checking permissions.

    Usage:
        @router.get("/protected")
        def protected_route(user: User = Depends(PermissionChecker("media.read"))):
            return {"message": "You have permission!"}
    """

    def __init__(self, permission: str):
        """
        Initialize permission checker.

        Args:
            permission: Required permission string
        """
        self.permission = permission

    def __call__(self, user: User = Depends(get_request_user)) -> User:
        """
        Check if user has required permission.

        Args:
            user: Current user from request

        Returns:
            User: The authenticated user if permission check passes

        Raises:
            HTTPException: If user lacks required permission
        """
        redact_logs = False
        try:
            current_settings = get_settings()
            redact_logs = current_settings.PII_REDACT_LOGS
        except Exception:
            current_settings = None
        if not check_permission(user, self.permission):
            # Soft-enforce option: log and allow if enabled
            try:
                if current_settings and current_settings.RBAC_SOFT_ENFORCE:
                    if redact_logs:
                        logger.warning(
                            f"[RBAC soft-enforce] Authenticated user lacks '{self.permission}' - allowing (soft mode)"
                        )
                    else:
                        logger.warning(
                            f"[RBAC soft-enforce] User {user.username} lacks '{self.permission}' - allowing (soft mode)"
                        )
                    return user
            except Exception:
                pass
            if redact_logs:
                logger.warning(f"Authenticated user denied access - lacks permission: {self.permission}")
            else:
                logger.warning(f"User {user.username} denied access - lacks permission: {self.permission}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required: {self.permission}"
            )
        return user

class RoleChecker:
    """
    FastAPI dependency for checking roles.

    Usage:
        @router.get("/admin")
        def admin_route(user: User = Depends(RoleChecker("admin"))):
            return {"message": "Welcome admin!"}
    """

    def __init__(self, role: str):
        """
        Initialize role checker.

        Args:
            role: Required role name
        """
        self.role = role

    def __call__(self, user: User = Depends(get_request_user)) -> User:
        """
        Check if user has required role.

        Args:
            user: Current user from request

        Returns:
            User: The authenticated user if role check passes

        Raises:
            HTTPException: If user lacks required role
        """
        redact_logs = False
        try:
            redact_logs = get_settings().PII_REDACT_LOGS
        except Exception:
            pass
        if not check_role(user, self.role):
            if redact_logs:
                logger.warning(f"Authenticated user denied access - lacks role: {self.role}")
            else:
                logger.warning(f"User {user.username} denied access - lacks role: {self.role}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {self.role}"
            )
        return user

class AnyPermissionChecker:
    """
    FastAPI dependency for checking if user has any of the specified permissions.

    Usage:
        @router.get("/content")
        def content_route(user: User = Depends(AnyPermissionChecker(["media.read", "media.update"]))):
            return {"message": "You can access content!"}
    """

    def __init__(self, permissions: List[str]):
        """
        Initialize any-permission checker.

        Args:
            permissions: List of permission strings (user needs at least one)
        """
        self.permissions = permissions

    def __call__(self, user: User = Depends(get_request_user)) -> User:
        """
        Check if user has any of the required permissions.

        Args:
            user: Current user from request

        Returns:
            User: The authenticated user if permission check passes

        Raises:
            HTTPException: If user lacks all required permissions
        """
        redact_logs = False
        try:
            redact_logs = get_settings().PII_REDACT_LOGS
        except Exception:
            pass
        if not check_any_permission(user, self.permissions):
            if redact_logs:
                logger.warning(f"Authenticated user denied access - lacks any of: {self.permissions}")
            else:
                logger.warning(f"User {user.username} denied access - lacks any of: {self.permissions}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Requires one of: {', '.join(self.permissions)}"
            )
        return user

class AllPermissionsChecker:
    """
    FastAPI dependency for checking if user has all specified permissions.

    Usage:
        @router.delete("/critical")
        def critical_operation(user: User = Depends(AllPermissionsChecker(["system.configure", "system.maintenance"]))):
            return {"message": "Critical operation allowed"}
    """

    def __init__(self, permissions: List[str]):
        """
        Initialize all-permissions checker.

        Args:
            permissions: List of permission strings (user needs all)
        """
        self.permissions = permissions

    def __call__(self, user: User = Depends(get_request_user)) -> User:
        """
        Check if user has all required permissions.

        Args:
            user: Current user from request

        Returns:
            User: The authenticated user if permission check passes

        Raises:
            HTTPException: If user lacks any required permission
        """
        redact_logs = False
        try:
            redact_logs = get_settings().PII_REDACT_LOGS
        except Exception:
            pass
        if not check_all_permissions(user, self.permissions):
            if redact_logs:
                logger.warning(f"Authenticated user denied access - lacks all of: {self.permissions}")
            else:
                logger.warning(f"User {user.username} denied access - lacks all of: {self.permissions}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Requires all: {', '.join(self.permissions)}"
            )
        return user

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

# Role names
ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLE_VIEWER = "viewer"
ROLE_CUSTOM = "custom"

#
# End of permissions.py
########################################################################################################################
