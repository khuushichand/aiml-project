from __future__ import annotations

from typing import Any, Dict, List, Optional
from loguru import logger
from tldw_Server_API.app.core.AuthNZ.database import is_postgres_backend


async def list_tool_catalogs(db, *, org_id: Optional[int], team_id: Optional[int], limit: int, offset: int) -> List[Dict[str, Any]]:
    pg = await is_postgres_backend()
    where: List[str] = []
    params: List[Any] = []
    if org_id is not None:
        where.append("org_id = $1" if pg else "org_id = ?")
        params.append(org_id)
    if team_id is not None:
        if pg:
            where.append(f"team_id = ${len(params)+1}")
        else:
            where.append("team_id = ?")
        params.append(team_id)
    where_clause = (" WHERE " + " AND ".join(where)) if where else ""
    try:
        if pg:
            q = (
                f"SELECT id, name, description, org_id, team_id, COALESCE(is_active,TRUE) as is_active, created_at, updated_at FROM tool_catalogs{where_clause} ORDER BY created_at DESC LIMIT $ {len(params)+1} OFFSET $ {len(params)+2}"
            ).replace('$ ', '$')
            rows = await db.fetch(q, *params, limit, offset)
            return [dict(r) for r in rows]
        cur = await db.execute(
            f"SELECT id, name, description, org_id, team_id, COALESCE(is_active,1), created_at, updated_at FROM tool_catalogs{where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        rows = await cur.fetchall()
        return [
            {"id": r[0], "name": r[1], "description": r[2], "org_id": r[3], "team_id": r[4], "is_active": bool(r[5]), "created_at": r[6], "updated_at": r[7]}
            for r in rows
        ]
    except Exception as e:
        logger.error(f"admin_tool_catalog_service.list_tool_catalogs failed: {e}")
        raise


async def create_tool_catalog(db, *, name: str, description: Optional[str], org_id: Optional[int], team_id: Optional[int], is_active: bool) -> Dict[str, Any]:
    pg = await is_postgres_backend()
    try:
        if pg:
            # Pre-check case-insensitive existence within scope
            exists = await db.fetchrow(
                "SELECT 1 FROM tool_catalogs WHERE LOWER(name) = LOWER($1) AND ((org_id IS NOT DISTINCT FROM $2) AND (team_id IS NOT DISTINCT FROM $3))",
                name, org_id, team_id,
            )
            if exists:
                raise ValueError("Catalog already exists")
            await db.execute(
                "INSERT INTO tool_catalogs (name, description, org_id, team_id, is_active) VALUES ($1,$2,$3,$4,$5)",
                name, description, org_id, team_id, is_active,
            )
            row = await db.fetchrow(
                "SELECT id, name, description, org_id, team_id, COALESCE(is_active, TRUE) as is_active, created_at, updated_at FROM tool_catalogs WHERE name = $1 AND ((org_id IS NOT DISTINCT FROM $2) AND (team_id IS NOT DISTINCT FROM $3))",
                name, org_id, team_id,
            )
            return dict(row)
        # SQLite path
        cur = await db.execute(
            "SELECT id FROM tool_catalogs WHERE LOWER(name) = LOWER(?) AND ( (org_id IS ? OR org_id = ?) AND (team_id IS ? OR team_id = ?) )",
            (name, None, org_id, None, team_id),
        )
        if await cur.fetchone():
            raise ValueError("Catalog already exists")
        await db.execute(
            "INSERT INTO tool_catalogs (name, description, org_id, team_id, is_active) VALUES (?, ?, ?, ?, ?)",
            (name, description, org_id, team_id, 1 if is_active else 0),
        )
        cur2 = await db.execute(
            "SELECT id, name, description, org_id, team_id, is_active, created_at, updated_at FROM tool_catalogs WHERE name = ? AND ( (org_id IS ? OR org_id = ?) AND (team_id IS ? OR team_id = ?) )",
            (name, None, org_id, None, team_id),
        )
        r = await cur2.fetchone()
        return {"id": r[0], "name": r[1], "description": r[2], "org_id": r[3], "team_id": r[4], "is_active": bool(r[5]), "created_at": r[6], "updated_at": r[7]}
    except Exception as e:
        logger.error(f"admin_tool_catalog_service.create_tool_catalog failed: {e}")
        raise


async def delete_tool_catalog(db, catalog_id: int) -> None:
    pg = await is_postgres_backend()
    try:
        if pg:
            await db.execute("DELETE FROM tool_catalogs WHERE id = $1", catalog_id)
            return
        await db.execute("DELETE FROM tool_catalogs WHERE id = ?", (catalog_id,))
        commit = getattr(db, "commit", None)
        if callable(commit):
            await commit()
    except Exception as e:
        logger.error(f"admin_tool_catalog_service.delete_tool_catalog failed: {e}")
        raise


async def list_tool_catalog_entries(db, catalog_id: int) -> List[Dict[str, Any]]:
    pg = await is_postgres_backend()
    try:
        if pg:
            rows = await db.fetch("SELECT catalog_id, tool_name, module_id FROM tool_catalog_entries WHERE catalog_id = $1 ORDER BY tool_name", catalog_id)
            return [dict(r) for r in rows]
        cur = await db.execute("SELECT catalog_id, tool_name, module_id FROM tool_catalog_entries WHERE catalog_id = ? ORDER BY tool_name", (catalog_id,))
        rows = await cur.fetchall()
        return [{"catalog_id": r[0], "tool_name": r[1], "module_id": r[2]} for r in rows]
    except Exception as e:
        logger.error(f"admin_tool_catalog_service.list_tool_catalog_entries failed: {e}")
        raise


async def add_tool_catalog_entry(db, catalog_id: int, tool_name: str, module_id: Optional[str]) -> Dict[str, Any]:
    pg = await is_postgres_backend()
    try:
        if pg:
            await db.execute("INSERT INTO tool_catalog_entries (catalog_id, tool_name, module_id) VALUES ($1,$2,$3) ON CONFLICT (catalog_id, tool_name) DO NOTHING", catalog_id, tool_name, module_id)
            row = await db.fetchrow("SELECT catalog_id, tool_name, module_id FROM tool_catalog_entries WHERE catalog_id = $1 AND tool_name = $2", catalog_id, tool_name)
            return dict(row) if row else {"catalog_id": catalog_id, "tool_name": tool_name, "module_id": module_id}
        cur = await db.execute("SELECT catalog_id, tool_name, module_id FROM tool_catalog_entries WHERE catalog_id = ? AND tool_name = ?", (catalog_id, tool_name))
        r = await cur.fetchone()
        if not r:
            await db.execute("INSERT OR IGNORE INTO tool_catalog_entries (catalog_id, tool_name, module_id) VALUES (?, ?, ?)", (catalog_id, tool_name, module_id))
            commit = getattr(db, "commit", None)
            if callable(commit):
                await commit()
            cur2 = await db.execute("SELECT catalog_id, tool_name, module_id FROM tool_catalog_entries WHERE catalog_id = ? AND tool_name = ?", (catalog_id, tool_name))
            r = await cur2.fetchone()
        return {"catalog_id": r[0], "tool_name": r[1], "module_id": r[2]} if r else {"catalog_id": catalog_id, "tool_name": tool_name, "module_id": module_id}
    except Exception as e:
        logger.error(f"admin_tool_catalog_service.add_tool_catalog_entry failed: {e}")
        raise


async def delete_tool_catalog_entry(db, catalog_id: int, tool_name: str) -> None:
    pg = await is_postgres_backend()
    try:
        if pg:
            await db.execute("DELETE FROM tool_catalog_entries WHERE catalog_id = $1 AND tool_name = $2", catalog_id, tool_name)
            return
        await db.execute("DELETE FROM tool_catalog_entries WHERE catalog_id = ? AND tool_name = ?", (catalog_id, tool_name))
        commit = getattr(db, "commit", None)
        if callable(commit):
            await commit()
    except Exception as e:
        logger.error(f"admin_tool_catalog_service.delete_tool_catalog_entry failed: {e}")
        raise
