"""Manuscript management API endpoints (projects, parts, chapters, scenes)."""
from __future__ import annotations

import json
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.schemas.writing_manuscript_schemas import (
    ChapterSummary,
    ManuscriptChapterCreate,
    ManuscriptChapterResponse,
    ManuscriptChapterUpdate,
    ManuscriptPartCreate,
    ManuscriptPartResponse,
    ManuscriptPartUpdate,
    ManuscriptProjectCreate,
    ManuscriptProjectListResponse,
    ManuscriptProjectResponse,
    ManuscriptProjectUpdate,
    ManuscriptSceneCreate,
    ManuscriptSceneResponse,
    ManuscriptSceneUpdate,
    ManuscriptSearchResponse,
    ManuscriptSearchResult,
    ManuscriptStructureResponse,
    PartSummary,
    ReorderRequest,
    SceneSummary,
)
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
    InputError,
)
from tldw_Server_API.app.core.DB_Management.ManuscriptDB import ManuscriptDBHelper

router = APIRouter()

# ---------------------------------------------------------------------------
# Exception tuple and helpers (mirrors writing.py)
# ---------------------------------------------------------------------------

_MANUSCRIPT_NONCRITICAL_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    CharactersRAGDBError,
    ConflictError,
    ConnectionError,
    FileNotFoundError,
    ImportError,
    IndexError,
    InputError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
    UnicodeDecodeError,
    json.JSONDecodeError,
)



def _handle_db_errors(exc: Exception, entity_label: str) -> NoReturn:
    """Translate database exceptions into HTTP errors."""
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, InputError):
        logger.warning("Input error for {}: {}", entity_label, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        message = str(exc)
        lowered = message.lower()
        # Check "not found" / "soft-deleted" first — the message may also contain
        # "version conflict" (e.g. "version conflict or not found"), and a pure 404
        # should not be reported as 409.
        if ("not found" in lowered or "soft-deleted" in lowered or "soft deleted" in lowered) and "version conflict" not in lowered:
            logger.debug("Entity not found for {}: {}", entity_label, exc)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity_label} not found"
            ) from exc
        logger.warning("Conflict error for {}: {}", entity_label, exc)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message) from exc
    if isinstance(exc, CharactersRAGDBError):
        logger.error("Database error for {}: {}", entity_label, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while processing {entity_label}",
        ) from exc
    logger.exception("Unexpected error for {}: {}", entity_label, exc)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Unexpected error while processing {entity_label}",
    ) from exc


def _get_helper(db: CharactersRAGDB) -> ManuscriptDBHelper:
    """Construct a ManuscriptDBHelper from the per-user DB dependency."""
    return ManuscriptDBHelper(db)


# ===================================================================
# Projects
# ===================================================================


@router.get(
    "/projects",
    response_model=ManuscriptProjectListResponse,
    summary="List manuscript projects",
    tags=["manuscripts"],
)
async def list_projects(
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.list")),
) -> ManuscriptProjectListResponse:
    """List manuscript projects for the current user."""
    try:
        helper = _get_helper(db)
        projects, total = helper.list_projects(
            status_filter=status_filter, limit=limit, offset=offset
        )
        items = [ManuscriptProjectResponse(**p) for p in projects]
        return ManuscriptProjectListResponse(projects=items, total=total)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript projects")


@router.post(
    "/projects",
    response_model=ManuscriptProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manuscript project",
    tags=["manuscripts"],
)
async def create_project(
    payload: ManuscriptProjectCreate,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.create")),
) -> ManuscriptProjectResponse:
    """Create a new manuscript project."""
    try:
        helper = _get_helper(db)
        project_id = helper.create_project(
            title=payload.title.strip(),
            subtitle=payload.subtitle,
            author=payload.author,
            genre=payload.genre,
            status=payload.status,
            synopsis=payload.synopsis,
            target_word_count=payload.target_word_count,
            settings=payload.settings,
            project_id=payload.id,
        )
        project = helper.get_project(project_id)
        if not project:
            raise CharactersRAGDBError("Project created but could not be retrieved")
        return ManuscriptProjectResponse(**project)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript project")


@router.get(
    "/projects/{project_id}",
    response_model=ManuscriptProjectResponse,
    summary="Get a manuscript project",
    tags=["manuscripts"],
)
async def get_project(
    project_id: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.get")),
) -> ManuscriptProjectResponse:
    """Fetch a manuscript project by ID."""
    try:
        helper = _get_helper(db)
        project = helper.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
        return ManuscriptProjectResponse(**project)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript project")


