from __future__ import annotations

from typing import Any, Dict, List
from loguru import logger
from tldw_Server_API.app.core.AuthNZ.database import is_postgres_backend


async def list_teams_by_org(db, org_id: int, limit: int, offset: int) -> List[Dict[str, Any]]:
    pg = await is_postgres_backend()
    try:
        if pg:
            rows = await db.fetch(
                "SELECT id, org_id, name, slug, description, COALESCE(is_active,TRUE) as is_active, created_at, updated_at FROM teams WHERE org_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                org_id, limit, offset,
            )
            return [dict(r) for r in rows]
        cur = await db.execute(
            "SELECT id, org_id, name, slug, description, COALESCE(is_active,1), created_at, updated_at FROM teams WHERE org_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (org_id, limit, offset),
        )
        rows = await cur.fetchall()
        return [
            {
                "id": r[0],
                "org_id": r[1],
                "name": r[2],
                "slug": r[3],
                "description": r[4],
                "is_active": bool(r[5]),
                "created_at": r[6],
                "updated_at": r[7],
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"admin_orgs_service.list_teams_by_org failed: {e}")
        raise
