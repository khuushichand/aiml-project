"""
MCP Tool Catalog Management for Org/Team leads (non-admin paths)

Allows organization owners/admins and team leads/admins to manage tool catalogs
within their scope. Admins also permitted.
"""

from __future__ import annotations

from typing import Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_user, get_db_transaction
from tldw_Server_API.app.core.AuthNZ.database import is_postgres_backend
from tldw_Server_API.app.core.AuthNZ.orgs_teams import list_org_members, list_team_members
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    ToolCatalogCreateRequest,
    ToolCatalogResponse,
    ToolCatalogEntryCreateRequest,
    ToolCatalogEntryResponse,
)


router = APIRouter(prefix="", tags=["mcp-catalogs-scope"])


def _is_manager(role: Optional[str]) -> bool:
    if not role:
        return False
    r = str(role).lower()
    return r in {"owner", "admin", "lead"}


async def _require_org_manager(user: dict, org_id: int) -> None:
    # Admin bypass
    if str(user.get("role", "")).lower() == "admin":
        return
    # Check org membership
    try:
        members = await list_org_members(org_id=org_id, limit=1000, offset=0)
        uid = int(user.get("id"))
        for m in members:
            try:
                if int(m.get("user_id")) == uid and _is_manager(m.get("role")):
                    return
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"Org manager check failed: {e}")
    raise HTTPException(status_code=403, detail="Org manager role required")


async def _require_team_manager(user: dict, team_id: int) -> None:
    # Admin bypass
    if str(user.get("role", "")).lower() == "admin":
        return
    try:
        members = await list_team_members(team_id)
        uid = int(user.get("id"))
        for m in members:
            try:
                if int(m.get("user_id")) == uid and _is_manager(m.get("role")):
                    return
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"Team manager check failed: {e}")
    raise HTTPException(status_code=403, detail="Team manager role required")


@router.get(
    "/orgs/{org_id}/mcp/tool_catalogs",
    response_model=List[ToolCatalogResponse],
    summary="List org-scoped MCP tool catalogs",
    description=(
        "List all MCP tool catalogs scoped to the specified organization.\n\n"
        "RBAC: Requires an org manager (owner/admin/lead) in this organization or a global admin.\n\n"
        "Scope: Results include only catalogs with `org_id` matching the path and `team_id` NULL."
    ),
)
async def list_org_tool_catalogs(
    org_id: int,
    user: dict = Depends(get_current_user),
    db=Depends(get_db_transaction),
) -> List[ToolCatalogResponse]:
    await _require_org_manager(user, org_id)
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            rows = await db.fetch(
                "SELECT id, name, description, org_id, team_id, COALESCE(is_active, TRUE) as is_active, created_at, updated_at FROM tool_catalogs WHERE org_id = $1 ORDER BY created_at DESC",
                org_id,
            )
            return [ToolCatalogResponse(**dict(r)) for r in rows]
        else:
            cur = await db.execute(
                "SELECT id, name, description, org_id, team_id, COALESCE(is_active,1), created_at, updated_at FROM tool_catalogs WHERE org_id = ? ORDER BY created_at DESC",
                (org_id,),
            )
            rows = await cur.fetchall()
            return [
                ToolCatalogResponse(
                    id=r[0], name=r[1], description=r[2], org_id=r[3], team_id=r[4], is_active=bool(r[5]), created_at=r[6], updated_at=r[7]
                ) for r in rows
            ]
    except Exception as e:
        logger.error(f"Failed to list org tool catalogs: {e}")
        raise HTTPException(status_code=500, detail="Failed to list org tool catalogs")