@router.patch(
    "/projects/{project_id}",
    response_model=ManuscriptProjectResponse,
    summary="Update a manuscript project",
    tags=["manuscripts"],
)
async def update_project(
    project_id: str,
    payload: ManuscriptProjectUpdate,
    expected_version: int = Header(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.update")),
) -> ManuscriptProjectResponse:
    """Update a manuscript project with optimistic locking."""
    update_data = payload.model_dump(exclude_none=True)
    if "title" in update_data:
        update_data["title"] = update_data["title"].strip()
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update"
        )
    try:
        helper = _get_helper(db)
        helper.update_project(project_id, update_data, expected_version)
        project = helper.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
        return ManuscriptProjectResponse(**project)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript project")


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a manuscript project",
    tags=["manuscripts"],
)
async def delete_project(
    project_id: str,
    expected_version: int = Header(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.delete")),
) -> Response:
    """Soft-delete a manuscript project."""
    try:
        helper = _get_helper(db)
        helper.soft_delete_project(project_id, expected_version)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript project")


@router.get(
    "/projects/{project_id}/structure",
    response_model=ManuscriptStructureResponse,
    summary="Get full manuscript structure tree",
    tags=["manuscripts"],
)
async def get_project_structure(
    project_id: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.get")),
) -> ManuscriptStructureResponse:
    """Build the hierarchical structure of a manuscript project."""
    try:
        helper = _get_helper(db)
        # Verify project exists
        project = helper.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
        raw = helper.get_project_structure(project_id)

        def _scene_summary(s: dict[str, Any]) -> SceneSummary:
            return SceneSummary(
                id=s["id"],
                title=s["title"],
                sort_order=s["sort_order"],
                word_count=s.get("word_count", 0),
                status=s.get("status", "draft"),
            )

        def _chapter_summary(c: dict[str, Any]) -> ChapterSummary:
            return ChapterSummary(
                id=c["id"],
                title=c["title"],
                sort_order=c["sort_order"],
                part_id=c.get("part_id"),
                word_count=c.get("word_count", 0),
                status=c.get("status", "draft"),
                scenes=[_scene_summary(s) for s in c.get("scenes", [])],
            )

        def _part_summary(p: dict[str, Any]) -> PartSummary:
            return PartSummary(
                id=p["id"],
                title=p["title"],
                sort_order=p["sort_order"],
                word_count=p.get("word_count", 0),
                chapters=[_chapter_summary(c) for c in p.get("chapters", [])],
            )

        return ManuscriptStructureResponse(
            project_id=project_id,
            parts=[_part_summary(p) for p in raw.get("parts", [])],
            unassigned_chapters=[
                _chapter_summary(c) for c in raw.get("unassigned_chapters", [])
            ],
        )
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript structure")


@router.post(
    "/projects/{project_id}/reorder",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Batch reorder parts, chapters, or scenes",
    tags=["manuscripts"],
)
async def reorder_entities(
    project_id: str,
    payload: ReorderRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.update")),
) -> Response:
    """Batch-update sort_order for parts, chapters, or scenes within a project."""
    # Map plural form from schema to singular form used by ManuscriptDBHelper
    entity_type_map = {"parts": "part", "chapters": "chapter", "scenes": "scene"}
    entity_type = entity_type_map[payload.entity_type]

    items = []
    for item in payload.items:
        entry: dict[str, Any] = {"id": item.id, "sort_order": item.sort_order, "version": item.version}
        if item.new_parent_id is not None and entity_type == "chapter":
            entry["part_id"] = item.new_parent_id
        items.append(entry)

    try:
        helper = _get_helper(db)
        helper.reorder_items(entity_type, items, project_id=project_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript reorder")


@router.get(
    "/projects/{project_id}/search",
    response_model=ManuscriptSearchResponse,
    summary="Full-text search across scenes in a project",
    tags=["manuscripts"],
)
async def search_project(
    project_id: str,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.get")),
) -> ManuscriptSearchResponse:
    """Search scenes within a project using FTS5."""
    try:
        helper = _get_helper(db)
        rows = helper.search_scenes(project_id, q, limit=limit)
        results = [
            ManuscriptSearchResult(
                id=r["id"],
                title=r["title"],
                chapter_id=r["chapter_id"],
                word_count=r.get("word_count", 0),
                status=r.get("status", "draft"),
                snippet=r.get("snippet"),
            )
            for r in rows
        ]
        return ManuscriptSearchResponse(query=q, results=results)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript search")


# ===================================================================
# Parts
# ===================================================================


@router.post(
    "/projects/{project_id}/parts",
    response_model=ManuscriptPartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manuscript part",
    tags=["manuscripts"],
)
async def create_part(
    project_id: str,
    payload: ManuscriptPartCreate,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.create")),
) -> ManuscriptPartResponse:
    """Create a new part within a project."""
    try:
        helper = _get_helper(db)
        part_id = helper.create_part(
            project_id=project_id,
            title=payload.title.strip(),
            sort_order=payload.sort_order,
            synopsis=payload.synopsis,
            part_id=payload.id,
        )
        part = helper.get_part(part_id)
        if not part:
            raise CharactersRAGDBError("Part created but could not be retrieved")
        return ManuscriptPartResponse(**part)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript part")


@router.get(
    "/projects/{project_id}/parts",
    response_model=list[ManuscriptPartResponse],
    summary="List parts in a project",
    tags=["manuscripts"],
)
async def list_parts(
    project_id: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.list")),
) -> list[ManuscriptPartResponse]:
    """List all parts within a project."""
    try:
        helper = _get_helper(db)
        parts = helper.list_parts(project_id)
        return [ManuscriptPartResponse(**p) for p in parts]
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript parts")


@router.get(
    "/parts/{part_id}",
    response_model=ManuscriptPartResponse,
    summary="Get a manuscript part",
    tags=["manuscripts"],
)
async def get_part(
    part_id: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.get")),
) -> ManuscriptPartResponse:
    """Fetch a manuscript part by ID."""
    try:
        helper = _get_helper(db)
        part = helper.get_part(part_id)
        if not part:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Part not found"
            )
        return ManuscriptPartResponse(**part)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript part")


@router.patch(
    "/parts/{part_id}",
    response_model=ManuscriptPartResponse,
    summary="Update a manuscript part",
    tags=["manuscripts"],
)
async def update_part(
    part_id: str,
    payload: ManuscriptPartUpdate,
    expected_version: int = Header(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.update")),
) -> ManuscriptPartResponse:
    """Update a manuscript part with optimistic locking."""
    update_data = payload.model_dump(exclude_none=True)
    if "title" in update_data:
        update_data["title"] = update_data["title"].strip()
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update"
        )
    try:
        helper = _get_helper(db)
        helper.update_part(part_id, update_data, expected_version)
        part = helper.get_part(part_id)
        if not part:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Part not found"
            )
        return ManuscriptPartResponse(**part)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript part")


