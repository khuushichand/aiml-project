"""Slides/Presentations API endpoints."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.Slides_DB_Deps import get_slides_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit, require_permissions
from tldw_Server_API.app.api.v1.schemas.slides_schemas import (
    PresentationCreateRequest,
    PresentationUpdateRequest,
    PresentationPatchRequest,
    PresentationResponse,
    PresentationSummary,
    PresentationListResponse,
    PresentationSearchResponse,
    Slide,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.AuthNZ.permissions import MEDIA_CREATE, MEDIA_READ, MEDIA_UPDATE, MEDIA_DELETE
from tldw_Server_API.app.core.Slides.slides_db import SlidesDatabase, ConflictError, InputError


router = APIRouter(prefix="/slides", tags=["slides"])

_ALLOWED_THEMES = {
    "black",
    "white",
    "league",
    "beige",
    "sky",
    "night",
    "serif",
    "simple",
    "solarized",
    "blood",
    "moon",
    "dracula",
}

_SETTINGS_ALLOWLIST: Dict[str, Tuple[type, ...]] = {
    "transition": (str,),
    "backgroundTransition": (str,),
    "slideNumber": (bool,),
    "controls": (bool,),
    "progress": (bool,),
    "hash": (bool,),
    "center": (bool,),
    "width": (int, float),
    "height": (int, float),
    "margin": (int, float),
    "minScale": (int, float),
    "maxScale": (int, float),
    "viewDistance": (int, float),
    "keyboard": (bool,),
    "touch": (bool,),
    "loop": (bool,),
    "rtl": (bool,),
    "navigationMode": (str,),
}

_ETAG_RE = re.compile(r'^(W/)?"v(?P<version>\d+)"$')


def _parse_etag(raw: Optional[str]) -> int:
    if not raw:
        raise HTTPException(status_code=428, detail="if_match_required")
    match = _ETAG_RE.match(raw.strip())
    if not match:
        raise HTTPException(status_code=400, detail="invalid_if_match")
    return int(match.group("version"))


def _format_etag(version: int) -> str:
    return f'W/"v{version}"'


def _normalize_dt(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _slide_from_obj(obj: Any) -> Slide:
    validator = getattr(Slide, "model_validate", None)
    if callable(validator):
        return validator(obj)
    return Slide.parse_obj(obj)


def _normalize_slides(slides: List[Slide]) -> List[Slide]:
    orders = [slide.order for slide in slides]
    if any(order < 0 for order in orders):
        raise HTTPException(status_code=422, detail="slide_order_negative")
    if len(set(orders)) != len(orders):
        raise HTTPException(status_code=422, detail="slide_order_not_unique")
    ordered = sorted(slides, key=lambda s: s.order)
    for idx, slide in enumerate(ordered):
        slide.order = idx
    return ordered


def _flatten_slides_text(slides: List[Slide]) -> str:
    parts: List[str] = []
    for slide in slides:
        if slide.title:
            parts.append(slide.title)
        if slide.content:
            parts.append(slide.content)
        if slide.speaker_notes:
            parts.append(slide.speaker_notes)
    return "\n".join(parts)


def _validate_theme(theme: str) -> None:
    if theme not in _ALLOWED_THEMES:
        raise HTTPException(status_code=422, detail="invalid_theme")


def _validate_settings(settings: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if settings is None:
        return None
    if not isinstance(settings, dict):
        raise HTTPException(status_code=422, detail="invalid_settings")
    unknown = [key for key in settings.keys() if key not in _SETTINGS_ALLOWLIST]
    if unknown:
        raise HTTPException(status_code=422, detail=f"invalid_settings: unknown keys {unknown}")
    for key, value in settings.items():
        expected = _SETTINGS_ALLOWLIST[key]
        if value is None:
            continue
        if not isinstance(value, expected):
            raise HTTPException(status_code=422, detail=f"invalid_settings: {key}")
    return settings


def _serialize_settings(settings: Optional[Dict[str, Any]]) -> Optional[str]:
    if settings is None:
        return None
    return json.dumps(settings)


def _deserialize_settings(value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _deserialize_source_ref(value: Optional[str]) -> Optional[Any]:
    if value is None:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def _serialize_source_ref(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return str(value)


def _build_presentation_response(row) -> PresentationResponse:
    slides_raw = json.loads(row.slides)
    slides = [_slide_from_obj(item) for item in slides_raw]
    slides = _normalize_slides(slides)
    return PresentationResponse(
        id=row.id,
        title=row.title,
        description=row.description,
        theme=row.theme,
        settings=_deserialize_settings(row.settings),
        slides=slides,
        custom_css=row.custom_css,
        source_type=row.source_type,
        source_ref=_deserialize_source_ref(row.source_ref),
        source_query=row.source_query,
        created_at=_normalize_dt(row.created_at),
        last_modified=_normalize_dt(row.last_modified),
        deleted=int(row.deleted or 0),
        client_id=row.client_id,
        version=int(row.version),
    )


def _build_summary(row) -> PresentationSummary:
    return PresentationSummary(
        id=row.id,
        title=row.title,
        description=row.description,
        theme=row.theme,
        created_at=_normalize_dt(row.created_at),
        last_modified=_normalize_dt(row.last_modified),
        deleted=int(row.deleted or 0),
        version=int(row.version),
    )


def _parse_sort(sort: Optional[str]) -> Tuple[str, str]:
    if not sort:
        return "created_at", "DESC"
    parts = sort.strip().split()
    col = parts[0]
    direction = parts[1] if len(parts) > 1 else "DESC"
    if col not in {"created_at", "last_modified", "title"}:
        raise HTTPException(status_code=400, detail="invalid_sort")
    if direction.upper() not in {"ASC", "DESC"}:
        raise HTTPException(status_code=400, detail="invalid_sort")
    return col, direction.upper()


@router.post(
    "/presentations",
    response_model=PresentationResponse,
    summary="Create a presentation",
    dependencies=[Depends(require_permissions(MEDIA_CREATE)), Depends(rbac_rate_limit("slides.create"))],
)
async def create_presentation(
    request: PresentationCreateRequest,
    response: Response,
    db: SlidesDatabase = Depends(get_slides_db_for_user),
    current_user: User = Depends(get_request_user),
) -> PresentationResponse:
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="title_required")
    _validate_theme(request.theme)
    settings = _validate_settings(request.settings)
    slides = _normalize_slides([_slide_from_obj(s) for s in request.slides])
    slides_text = _flatten_slides_text(slides)
    row = db.create_presentation(
        presentation_id=None,
        title=title,
        description=request.description,
        theme=request.theme,
        settings=_serialize_settings(settings),
        slides=json.dumps([slide.model_dump() if hasattr(slide, "model_dump") else slide.dict() for slide in slides]),
        slides_text=slides_text,
        source_type="manual",
        source_ref=None,
        source_query=None,
        custom_css=request.custom_css,
    )
    response.headers["ETag"] = _format_etag(row.version)
    response.headers["Last-Modified"] = row.last_modified
    return _build_presentation_response(row)


@router.get(
    "/presentations",
    response_model=PresentationListResponse,
    summary="List presentations",
    dependencies=[Depends(require_permissions(MEDIA_READ)), Depends(rbac_rate_limit("slides.list"))],
)
async def list_presentations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: Optional[str] = Query(None, description="Sort by created_at/last_modified/title, e.g. 'created_at desc'"),
    include_deleted: bool = Query(False),
    db: SlidesDatabase = Depends(get_slides_db_for_user),
) -> PresentationListResponse:
    sort_col, sort_dir = _parse_sort(sort)
    rows, total = db.list_presentations(
        limit=limit,
        offset=offset,
        include_deleted=include_deleted,
        sort_column=sort_col,
        sort_direction=sort_dir,
    )
    return PresentationListResponse(
        presentations=[_build_summary(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/presentations/search",
    response_model=PresentationSearchResponse,
    summary="Search presentations",
    dependencies=[Depends(require_permissions(MEDIA_READ)), Depends(rbac_rate_limit("slides.search"))],
)
async def search_presentations(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    include_deleted: bool = Query(False),
    db: SlidesDatabase = Depends(get_slides_db_for_user),
) -> PresentationSearchResponse:
    rows, total = db.search_presentations(query=q, limit=limit, offset=offset, include_deleted=include_deleted)
    return PresentationSearchResponse(
        presentations=[_build_summary(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/presentations/{presentation_id}",
    response_model=PresentationResponse,
    summary="Get presentation",
    dependencies=[Depends(require_permissions(MEDIA_READ)), Depends(rbac_rate_limit("slides.get"))],
)
async def get_presentation(
    presentation_id: str,
    response: Response,
    include_deleted: bool = Query(False),
    db: SlidesDatabase = Depends(get_slides_db_for_user),
) -> PresentationResponse:
    try:
        row = db.get_presentation_by_id(presentation_id, include_deleted=include_deleted)
    except KeyError:
        raise HTTPException(status_code=404, detail="presentation_not_found") from None
    response.headers["ETag"] = _format_etag(row.version)
    response.headers["Last-Modified"] = row.last_modified
    return _build_presentation_response(row)


@router.put(
    "/presentations/{presentation_id}",
    response_model=PresentationResponse,
    summary="Update presentation",
    dependencies=[Depends(require_permissions(MEDIA_UPDATE)), Depends(rbac_rate_limit("slides.update"))],
)
async def update_presentation(
    presentation_id: str,
    request: PresentationUpdateRequest,
    response: Response,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: SlidesDatabase = Depends(get_slides_db_for_user),
) -> PresentationResponse:
    expected_version = _parse_etag(if_match)
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="title_required")
    _validate_theme(request.theme)
    settings = _validate_settings(request.settings)
    slides = _normalize_slides([_slide_from_obj(s) for s in request.slides])
    slides_text = _flatten_slides_text(slides)
    try:
        row = db.update_presentation(
            presentation_id=presentation_id,
            update_fields={
                "title": title,
                "description": request.description,
                "theme": request.theme,
                "settings": _serialize_settings(settings),
                "slides": json.dumps([slide.model_dump() if hasattr(slide, "model_dump") else slide.dict() for slide in slides]),
                "slides_text": slides_text,
                "custom_css": request.custom_css,
            },
            expected_version=expected_version,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="presentation_not_found") from None
    except InputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConflictError:
        raise HTTPException(status_code=412, detail="precondition_failed") from None
    response.headers["ETag"] = _format_etag(row.version)
    response.headers["Last-Modified"] = row.last_modified
    return _build_presentation_response(row)


@router.patch(
    "/presentations/{presentation_id}",
    response_model=PresentationResponse,
    summary="Patch presentation",
    dependencies=[Depends(require_permissions(MEDIA_UPDATE)), Depends(rbac_rate_limit("slides.update"))],
)
async def patch_presentation(
    presentation_id: str,
    request: PresentationPatchRequest,
    response: Response,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: SlidesDatabase = Depends(get_slides_db_for_user),
) -> PresentationResponse:
    expected_version = _parse_etag(if_match)
    update_fields: Dict[str, Any] = {}
    if request.title is not None:
        title = request.title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="title_required")
        update_fields["title"] = title
    if request.description is not None:
        update_fields["description"] = request.description
    if request.theme is not None:
        _validate_theme(request.theme)
        update_fields["theme"] = request.theme
    if request.settings is not None:
        settings = _validate_settings(request.settings)
        update_fields["settings"] = _serialize_settings(settings)
    if request.slides is not None:
        slides = _normalize_slides([_slide_from_obj(s) for s in request.slides])
        update_fields["slides"] = json.dumps([slide.model_dump() if hasattr(slide, "model_dump") else slide.dict() for slide in slides])
        update_fields["slides_text"] = _flatten_slides_text(slides)
    if request.custom_css is not None:
        update_fields["custom_css"] = request.custom_css
    if not update_fields:
        raise HTTPException(status_code=400, detail="no_fields_to_update")
    try:
        row = db.update_presentation(
            presentation_id=presentation_id,
            update_fields=update_fields,
            expected_version=expected_version,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="presentation_not_found") from None
    except InputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConflictError:
        raise HTTPException(status_code=412, detail="precondition_failed") from None
    response.headers["ETag"] = _format_etag(row.version)
    response.headers["Last-Modified"] = row.last_modified
    return _build_presentation_response(row)


@router.delete(
    "/presentations/{presentation_id}",
    response_model=PresentationResponse,
    summary="Soft delete presentation",
    dependencies=[Depends(require_permissions(MEDIA_DELETE)), Depends(rbac_rate_limit("slides.delete"))],
)
async def delete_presentation(
    presentation_id: str,
    response: Response,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: SlidesDatabase = Depends(get_slides_db_for_user),
) -> PresentationResponse:
    expected_version = _parse_etag(if_match)
    try:
        row = db.soft_delete_presentation(presentation_id, expected_version)
    except KeyError:
        raise HTTPException(status_code=404, detail="presentation_not_found") from None
    except InputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConflictError:
        raise HTTPException(status_code=412, detail="precondition_failed") from None
    response.headers["ETag"] = _format_etag(row.version)
    response.headers["Last-Modified"] = row.last_modified
    return _build_presentation_response(row)


@router.post(
    "/presentations/{presentation_id}/restore",
    response_model=PresentationResponse,
    summary="Restore soft-deleted presentation",
    dependencies=[Depends(require_permissions(MEDIA_UPDATE)), Depends(rbac_rate_limit("slides.restore"))],
)
async def restore_presentation(
    presentation_id: str,
    response: Response,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: SlidesDatabase = Depends(get_slides_db_for_user),
) -> PresentationResponse:
    expected_version = _parse_etag(if_match)
    try:
        row = db.restore_presentation(presentation_id, expected_version)
    except KeyError:
        raise HTTPException(status_code=404, detail="presentation_not_found") from None
    except InputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConflictError:
        raise HTTPException(status_code=412, detail="precondition_failed") from None
    response.headers["ETag"] = _format_etag(row.version)
    response.headers["Last-Modified"] = row.last_modified
    return _build_presentation_response(row)


@router.get(
    "/health",
    summary="Slides health check",
    dependencies=[Depends(rbac_rate_limit("slides.health"))],
)
async def slides_health(db: SlidesDatabase = Depends(get_slides_db_for_user)) -> Dict[str, Any]:
    try:
        _ = db.list_presentations(limit=1, offset=0, include_deleted=True, sort_column="created_at", sort_direction="DESC")
    except Exception as exc:
        logger.warning("slides health check failed: %s", exc)
        raise HTTPException(status_code=500, detail="slides_db_unavailable") from exc
    return {"service": "slides", "status": "ok"}
