"""Slides/Presentations API endpoints."""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.encoders import jsonable_encoder
from loguru import logger
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.Slides_DB_Deps import get_slides_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit, require_permissions
from tldw_Server_API.app.api.v1.schemas.slides_schemas import (
    ExportFormat,
    GenerateFromChatRequest,
    GenerateFromMediaRequest,
    GenerateFromNotesRequest,
    GenerateFromPromptRequest,
    GenerateFromRagRequest,
    PresentationCreateRequest,
    PresentationUpdateRequest,
    PresentationPatchRequest,
    PresentationReorderRequest,
    PresentationResponse,
    PresentationSummary,
    PresentationListResponse,
    SlidesTemplateListResponse,
    SlidesTemplateResponse,
    PresentationVersionListResponse,
    PresentationVersionSummary,
    PresentationSearchResponse,
    Slide,
    SlidesHealthResponse,
)
from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import DEFAULT_LLM_PROVIDER
from tldw_Server_API.app.core.AuthNZ.permissions import MEDIA_CREATE, MEDIA_READ, MEDIA_UPDATE, MEDIA_DELETE
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase, get_latest_transcription
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline
from tldw_Server_API.app.core.Slides.slides_db import SlidesDatabase, ConflictError, InputError
from tldw_Server_API.app.core.Slides.slides_export import (
    SlidesAssetsMissingError,
    SlidesExportError,
    SlidesExportInputError,
    export_presentation_bundle,
    export_presentation_json,
    export_presentation_markdown,
    export_presentation_pdf,
)
from tldw_Server_API.app.core.Slides.slides_generator import (
    SlidesGenerationError,
    SlidesGenerationInputError,
    SlidesGenerationOutputError,
    SlidesGenerator,
    SlidesSourceTooLargeError,
)
from tldw_Server_API.app.core.Slides.slides_images import (
    SlidesImageError,
    collect_image_alt_text,
    validate_images_payload,
)
from tldw_Server_API.app.core.Slides.slides_templates import (
    SlidesTemplateInvalidError,
    SlidesTemplateNotFoundError,
    SlidesTemplate,
    get_slide_template,
    list_slide_templates,
)


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
_MARP_THEME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


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
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid_timestamp") from exc
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
        if slide.metadata is None:
            slide.metadata = {}
        if not isinstance(slide.metadata, dict):
            raise HTTPException(status_code=422, detail="slide_metadata_invalid")
        _validate_slide_images(slide.metadata)
    return ordered


def _validate_slide_images(metadata: Dict[str, Any]) -> None:
    images = metadata.get("images")
    if images is None:
        return
    try:
        normalized = validate_images_payload(images)
    except SlidesImageError as exc:
        raise HTTPException(status_code=422, detail=exc.code) from exc
    metadata["images"] = normalized


def _flatten_slides_text(slides: List[Slide]) -> str:
    parts: List[str] = []
    for slide in slides:
        if slide.title:
            parts.append(slide.title)
        if slide.content:
            parts.append(slide.content)
        if slide.speaker_notes:
            parts.append(slide.speaker_notes)
        metadata = slide.metadata if isinstance(slide.metadata, dict) else None
        if metadata:
            images = metadata.get("images")
            parts.extend(collect_image_alt_text(images if isinstance(images, list) else None))
    return "\n".join(parts)


def _validate_theme(theme: str) -> None:
    if theme not in _ALLOWED_THEMES:
        raise HTTPException(status_code=422, detail="invalid_theme")


def _validate_marp_theme(marp_theme: Optional[str]) -> Optional[str]:
    if marp_theme is None:
        return None
    if not isinstance(marp_theme, str) or not marp_theme.strip():
        raise HTTPException(status_code=422, detail="invalid_marp_theme")
    if not _MARP_THEME_RE.match(marp_theme):
        raise HTTPException(status_code=422, detail="invalid_marp_theme")
    return marp_theme


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
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="invalid_settings_json") from exc
    return parsed if isinstance(parsed, dict) else None