@router.delete(
    "/parts/{part_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a manuscript part",
    tags=["manuscripts"],
)
async def delete_part(
    part_id: str,
    expected_version: int = Header(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.delete")),
) -> Response:
    """Soft-delete a manuscript part."""
    try:
        helper = _get_helper(db)
        helper.soft_delete_part(part_id, expected_version)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript part")


# ===================================================================
# Chapters
# ===================================================================


@router.post(
    "/projects/{project_id}/chapters",
    response_model=ManuscriptChapterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manuscript chapter",
    tags=["manuscripts"],
)
async def create_chapter(
    project_id: str,
    payload: ManuscriptChapterCreate,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.create")),
) -> ManuscriptChapterResponse:
    """Create a new chapter within a project."""
    try:
        helper = _get_helper(db)
        chapter_id = helper.create_chapter(
            project_id=project_id,
            title=payload.title.strip(),
            part_id=payload.part_id,
            sort_order=payload.sort_order,
            synopsis=payload.synopsis,
            status=payload.status,
            chapter_id=payload.id,
        )
        chapter = helper.get_chapter(chapter_id)
        if not chapter:
            raise CharactersRAGDBError("Chapter created but could not be retrieved")
        return ManuscriptChapterResponse(**chapter)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript chapter")


@router.get(
    "/projects/{project_id}/chapters",
    response_model=list[ManuscriptChapterResponse],
    summary="List chapters in a project",
    tags=["manuscripts"],
)
async def list_chapters(
    project_id: str,
    part_id: str | None = Query(None, description="Filter by part ID"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.list")),
) -> list[ManuscriptChapterResponse]:
    """List chapters within a project, optionally filtered by part."""
    try:
        helper = _get_helper(db)
        chapters = helper.list_chapters(project_id, part_id=part_id)
        return [ManuscriptChapterResponse(**c) for c in chapters]
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript chapters")


@router.get(
    "/chapters/{chapter_id}",
    response_model=ManuscriptChapterResponse,
    summary="Get a manuscript chapter",
    tags=["manuscripts"],
)
async def get_chapter(
    chapter_id: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.get")),
) -> ManuscriptChapterResponse:
    """Fetch a manuscript chapter by ID."""
    try:
        helper = _get_helper(db)
        chapter = helper.get_chapter(chapter_id)
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
            )
        return ManuscriptChapterResponse(**chapter)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript chapter")


@router.patch(
    "/chapters/{chapter_id}",
    response_model=ManuscriptChapterResponse,
    summary="Update a manuscript chapter",
    tags=["manuscripts"],
)
async def update_chapter(
    chapter_id: str,
    payload: ManuscriptChapterUpdate,
    expected_version: int = Header(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.update")),
) -> ManuscriptChapterResponse:
    """Update a manuscript chapter with optimistic locking."""
    update_data = payload.model_dump(exclude_none=True)
    if "title" in update_data:
        update_data["title"] = update_data["title"].strip()
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update"
        )
    try:
        helper = _get_helper(db)
        helper.update_chapter(chapter_id, update_data, expected_version)
        chapter = helper.get_chapter(chapter_id)
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
            )
        return ManuscriptChapterResponse(**chapter)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript chapter")


