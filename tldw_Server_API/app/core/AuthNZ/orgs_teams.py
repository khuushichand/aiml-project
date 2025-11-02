from __future__ import annotations

from typing import Optional, Dict, Any, List
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, DatabasePool
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.exceptions import DuplicateOrganizationError, DuplicateTeamError


DEFAULT_BASE_TEAM_NAME = "Default-Base"
DEFAULT_BASE_TEAM_SLUG = "default-base"
DEFAULT_BASE_TEAM_DESCRIPTION = "Automatically managed base team for organization-wide membership."


async def _get_or_create_default_team_id(conn, org_id: int, *, create: bool = True) -> Optional[int]:
    """Fetch (and optionally create) the Default-Base team for an organization."""
    is_postgres = hasattr(conn, "fetchrow")
    if is_postgres:
        row = await conn.fetchrow(
            "SELECT id FROM teams WHERE org_id = $1 AND name = $2",
            org_id,
            DEFAULT_BASE_TEAM_NAME,
        )
        if row:
            return int(row["id"])
        if not create:
            return None
        new_row = await conn.fetchrow(
            """
            INSERT INTO teams (org_id, name, slug, description, metadata)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            org_id,
            DEFAULT_BASE_TEAM_NAME,
            DEFAULT_BASE_TEAM_SLUG,
            DEFAULT_BASE_TEAM_DESCRIPTION,
            None,
        )
        return int(new_row["id"])
    # SQLite / aiosqlite connection
    cur = await conn.execute(
        "SELECT id FROM teams WHERE org_id = ? AND name = ?",
        (org_id, DEFAULT_BASE_TEAM_NAME),
    )
    row = await cur.fetchone()
    if row:
        return int(row[0])
    if not create:
        return None
    await conn.execute(
        "INSERT INTO teams (org_id, name, slug, description, metadata) VALUES (?, ?, ?, ?, ?)",
        (org_id, DEFAULT_BASE_TEAM_NAME, DEFAULT_BASE_TEAM_SLUG, DEFAULT_BASE_TEAM_DESCRIPTION, None),
    )
    cur = await conn.execute(
        "SELECT id FROM teams WHERE org_id = ? AND name = ?",
        (org_id, DEFAULT_BASE_TEAM_NAME),
    )
    row = await cur.fetchone()
    return int(row[0]) if row else None


async def _ensure_user_in_default_team(conn, org_id: int, user_id: int) -> None:
    """Ensure the user is enrolled in the organization's Default-Base team."""
    team_id = await _get_or_create_default_team_id(conn, org_id, create=True)
    if team_id is None:
        return
    if hasattr(conn, "execute") and hasattr(conn, "fetchrow"):
        # Postgres
        await conn.execute(
            "INSERT INTO team_members (team_id, user_id, role) VALUES ($1, $2, $3) "
            "ON CONFLICT (team_id, user_id) DO NOTHING",
            team_id,
            user_id,
            "member",
        )
    else:
        await conn.execute(
            "INSERT OR IGNORE INTO team_members (team_id, user_id, role) VALUES (?, ?, ?)",
            (team_id, user_id, "member"),
        )


async def _remove_user_from_default_team(conn, org_id: int, user_id: int) -> None:
    """Remove the user from the organization's Default-Base team if present."""
    team_id = await _get_or_create_default_team_id(conn, org_id, create=False)
    if team_id is None:
        return
    if hasattr(conn, "execute") and hasattr(conn, "fetchrow"):
        await conn.execute(
            "DELETE FROM team_members WHERE team_id = $1 AND user_id = $2",
            team_id,
            user_id,
        )
    else:
        await conn.execute(
            "DELETE FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, user_id),
        )


async def create_organization(
    *,
    name: str,
    owner_user_id: Optional[int] = None,
    slug: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    pool: DatabasePool = await get_db_pool()
    import json
    async with pool.transaction() as conn:
        if hasattr(conn, 'fetchrow'):
            # PostgreSQL path
            # Pre-check for case-insensitive duplicates on name and slug
            if slug is not None and slug != "":
                exists_slug = await conn.fetchrow(
                    "SELECT 1 FROM organizations WHERE LOWER(slug) = LOWER($1)", slug
                )
                if exists_slug:
                    raise DuplicateOrganizationError("slug", str(slug))
            exists_name = await conn.fetchrow(
                "SELECT 1 FROM organizations WHERE LOWER(name) = LOWER($1)", name
            )
            if exists_name:
                raise DuplicateOrganizationError("name", str(name))
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO organizations (name, slug, owner_user_id, metadata)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, name, slug, owner_user_id, is_active, created_at, updated_at
                    """,
                    name, slug, owner_user_id, (metadata if metadata is not None else None),
                )
            except Exception:
                # Unknown error path: re-raise original
                raise
            d = dict(row)
            try:
                from datetime import datetime
                if isinstance(d.get('created_at'), datetime):
                    d['created_at'] = d['created_at'].isoformat()
                if isinstance(d.get('updated_at'), datetime):
                    d['updated_at'] = d['updated_at'].isoformat()
            except Exception:
                pass
            return d
        else:
            # SQLite / aiosqlite path
            # Pre-check for case-insensitive duplicates
            if slug is not None and slug != "":
                cur_chk = await conn.execute(
                    "SELECT 1 FROM organizations WHERE LOWER(slug) = LOWER(?)",
                    (slug,),
                )
                if await cur_chk.fetchone():
                    raise DuplicateOrganizationError("slug", str(slug))
            cur_chk2 = await conn.execute(
                "SELECT 1 FROM organizations WHERE LOWER(name) = LOWER(?)",
                (name,),
            )
            if await cur_chk2.fetchone():
                raise DuplicateOrganizationError("name", str(name))
            cur = await conn.execute(
                "INSERT INTO organizations (name, slug, owner_user_id, metadata) VALUES (?, ?, ?, ?)",
                (name, slug, owner_user_id, json.dumps(metadata) if metadata else None),
            )
            org_id = cur.lastrowid
            await conn.commit()
            cur2 = await conn.execute(
                "SELECT id, name, slug, owner_user_id, is_active, created_at, updated_at FROM organizations WHERE id = ?",
                (org_id,),
            )
            row = await cur2.fetchone()
            return {
                "id": row[0], "name": row[1], "slug": row[2], "owner_user_id": row[3],
                "is_active": bool(row[4]), "created_at": row[5], "updated_at": row[6]
            }


async def list_organizations(
    limit: int = 100,
    offset: int = 0,
    q: Optional[str] = None,
    *,
    with_total: bool = False,
) -> List[Dict[str, Any]] | tuple[List[Dict[str, Any]], int]:
    """List organizations with optional server-side filtering and total count.

    When with_total=True, returns a tuple of (rows, total). Otherwise returns rows only.
    """
    pool = await get_db_pool()
    if pool.pool:
        # Postgres path
        if q:
            like = f"%{str(q).lower()}%"
            rows = await pool.fetchall(
                """
                SELECT id, name, slug, owner_user_id, is_active, created_at, updated_at
                FROM organizations
                WHERE LOWER(name) LIKE $1 OR LOWER(COALESCE(slug, '')) LIKE $1 OR CAST(id AS TEXT) LIKE $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                like, limit, offset,
            )
            total = await pool.fetchval(
                """
                SELECT COUNT(*) FROM organizations
                WHERE LOWER(name) LIKE $1 OR LOWER(COALESCE(slug, '')) LIKE $1 OR CAST(id AS TEXT) LIKE $1
                """,
                like,
            ) if with_total else 0
        else:
            rows = await pool.fetchall(
                "SELECT id, name, slug, owner_user_id, is_active, created_at, updated_at FROM organizations ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, offset,
            )
            total = await pool.fetchval("SELECT COUNT(*) FROM organizations") if with_total else 0
        return (rows, int(total)) if with_total else rows
    else:
        # SQLite / aiosqlite path
        async with pool.acquire() as conn:
            params: list[Any] = []
            if q:
                like = f"%{str(q).lower()}%"
                params = [like, like, like, limit, offset]
                cursor = await conn.execute(
                    """
                    SELECT id, name, slug, owner_user_id, is_active, created_at, updated_at
                    FROM organizations
                    WHERE LOWER(name) LIKE ? OR LOWER(COALESCE(slug, '')) LIKE ? OR CAST(id AS TEXT) LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    params,
                )
                rows_raw = await cursor.fetchall()
                rows = [
                    {
                        "id": r[0], "name": r[1], "slug": r[2], "owner_user_id": r[3],
                        "is_active": bool(r[4]), "created_at": r[5], "updated_at": r[6]
                    } for r in rows_raw
                ]
                if with_total:
                    cur2 = await conn.execute(
                        """
                        SELECT COUNT(*) FROM organizations
                        WHERE LOWER(name) LIKE ? OR LOWER(COALESCE(slug, '')) LIKE ? OR CAST(id AS TEXT) LIKE ?
                        """,
                        (like, like, like),
                    )
                    total_row = await cur2.fetchone()
                    total = int(total_row[0]) if total_row else 0
                else:
                    total = 0
            else:
                cursor = await conn.execute(
                    "SELECT id, name, slug, owner_user_id, is_active, created_at, updated_at FROM organizations ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
                rows_raw = await cursor.fetchall()
                rows = [
                    {
                        "id": r[0], "name": r[1], "slug": r[2], "owner_user_id": r[3],
                        "is_active": bool(r[4]), "created_at": r[5], "updated_at": r[6]
                    } for r in rows_raw
                ]
                if with_total:
                    cur2 = await conn.execute("SELECT COUNT(*) FROM organizations")
                    total_row = await cur2.fetchone()
                    total = int(total_row[0]) if total_row else 0
                else:
                    total = 0
            return (rows, total) if with_total else rows


async def create_team(
    *,
    org_id: int,
    name: str,
    slug: Optional[str] = None,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    pool = await get_db_pool()
    import json
    async with pool.transaction() as conn:
        if hasattr(conn, 'fetchrow'):
            # Pre-check duplicate by (org_id, LOWER(name))
            exists = await conn.fetchrow(
                "SELECT 1 FROM teams WHERE org_id = $1 AND LOWER(name) = LOWER($2)",
                org_id, name,
            )
            if exists:
                raise DuplicateTeamError(org_id, "name", str(name))
            row = await conn.fetchrow(
                """
                INSERT INTO teams (org_id, name, slug, description, metadata)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, org_id, name, slug, description, is_active, created_at, updated_at
                """,
                org_id, name, slug, description, (metadata if metadata is not None else None),
            )
            d = dict(row)
            try:
                from datetime import datetime
                if isinstance(d.get('created_at'), datetime):
                    d['created_at'] = d['created_at'].isoformat()
                if isinstance(d.get('updated_at'), datetime):
                    d['updated_at'] = d['updated_at'].isoformat()
            except Exception:
                pass
            return d
        else:
            # SQLite path: pre-check case-insensitive per-org name
            curx = await conn.execute(
                "SELECT 1 FROM teams WHERE org_id = ? AND LOWER(name) = LOWER(?)",
                (org_id, name),
            )
            if await curx.fetchone():
                raise DuplicateTeamError(org_id, "name", str(name))
            cur = await conn.execute(
                "INSERT INTO teams (org_id, name, slug, description, metadata) VALUES (?, ?, ?, ?, ?)",
                (org_id, name, slug, description, json.dumps(metadata) if metadata else None),
            )
            team_id = cur.lastrowid
            await conn.commit()
            cur2 = await conn.execute(
                "SELECT id, org_id, name, slug, description, is_active, created_at, updated_at FROM teams WHERE id = ?",
                (team_id,),
            )
            row = await cur2.fetchone()
            return {
                "id": row[0], "org_id": row[1], "name": row[2], "slug": row[3], "description": row[4],
                "is_active": bool(row[5]), "created_at": row[6], "updated_at": row[7]
            }


async def add_team_member(*, team_id: int, user_id: int, role: str = "member") -> Dict[str, Any]:
    pool = await get_db_pool()
    async with pool.transaction() as conn:
        if hasattr(conn, 'fetchrow'):
            await conn.execute(
                "INSERT INTO team_members (team_id, user_id, role) VALUES ($1, $2, $3) ON CONFLICT (team_id, user_id) DO NOTHING",
                team_id, user_id, role,
            )
            row = await conn.fetchrow(
                """
                SELECT tm.team_id, tm.user_id, tm.role, t.org_id
                FROM team_members tm JOIN teams t ON tm.team_id = t.id
                WHERE tm.team_id = $1 AND tm.user_id = $2
                """,
                team_id, user_id,
            )
            return dict(row) if row else {"team_id": team_id, "user_id": user_id, "role": role}
        else:
            await conn.execute(
                "INSERT OR IGNORE INTO team_members (team_id, user_id, role) VALUES (?, ?, ?)",
                (team_id, user_id, role),
            )
            await conn.commit()
            cur = await conn.execute(
                """
                SELECT tm.team_id, tm.user_id, tm.role, t.org_id
                FROM team_members tm JOIN teams t ON tm.team_id = t.id
                WHERE tm.team_id = ? AND tm.user_id = ?
                """,
                (team_id, user_id),
            )
            row = await cur.fetchone()
            if row:
                return {"team_id": row[0], "user_id": row[1], "role": row[2], "org_id": row[3]}
            return {"team_id": team_id, "user_id": user_id, "role": role}


async def list_team_members(team_id: int) -> List[Dict[str, Any]]:
    pool = await get_db_pool()
    if pool.pool:
        rows = await pool.fetchall(
            "SELECT user_id, role, status, added_at FROM team_members WHERE team_id = $1 ORDER BY added_at DESC",
            team_id,
        )
        return rows
    else:
        async with pool.acquire() as conn:
            cursor = await conn.execute(
                "SELECT user_id, role, status, added_at FROM team_members WHERE team_id = ? ORDER BY added_at DESC",
                (team_id,),
            )
            rows = await cursor.fetchall()
            return [
                {"user_id": r[0], "role": r[1], "status": r[2], "added_at": r[3]} for r in rows
            ]


async def list_memberships_for_user(user_id: int) -> List[Dict[str, Any]]:
    """List team memberships (and org_id) for a given user.

    Returns: list of {team_id, org_id, role}
    """
    pool = await get_db_pool()
    if pool.pool:
        rows = await pool.fetchall(
            """
            SELECT tm.team_id, tm.user_id, tm.role, t.org_id
            FROM team_members tm JOIN teams t ON tm.team_id = t.id
            WHERE tm.user_id = $1
            ORDER BY tm.team_id
            """,
            user_id,
        )
        # rows already dict in postgres path
        return rows
    else:
        async with pool.acquire() as conn:
            cur = await conn.execute(
                """
                SELECT tm.team_id, tm.user_id, tm.role, t.org_id
                FROM team_members tm JOIN teams t ON tm.team_id = t.id
                WHERE tm.user_id = ?
                ORDER BY tm.team_id
                """,
                (user_id,),
            )
            rows = await cur.fetchall()
            return [
                {"team_id": r[0], "user_id": r[1], "role": r[2], "org_id": r[3]} for r in rows
            ]


# ============================
# Organization membership APIs
# ============================

async def add_org_member(*, org_id: int, user_id: int, role: str = "member") -> Dict[str, Any]:
    """Add a user to an organization (idempotent)."""
    pool = await get_db_pool()
    async with pool.transaction() as conn:
        if hasattr(conn, 'fetchrow'):
            # Postgres
            await conn.execute(
                "INSERT INTO org_members (org_id, user_id, role) VALUES ($1, $2, $3) ON CONFLICT (org_id, user_id) DO NOTHING",
                org_id, user_id, role,
            )
            row = await conn.fetchrow(
                "SELECT org_id, user_id, role FROM org_members WHERE org_id = $1 AND user_id = $2",
                org_id,
                user_id,
            )
            result = dict(row) if row else {"org_id": org_id, "user_id": user_id, "role": role}
            try:
                await _ensure_user_in_default_team(conn, org_id, user_id)
            except Exception as exc:
                logger.warning(
                    f"Default team auto-enroll failed for org_id={org_id}, user_id={user_id}: {exc}"
                )
            return result
        else:
            # SQLite
            await conn.execute(
                "INSERT OR IGNORE INTO org_members (org_id, user_id, role) VALUES (?, ?, ?)",
                (org_id, user_id, role),
            )
            try:
                await conn.commit()
            except Exception:
                pass
            cur = await conn.execute(
                "SELECT org_id, user_id, role FROM org_members WHERE org_id = ? AND user_id = ?",
                (org_id, user_id),
            )
            row = await cur.fetchone()
            if row:
                try:
                    result = {"org_id": row[0], "user_id": row[1], "role": row[2]}
                except Exception:
                    result = dict(row)
            else:
                result = {"org_id": org_id, "user_id": user_id, "role": role}
            try:
                await _ensure_user_in_default_team(conn, org_id, user_id)
            except Exception as exc:
                logger.warning(
                    f"Default team auto-enroll failed for org_id={org_id}, user_id={user_id}: {exc}"
                )
            return result


async def list_org_members(
    *, org_id: int, limit: int = 100, offset: int = 0, role: Optional[str] = None, status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List members of an organization with pagination and optional filters."""
    pool = await get_db_pool()
    if pool.pool:
        # Postgres path
        conditions = ["org_id = $1"]
        params: List[Any] = [org_id]
        p = 1
        if role:
            p += 1
            conditions.append(f"role = ${p}")
            params.append(role)
        if status:
            p += 1
            conditions.append(f"status = ${p}")
            params.append(status)
        where_clause = " AND ".join(conditions)
        p += 1
        params.append(limit)
        p += 1
        params.append(offset)
        sql = (
            f"SELECT user_id, role, status, added_at FROM org_members WHERE {where_clause} "
            f"ORDER BY added_at DESC LIMIT ${p-1} OFFSET ${p}"
        )
        rows = await pool.fetchall(sql, *params)
        return rows
    else:
        # SQLite path
        async with pool.acquire() as conn:
            conditions = ["org_id = ?"]
            params: List[Any] = [org_id]
            if role:
                conditions.append("role = ?")
                params.append(role)
            if status:
                conditions.append("status = ?")
                params.append(status)
            where_clause = " AND ".join(conditions)
            sql = (
                f"SELECT user_id, role, status, added_at FROM org_members WHERE {where_clause} "
                f"ORDER BY added_at DESC LIMIT ? OFFSET ?"
            )
            params.extend([limit, offset])
            cur = await conn.execute(sql, tuple(params))
            rows = await cur.fetchall()
            try:
                return [
                    {"user_id": r[0], "role": r[1], "status": r[2], "added_at": r[3]} for r in rows
                ]
            except Exception:
                return rows


async def remove_org_member(*, org_id: int, user_id: int) -> Dict[str, Any]:
    """Remove a user from an organization. Returns removal status."""
    pool = await get_db_pool()
    async with pool.transaction() as conn:
        removed = False
        if hasattr(conn, 'fetchrow'):
            # PostgreSQL: use RETURNING to detect if a row was deleted
            current_role = await conn.fetchval(
                "SELECT role FROM org_members WHERE org_id = $1 AND user_id = $2",
                org_id,
                user_id,
            )
            if (current_role or "").lower() == "owner":
                owner_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM org_members WHERE org_id = $1 AND role = 'owner'",
                    org_id,
                )
                if owner_count is not None and int(owner_count) <= 1:
                    return {
                        "org_id": int(org_id),
                        "user_id": int(user_id),
                        "removed": False,
                        "error": "owner_required",
                    }
            row = await conn.fetchrow(
                "DELETE FROM org_members WHERE org_id = $1 AND user_id = $2 RETURNING org_id, user_id",
                org_id, user_id,
            )
            removed = row is not None
            if removed:
                try:
                    await _remove_user_from_default_team(conn, org_id, user_id)
                except Exception as exc:
                    logger.warning(
                        f"Default team removal failed for org_id={org_id}, user_id={user_id}: {exc}"
                    )
        else:
            # SQLite: check rowcount
            cur_role = await conn.execute(
                "SELECT role FROM org_members WHERE org_id = ? AND user_id = ?",
                (org_id, user_id),
            )
            role_row = await cur_role.fetchone()
            if role_row and (role_row[0] or "").lower() == "owner":
                owner_count_row = await conn.execute(
                    "SELECT COUNT(*) FROM org_members WHERE org_id = ? AND role = 'owner'",
                    (org_id,),
                )
                owner_count = await owner_count_row.fetchone()
                if owner_count and int(owner_count[0]) <= 1:
                    return {
                        "org_id": int(org_id),
                        "user_id": int(user_id),
                        "removed": False,
                        "error": "owner_required",
                    }
            cur = await conn.execute(
                "DELETE FROM org_members WHERE org_id = ? AND user_id = ?",
                (org_id, user_id),
            )
            try:
                await conn.commit()
            except Exception:
                pass
            try:
                removed = (cur.rowcount or 0) > 0
            except Exception:
                removed = True  # best-effort fallback
            if removed:
                try:
                    await _remove_user_from_default_team(conn, org_id, user_id)
                except Exception as exc:
                    logger.warning(
                        f"Default team removal failed for org_id={org_id}, user_id={user_id}: {exc}"
                    )
        return {"org_id": int(org_id), "user_id": int(user_id), "removed": bool(removed)}


async def update_org_member_role(*, org_id: int, user_id: int, role: str) -> Optional[Dict[str, Any]]:
    """Update an org member's role; returns updated row or None if missing."""
    pool = await get_db_pool()
    target_role = (role or "").lower()
    async with pool.transaction() as conn:
        if hasattr(conn, 'fetchrow'):
            current_role = await conn.fetchval(
                "SELECT role FROM org_members WHERE org_id = $1 AND user_id = $2",
                org_id,
                user_id,
            )
            if current_role is None:
                return None
            if (current_role or "").lower() == "owner" and target_role != "owner":
                owner_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM org_members WHERE org_id = $1 AND role = 'owner'",
                    org_id,
                )
                if owner_count is not None and int(owner_count) <= 1:
                    return {
                        "org_id": int(org_id),
                        "user_id": int(user_id),
                        "role": current_role,
                        "error": "owner_required",
                    }
            row = await conn.fetchrow(
                "UPDATE org_members SET role = $3 WHERE org_id = $1 AND user_id = $2 RETURNING org_id, user_id, role",
                org_id, user_id, role,
            )
            return dict(row) if row else None
        else:
            cur = await conn.execute(
                "SELECT role FROM org_members WHERE org_id = ? AND user_id = ?",
                (org_id, user_id),
            )
            row = await cur.fetchone()
            if not row:
                return None
            current_role = row[0] if not hasattr(row, "keys") else row["role"]
            if (current_role or "").lower() == "owner" and target_role != "owner":
                owner_count_cur = await conn.execute(
                    "SELECT COUNT(*) FROM org_members WHERE org_id = ? AND role = 'owner'",
                    (org_id,),
                )
                owner_count_row = await owner_count_cur.fetchone()
                if owner_count_row and int(owner_count_row[0]) <= 1:
                    return {
                        "org_id": int(org_id),
                        "user_id": int(user_id),
                        "role": current_role,
                        "error": "owner_required",
                    }
            await conn.execute(
                "UPDATE org_members SET role = ? WHERE org_id = ? AND user_id = ?",
                (role, org_id, user_id),
            )
            try:
                await conn.commit()
            except Exception:
                pass
            cur = await conn.execute(
                "SELECT org_id, user_id, role FROM org_members WHERE org_id = ? AND user_id = ?",
                (org_id, user_id),
            )
            row = await cur.fetchone()
            if row:
                try:
                    return {"org_id": row[0], "user_id": row[1], "role": row[2]}
                except Exception:
                    return dict(row)
            return None


