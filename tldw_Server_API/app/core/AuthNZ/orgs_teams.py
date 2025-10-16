from __future__ import annotations

from typing import Optional, Dict, Any, List
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, DatabasePool


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
            row = await conn.fetchrow(
                """
                INSERT INTO organizations (name, slug, owner_user_id, metadata)
                VALUES ($1, $2, $3, $4)
                RETURNING id, name, slug, owner_user_id, is_active, created_at, updated_at
                """,
                name, slug, owner_user_id, (metadata if metadata is not None else None),
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


async def list_organizations(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    pool = await get_db_pool()
    if pool.pool:
        rows = await pool.fetchall(
            "SELECT id, name, slug, owner_user_id, is_active, created_at, updated_at FROM organizations ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit, offset,
        )
        return rows
    else:
        async with pool.acquire() as conn:
            cursor = await conn.execute(
                "SELECT id, name, slug, owner_user_id, is_active, created_at, updated_at FROM organizations ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "id": r[0], "name": r[1], "slug": r[2], "owner_user_id": r[3],
                    "is_active": bool(r[4]), "created_at": r[5], "updated_at": r[6]
                } for r in rows
            ]


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
                org_id, user_id,
            )
            return dict(row) if row else {"org_id": org_id, "user_id": user_id, "role": role}
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
                    return {"org_id": row[0], "user_id": row[1], "role": row[2]}
                except Exception:
                    return dict(row)
            return {"org_id": org_id, "user_id": user_id, "role": role}


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
            row = await conn.fetchrow(
                "DELETE FROM org_members WHERE org_id = $1 AND user_id = $2 RETURNING org_id, user_id",
                org_id, user_id,
            )
            removed = row is not None
        else:
            # SQLite: check rowcount
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
        return {"org_id": int(org_id), "user_id": int(user_id), "removed": bool(removed)}


async def update_org_member_role(*, org_id: int, user_id: int, role: str) -> Optional[Dict[str, Any]]:
    """Update an org member's role; returns updated row or None if missing."""
    pool = await get_db_pool()
    async with pool.transaction() as conn:
        if hasattr(conn, 'fetchrow'):
            row = await conn.fetchrow(
                "UPDATE org_members SET role = $3 WHERE org_id = $1 AND user_id = $2 RETURNING org_id, user_id, role",
                org_id, user_id, role,
            )
            return dict(row) if row else None
        else:
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
            logger.error(f"Failed to remove team member user_id={user_id} from team_id={team_id}: {e}")
            return {"team_id": int(team_id), "user_id": int(user_id), "removed": False}
