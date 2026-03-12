"""Workspace lifecycle CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.schemas.workspace_schemas import (
    WorkspaceListResponse,
    WorkspacePatchRequest,
    WorkspaceResponse,
    WorkspaceUpsertRequest,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB, ConflictError

router = APIRouter()


def _ws_to_response(ws: dict) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=ws["id"],
        name=ws.get("name"),
        archived=bool(ws.get("archived", False)),
        deleted=bool(ws.get("deleted", False)),
        created_at=str(ws.get("created_at", "")),
        last_modified=str(ws.get("last_modified", "")),
        version=ws.get("version", 1),
    )


@router.get(
    "/",
    response_model=WorkspaceListResponse,
    summary="List workspaces",
)
async def list_workspaces(
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    """List non-deleted workspaces for the current user."""
    items = db.list_workspaces()
    return WorkspaceListResponse(
        items=[_ws_to_response(w) for w in items],
        total=len(items),
    )


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Get workspace",
)
async def get_workspace(
    workspace_id: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    """Fetch a workspace by ID."""
    ws = db.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _ws_to_response(ws)


@router.put(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Create or update workspace",
)
async def upsert_workspace(
    workspace_id: str,
    body: WorkspaceUpsertRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    """Create or update a workspace (idempotent)."""
    ws = db.upsert_workspace(workspace_id, body.name)
    return _ws_to_response(ws)


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Update workspace",
)
async def patch_workspace(
    workspace_id: str,
    body: WorkspacePatchRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    """Update workspace fields with optimistic locking."""
    updates = body.model_dump(exclude_unset=True, exclude={"version"})
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields to update",
        )
    try:
        ws = db.update_workspace(workspace_id, updates, body.version)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _ws_to_response(ws)


@router.delete(
    "/{workspace_id}",
    status_code=204,
    summary="Delete workspace",
)
async def delete_workspace(
    workspace_id: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    """Soft-delete a workspace and cascade soft-delete its conversations."""
    ws = db.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    db.delete_workspace(workspace_id, ws["version"])
