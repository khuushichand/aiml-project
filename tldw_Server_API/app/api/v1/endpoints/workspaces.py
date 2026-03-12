"""Workspace lifecycle CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.schemas.workspace_schemas import (
    WorkspaceArtifactCreateRequest,
    WorkspaceArtifactResponse,
    WorkspaceArtifactUpdateRequest,
    WorkspaceListResponse,
    WorkspaceNoteCreateRequest,
    WorkspaceNoteResponse,
    WorkspaceNoteUpdateRequest,
    WorkspacePatchRequest,
    WorkspaceResponse,
    WorkspaceSourceCreateRequest,
    WorkspaceSourceReorderRequest,
    WorkspaceSourceResponse,
    WorkspaceSourceSelectionRequest,
    WorkspaceSourceUpdateRequest,
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
        banner_title=ws.get("banner_title"),
        banner_subtitle=ws.get("banner_subtitle"),
        banner_color=ws.get("banner_color"),
        audio_provider=ws.get("audio_provider"),
        audio_model=ws.get("audio_model"),
        audio_voice=ws.get("audio_voice"),
        audio_speed=ws.get("audio_speed"),
        created_at=str(ws.get("created_at", "")),
        last_modified=str(ws.get("last_modified", "")),
        version=ws.get("version", 1),
    )


def _src_to_response(src: dict) -> WorkspaceSourceResponse:
    return WorkspaceSourceResponse(
        id=src["id"],
        workspace_id=src["workspace_id"],
        media_id=src["media_id"],
        title=src["title"],
        source_type=src["source_type"],
        url=src.get("url"),
        position=src.get("position", 0),
        selected=bool(src.get("selected", True)),
        added_at=str(src.get("added_at", "")),
        version=src.get("version", 1),
    )


def _art_to_response(art: dict) -> WorkspaceArtifactResponse:
    return WorkspaceArtifactResponse(
        id=art["id"],
        workspace_id=art["workspace_id"],
        artifact_type=art["artifact_type"],
        title=art["title"],
        status=art.get("status", "pending"),
        content=art.get("content"),
        total_tokens=art.get("total_tokens"),
        total_cost_usd=art.get("total_cost_usd"),
        created_at=str(art.get("created_at", "")),
        completed_at=str(art["completed_at"]) if art.get("completed_at") else None,
        version=art.get("version", 1),
    )


def _note_to_response(note: dict) -> WorkspaceNoteResponse:
    return WorkspaceNoteResponse(
        id=note["id"],
        workspace_id=note["workspace_id"],
        title=note["title"],
        content=note["content"],
        keywords_json=note.get("keywords_json", "[]"),
        created_at=str(note.get("created_at", "")),
        last_modified=str(note.get("last_modified", "")),
        version=note.get("version", 1),
    )


def _require_workspace(db: CharactersRAGDB, workspace_id: str) -> dict:
    ws = db.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


# ── Workspace CRUD ──────────────────────────────────────────────

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
    ws = _require_workspace(db, workspace_id)
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
    ws = _require_workspace(db, workspace_id)
    db.delete_workspace(workspace_id, ws["version"])


# ── Sources ─────────────────────────────────────────────────────

@router.get(
    "/{workspace_id}/sources",
    response_model=list[WorkspaceSourceResponse],
    summary="List workspace sources",
)
async def list_sources(
    workspace_id: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    _require_workspace(db, workspace_id)
    return [_src_to_response(s) for s in db.list_workspace_sources(workspace_id)]


@router.post(
    "/{workspace_id}/sources",
    response_model=WorkspaceSourceResponse,
    status_code=201,
    summary="Add source to workspace",
)
async def add_source(
    workspace_id: str,
    body: WorkspaceSourceCreateRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    _require_workspace(db, workspace_id)
    src = db.add_workspace_source(workspace_id, body.model_dump())
    return _src_to_response(src)


@router.put(
    "/{workspace_id}/sources/{source_id}",
    response_model=WorkspaceSourceResponse,
    summary="Update workspace source",
)
async def update_source(
    workspace_id: str,
    source_id: str,
    body: WorkspaceSourceUpdateRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    _require_workspace(db, workspace_id)
    updates = body.model_dump(exclude_unset=True, exclude={"version"})
    try:
        src = db.update_workspace_source(workspace_id, source_id, updates, expected_version=body.version)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _src_to_response(src)


@router.delete(
    "/{workspace_id}/sources/{source_id}",
    status_code=204,
    summary="Delete workspace source",
)
async def delete_source(
    workspace_id: str,
    source_id: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    _require_workspace(db, workspace_id)
    db.delete_workspace_source(workspace_id, source_id)


@router.put(
    "/{workspace_id}/sources/selection",
    status_code=200,
    summary="Batch-update source selection",
)
async def update_source_selection(
    workspace_id: str,
    body: WorkspaceSourceSelectionRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    _require_workspace(db, workspace_id)
    db.update_workspace_source_selection(workspace_id, selected_ids=body.selected_ids)
    return {"ok": True}


@router.put(
    "/{workspace_id}/sources/reorder",
    status_code=200,
    summary="Reorder workspace sources",
)
async def reorder_sources(
    workspace_id: str,
    body: WorkspaceSourceReorderRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    _require_workspace(db, workspace_id)
    db.reorder_workspace_sources(workspace_id, body.ordered_ids)
    return {"ok": True}


# ── Artifacts ───────────────────────────────────────────────────

@router.get(
    "/{workspace_id}/artifacts",
    response_model=list[WorkspaceArtifactResponse],
    summary="List workspace artifacts",
)
async def list_artifacts(
    workspace_id: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    _require_workspace(db, workspace_id)
    return [_art_to_response(a) for a in db.list_workspace_artifacts(workspace_id)]


@router.post(
    "/{workspace_id}/artifacts",
    response_model=WorkspaceArtifactResponse,
    status_code=201,
    summary="Add artifact to workspace",
)
async def add_artifact(
    workspace_id: str,
    body: WorkspaceArtifactCreateRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    _require_workspace(db, workspace_id)
    art = db.add_workspace_artifact(workspace_id, body.model_dump())
    return _art_to_response(art)


@router.put(
    "/{workspace_id}/artifacts/{artifact_id}",
    response_model=WorkspaceArtifactResponse,
    summary="Update workspace artifact",
)
async def update_artifact(
    workspace_id: str,
    artifact_id: str,
    body: WorkspaceArtifactUpdateRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    _require_workspace(db, workspace_id)
    updates = body.model_dump(exclude_unset=True, exclude={"version"})
    try:
        art = db.update_workspace_artifact(workspace_id, artifact_id, updates, expected_version=body.version)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _art_to_response(art)


@router.delete(
    "/{workspace_id}/artifacts/{artifact_id}",
    status_code=204,
    summary="Delete workspace artifact",
)
async def delete_artifact(
    workspace_id: str,
    artifact_id: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    _require_workspace(db, workspace_id)
    db.delete_workspace_artifact(workspace_id, artifact_id)


# ── Notes ───────────────────────────────────────────────────────

@router.get(
    "/{workspace_id}/notes",
    response_model=list[WorkspaceNoteResponse],
    summary="List workspace notes",
)
async def list_notes(
    workspace_id: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    _require_workspace(db, workspace_id)
    return [_note_to_response(n) for n in db.list_workspace_notes(workspace_id)]


@router.post(
    "/{workspace_id}/notes",
    response_model=WorkspaceNoteResponse,
    status_code=201,
    summary="Add note to workspace",
)
async def add_note(
    workspace_id: str,
    body: WorkspaceNoteCreateRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    _require_workspace(db, workspace_id)
    note = db.add_workspace_note(workspace_id, body.model_dump())
    return _note_to_response(note)


@router.put(
    "/{workspace_id}/notes/{note_id}",
    response_model=WorkspaceNoteResponse,
    summary="Update workspace note",
)
async def update_note(
    workspace_id: str,
    note_id: int,
    body: WorkspaceNoteUpdateRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    _require_workspace(db, workspace_id)
    updates = body.model_dump(exclude_unset=True, exclude={"version"})
    try:
        note = db.update_workspace_note(workspace_id, note_id, updates, expected_version=body.version)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _note_to_response(note)


@router.delete(
    "/{workspace_id}/notes/{note_id}",
    status_code=204,
    summary="Delete workspace note",
)
async def delete_note(
    workspace_id: str,
    note_id: int,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    current_user: User = Depends(get_request_user),
):
    _require_workspace(db, workspace_id)
    db.delete_workspace_note(workspace_id, note_id)