def _deserialize_source_ref(value: Optional[str]) -> Optional[Any]:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _serialize_source_ref(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return str(value)


def _field_was_set(model: Any, field_name: str) -> bool:
    fields_set = getattr(model, "model_fields_set", None)
    if isinstance(fields_set, set):
        return field_name in fields_set
    return field_name in getattr(model, "__fields_set__", set())


def _resolve_template(template_id: Optional[str]) -> Optional[SlidesTemplate]:
    if not template_id:
        return None
    try:
        return get_slide_template(template_id)
    except SlidesTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail="template_not_found") from exc
    except SlidesTemplateInvalidError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _apply_template_defaults(
    *,
    request: Any,
    template: Optional[SlidesTemplate],
) -> Tuple[str, Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    theme = request.theme if _field_was_set(request, "theme") else None
    marp_theme = request.marp_theme if _field_was_set(request, "marp_theme") else None
    settings = request.settings if _field_was_set(request, "settings") else None
    custom_css = request.custom_css if _field_was_set(request, "custom_css") else None

    if template:
        if theme is None:
            theme = template.theme
        if marp_theme is None:
            marp_theme = template.marp_theme
        if settings is None:
            settings = template.settings
        if custom_css is None:
            custom_css = template.custom_css

    if theme is None:
        theme = "black"
    return theme, marp_theme, settings, custom_css


def _template_to_response(template: SlidesTemplate) -> SlidesTemplateResponse:
    slides_payload = template.default_slides
    slides: Optional[List[Slide]] = None
    if slides_payload:
        try:
            slides = _normalize_slides([_slide_from_obj(item) for item in slides_payload])
        except HTTPException as exc:
            raise HTTPException(status_code=500, detail="template_slides_invalid") from exc
    return SlidesTemplateResponse(
        id=template.template_id,
        name=template.name,
        theme=template.theme,
        marp_theme=template.marp_theme,
        settings=template.settings,
        default_slides=slides,
        custom_css=template.custom_css,
    )


def _normalize_template_slides(slides_payload: List[Any]) -> List[Slide]:
    try:
        return _normalize_slides([_slide_from_obj(item) for item in slides_payload])
    except HTTPException as exc:
        raise HTTPException(status_code=500, detail="template_slides_invalid") from exc


def _load_version_payload(payload_json: str) -> Dict[str, Any]:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="version_payload_invalid") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="version_payload_invalid")
    return payload


def _payload_to_presentation(payload: Dict[str, Any]) -> PresentationResponse:
    slides_raw = payload.get("slides") or []
    if isinstance(slides_raw, str):
        try:
            slides_raw = json.loads(slides_raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=500, detail="version_payload_invalid") from exc
    slides = [_slide_from_obj(item) for item in slides_raw]
    slides = _normalize_slides(slides)
    settings = payload.get("settings")
    if isinstance(settings, str):
        settings = _deserialize_settings(settings)
    source_ref = payload.get("source_ref")
    if isinstance(source_ref, str):
        source_ref = _deserialize_source_ref(source_ref)
    created_at = payload.get("created_at") or payload.get("last_modified")
    last_modified = payload.get("last_modified") or payload.get("created_at")
    if not created_at:
        created_at = datetime.now(timezone.utc).isoformat()
    if not last_modified:
        last_modified = created_at
    presentation_id = payload.get("id") or payload.get("presentation_id")
    if not presentation_id:
        raise HTTPException(status_code=500, detail="version_payload_invalid")
    title = payload.get("title") or ""
    if not title:
        raise HTTPException(status_code=500, detail="version_payload_invalid")
    return PresentationResponse(
        id=str(presentation_id),
        title=title,
        description=payload.get("description"),
        theme=payload.get("theme") or "black",
        marp_theme=payload.get("marp_theme"),
        template_id=payload.get("template_id"),
        settings=settings if isinstance(settings, dict) or settings is None else None,
        slides=slides,
        custom_css=payload.get("custom_css"),
        source_type=payload.get("source_type"),
        source_ref=source_ref,
        source_query=payload.get("source_query"),
        created_at=_normalize_dt(str(created_at)),
        last_modified=_normalize_dt(str(last_modified)),
        deleted=bool(payload.get("deleted")),
        client_id=payload.get("client_id") or "",
        version=int(payload.get("version") or 0),
    )


