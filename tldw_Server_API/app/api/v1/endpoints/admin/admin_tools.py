from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_db_transaction
from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    ToolCatalogCreateRequest,
    ToolCatalogEntryCreateRequest,
    ToolCatalogEntryResponse,
    ToolCatalogResponse,
)
from tldw_Server_API.app.services import admin_tool_catalog_service

router = APIRouter()


@router.get(
    "/mcp/tool_catalogs",
    response_model=list[ToolCatalogResponse],
    summary="List MCP tool catalogs (admin)",
    description=(
        "List MCP tool catalogs across global/org/team scopes.\n\n"
        "RBAC: Admin-only.\n\n"
        "Filters: Optional `org_id` and/or `team_id` parameters restrict results to a given scope.\n"
        "Without filters, returns all catalogs."
    ),
)
async def list_tool_catalogs(
    org_id: int | None = Query(None),
    team_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db=Depends(get_db_transaction),
) -> list[ToolCatalogResponse]:
    """List tool catalogs with optional org/team filtering."""
    try:
        rows = await admin_tool_catalog_service.list_tool_catalogs(
            db,
            org_id=org_id,
            team_id=team_id,
            limit=limit,
            offset=offset,
        )
        return [ToolCatalogResponse(**r) for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to list tool catalogs") from exc


@router.post(
    "/mcp/tool_catalogs",
    response_model=ToolCatalogResponse,
    status_code=201,
    summary="Create MCP tool catalog (admin)",
    description=(
        "Create a new MCP tool catalog in the chosen scope.\n\n"
        "RBAC: Admin-only.\n\n"
        "Scope: Set `org_id` for org-owned, `team_id` for team-owned, or neither for global.\n"
        "Name must be unique per (name, org_id, team_id)."
    ),
)
async def create_tool_catalog(
    payload: ToolCatalogCreateRequest,
    db=Depends(get_db_transaction),
) -> ToolCatalogResponse:
    """Create a tool catalog."""
    try:
        name = payload.name.strip()
        desc = payload.description
        org_id = payload.org_id
        team_id = payload.team_id
        is_active = bool(payload.is_active if payload.is_active is not None else True)
        row = await admin_tool_catalog_service.create_tool_catalog(
            db,
            name=name,
            description=desc,
            org_id=org_id,
            team_id=team_id,
            is_active=is_active,
        )
        return ToolCatalogResponse(**row)
    except ValueError as exc:
        if str(exc) == "Catalog already exists":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Catalog already exists") from exc
        raise HTTPException(status_code=400, detail="Invalid tool catalog") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to create tool catalog") from exc


@router.delete(
    "/mcp/tool_catalogs/{catalog_id}",
    summary="Delete MCP tool catalog (admin)",
    description=(
        "Delete a catalog by id. Entries are removed via ON DELETE CASCADE.\n\n"
        "RBAC: Admin-only.\n\n"
        "Scope: Works for any catalog (global/org/team)."
    ),
)
async def delete_tool_catalog(
    catalog_id: int,
    db=Depends(get_db_transaction),
) -> dict:
    """Delete a tool catalog (entries cascade)."""
    try:
        await admin_tool_catalog_service.delete_tool_catalog(db, catalog_id)
        return {"message": "Catalog deleted", "id": catalog_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to delete tool catalog") from exc


@router.get(
    "/mcp/tool_catalogs/{catalog_id}/entries",
    response_model=list[ToolCatalogEntryResponse],
    summary="List catalog entries (admin)",
    description=(
        "List tools included in the specified catalog.\n\n"
        "RBAC: Admin-only."
    ),
)
async def list_tool_catalog_entries(
    catalog_id: int,
    db=Depends(get_db_transaction),
) -> list[ToolCatalogEntryResponse]:
    """List entries in a tool catalog."""
    try:
        rows = await admin_tool_catalog_service.list_tool_catalog_entries(db, catalog_id)
        return [ToolCatalogEntryResponse(**r) for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to list tool catalog entries") from exc


@router.post(
    "/mcp/tool_catalogs/{catalog_id}/entries",
    response_model=ToolCatalogEntryResponse,
    status_code=201,
    summary="Add tool to catalog (admin)",
    description=(
        "Add a tool entry to the catalog. Idempotent per (catalog_id, tool_name).\n\n"
        "RBAC: Admin-only."
    ),
)
async def add_tool_catalog_entry(
    catalog_id: int,
    payload: ToolCatalogEntryCreateRequest,
    db=Depends(get_db_transaction),
) -> ToolCatalogEntryResponse:
    """Add a tool entry to a catalog (idempotent)."""
    try:
        tool = payload.tool_name.strip()
        module_id = payload.module_id.strip() if payload.module_id else None
        row = await admin_tool_catalog_service.add_tool_catalog_entry(db, catalog_id, tool, module_id)
        return ToolCatalogEntryResponse(**row)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to add tool catalog entry") from exc


@router.delete(
    "/mcp/tool_catalogs/{catalog_id}/entries/{tool_name}",
    summary="Remove tool from catalog (admin)",
    description=(
        "Remove a tool entry from the catalog. Returns 200 whether or not the entry existed.\n\n"
        "RBAC: Admin-only."
    ),
)
async def delete_tool_catalog_entry(
    catalog_id: int,
    tool_name: str,
    db=Depends(get_db_transaction),
) -> dict:
    """Remove a tool from a catalog."""
    try:
        await admin_tool_catalog_service.delete_tool_catalog_entry(db, catalog_id, tool_name)
        return {"message": "Entry deleted", "catalog_id": catalog_id, "tool_name": tool_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to delete tool catalog entry") from exc
