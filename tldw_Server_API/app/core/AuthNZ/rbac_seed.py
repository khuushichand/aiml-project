"""
rbac_seed.py

Centralized RBAC seed helpers for AuthNZ bootstrap/backstop flows.

This module exists to avoid duplicating "baseline roles/permissions" SQL in
multiple call sites (initialize bootstrap + single-user backstop). The helpers
are intentionally idempotent and safe to call repeatedly.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from loguru import logger

RoleDef = tuple[str, str, bool]
PermissionDef = tuple[str, str, str]


_BASELINE_ROLES: Sequence[RoleDef] = (
    ("admin", "Administrator", True),
    ("user", "Standard User", True),
    ("viewer", "Read-only User", True),
    ("reviewer", "Claims Reviewer", True),
)

_BASELINE_PERMISSIONS: Sequence[PermissionDef] = (
    ("media.read", "Read media", "media"),
    ("media.create", "Create media", "media"),
    ("media.delete", "Delete media", "media"),
    ("system.configure", "Configure system", "system"),
    ("users.manage_roles", "Manage user roles", "users"),
    ("claims.review", "Review claims", "claims"),
    ("claims.admin", "Administer claims", "claims"),
)

_MCP_PERMISSIONS: Sequence[PermissionDef] = (
    ("modules.read", "Read MCP modules", "modules"),
    ("tools.execute:*", "Execute any MCP tool", "tools"),
)


def _is_postgres_connection(conn: Any) -> bool:
    """Return True when the connection looks like an asyncpg connection."""
    return callable(getattr(conn, "fetch", None))


def _build_role_grants(permission_names: Iterable[str], *, include_mcp_permissions: bool) -> dict[str, list[str]]:
    base = set(permission_names)
    grants: dict[str, list[str]] = {
        "user": [p for p in ("media.read", "media.create") if p in base],
        "viewer": [p for p in ("media.read",) if p in base],
        "reviewer": [p for p in ("media.read", "claims.review") if p in base],
        "admin": sorted(base),
    }

    if include_mcp_permissions:
        if "modules.read" in base and "modules.read" not in grants["user"]:
            grants["user"].append("modules.read")
        for p in ("modules.read", "tools.execute:*"):
            if p in base and p not in grants["admin"]:
                grants["admin"].append(p)
    return grants


async def ensure_baseline_rbac_seed(
    conn: Any,
    *,
    include_mcp_permissions: bool = False,
) -> None:
    """
    Ensure baseline RBAC roles, permissions, and role-permission mappings exist.

    This helper is used by both:
    - Postgres bootstrap in initialize.setup_database()
    - Single-user backstop seed in ensure_single_user_rbac_seed_if_needed()

    It is intentionally idempotent (INSERT ... ON CONFLICT / OR IGNORE) and
    should be safe to call repeatedly.
    """
    is_postgres = _is_postgres_connection(conn)

    permissions: list[PermissionDef] = list(_BASELINE_PERMISSIONS)
    if include_mcp_permissions:
        permissions.extend(_MCP_PERMISSIONS)

    grants = _build_role_grants((p[0] for p in permissions), include_mcp_permissions=include_mcp_permissions)

    if is_postgres:
        for name, description, is_system in _BASELINE_ROLES:
            await conn.execute(
                "INSERT INTO roles (name, description, is_system) VALUES ($1, $2, $3) "
                "ON CONFLICT (name) DO NOTHING",
                name,
                description,
                bool(is_system),
            )
        for name, description, category in permissions:
            await conn.execute(
                "INSERT INTO permissions (name, description, category) VALUES ($1, $2, $3) "
                "ON CONFLICT (name) DO NOTHING",
                name,
                description,
                category,
            )

        role_rows = await conn.fetch(
            "SELECT id, name FROM roles WHERE name = ANY($1::text[])",
            [r[0] for r in _BASELINE_ROLES],
        )
        perm_rows = await conn.fetch(
            "SELECT id, name FROM permissions WHERE name = ANY($1::text[])",
            [p[0] for p in permissions],
        )
        role_id = {str(r["name"]): int(r["id"]) for r in role_rows}
        perm_id = {str(p["name"]): int(p["id"]) for p in perm_rows}

        for role_name, perm_names in grants.items():
            rid = role_id.get(role_name)
            if not rid:
                continue
            for perm_name in perm_names:
                pid = perm_id.get(perm_name)
                if not pid:
                    continue
                await conn.execute(
                    "INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2) "
                    "ON CONFLICT (role_id, permission_id) DO NOTHING",
                    rid,
                    pid,
                )
        return

    # SQLite path (aiosqlite)
    for name, description, is_system in _BASELINE_ROLES:
        await conn.execute(
            "INSERT OR IGNORE INTO roles (name, description, is_system) VALUES (?, ?, ?)",
            (name, description, 1 if is_system else 0),
        )
    for name, description, category in permissions:
        await conn.execute(
            "INSERT OR IGNORE INTO permissions (name, description, category) VALUES (?, ?, ?)",
            (name, description, category),
        )

    try:
        role_names = [r[0] for r in _BASELINE_ROLES]
        placeholders = ",".join("?" for _ in role_names)
        cur = await conn.execute(
            f"SELECT id, name FROM roles WHERE name IN ({placeholders})",
            tuple(role_names),
        )
        role_rows = await cur.fetchall()
        role_id = {str(r[1]): int(r[0]) for r in role_rows}
    except Exception as exc:
        logger.debug(f"SQLite RBAC seed: role id lookup failed: {exc}")
        role_id = {}

    try:
        perm_names = [p[0] for p in permissions]
        placeholders = ",".join("?" for _ in perm_names)
        cur = await conn.execute(
            f"SELECT id, name FROM permissions WHERE name IN ({placeholders})",
            tuple(perm_names),
        )
        perm_rows = await cur.fetchall()
        perm_id = {str(p[1]): int(p[0]) for p in perm_rows}
    except Exception as exc:
        logger.debug(f"SQLite RBAC seed: permission id lookup failed: {exc}")
        perm_id = {}

    for role_name, perm_names in grants.items():
        rid = role_id.get(role_name)
        if not rid:
            continue
        for perm_name in perm_names:
            pid = perm_id.get(perm_name)
            if not pid:
                continue
            await conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (rid, pid),
            )
