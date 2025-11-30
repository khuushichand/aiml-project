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
