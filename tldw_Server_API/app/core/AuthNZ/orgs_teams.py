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
                name, slug, owner_user_id, json.dumps(metadata) if metadata else None,
            )
            return dict(row)
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
                org_id, name, slug, description, json.dumps(metadata) if metadata else None,
            )
            return dict(row)
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
        if hasattr(conn, 'execute'):
            await conn.execute(
                "INSERT INTO team_members (team_id, user_id, role) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
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
