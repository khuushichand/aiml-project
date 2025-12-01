from __future__ import annotations

from dataclasses import dataclass
from typing import List, TypedDict

from tldw_Server_API.app.core.AuthNZ.db_config import get_configured_user_database


class RolePermissionsResult(TypedDict):
    role_name: str
    permissions: List[str]
    tool_permissions: List[str]
    all_permissions: List[str]


@dataclass
class AuthnzRbacRepo:
    """
    Repository facade for RBAC permission lookups.

    This wrapper centralizes calls into ``UserDatabase_v2`` so that higher-level
    helpers depend on a small, testable surface instead of constructing their
    own database handles.
    """

    client_id: str = "rbac_service"

    def _db(self):
        return get_configured_user_database(client_id=self.client_id)

    def get_effective_permissions(self, user_id: int) -> List[str]:
        """
        Return the effective permission codes for the given user.

        This delegates to the configured RBAC backend (SQLite/Postgres) via
        ``UserDatabase_v2``.
        """
        db = self._db()
        return db.get_user_permissions(user_id)

    def has_permission(self, user_id: int, permission: str) -> bool:
        """Return True when the RBAC backend reports the permission as allowed."""
        db = self._db()
        return db.has_permission(user_id, permission)

    def get_user_roles(self, user_id: int) -> list[dict]:
        """
        Return active roles for a user.

        This wraps the common join between ``roles`` and ``user_roles`` and
        normalizes backend differences so callers do not need to issue their
        own SQL.
        """
        db = self._db()
        result = db.backend.execute(
            """
            SELECT
                r.id,
                r.name,
                r.description,
                COALESCE(r.is_system, 0) AS is_system
            FROM roles r
            JOIN user_roles ur ON r.id = ur.role_id
            WHERE ur.user_id = ?
              AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
            ORDER BY r.name
            """,
            (int(user_id),),
        )
        return [dict(row) for row in result.rows]

    def get_user_overrides(self, user_id: int) -> list[dict]:
        """
        Return user-specific permission overrides.

        Each row includes:
        - permission_id
        - permission_name
        - granted (0/1 or bool)
        - expires_at (backend-native representation)
        """
        db = self._db()
        result = db.backend.execute(
            """
            SELECT
                p.id AS permission_id,
                p.name AS permission_name,
                up.granted,
                up.expires_at
            FROM user_permissions up
            JOIN permissions p ON up.permission_id = p.id
            WHERE up.user_id = ?
            ORDER BY p.name
            """,
            (int(user_id),),
        )
        return [dict(row) for row in result.rows]

    def get_role_effective_permissions(self, role_id: int) -> RolePermissionsResult:
        """
        Return effective permissions for a role, split into regular and tool permissions.

        The response shape mirrors the admin API:
        - role_name
        - permissions
        - tool_permissions
        - all_permissions
        """
        db = self._db()
        # Fetch role information
        role_rows = db.backend.execute(
            "SELECT id, name FROM roles WHERE id = ?",
            (int(role_id),),
        )
        if not role_rows.rows:
            raise KeyError("role_not_found")
        role_name = str(role_rows.rows[0]["name"])

        # Fetch permission names for this role
        perm_rows = db.backend.execute(
            """
            SELECT p.name
            FROM permissions p
            JOIN role_permissions rp ON p.id = rp.permission_id
            WHERE rp.role_id = ?
            ORDER BY p.name
            """,
            (int(role_id),),
        )
        names = [str(r["name"]) for r in perm_rows.rows]

        tool_prefix = "tools.execute:"
        tool_permissions = [n for n in names if n.startswith(tool_prefix)]
        permissions = [n for n in names if not n.startswith(tool_prefix)]
        all_permissions = sorted(set(tool_permissions) | set(permissions))

        return {
            "role_name": role_name,
            "permissions": permissions,
            "tool_permissions": tool_permissions,
            "all_permissions": all_permissions,
        }