@router.post(
    "/orgs/{org_id}/mcp/tool_catalogs",
    response_model=ToolCatalogResponse,
    status_code=201,
    summary="Create new org-scoped MCP tool catalog",
    description=(
        "Create an MCP tool catalog owned by the specified organization.\n\n"
        "RBAC: Requires an org manager (owner/admin/lead) in this organization or a global admin.\n\n"
        "Scope: Catalog is created with `org_id` set and `team_id` NULL. Name must be unique within the org scope."
    ),
)
async def create_org_tool_catalog(
    org_id: int,
    payload: ToolCatalogCreateRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db_transaction),
) -> ToolCatalogResponse:
    await _require_org_manager(user, org_id)
    # Force scope to org
    name = payload.name.strip()
    desc = payload.description
    is_active = bool(payload.is_active if payload.is_active is not None else True)
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute(
                """
                INSERT INTO tool_catalogs (name, description, org_id, team_id, is_active)
                VALUES ($1, $2, $3, NULL, $4) ON CONFLICT (name, org_id, team_id) DO NOTHING
                """,
                name, desc, org_id, is_active,
            )
            row = await db.fetchrow(
                "SELECT id, name, description, org_id, team_id, COALESCE(is_active, TRUE) as is_active, created_at, updated_at FROM tool_catalogs WHERE name = $1 AND org_id = $2 AND team_id IS NULL",
                name, org_id,
            )
            if not row:
                raise HTTPException(status_code=409, detail="Catalog already exists")
            return ToolCatalogResponse(**dict(row))
        else:
            cur = await db.execute(
                "SELECT id FROM tool_catalogs WHERE name = ? AND org_id = ? AND team_id IS NULL",
                (name, org_id),
            )
            if await cur.fetchone():
                raise HTTPException(status_code=409, detail="Catalog already exists")
            await db.execute(
                "INSERT INTO tool_catalogs (name, description, org_id, team_id, is_active) VALUES (?, ?, ?, NULL, ?)",
                (name, desc, org_id, 1 if is_active else 0),
            )
            cur2 = await db.execute(
                "SELECT id, name, description, org_id, team_id, is_active, created_at, updated_at FROM tool_catalogs WHERE name = ? AND org_id = ? AND team_id IS NULL",
                (name, org_id),
            )
            r = await cur2.fetchone()
            return ToolCatalogResponse(
                id=r[0], name=r[1], description=r[2], org_id=r[3], team_id=r[4], is_active=bool(r[5]), created_at=r[6], updated_at=r[7]
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create org tool catalog: {e}")
        raise HTTPException(status_code=500, detail="Failed to create tool catalog")


@router.get(
    "/teams/{team_id}/mcp/tool_catalogs",
    response_model=List[ToolCatalogResponse],
    summary="List team-scoped MCP tool catalogs",
    description=(
        "List all MCP tool catalogs scoped to the specified team.\n\n"
        "RBAC: Requires a team manager (owner/admin/lead) on this team or a global admin.\n\n"
        "Scope: Results include only catalogs with `team_id` matching the path."
    ),
)
async def list_team_tool_catalogs(
    team_id: int,
    user: dict = Depends(get_current_user),
    db=Depends(get_db_transaction),
) -> List[ToolCatalogResponse]:
    await _require_team_manager(user, team_id)
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            rows = await db.fetch(
                "SELECT id, name, description, org_id, team_id, COALESCE(is_active, TRUE) as is_active, created_at, updated_at FROM tool_catalogs WHERE team_id = $1 ORDER BY created_at DESC",
                team_id,
            )
            return [ToolCatalogResponse(**dict(r)) for r in rows]
        else:
            cur = await db.execute(
                "SELECT id, name, description, org_id, team_id, COALESCE(is_active,1), created_at, updated_at FROM tool_catalogs WHERE team_id = ? ORDER BY created_at DESC",
                (team_id,),
            )
            rows = await cur.fetchall()
            return [
                ToolCatalogResponse(
                    id=r[0], name=r[1], description=r[2], org_id=r[3], team_id=r[4], is_active=bool(r[5]), created_at=r[6], updated_at=r[7]
                ) for r in rows
            ]
    except Exception as e:
        logger.error(f"Failed to list team tool catalogs: {e}")
        raise HTTPException(status_code=500, detail="Failed to list team tool catalogs")


@router.post(
    "/teams/{team_id}/mcp/tool_catalogs",
    response_model=ToolCatalogResponse,
    status_code=201,
    summary="Create new team-scoped MCP tool catalog",
    description=(
        "Create an MCP tool catalog owned by the specified team.\n\n"
        "RBAC: Requires a team manager (owner/admin/lead) on this team or a global admin.\n\n"
        "Scope: Catalog is created with `team_id` set. Name must be unique within the team scope."
    ),
)
async def create_team_tool_catalog(
    team_id: int,
    payload: ToolCatalogCreateRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db_transaction),
) -> ToolCatalogResponse:
    await _require_team_manager(user, team_id)
    name = payload.name.strip()
    desc = payload.description
    is_active = bool(payload.is_active if payload.is_active is not None else True)
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            await db.execute(
                "INSERT INTO tool_catalogs (name, description, org_id, team_id, is_active) VALUES ($1, $2, NULL, $3, $4) ON CONFLICT (name, org_id, team_id) DO NOTHING",
                name, desc, team_id, is_active,
            )
            row = await db.fetchrow(
                "SELECT id, name, description, org_id, team_id, COALESCE(is_active, TRUE) as is_active, created_at, updated_at FROM tool_catalogs WHERE name = $1 AND team_id = $2",
                name, team_id,
            )
            if not row:
                raise HTTPException(status_code=409, detail="Catalog already exists")
            return ToolCatalogResponse(**dict(row))
        else:
            cur = await db.execute(
                "SELECT id FROM tool_catalogs WHERE name = ? AND team_id = ?",
                (name, team_id),
            )
            if await cur.fetchone():
                raise HTTPException(status_code=409, detail="Catalog already exists")
            await db.execute(
                "INSERT INTO tool_catalogs (name, description, org_id, team_id, is_active) VALUES (?, ?, NULL, ?, ?)",
                (name, desc, team_id, 1 if is_active else 0),
            )
            cur2 = await db.execute(
                "SELECT id, name, description, org_id, team_id, is_active, created_at, updated_at FROM tool_catalogs WHERE name = ? AND team_id = ?",
                (name, team_id),
            )
            r = await cur2.fetchone()
            return ToolCatalogResponse(
                id=r[0], name=r[1], description=r[2], org_id=r[3], team_id=r[4], is_active=bool(r[5]), created_at=r[6], updated_at=r[7]
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create team tool catalog: {e}")
        raise HTTPException(status_code=500, detail="Failed to create tool catalog")


@router.post(
    "/orgs/{org_id}/mcp/tool_catalogs/{catalog_id}/entries",
    response_model=ToolCatalogEntryResponse,
    status_code=201,
    summary="Add tool entry to an org-scoped catalog",
    description=(
        "Add a tool entry to an org-scoped catalog. Idempotent per (catalog_id, tool_name).\n\n"
        "RBAC: Requires an org manager (owner/admin/lead) in this organization or a global admin.\n\n"
        "Scope: Fails with 404 if the catalog is not owned by the specified org."
    ),
)
async def add_org_catalog_entry(org_id: int, catalog_id: int, payload: ToolCatalogEntryCreateRequest, user: dict = Depends(get_current_user), db=Depends(get_db_transaction)) -> ToolCatalogEntryResponse:
    await _require_org_manager(user, org_id)
    # Confirm catalog scope
    is_pg = await is_postgres_backend()
    if is_pg:
        owner = await db.fetchrow("SELECT id FROM tool_catalogs WHERE id = $1 AND org_id = $2", catalog_id, org_id)
    else:
        cur = await db.execute("SELECT id FROM tool_catalogs WHERE id = ? AND org_id = ?", (catalog_id, org_id))
        owner = await cur.fetchone()
    if not owner:
        raise HTTPException(status_code=404, detail="Catalog not found in org")
    # Upsert entry
    tool = payload.tool_name.strip()
    module_id = payload.module_id.strip() if payload.module_id else None
    if is_pg:
        await db.execute(
            "INSERT INTO tool_catalog_entries (catalog_id, tool_name, module_id) VALUES ($1, $2, $3) ON CONFLICT (catalog_id, tool_name) DO NOTHING",
            catalog_id, tool, module_id,
        )
        row = await db.fetchrow("SELECT catalog_id, tool_name, module_id FROM tool_catalog_entries WHERE catalog_id = $1 AND tool_name = $2", catalog_id, tool)
        return ToolCatalogEntryResponse(**dict(row)) if row else ToolCatalogEntryResponse(catalog_id=catalog_id, tool_name=tool, module_id=module_id)
    else:
        cur = await db.execute("SELECT catalog_id, tool_name, module_id FROM tool_catalog_entries WHERE catalog_id = ? AND tool_name = ?", (catalog_id, tool))
        r = await cur.fetchone()
        if not r:
            await db.execute("INSERT OR IGNORE INTO tool_catalog_entries (catalog_id, tool_name, module_id) VALUES (?, ?, ?)", (catalog_id, tool, module_id))
            await db.commit()
            cur2 = await db.execute("SELECT catalog_id, tool_name, module_id FROM tool_catalog_entries WHERE catalog_id = ? AND tool_name = ?", (catalog_id, tool))
            r = await cur2.fetchone()
        return ToolCatalogEntryResponse(catalog_id=r[0], tool_name=r[1], module_id=r[2]) if r else ToolCatalogEntryResponse(catalog_id=catalog_id, tool_name=tool, module_id=module_id)


@router.post(
    "/teams/{team_id}/mcp/tool_catalogs/{catalog_id}/entries",
    response_model=ToolCatalogEntryResponse,
    status_code=201,
    summary="Add tool entry to a team-scoped catalog",
    description=(
        "Add a tool entry to a team-scoped catalog. Idempotent per (catalog_id, tool_name).\n\n"
        "RBAC: Requires a team manager (owner/admin/lead) on this team or a global admin.\n\n"
        "Scope: Fails with 404 if the catalog is not owned by the specified team."
    ),
)
async def add_team_catalog_entry(team_id: int, catalog_id: int, payload: ToolCatalogEntryCreateRequest, user: dict = Depends(get_current_user), db=Depends(get_db_transaction)) -> ToolCatalogEntryResponse:
    await _require_team_manager(user, team_id)
    is_pg = await is_postgres_backend()
    if is_pg:
        owner = await db.fetchrow("SELECT id FROM tool_catalogs WHERE id = $1 AND team_id = $2", catalog_id, team_id)
    else:
        cur = await db.execute("SELECT id FROM tool_catalogs WHERE id = ? AND team_id = ?", (catalog_id, team_id))
        owner = await cur.fetchone()
    if not owner:
        raise HTTPException(status_code=404, detail="Catalog not found in team")
    tool = payload.tool_name.strip()
    module_id = payload.module_id.strip() if payload.module_id else None
    if is_pg:
        await db.execute(
            "INSERT INTO tool_catalog_entries (catalog_id, tool_name, module_id) VALUES ($1, $2, $3) ON CONFLICT (catalog_id, tool_name) DO NOTHING",
            catalog_id, tool, module_id,
        )
        row = await db.fetchrow("SELECT catalog_id, tool_name, module_id FROM tool_catalog_entries WHERE catalog_id = $1 AND tool_name = $2", catalog_id, tool)
        return ToolCatalogEntryResponse(**dict(row)) if row else ToolCatalogEntryResponse(catalog_id=catalog_id, tool_name=tool, module_id=module_id)
    else:
        cur = await db.execute("SELECT catalog_id, tool_name, module_id FROM tool_catalog_entries WHERE catalog_id = ? AND tool_name = ?", (catalog_id, tool))
        r = await cur.fetchone()
        if not r:
            await db.execute("INSERT OR IGNORE INTO tool_catalog_entries (catalog_id, tool_name, module_id) VALUES (?, ?, ?)", (catalog_id, tool, module_id))
            await db.commit()
            cur2 = await db.execute("SELECT catalog_id, tool_name, module_id FROM tool_catalog_entries WHERE catalog_id = ? AND tool_name = ?", (catalog_id, tool))
            r = await cur2.fetchone()
        return ToolCatalogEntryResponse(catalog_id=r[0], tool_name=r[1], module_id=r[2]) if r else ToolCatalogEntryResponse(catalog_id=catalog_id, tool_name=tool, module_id=module_id)


@router.delete(
    "/orgs/{org_id}/mcp/tool_catalogs/{catalog_id}",
    summary="Delete an org-scoped catalog (cascade entries)",
    description=(
        "Delete an org-owned catalog. Entries are removed via ON DELETE CASCADE.\n\n"
        "RBAC: Requires an org manager (owner/admin/lead) in this organization or a global admin.\n\n"
        "Scope: Returns 404 if the catalog does not belong to the specified org."
    ),
)
async def delete_org_tool_catalog(org_id: int, catalog_id: int, user: dict = Depends(get_current_user), db=Depends(get_db_transaction)) -> dict:
    """Delete an org-scoped tool catalog (entries cascade).

    Requires the requester to be an org manager (owner/admin/lead) or global admin.
    """
    await _require_org_manager(user, org_id)
    try:
        is_pg = await is_postgres_backend()
        # Ensure catalog belongs to org
        if is_pg:
            owner = await db.fetchrow("SELECT id FROM tool_catalogs WHERE id = $1 AND org_id = $2", catalog_id, org_id)
            if not owner:
                raise HTTPException(status_code=404, detail="Catalog not found in org")
            await db.execute("DELETE FROM tool_catalogs WHERE id = $1", catalog_id)
        else:
            cur = await db.execute("SELECT id FROM tool_catalogs WHERE id = ? AND org_id = ?", (catalog_id, org_id))
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Catalog not found in org")
            await db.execute("DELETE FROM tool_catalogs WHERE id = ?", (catalog_id,))
            await db.commit()
        return {"message": "Catalog deleted", "id": catalog_id, "scope": {"org_id": org_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete org tool catalog {catalog_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete tool catalog")


@router.delete(
    "/orgs/{org_id}/mcp/tool_catalogs/{catalog_id}/entries/{tool_name}",
    summary="Remove tool entry from an org-scoped catalog",
    description=(
        "Remove a tool entry from an org-owned catalog.\n\n"
        "RBAC: Requires an org manager (owner/admin/lead) in this organization or a global admin.\n\n"
        "Scope: Returns 404 if the catalog does not belong to the specified org."
    ),
)
async def delete_org_catalog_entry(org_id: int, catalog_id: int, tool_name: str, user: dict = Depends(get_current_user), db=Depends(get_db_transaction)) -> dict:
    """Remove a tool entry from an org-scoped catalog.

    Requires the requester to be an org manager (owner/admin/lead) or global admin.
    """
    await _require_org_manager(user, org_id)
    try:
        is_pg = await is_postgres_backend()
        # Verify scope
        if is_pg:
            owner = await db.fetchrow("SELECT id FROM tool_catalogs WHERE id = $1 AND org_id = $2", catalog_id, org_id)
            if not owner:
                raise HTTPException(status_code=404, detail="Catalog not found in org")
            await db.execute("DELETE FROM tool_catalog_entries WHERE catalog_id = $1 AND tool_name = $2", catalog_id, tool_name)
        else:
            cur = await db.execute("SELECT id FROM tool_catalogs WHERE id = ? AND org_id = ?", (catalog_id, org_id))
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Catalog not found in org")
            await db.execute(
                "DELETE FROM tool_catalog_entries WHERE catalog_id = ? AND tool_name = ?",
                (catalog_id, tool_name),
            )
            await db.commit()
        return {"message": "Entry deleted", "catalog_id": catalog_id, "tool_name": tool_name, "scope": {"org_id": org_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete org tool catalog entry: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete tool catalog entry")


@router.delete(
    "/teams/{team_id}/mcp/tool_catalogs/{catalog_id}",
    summary="Delete a team-scoped catalog (cascade entries)",
    description=(
        "Delete a team-owned catalog. Entries are removed via ON DELETE CASCADE.\n\n"
        "RBAC: Requires a team manager (owner/admin/lead) on this team or a global admin.\n\n"
        "Scope: Returns 404 if the catalog does not belong to the specified team."
    ),
)
async def delete_team_tool_catalog(team_id: int, catalog_id: int, user: dict = Depends(get_current_user), db=Depends(get_db_transaction)) -> dict:
    """Delete a team-scoped tool catalog (entries cascade).

    Requires the requester to be a team manager (owner/admin/lead) or global admin.
    """
    await _require_team_manager(user, team_id)
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            owner = await db.fetchrow("SELECT id FROM tool_catalogs WHERE id = $1 AND team_id = $2", catalog_id, team_id)
            if not owner:
                raise HTTPException(status_code=404, detail="Catalog not found in team")
            await db.execute("DELETE FROM tool_catalogs WHERE id = $1", catalog_id)
        else:
            cur = await db.execute("SELECT id FROM tool_catalogs WHERE id = ? AND team_id = ?", (catalog_id, team_id))
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Catalog not found in team")
            await db.execute("DELETE FROM tool_catalogs WHERE id = ?", (catalog_id,))
            await db.commit()
        return {"message": "Catalog deleted", "id": catalog_id, "scope": {"team_id": team_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete team tool catalog {catalog_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete tool catalog")


@router.delete(
    "/teams/{team_id}/mcp/tool_catalogs/{catalog_id}/entries/{tool_name}",
    summary="Remove tool entry from a team-scoped catalog",
    description=(
        "Remove a tool entry from a team-owned catalog.\n\n"
        "RBAC: Requires a team manager (owner/admin/lead) on this team or a global admin.\n\n"
        "Scope: Returns 404 if the catalog does not belong to the specified team."
    ),
)
async def delete_team_catalog_entry(team_id: int, catalog_id: int, tool_name: str, user: dict = Depends(get_current_user), db=Depends(get_db_transaction)) -> dict:
    """Remove a tool entry from a team-scoped catalog.

    Requires the requester to be a team manager (owner/admin/lead) or global admin.
    """
    await _require_team_manager(user, team_id)
    try:
        is_pg = await is_postgres_backend()
        if is_pg:
            owner = await db.fetchrow("SELECT id FROM tool_catalogs WHERE id = $1 AND team_id = $2", catalog_id, team_id)
            if not owner:
                raise HTTPException(status_code=404, detail="Catalog not found in team")
            await db.execute("DELETE FROM tool_catalog_entries WHERE catalog_id = $1 AND tool_name = $2", catalog_id, tool_name)
        else:
            cur = await db.execute("SELECT id FROM tool_catalogs WHERE id = ? AND team_id = ?", (catalog_id, team_id))
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Catalog not found in team")
            await db.execute(
                "DELETE FROM tool_catalog_entries WHERE catalog_id = ? AND tool_name = ?",
                (catalog_id, tool_name),
            )
            await db.commit()
        return {"message": "Entry deleted", "catalog_id": catalog_id, "tool_name": tool_name, "scope": {"team_id": team_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete team tool catalog entry: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete tool catalog entry")