def _version_summary_from_payload(
    *,
    presentation_id: str,
    version: int,
    created_at: str,
    payload: Dict[str, Any],
) -> PresentationVersionSummary:
    title = payload.get("title")
    deleted_val = payload.get("deleted")
    deleted = None if deleted_val is None else bool(deleted_val)
    return PresentationVersionSummary(
        presentation_id=presentation_id,
        version=version,
        created_at=_normalize_dt(created_at),
        title=title,
        deleted=deleted,
    )


def _build_presentation_response(row) -> PresentationResponse:
    slides_raw = json.loads(row.slides)
    slides = [_slide_from_obj(item) for item in slides_raw]
    slides = _normalize_slides(slides)
    return PresentationResponse(
        id=row.id,
        title=row.title,
        description=row.description,
        theme=row.theme,
        marp_theme=getattr(row, "marp_theme", None),
        template_id=getattr(row, "template_id", None),
        settings=_deserialize_settings(row.settings),
        slides=slides,
        custom_css=row.custom_css,
        source_type=row.source_type,
        source_ref=_deserialize_source_ref(row.source_ref),
        source_query=row.source_query,
        created_at=_normalize_dt(row.created_at),
        last_modified=_normalize_dt(row.last_modified),
        deleted=bool(row.deleted),
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
        deleted=bool(row.deleted),
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


def _resolve_provider(request_provider: Optional[str]) -> str:
    provider = (request_provider or DEFAULT_LLM_PROVIDER or "openai").strip()
    return provider.lower() if provider else "openai"


def _format_chat_messages(messages: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for msg in messages:
        sender = msg.get("sender") or msg.get("role") or "unknown"
        content = msg.get("content") or ""
        if content:
            lines.append(f"{sender}: {content}")
    return "\n".join(lines).strip()


def _format_notes(notes: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for note in notes:
        title = note.get("title") or ""
        content = note.get("content") or ""
        if title:
            parts.append(f"# {title}")
        if content:
            parts.append(str(content))
    return "\n\n".join(parts).strip()


def _format_rag_documents(documents: List[Any]) -> str:
    parts: List[str] = []
    for doc in documents:
        metadata = getattr(doc, "metadata", {}) or {}
        title = metadata.get("title") or metadata.get("source_title") or getattr(doc, "id", "source")
        content = getattr(doc, "content", "")
        if title:
            parts.append(f"# {title}")
        if content:
            parts.append(str(content))
    return "\n\n".join(parts).strip()


def _generate_presentation(
    *,
    response: Response,
    db: SlidesDatabase,
    request: Any,
    source_text: str,
    source_type: str,
    source_ref: Optional[Any],
    source_query: Optional[str],
) -> PresentationResponse:
    template = _resolve_template(getattr(request, "template_id", None))
    theme, marp_theme, settings, custom_css = _apply_template_defaults(request=request, template=template)
    _validate_theme(theme)
    marp_theme = _validate_marp_theme(marp_theme)
    settings = _validate_settings(settings)
    provider = _resolve_provider(request.provider)
    generator = SlidesGenerator()
    try:
        metrics = get_metrics_registry()
    except Exception:
        logger.debug("Failed to get metrics registry, metrics disabled")
        metrics = None
    started_at = time.perf_counter()

    def _record_generation_error(error_type: str) -> None:
        if metrics is None:
            return
        try:
            metrics.increment(
                "slides_generation_errors_total",
                labels={"source_type": source_type, "error": error_type},
            )
        except Exception as exc:
            logger.debug("Failed to record generation error metric: {}", exc)

    try:
        generated = generator.generate_from_text(
            source_text=source_text,
            title_hint=request.title_hint,
            provider=provider,
            model=request.model,
            api_key=None,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            max_source_tokens=request.max_source_tokens,
            max_source_chars=request.max_source_chars,
            enable_chunking=request.enable_chunking,
            chunk_size_tokens=request.chunk_size_tokens,
            summary_tokens=request.summary_tokens,
        )
    except SlidesSourceTooLargeError as exc:
        _record_generation_error("input_too_large")
        detail = {
            "detail": "Input exceeds size limits and chunking is disabled.",
            "code": "input_too_large",
        }
        if exc.max_source_tokens is not None:
            detail["max_source_tokens"] = exc.max_source_tokens
        if exc.max_source_chars is not None:
            detail["max_source_chars"] = exc.max_source_chars
        raise HTTPException(status_code=413, detail=detail) from exc
    except SlidesGenerationInputError as exc:
        _record_generation_error("input_error")
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SlidesGenerationOutputError as exc:
        _record_generation_error("output_error")
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SlidesGenerationError as exc:
        _record_generation_error("generation_error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        slides = _normalize_slides([_slide_from_obj(s) for s in generated["slides"]])
    except HTTPException:
        raise
    except (ValidationError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid_generated_slides") from exc
    slides_text = _flatten_slides_text(slides)
    row = db.create_presentation(
        presentation_id=None,
        title=generated["title"],
        description=None,
        theme=theme,
        marp_theme=marp_theme,
        template_id=template.template_id if template else None,
        settings=_serialize_settings(settings),
        slides=json.dumps([slide.model_dump() if hasattr(slide, "model_dump") else slide.dict() for slide in slides]),
        slides_text=slides_text,
        source_type=source_type,
        source_ref=_serialize_source_ref(source_ref),
        source_query=source_query,
        custom_css=custom_css,
    )
    if metrics is not None:
        try:
            metrics.observe(
                "slides_generation_latency_seconds",
                time.perf_counter() - started_at,
                labels={"source_type": source_type},
            )
        except Exception as exc:
            logger.debug("Failed to record generation latency metric: {}", exc)
    response.headers["ETag"] = _format_etag(row.version)
    response.headers["Last-Modified"] = row.last_modified
    return _build_presentation_response(row)


@router.post(
    "/presentations",
    response_model=PresentationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a presentation",
    dependencies=[Depends(require_permissions(MEDIA_CREATE)), Depends(rbac_rate_limit("slides.create"))],
)
async def create_presentation(
    request: PresentationCreateRequest,
    response: Response,
    db: SlidesDatabase = Depends(get_slides_db_for_user),
) -> PresentationResponse:
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="title_required")
    template = _resolve_template(request.template_id)
    theme, marp_theme, settings, custom_css = _apply_template_defaults(request=request, template=template)
    _validate_theme(theme)
    marp_theme = _validate_marp_theme(marp_theme)
    settings = _validate_settings(settings)
    if template and not _field_was_set(request, "slides") and template.default_slides:
        slides = _normalize_template_slides(template.default_slides)
    else:
        slides = _normalize_slides([_slide_from_obj(s) for s in request.slides])
    slides_text = _flatten_slides_text(slides)
    row = db.create_presentation(
        presentation_id=None,
        title=title,
        description=request.description,
        theme=theme,
        marp_theme=marp_theme,
        template_id=template.template_id if template else None,
        settings=_serialize_settings(settings),
        slides=json.dumps([slide.model_dump() if hasattr(slide, "model_dump") else slide.dict() for slide in slides]),
        slides_text=slides_text,
        source_type="manual",
        source_ref=None,
        source_query=None,
        custom_css=custom_css,
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
    template = _resolve_template(request.template_id)
    theme, marp_theme, settings, custom_css = _apply_template_defaults(request=request, template=template)
    _validate_theme(theme)
    marp_theme = _validate_marp_theme(marp_theme)
    settings = _validate_settings(settings)
    if template and not _field_was_set(request, "slides") and template.default_slides:
        slides = _normalize_template_slides(template.default_slides)
    else:
        slides = _normalize_slides([_slide_from_obj(s) for s in request.slides])
    slides_text = _flatten_slides_text(slides)
    try:
        row = db.update_presentation(
            presentation_id=presentation_id,
            update_fields={
                "title": title,
                "description": request.description,
                "theme": theme,
                "marp_theme": marp_theme,
                "template_id": template.template_id if template else None,
                "settings": _serialize_settings(settings),
                "slides": json.dumps([slide.model_dump() if hasattr(slide, "model_dump") else slide.dict() for slide in slides]),
                "slides_text": slides_text,
                "custom_css": custom_css,
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
    if request.marp_theme is not None:
        update_fields["marp_theme"] = _validate_marp_theme(request.marp_theme)
    if _field_was_set(request, "template_id"):
        template = _resolve_template(request.template_id)
        update_fields["template_id"] = template.template_id if template else None
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


@router.post(
    "/presentations/{presentation_id}/reorder",
    response_model=PresentationResponse,
    summary="Reorder slides in a presentation",
    dependencies=[Depends(require_permissions(MEDIA_UPDATE)), Depends(rbac_rate_limit("slides.update"))],
)
async def reorder_presentation(
    presentation_id: str,
    request: PresentationReorderRequest,
    response: Response,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: SlidesDatabase = Depends(get_slides_db_for_user),
) -> PresentationResponse:
    expected_version = _parse_etag(if_match)
    try:
        row = db.get_presentation_by_id(presentation_id, include_deleted=False)
    except KeyError:
        raise HTTPException(status_code=404, detail="presentation_not_found") from None

    slides_raw = json.loads(row.slides)
    slides = _normalize_slides([_slide_from_obj(item) for item in slides_raw])
    order = request.order
    if len(order) != len(slides):
        raise HTTPException(status_code=422, detail="invalid_reorder_length")
    if set(order) != set(range(len(slides))):
        raise HTTPException(status_code=422, detail="invalid_reorder_indices")

    reordered = [slides[idx] for idx in order]
    for idx, slide in enumerate(reordered):
        slide.order = idx
    slides_text = _flatten_slides_text(reordered)
    try:
        row = db.update_presentation(
            presentation_id=presentation_id,
            update_fields={
                "slides": json.dumps(
                    [slide.model_dump() if hasattr(slide, "model_dump") else slide.dict() for slide in reordered]
                ),
                "slides_text": slides_text,
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
    "/templates",
    response_model=SlidesTemplateListResponse,
    summary="List slide templates",
    dependencies=[Depends(require_permissions(MEDIA_READ)), Depends(rbac_rate_limit("slides.templates.list"))],
)
async def list_templates() -> SlidesTemplateListResponse:
    try:
        templates = list_slide_templates()
    except SlidesTemplateInvalidError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SlidesTemplateListResponse(templates=[_template_to_response(t) for t in templates])


@router.get(
    "/templates/{template_id}",
    response_model=SlidesTemplateResponse,
    summary="Get slide template",
    dependencies=[Depends(require_permissions(MEDIA_READ)), Depends(rbac_rate_limit("slides.templates.get"))],
)
async def get_template(template_id: str) -> SlidesTemplateResponse:
    try:
        template = get_slide_template(template_id)
    except SlidesTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail="template_not_found") from exc
    except SlidesTemplateInvalidError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _template_to_response(template)


@router.get(
    "/presentations/{presentation_id}/versions",
    response_model=PresentationVersionListResponse,
    summary="List presentation versions",
    dependencies=[Depends(require_permissions(MEDIA_READ)), Depends(rbac_rate_limit("slides.versions.list"))],
)
async def list_presentation_versions(
    presentation_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: SlidesDatabase = Depends(get_slides_db_for_user),
) -> PresentationVersionListResponse:
    try:
        _ = db.get_presentation_by_id(presentation_id, include_deleted=True)
    except KeyError:
        raise HTTPException(status_code=404, detail="presentation_not_found") from None
    rows, total = db.list_presentation_versions(presentation_id=presentation_id, limit=limit, offset=offset)
    versions: List[PresentationVersionSummary] = []
    for row in rows:
        payload = _load_version_payload(row.payload_json)
        versions.append(
            _version_summary_from_payload(
                presentation_id=row.presentation_id,
                version=row.version,
                created_at=row.created_at,
                payload=payload,
            )
        )
    return PresentationVersionListResponse(versions=versions, total=total, limit=limit, offset=offset)


@router.get(
    "/presentations/{presentation_id}/versions/{version}",
    response_model=PresentationResponse,
    summary="Get presentation version",
    dependencies=[Depends(require_permissions(MEDIA_READ)), Depends(rbac_rate_limit("slides.versions.get"))],
)
async def get_presentation_version(
    presentation_id: str,
    version: int,
    db: SlidesDatabase = Depends(get_slides_db_for_user),
) -> PresentationResponse:
    try:
        row = db.get_presentation_version(presentation_id=presentation_id, version=version)
    except KeyError:
        raise HTTPException(status_code=404, detail="presentation_version_not_found") from None
    payload = _load_version_payload(row.payload_json)
    return _payload_to_presentation(payload)


@router.post(
    "/presentations/{presentation_id}/versions/{version}/restore",
    response_model=PresentationResponse,
    summary="Restore presentation to a previous version",
    dependencies=[Depends(require_permissions(MEDIA_UPDATE)), Depends(rbac_rate_limit("slides.versions.restore"))],
)
async def restore_presentation_version(
    presentation_id: str,
    version: int,
    response: Response,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    db: SlidesDatabase = Depends(get_slides_db_for_user),
) -> PresentationResponse:
    expected_version = _parse_etag(if_match)
    try:
        version_row = db.get_presentation_version(presentation_id=presentation_id, version=version)
    except KeyError:
        raise HTTPException(status_code=404, detail="presentation_version_not_found") from None
    payload = _load_version_payload(version_row.payload_json)
    try:
        restored = _payload_to_presentation(payload)
    except HTTPException:
        raise
    theme = restored.theme
    _validate_theme(theme)
    marp_theme = _validate_marp_theme(restored.marp_theme)
    settings = _validate_settings(restored.settings)
    slides = _normalize_slides(restored.slides)
    slides_text = _flatten_slides_text(slides)
    title = restored.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="title_required")
    try:
        row = db.update_presentation(
            presentation_id=presentation_id,
            update_fields={
                "title": title,
                "description": restored.description,
                "theme": theme,
                "marp_theme": marp_theme,
                "template_id": restored.template_id,
                "settings": _serialize_settings(settings),
                "slides": json.dumps([slide.model_dump() if hasattr(slide, "model_dump") else slide.dict() for slide in slides]),
                "slides_text": slides_text,
                "custom_css": restored.custom_css,
                "source_type": restored.source_type,
                "source_ref": _serialize_source_ref(restored.source_ref),
                "source_query": restored.source_query,
                "deleted": 0,
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


@router.post(
    "/generate",
    response_model=PresentationResponse,
    summary="Generate slides from prompt",
    dependencies=[Depends(require_permissions(MEDIA_CREATE)), Depends(rbac_rate_limit("slides.generate"))],
)
async def generate_from_prompt(
    request: GenerateFromPromptRequest,
    response: Response,
    db: SlidesDatabase = Depends(get_slides_db_for_user),
) -> PresentationResponse:
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="prompt_required")
    return _generate_presentation(
        response=response,
        db=db,
        request=request,
        source_text=prompt,
        source_type="prompt",
        source_ref=None,
        source_query=request.prompt,
    )


@router.post(
    "/generate/from-chat",
    response_model=PresentationResponse,
    summary="Generate slides from chat conversation",
    dependencies=[Depends(require_permissions(MEDIA_CREATE)), Depends(rbac_rate_limit("slides.generate"))],
)
async def generate_from_chat(
    request: GenerateFromChatRequest,
    response: Response,
    db: SlidesDatabase = Depends(get_slides_db_for_user),
    notes_db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> PresentationResponse:
    conversation_id = request.conversation_id.strip()
    if not conversation_id:
        raise HTTPException(status_code=422, detail="conversation_id_required")
    conversation = notes_db.get_conversation_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    messages = notes_db.get_messages_for_conversation(conversation_id, limit=500, offset=0, order_by_timestamp="ASC")
    source_text = _format_chat_messages(messages)
    if not source_text:
        raise HTTPException(status_code=404, detail="conversation_empty")
    return _generate_presentation(
        response=response,
        db=db,
        request=request,
        source_text=source_text,
        source_type="chat",
        source_ref=conversation_id,
        source_query=None,
    )


@router.post(
    "/generate/from-media",
    response_model=PresentationResponse,
    summary="Generate slides from media transcript",
    dependencies=[Depends(require_permissions(MEDIA_CREATE)), Depends(rbac_rate_limit("slides.generate"))],
)
async def generate_from_media(
    request: GenerateFromMediaRequest,
    response: Response,
    db: SlidesDatabase = Depends(get_slides_db_for_user),
    media_db: MediaDatabase = Depends(get_media_db_for_user),
) -> PresentationResponse:
    try:
        media_id = int(request.media_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="media_id_invalid") from exc
    media_row = media_db.get_media_by_id(media_id, include_deleted=False, include_trash=False)
    if not media_row:
        raise HTTPException(status_code=404, detail="media_not_found")
    transcript = get_latest_transcription(media_db, media_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="media_transcript_not_found")
    return _generate_presentation(
        response=response,
        db=db,
        request=request,
        source_text=transcript,
        source_type="media",
        source_ref=str(media_id),
        source_query=None,
    )


@router.post(
    "/generate/from-notes",
    response_model=PresentationResponse,
    summary="Generate slides from notes",
    dependencies=[Depends(require_permissions(MEDIA_CREATE)), Depends(rbac_rate_limit("slides.generate"))],
)
async def generate_from_notes(
    request: GenerateFromNotesRequest,
    response: Response,
    db: SlidesDatabase = Depends(get_slides_db_for_user),
    notes_db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> PresentationResponse:
    if not request.note_ids:
        raise HTTPException(status_code=422, detail="note_ids_required")
    notes: List[Dict[str, Any]] = []
    missing: List[str] = []
    for note_id in request.note_ids:
        note = notes_db.get_note_by_id(note_id)
        if not note:
            missing.append(note_id)
            continue
        notes.append(note)
    if missing:
        raise HTTPException(status_code=404, detail={"missing_note_ids": missing})
    source_text = _format_notes(notes)
    if not source_text:
        raise HTTPException(status_code=404, detail="notes_empty")
    return _generate_presentation(
        response=response,
        db=db,
        request=request,
        source_text=source_text,
        source_type="notes",
        source_ref=request.note_ids,
        source_query=None,
    )


@router.post(
    "/generate/from-rag",
    response_model=PresentationResponse,
    summary="Generate slides from RAG results",
    dependencies=[Depends(require_permissions(MEDIA_CREATE)), Depends(rbac_rate_limit("slides.generate"))],
)
async def generate_from_rag(
    request: GenerateFromRagRequest,
    response: Response,
    db: SlidesDatabase = Depends(get_slides_db_for_user),
) -> PresentationResponse:
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query_required")
    try:
        user_id = int(db.client_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="user_unavailable") from exc
    rag_result = await unified_rag_pipeline(
        query=query,
        top_k=request.top_k or 8,
        sources=["media_db", "notes", "chats"],
        media_db_path=str(DatabasePaths.get_media_db_path(user_id)),
        notes_db_path=str(DatabasePaths.get_chacha_db_path(user_id)),
        character_db_path=str(DatabasePaths.get_chacha_db_path(user_id)),
    )
    documents = rag_result.documents if hasattr(rag_result, "documents") else []
    source_text = _format_rag_documents(documents)
    if not source_text and hasattr(rag_result, "generated_answer") and rag_result.generated_answer:
        source_text = str(rag_result.generated_answer)
    if not source_text:
        raise HTTPException(status_code=404, detail="rag_no_results")
    return _generate_presentation(
        response=response,
        db=db,
        request=request,
        source_text=source_text,
        source_type="rag",
        source_ref=None,
        source_query=query,
    )


@router.get(
    "/presentations/{presentation_id}/export",
    summary="Export presentation",
    dependencies=[Depends(require_permissions(MEDIA_READ)), Depends(rbac_rate_limit("slides.export"))],
)
async def export_presentation(
    presentation_id: str,
    format: ExportFormat = Query(ExportFormat.REVEAL),
    pdf_format: Optional[str] = Query(None),
    pdf_width: Optional[str] = Query(None),
    pdf_height: Optional[str] = Query(None),
    pdf_landscape: Optional[bool] = Query(None),
    pdf_margin_top: Optional[str] = Query(None),
    pdf_margin_bottom: Optional[str] = Query(None),
    pdf_margin_left: Optional[str] = Query(None),
    pdf_margin_right: Optional[str] = Query(None),
    db: SlidesDatabase = Depends(get_slides_db_for_user),
) -> Response:
    try:
        row = db.get_presentation_by_id(presentation_id, include_deleted=False)
    except KeyError:
        raise HTTPException(status_code=404, detail="presentation_not_found") from None

    slides_raw = json.loads(row.slides)
    slides = [_slide_from_obj(item) for item in slides_raw]
    slides = _normalize_slides(slides)
    settings = _deserialize_settings(row.settings)
    try:
        metrics = get_metrics_registry()
    except Exception:
        metrics = None
    started_at = time.perf_counter()

    if format == ExportFormat.JSON:
        payload = jsonable_encoder(_build_presentation_response(row))
        body = export_presentation_json(payload).encode("utf-8")
        filename = f"presentation_{presentation_id}.json"
        media_type = "application/json"
    elif format == ExportFormat.MARKDOWN:
        try:
            body = export_presentation_markdown(
                title=row.title,
                slides=slides,
                theme=row.theme,
                marp_theme=getattr(row, "marp_theme", None),
            ).encode("utf-8")
        except SlidesExportInputError as exc:
            if metrics is not None:
                try:
                    metrics.increment(
                        "slides_export_errors_total",
                        labels={"format": format.value, "error": "input_error"},
                    )
                except Exception:
                    pass
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except SlidesExportError as exc:
            if metrics is not None:
                try:
                    metrics.increment(
                        "slides_export_errors_total",
                        labels={"format": format.value, "error": "export_error"},
                    )
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        filename = f"presentation_{presentation_id}.md"
        media_type = "text/markdown"
    elif format == ExportFormat.PDF:
        pdf_options = {
            "format": pdf_format,
            "width": pdf_width,
            "height": pdf_height,
            "landscape": pdf_landscape,
            "margin": {
                "top": pdf_margin_top,
                "bottom": pdf_margin_bottom,
                "left": pdf_margin_left,
                "right": pdf_margin_right,
            },
        }
        try:
            body = await asyncio.to_thread(
                export_presentation_pdf,
                title=row.title,
                slides=slides,
                theme=row.theme,
                settings=settings,
                custom_css=row.custom_css,
                pdf_options=pdf_options,
            )
        except SlidesExportInputError as exc:
            if metrics is not None:
                try:
                    metrics.increment(
                        "slides_export_errors_total",
                        labels={"format": format.value, "error": "input_error"},
                    )
                except Exception:
                    pass
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except SlidesExportError as exc:
            if metrics is not None:
                try:
                    metrics.increment(
                        "slides_export_errors_total",
                        labels={"format": format.value, "error": "export_error"},
                    )
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        filename = f"presentation_{presentation_id}.pdf"
        media_type = "application/pdf"
    elif format == ExportFormat.REVEAL:
        try:
            body = export_presentation_bundle(
                title=row.title,
                slides=slides,
                theme=row.theme,
                settings=settings,
                custom_css=row.custom_css,
            )
        except SlidesAssetsMissingError as exc:
            if metrics is not None:
                try:
                    metrics.increment(
                        "slides_export_errors_total",
                        labels={"format": format.value, "error": "assets_missing"},
                    )
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail="slides_assets_missing") from exc
        except SlidesExportInputError as exc:
            if metrics is not None:
                try:
                    metrics.increment(
                        "slides_export_errors_total",
                        labels={"format": format.value, "error": "input_error"},
                    )
                except Exception:
                    pass
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except SlidesExportError as exc:
            if metrics is not None:
                try:
                    metrics.increment(
                        "slides_export_errors_total",
                        labels={"format": format.value, "error": "export_error"},
                    )
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        filename = f"presentation_{presentation_id}.zip"
        media_type = "application/zip"
    else:
        if metrics is not None:
            try:
                metrics.increment(
                    "slides_export_errors_total",
                    labels={"format": str(format), "error": "invalid_format"},
                )
            except Exception:
                pass
        raise HTTPException(status_code=400, detail="invalid_export_format")

    if metrics is not None:
        try:
            metrics.observe(
                "slides_export_latency_seconds",
                time.perf_counter() - started_at,
                labels={"format": format.value},
            )
        except Exception:
            pass

    headers = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
    return Response(content=body, media_type=media_type, headers=headers)


@router.get(
    "/health",
    summary="Slides health check",
    response_model=SlidesHealthResponse,
    dependencies=[Depends(rbac_rate_limit("slides.health"))],
)
async def slides_health(db: SlidesDatabase = Depends(get_slides_db_for_user)) -> SlidesHealthResponse:
    try:
        _ = db.list_presentations(limit=1, offset=0, include_deleted=True, sort_column="created_at", sort_direction="DESC")
    except Exception as exc:
        logger.warning("slides health check failed: {}", exc)
        raise HTTPException(status_code=500, detail="slides_db_unavailable") from exc
    return SlidesHealthResponse(service="slides", status="ok")