@router.delete(
    "/chapters/{chapter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a manuscript chapter",
    tags=["manuscripts"],
)
async def delete_chapter(
    chapter_id: str,
    expected_version: int = Header(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.delete")),
) -> Response:
    """Soft-delete a manuscript chapter."""
    try:
        helper = _get_helper(db)
        helper.soft_delete_chapter(chapter_id, expected_version)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript chapter")


# ===================================================================
# Scenes
# ===================================================================


@router.post(
    "/chapters/{chapter_id}/scenes",
    response_model=ManuscriptSceneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manuscript scene",
    tags=["manuscripts"],
)
async def create_scene(
    chapter_id: str,
    payload: ManuscriptSceneCreate,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.create")),
) -> ManuscriptSceneResponse:
    """Create a new scene within a chapter.

    The project_id is resolved from the chapter's parent project.
    """
    try:
        helper = _get_helper(db)
        # Resolve project_id from the chapter
        chapter = helper.get_chapter(chapter_id)
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
            )
        project_id = chapter["project_id"]

        content_json = None
        if payload.content is not None:
            content_json = json.dumps(payload.content)

        scene_id = helper.create_scene(
            chapter_id=chapter_id,
            project_id=project_id,
            title=payload.title.strip(),
            content_json=content_json,
            content_plain=payload.content_plain,
            synopsis=payload.synopsis,
            sort_order=payload.sort_order,
            status=payload.status,
            scene_id=payload.id,
        )
        scene = helper.get_scene(scene_id)
        if not scene:
            raise CharactersRAGDBError("Scene created but could not be retrieved")
        return ManuscriptSceneResponse(**scene)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript scene")


@router.get(
    "/chapters/{chapter_id}/scenes",
    response_model=list[ManuscriptSceneResponse],
    summary="List scenes in a chapter",
    tags=["manuscripts"],
)
async def list_scenes(
    chapter_id: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.list")),
) -> list[ManuscriptSceneResponse]:
    """List all scenes within a chapter."""
    try:
        helper = _get_helper(db)
        scenes = helper.list_scenes(chapter_id)
        return [ManuscriptSceneResponse(**s) for s in scenes]
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript scenes")


@router.get(
    "/scenes/{scene_id}",
    response_model=ManuscriptSceneResponse,
    summary="Get a manuscript scene",
    tags=["manuscripts"],
)
async def get_scene(
    scene_id: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.get")),
) -> ManuscriptSceneResponse:
    """Fetch a manuscript scene by ID."""
    try:
        helper = _get_helper(db)
        scene = helper.get_scene(scene_id)
        if not scene:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found"
            )
        return ManuscriptSceneResponse(**scene)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript scene")


@router.patch(
    "/scenes/{scene_id}",
    response_model=ManuscriptSceneResponse,
    summary="Update a manuscript scene",
    tags=["manuscripts"],
)
async def update_scene(
    scene_id: str,
    payload: ManuscriptSceneUpdate,
    expected_version: int = Header(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.update")),
) -> ManuscriptSceneResponse:
    """Update a manuscript scene with optimistic locking.

    When ``content`` (TipTap JSON dict) is provided, it is serialised to
    ``content_json`` before storage.
    """
    update_data = payload.model_dump(exclude_none=True)
    if "title" in update_data:
        update_data["title"] = update_data["title"].strip()
    if "content" in update_data:
        update_data["content_json"] = json.dumps(update_data.pop("content"))
    elif "content_plain" in update_data:
        # Plain-text-only edit: clear stale rich content so they don't diverge
        update_data["content_json"] = None
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update"
        )
    try:
        helper = _get_helper(db)
        helper.update_scene(scene_id, update_data, expected_version)
        scene = helper.get_scene(scene_id)
        if not scene:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found"
            )
        return ManuscriptSceneResponse(**scene)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript scene")


@router.delete(
    "/scenes/{scene_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a manuscript scene",
    tags=["manuscripts"],
)
async def delete_scene(
    scene_id: str,
    expected_version: int = Header(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("writing.manuscripts.delete")),
) -> Response:
    """Soft-delete a manuscript scene."""
    try:
        helper = _get_helper(db)
        helper.soft_delete_scene(scene_id, expected_version)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except _MANUSCRIPT_NONCRITICAL_EXCEPTIONS as exc:
        _handle_db_errors(exc, "manuscript scene")