async def list_org_memberships_for_user(user_id: int) -> List[Dict[str, Any]]:
    """List org memberships for a given user: [{org_id, role}]."""
    pool = await get_db_pool()
    if pool.pool:
        rows = await pool.fetchall(
            "SELECT org_id, role FROM org_members WHERE user_id = $1 ORDER BY org_id",
            user_id,
        )
        return rows
    else:
        async with pool.acquire() as conn:
            cur = await conn.execute(
                "SELECT org_id, role FROM org_members WHERE user_id = ? ORDER BY org_id",
                (user_id,),
            )
            rows = await cur.fetchall()
            try:
                return [{"org_id": r[0], "role": r[1]} for r in rows]
            except Exception:
                return rows


async def remove_team_member(*, team_id: int, user_id: int) -> Dict[str, Any]:
    """Remove a user from a team. Returns a simple dict with removal status."""
    pool = await get_db_pool()
    async with pool.transaction() as conn:
        try:
            removed = False
            if hasattr(conn, 'fetchrow'):
                row = await conn.fetchrow(
                    "DELETE FROM team_members WHERE team_id = $1 AND user_id = $2 RETURNING team_id, user_id",
                    team_id, user_id,
                )
                removed = row is not None
            else:
                cur = await conn.execute(
                    "DELETE FROM team_members WHERE team_id = ? AND user_id = ?",
                    (team_id, user_id),
                )
                try:
                    await conn.commit()
                except Exception:
                    pass
                try:
                    removed = (cur.rowcount or 0) > 0
                except Exception:
                    removed = True
            return {"team_id": int(team_id), "user_id": int(user_id), "removed": bool(removed)}
        except Exception as e:
            try:
                redact_logs = get_settings().PII_REDACT_LOGS
            except Exception:
                redact_logs = False
            if redact_logs:
                logger.error(f"Failed to remove team member (details redacted) from team_id={team_id}: {e}")
            else:
                logger.error(f"Failed to remove team member user_id={user_id} from team_id={team_id}: {e}")
            return {"team_id": int(team_id), "user_id": int(user_id), "removed": False}
