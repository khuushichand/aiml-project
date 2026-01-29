# app/api/v1/endpoints/notes.py
#
#
# Imports
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
#
# 3rd-party Libraries
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
    Body,
    Header  # Keep Header for expected_version
)
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
#
# Local Imports
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (  # Corrected import path if needed
    CharactersRAGDB, InputError, ConflictError, CharactersRAGDBError
)
#
# Schemas for notes
from tldw_Server_API.app.api.v1.schemas.notes_schemas import (
    NoteCreate, NoteUpdate, NoteResponse,
    KeywordCreate, KeywordResponse,
    NoteKeywordLinkResponse, KeywordsForNoteResponse, NotesForKeywordResponse,
    DetailResponse,
    NoteBulkCreateRequest, NoteBulkCreateItemResult, NoteBulkCreateResponse,
    NotesListResponse, NotesExportResponse, NotesExportRequest,
    TitleSuggestRequest, TitleSuggestResponse,
)
# Dependency to get user-specific ChaChaNotes_DB instance
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import (
    get_chacha_db_for_user,
    resolve_chacha_user_base_dir,
)
from tldw_Server_API.app.core.Monitoring.topic_monitoring_service import get_topic_monitoring_service
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_rate_limiter_dep, rbac_rate_limit
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.Writing.note_title import generate_note_title, TitleGenOptions
from tldw_Server_API.app.core.config import settings as core_settings
#
#
#######################################################################################################################
#
# Functions:

router = APIRouter()

# --- Title options helper -----------------------------------------------------
def _field_supplied(model_obj: Any, field_name: str) -> bool:
    """Return True if the incoming model explicitly supplied the field.

    Works across Pydantic v2 (model_fields_set) and v1 (__fields_set__).
    Falls back to checking a best-effort dump with exclude_unset.
    """
    try:
        s = getattr(model_obj, "model_fields_set", None)
        if isinstance(s, set):
            return field_name in s
    except Exception:
        pass
    try:
        s = getattr(model_obj, "__fields_set__", None)  # pydantic v1
        if isinstance(s, set):
            return field_name in s
    except Exception:
        pass
    try:
        from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat as _dump
        data = _dump(model_obj, exclude_unset=True)
        return field_name in (data or {})
    except Exception:
        return False


def _build_title_opts(note_in: Any) -> TitleGenOptions:
    """Build TitleGenOptions from request payload with sane defaults and clamping.

    - Strategy: use client-provided value if supplied; otherwise fall back to default setting.
    - LLM gating: downgrade to heuristic when LLM strategies are disabled.
    - Max length: coerce to int, default 250, clamp to [min_len, max_len_bound].
    """
    # Resolve strategy honoring client intent when provided
    default_strategy = str(core_settings.get("NOTES_TITLE_DEFAULT_STRATEGY", "heuristic")).lower()
    if _field_supplied(note_in, "title_strategy"):
        strategy = getattr(note_in, "title_strategy", default_strategy) or default_strategy
    else:
        strategy = default_strategy

    # Apply LLM enabled gate after resolving strategy
    if strategy in ("llm", "llm_fallback") and not bool(core_settings.get("NOTES_TITLE_LLM_ENABLED", False)):
        strategy = "heuristic"

    # Resolve and clamp max length
    try:
        raw_len = getattr(note_in, "title_max_len", None)
        max_len_val = int(raw_len) if raw_len is not None else 250
    except Exception:
        max_len_val = 250
    try:
        max_bound = int(core_settings.get("NOTES_TITLE_MAX_LEN", 1000))
        if max_bound <= 0:
            max_bound = 1000
    except Exception:
        max_bound = 1000
    min_bound = 10
    # Clamp to API schema max for titles (NoteBase.title max_length=255).
    schema_max = 255
    max_bound = min(max_bound, schema_max)
    if max_bound < min_bound:
        max_bound = min_bound
    if max_len_val < min_bound:
        max_len_val = min_bound
    if max_len_val > max_bound:
        max_len_val = max_bound

    opts = TitleGenOptions()
    opts.strategy = strategy
    opts.max_len = max_len_val
    try:
        opts.language = getattr(note_in, "language", None)
    except Exception:
        opts.language = None
    return opts

# --- Note link validation -----------------------------------------------------
def _normalize_optional_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value).strip() or None


def _validate_note_links(
    db: CharactersRAGDB,
    conversation_id: Optional[str],
    message_id: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    normalized_conversation_id = _normalize_optional_id(conversation_id)
    normalized_message_id = _normalize_optional_id(message_id)

    if normalized_conversation_id:
        conv = db.get_conversation_by_id(normalized_conversation_id)
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    message_conversation_id = None
    if normalized_message_id:
        message_conversation_id = db.get_message_conversation_id(normalized_message_id)
        if not message_conversation_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    if normalized_conversation_id and normalized_message_id:
        if message_conversation_id != normalized_conversation_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found in conversation",
            )

    return normalized_conversation_id, normalized_message_id


# --- CSV export helper --------------------------------------------------------
def _notes_csv_response(notes_data: List[Dict[str, Any]], include_keywords: bool) -> StreamingResponse:
    import io, csv
    output = io.StringIO()
    writer = csv.writer(output)
    headers = ["id", "title", "content", "created_at", "last_modified", "version", "client_id"]
    if include_keywords:
        headers.append("keywords")
    writer.writerow(headers)
    for n in notes_data:
        row = [
            n.get("id"),
            n.get("title"),
            n.get("content"),
            n.get("created_at"),
            n.get("last_modified") or n.get("updated_at"),
            n.get("version"),
            n.get("client_id"),
        ]
        if include_keywords:
            kws = n.get("keywords") or []
            row.append(",".join([str(k.get("keyword")) for k in kws if isinstance(k, dict) and k.get("keyword") is not None]))
        writer.writerow(row)
    output.seek(0)
    from datetime import datetime as _dt, timezone
    headers_map = {"Content-Disposition": f"attachment; filename=notes_export_{_dt.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv"}
    return StreamingResponse(output, media_type="text/csv; charset=utf-8", headers=headers_map)


# --- Keyword attach helper ----------------------------------------------------
def _attach_keywords_bulk(db: CharactersRAGDB, notes_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    note_ids = [nd.get("id") for nd in notes_data if isinstance(nd, dict) and nd.get("id")]
    if not note_ids:
        return notes_data
    try:
        kw_map = db.get_keywords_for_notes(note_ids)
    except Exception as e:
        logger.warning(f"Bulk keyword lookup failed: {e}")
        return notes_data
    for nd in notes_data:
        if isinstance(nd, dict):
            nid = nd.get("id")
            if nid:
                nd["keywords"] = kw_map.get(nid, [])
    return notes_data


# --- Keyword attach helper ----------------------------------------------------
def _attach_keywords_inline(db: CharactersRAGDB, note_dict: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if note_dict and note_dict.get('id'):
            note_dict['keywords'] = db.get_keywords_for_note(note_id=note_dict['id'])
    except Exception as e:
        logger.warning(f"Failed to attach keywords to note {note_dict.get('id')}: {e}")
    return note_dict


def _normalize_keyword_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _keyword_text_from_row(row: Any) -> Optional[str]:
    if isinstance(row, dict):
        for key in ("keyword", "keyword_text", "text"):
            if key in row:
                return _normalize_keyword_text(row.get(key))
    return _normalize_keyword_text(row)


def _get_or_create_keyword_row(db: CharactersRAGDB, keyword_text: Any) -> Optional[Dict[str, Any]]:
    """Return existing keyword row or create one, handling concurrent creation."""
    text = _normalize_keyword_text(keyword_text)
    if not text:
        return None
    kw_row = db.get_keyword_by_text(text)
    if kw_row:
        return kw_row
    try:
        kw_id = db.add_keyword(text)
    except ConflictError:
        # Keyword may have been created concurrently; refetch and return if present.
        kw_row = db.get_keyword_by_text(text)
        if kw_row:
            return kw_row
        raise
    if kw_id is None:
        return None
    return db.get_keyword_by_id(kw_id)


def _sync_note_keywords(db: CharactersRAGDB, note_id: str, keywords: List[str]) -> None:
    desired: Dict[str, str] = {}
    for kw in keywords:
        text = _normalize_keyword_text(kw)
        if not text:
            continue
        key = text.lower()
        if key in desired:
            continue
        desired[key] = text

    try:
        existing_rows = db.get_keywords_for_note(note_id=note_id)
    except Exception as err:
        logger.warning(f"Keyword sync lookup failed for note {note_id}: {err}")
        existing_rows = []

    existing_by_key: Dict[str, Dict[str, Any]] = {}
    for row in existing_rows:
        text = _keyword_text_from_row(row)
        if not text:
            continue
        existing_by_key[text.lower()] = row

    desired_keys = set(desired.keys())

    for key, row in existing_by_key.items():
        if key in desired_keys:
            continue
        kw_id = row.get("id") if isinstance(row, dict) else None
        if kw_id is None:
            continue
        try:
            db.unlink_note_from_keyword(note_id=note_id, keyword_id=int(kw_id))
        except Exception as err:
            logger.warning(f"Keyword unlink failed for note {note_id}, keyword {kw_id}: {err}")

    for key, text in desired.items():
        if key in existing_by_key:
            continue
        try:
            kw_row = _get_or_create_keyword_row(db, text)
            if kw_row and kw_row.get("id") is not None:
                db.link_note_to_keyword(note_id=note_id, keyword_id=int(kw_row["id"]))
        except Exception as err:
            logger.warning(f"Keyword attach failed for '{text}' on note {note_id}: {err}")


def _normalize_keyword_tokens(tokens: Optional[List[str]]) -> List[str]:
    if not tokens:
        return []
    seen: set[str] = set()
    out: List[str] = []
    for token in tokens:
        if token is None:
            continue
        text = str(token).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


# --- Helper for Exception Handling (largely the same) ---
def handle_db_errors(e: Exception, entity_type: str = "resource"):
    if isinstance(e, HTTPException):  # If it's already an HTTPException, re-raise
        raise e

    logger_func = logger.warning  # Default to warning for known DB operational errors
    http_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR  # Default
    detail_message = f"An unexpected error occurred while processing your request for {entity_type}."

    if isinstance(e, InputError):
        http_status_code = status.HTTP_400_BAD_REQUEST
        detail_message = str(e)
    elif isinstance(e, ConflictError):
        http_status_code = status.HTTP_409_CONFLICT
        # Prioritize version mismatch and not-found semantics
        exception_message_str = str(e.args[0]) if e.args else str(e)  # Get the primary message
        lowered_msg = exception_message_str.lower()
        if "version mismatch" in lowered_msg:
            detail_message = "The resource has been modified since you last fetched it. Please refresh and try again."
        elif "not found" in lowered_msg or "soft-deleted" in lowered_msg or "soft deleted" in lowered_msg:
            http_status_code = status.HTTP_404_NOT_FOUND
            if "conversation" in lowered_msg or "message" in lowered_msg:
                detail_message = exception_message_str
            else:
                resource_name = entity_type or "resource"
                detail_message = f"{resource_name.capitalize()} not found."
        elif hasattr(e, 'entity') and e.entity and hasattr(e, 'entity_id') and e.entity_id:
            detail_message = f"A conflict occurred with {e.entity} (ID: {e.entity_id}). It might have been modified or deleted, or a unique constraint was violated."
        elif "already exists" in lowered_msg:
            detail_message = f"A {entity_type} with the provided identifier already exists."
        else:  # Generic conflict based on the exception's original message
            detail_message = exception_message_str
    elif isinstance(e, CharactersRAGDBError):  # General DB Error from our library
        logger_func = logger.error  # Log as error
        detail_message = f"A database error occurred while processing your request for {entity_type}."
    elif isinstance(e, ValueError):  # Catch generic ValueErrors that might not be InputError
        http_status_code = status.HTTP_400_BAD_REQUEST
        detail_message = str(e)
    else:  # Truly unexpected errors
        logger_func = logger.error

    logger_func(f"Error for {entity_type}: {type(e).__name__} - {str(e)}",
                exc_info=isinstance(e, (CharactersRAGDBError, Exception)) and not isinstance(e,
                                                                                             (InputError, ConflictError,
                                                                                              ValueError)))
    raise HTTPException(status_code=http_status_code, detail=detail_message)


# --- Notes Endpoints ---

@router.get(
    "/health",
    summary="Notes service health",
    tags=["notes"],
    openapi_extra={"security": []},
)
async def notes_health() -> Dict[str, Any]:
    """Unauthenticated health endpoint for Notes storage."""
    import os
    base_dir: Optional[Path] = None
    health = {
        "service": "notes",
        "status": "healthy",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "components": {}
    }
    storage_info: Dict[str, Any] = {
        "base_dir": None,
        "db_path": None,
        "exists": False,
        "writable": False,
    }

    try:
        base_dir = resolve_chacha_user_base_dir()
        exists = base_dir.exists()
        writable = False
        if exists:
            try:
                test_path = base_dir / ".health_check"
                with open(test_path, "w") as f:
                    f.write("ok")
                os.remove(test_path)
                writable = True
            except Exception:
                writable = False

        storage_info.update(
            {
                "base_dir": str(base_dir),
                "db_path": None,
                "exists": exists,
                "writable": writable,
            }
        )

        if not exists or not writable:
            health["status"] = "degraded"
    except Exception as e:
        health["status"] = "unhealthy"
        health["error"] = str(e)
        if base_dir:
            storage_info["base_dir"] = str(base_dir)

    health["components"]["storage"] = storage_info
    return health

@router.post(
    "/",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new note",
    tags=["notes"]
)
async def create_note(
        request: Request,
        note_in: NoteCreate,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),  # Use the user-specific DB instance
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.create")),
):
    try:
        # Centralized rate limit for notes.create
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.create")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.create",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})

        # The user context (user_id) is implicitly handled by `get_chacha_db_for_user`
        # The `db` instance is already specific to the authenticated user.
        safe_title_log = (note_in.title or "").strip()
        if len(safe_title_log) > 30:
            safe_title_log = safe_title_log[:30] + "..."
        logger.info(f"User (via DB instance client_id: {db.client_id}) creating note: Title='{safe_title_log}'")
        # Compute title (auto-generate if requested)
        effective_title = (note_in.title or "").strip()
        if not effective_title:
            if getattr(note_in, "auto_title", False):
                try:
                    opts = _build_title_opts(note_in)
                    effective_title = await asyncio.to_thread(
                        generate_note_title,
                        note_in.content,
                        options=opts,
                    )
                except Exception as gen_err:
                    logger.warning(f"Auto-title generation failed, falling back: {gen_err}")
                    # Fallback to safe timestamped title
                    effective_title = await asyncio.to_thread(generate_note_title, note_in.content)
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="Title is required unless auto_title=true")

        conversation_id, message_id = _validate_note_links(
            db,
            note_in.conversation_id,
            note_in.message_id,
        )

        note_id = db.add_note(
            title=effective_title,
            content=note_in.content,
            note_id=note_in.id,  # Pass optional client-provided ID
            conversation_id=conversation_id,
            message_id=message_id,
        )
        if note_id is None:  # Should be caught by exceptions
            raise CharactersRAGDBError("Note creation failed to return an ID.")

        # Topic monitoring (non-blocking) for title and content
        try:
            mon = get_topic_monitoring_service()
            uid = getattr(db, 'client_id', None)
            src_id = str(note_id)
            if effective_title:
                mon.schedule_evaluate_and_alert(
                    user_id=str(uid) if uid else None,
                    text=effective_title,
                    source="notes.create",
                    scope_type="user",
                    scope_id=str(uid) if uid else None,
                    source_id=src_id,
                )
            if note_in.content:
                mon.schedule_evaluate_and_alert(
                    user_id=str(uid) if uid else None,
                    text=note_in.content,
                    source="notes.create",
                    scope_type="user",
                    scope_id=str(uid) if uid else None,
                    source_id=src_id,
                )
        except Exception:
            pass

        # Handle optional keywords: create if needed and link to this note
        try:
            kw_list = note_in.normalized_keywords if hasattr(note_in, 'normalized_keywords') else None
            if kw_list:
                for kw in kw_list:
                    try:
                        # Find or create keyword (case-insensitive uniqueness enforced by DB schema)
                        kw_row = _get_or_create_keyword_row(db, kw)
                        if kw_row and kw_row.get('id') is not None:
                            db.link_note_to_keyword(note_id=note_id, keyword_id=int(kw_row['id']))
                    except Exception as kw_err:
                        # Log but do not fail the note creation if a single keyword fails
                        logger.warning(f"Keyword attach failed for '{kw}' on note {note_id}: {kw_err}")
        except Exception as kw_outer_err:
            logger.warning(f"Keyword processing encountered an issue for note {note_id}: {kw_outer_err}")

        created_note_data = db.get_note_by_id(note_id=note_id)
        if not created_note_data:
            logger.error(
                f"Failed to retrieve note '{note_id}' immediately after creation for user (DB client_id: {db.client_id}).")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Note created but could not be retrieved.")
        # Attach keywords inline
        created_note_data = _attach_keywords_inline(db, created_note_data)

        logger.info(f"Note '{note_id}' created successfully for user (DB client_id: {db.client_id}).")
        return created_note_data  # Pydantic will convert dict to NoteResponse (including keywords)
    except Exception as e:
        handle_db_errors(e, "note")


@router.get(
    "/",
    response_model=NotesListResponse,
    summary="List all notes for the current user",
    tags=["notes"]
)
async def list_notes(
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        limit: int = Query(100, ge=1, le=1000, description="Number of notes to return"),
        offset: int = Query(0, ge=0, description="Offset for pagination"),
        include_keywords: bool = Query(False, description="If true, include linked keywords inline per note"),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.list")),
):
    """Always returns a consistent object with a `notes` array and pagination fields."""
    try:
        # Rate limit: notes.list
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.list")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.list",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        logger.debug(f"User (DB client_id: {db.client_id}) listing notes: limit={limit}, offset={offset}")
        notes_data = db.list_notes(limit=limit, offset=offset)
        # Attach keywords inline for each note (optional for performance)
        if include_keywords:
            try:
                _attach_keywords_bulk(db, notes_data)
            except Exception as outer_err:
                logger.warning(f"Attaching keywords for notes list failed: {outer_err}")
        # Lightweight total count
        total = None
        try:
            total = db.count_notes()
        except Exception:
            total = None
        # Back-compat aliases for list consumers
        return {
            "notes": notes_data,
            "items": notes_data,
            "results": notes_data,
            "count": len(notes_data),
            "limit": limit,
            "offset": offset,
            "total": total,
        }
    except Exception as e:
        handle_db_errors(e, "notes list")


@router.get(
    "/search",
    response_model=List[NoteResponse],
    summary="Search notes for the current user",
    tags=["notes"]
)
@router.get(
    "/search/",
    response_model=List[NoteResponse],
    summary="Search notes for the current user",
    tags=["notes"]
)
async def search_notes_endpoint(  # Renamed to avoid conflict with imported search_notes
        query: Optional[str] = Query(None, min_length=1, description="Search term for notes"),
        tokens: Optional[List[str]] = Query(None, description="Keyword tokens to filter notes"),
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        limit: int = Query(10, ge=1, le=100, description="Number of results to return"),
        offset: int = Query(0, ge=0, description="Result offset for pagination"),
        include_keywords: bool = Query(False, description="If true, include linked keywords inline per note"),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.search")),
):
    try:
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.search")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.search",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        token_list = _normalize_keyword_tokens(tokens)
        query_term = query.strip() if query else ""
        if not query_term and not token_list:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="query or tokens is required")
        logger.debug(
            f"User (DB client_id: {db.client_id}) searching notes: query='{query_term}', limit={limit}, offset={offset}, tokens={token_list}")
        if token_list:
            notes_data = db.search_notes_with_keywords(
                search_term=query_term or None,
                keyword_tokens=token_list,
                limit=limit,
                offset=offset
            )
        else:
            notes_data = db.search_notes(search_term=query_term, limit=limit, offset=offset)
        # Attach keywords inline (optional)
        if include_keywords:
            try:
                _attach_keywords_bulk(db, notes_data)
            except Exception as outer_err:
                logger.warning(f"Attaching keywords for notes search failed: {outer_err}")
        return notes_data
    except Exception as e:
        handle_db_errors(e, "notes search")


@router.get(
    "/export",
    response_model=NotesExportResponse,
    summary="Export notes as JSON",
    tags=["notes"]
)
async def export_notes(
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        q: Optional[str] = Query(None, description="Optional search query to filter notes"),
        limit: int = Query(1000, ge=1, le=10000, description="Max notes to export"),
        offset: int = Query(0, ge=0, description="Offset for pagination"),
        include_keywords: bool = Query(False, description="If true, include linked keywords inline per note"),
        format: str = Query("json", description="Export format. Only json here; use /export.csv for CSV."),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.export")),
):
    """Simple JSON export for notes. If `q` is provided, uses FTS search; otherwise lists notes."""
    try:
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.export")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.export",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        if str(format).lower() != "json":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="CSV export is available at /api/v1/notes/export.csv")
        total = None
        if q:
            notes_data = db.search_notes(search_term=q, limit=limit, offset=offset)
            try:
                total = db.count_notes_matching(q)
            except Exception:
                total = None
        else:
            notes_data = db.list_notes(limit=limit, offset=offset)
            try:
                total = db.count_notes()
            except Exception:
                total = None
        for nd in notes_data:
            if isinstance(nd, dict):
                nd.pop("bm25_score", None)
                nd.pop("rank", None)
        if include_keywords:
            _attach_keywords_bulk(db, notes_data)

        return {
            "notes": notes_data,
            "data": notes_data,
            "items": notes_data,
            "results": notes_data,
            "count": len(notes_data),
            "total": total,
            "limit": limit,
            "offset": offset,
            "exported_at": __import__("datetime").datetime.utcnow().isoformat()
        }
    except Exception as e:
        handle_db_errors(e, "notes export")


@router.get(
    "/export.csv",
    response_class=StreamingResponse,
    summary="Export notes as CSV",
    tags=["notes"]
)
async def export_notes_csv(
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        q: Optional[str] = Query(None, description="Optional search query to filter notes"),
        limit: int = Query(1000, ge=1, le=10000, description="Max notes to export"),
        offset: int = Query(0, ge=0, description="Offset for pagination"),
        include_keywords: bool = Query(False, description="If true, include linked keywords inline per note"),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.export")),
):
    """CSV export for notes. If `q` is provided, uses FTS search; otherwise lists notes."""
    try:
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.export")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.export",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        if q:
            notes_data = db.search_notes(search_term=q, limit=limit, offset=offset)
        else:
            notes_data = db.list_notes(limit=limit, offset=offset)
        for nd in notes_data:
            if isinstance(nd, dict):
                nd.pop("bm25_score", None)
                nd.pop("rank", None)
        if include_keywords:
            _attach_keywords_bulk(db, notes_data)
        return _notes_csv_response(notes_data, include_keywords)
    except Exception as e:
        handle_db_errors(e, "notes export (csv)")


@router.post(
    "/export",
    response_model=NotesExportResponse,
    summary="Export selected notes by ID",
    tags=["notes"]
)
async def export_notes_post(
        payload: NotesExportRequest,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.export")),
):
    """Export notes by explicit IDs (parity with E2E scaffold)."""
    try:
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.export")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.export",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        note_ids = payload.note_ids
        include_keywords = bool(payload.include_keywords)
        fmt = str(payload.format).lower()
        if fmt != "json":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="CSV export is available at /api/v1/notes/export.csv")

        results: List[Dict[str, Any]] = []
        for nid in note_ids:
            try:
                nd = db.get_note_by_id(note_id=nid)
                if not nd:
                    continue
                if include_keywords:
                    nd["keywords"] = []
                results.append(nd)
            except Exception as fetch_err:
                logger.debug(f"Skipping note ID '{nid}' during export: {fetch_err}")
                continue

        if include_keywords and results:
            _attach_keywords_bulk(db, results)

        return {
            "notes": results,
            "data": results,
            "items": results,
            "results": results,
            "count": len(results),
            "exported_at": __import__("datetime").datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        handle_db_errors(e, "notes export (POST)")


@router.post(
    "/export.csv",
    response_class=StreamingResponse,
    summary="Export selected notes as CSV",
    tags=["notes"]
)
async def export_notes_post_csv(
        payload: NotesExportRequest,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.export")),
):
    """CSV export for notes by explicit IDs."""
    try:
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.export")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.export",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        note_ids = payload.note_ids
        include_keywords = bool(payload.include_keywords)

        results: List[Dict[str, Any]] = []
        for nid in note_ids:
            try:
                nd = db.get_note_by_id(note_id=nid)
                if not nd:
                    continue
                if include_keywords:
                    nd["keywords"] = []
                results.append(nd)
            except Exception as fetch_err:
                logger.debug(f"Skipping note ID '{nid}' during CSV export: {fetch_err}")
                continue

        if include_keywords and results:
            _attach_keywords_bulk(db, results)

        return _notes_csv_response(results, include_keywords)
    except HTTPException:
        raise
    except Exception as e:
        handle_db_errors(e, "notes export (POST csv)")


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Get a specific note by ID",
    tags=["notes"],
    responses={status.HTTP_404_NOT_FOUND: {"model": DetailResponse}}
)
async def get_note(
        note_id: str,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.get")),
):
    logger.debug(f"User (DB client_id: {db.client_id}) fetching note: ID='{note_id}'")
    try:  # Added try block here to catch DB errors during fetch
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.get")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.get",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        note_data = db.get_note_by_id(note_id=note_id)
    except Exception as e:  # Catch DB errors from get_note_by_id
        handle_db_errors(e, "note")  # This will reraise appropriately

    if not note_data:
        logger.warning(f"Note ID '{note_id}' not found for user (DB client_id: {db.client_id}).")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    # If note_data is found, it's a dict from the DB. Pydantic will validate it on return.
    # No need for an explicit try-except for Pydantic here, FastAPI handles it.
    # Attach keywords inline
    try:
        kw_rows = db.get_keywords_for_note(note_id=note_id)
        note_data['keywords'] = kw_rows
    except Exception as kw_fetch_err:
        logger.warning(f"Fetching keywords for note {note_id} failed: {kw_fetch_err}")
    return note_data


@router.put(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Update an existing note",
    tags=["notes"],
    responses={
        status.HTTP_404_NOT_FOUND: {"model": DetailResponse},
        status.HTTP_409_CONFLICT: {"model": DetailResponse}
    }
)
async def update_note(
        note_id: str,
        note_in: NoteUpdate,
        expected_version: int = Header(..., description="The expected version of the note for optimistic locking"),
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.update")),
):
    keywords_supplied = _field_supplied(note_in, "keywords")
    conversation_supplied = _field_supplied(note_in, "conversation_id")
    message_supplied = _field_supplied(note_in, "message_id")
    kw_list = note_in.normalized_keywords if keywords_supplied else None
    raw_data = note_in.model_dump(exclude_unset=True)
    update_data: Dict[str, Any] = {}
    if "title" in raw_data and raw_data["title"] is not None:
        update_data["title"] = raw_data["title"]
    if "content" in raw_data and raw_data["content"] is not None:
        update_data["content"] = raw_data["content"]
    if conversation_supplied:
        update_data["conversation_id"] = raw_data.get("conversation_id")
    if message_supplied:
        update_data["message_id"] = raw_data.get("message_id")
    if "title" in update_data and isinstance(update_data["title"], str):
        stripped_title = update_data["title"].strip()
        if not stripped_title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Title cannot be empty or whitespace.")
        update_data["title"] = stripped_title
    if not update_data and not keywords_supplied:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields provided for update.")
    try:
        current_note: Optional[Dict[str, Any]] = None

        def _get_current_note() -> Dict[str, Any]:
            nonlocal current_note
            if current_note is None:
                current_note = db.get_note_by_id(note_id=note_id)
            if not current_note:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
            return current_note

        # Rate limit: notes.update
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.update")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.update",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        if not update_data and keywords_supplied:
            current_note = _get_current_note()
            current_version = current_note.get("version")
            if current_version is not None and int(current_version) != int(expected_version):
                raise ConflictError(
                    f"Note ID {note_id} update failed: version mismatch (db has {current_version}, client expected {expected_version}).",
                    entity="notes",
                    entity_id=note_id,
                )
        if conversation_supplied or message_supplied:
            current_note = _get_current_note()
            current_conversation_id = current_note.get("conversation_id")
            effective_conversation_id = update_data.get("conversation_id") if conversation_supplied else current_conversation_id
            if message_supplied:
                effective_message_id = update_data.get("message_id")
            else:
                # Preserve the existing message_id so a conversation change is validated
                # against the current message linkage rather than silently clearing it.
                effective_message_id = current_note.get("message_id")
            validated_conversation_id, validated_message_id = _validate_note_links(
                db,
                effective_conversation_id,
                effective_message_id,
            )
            if conversation_supplied:
                update_data["conversation_id"] = validated_conversation_id
            if message_supplied:
                update_data["message_id"] = validated_message_id
        data_keys = list(update_data.keys())
        if keywords_supplied:
            data_keys.append("keywords")
        logger.info(
            f"User (DB client_id: {db.client_id}) updating note: ID='{note_id}', Version={expected_version}, DataKeys={data_keys}")
        # Topic monitoring (non-blocking) for updated fields
        try:
            mon = get_topic_monitoring_service()
            uid = getattr(db, 'client_id', None)
            src_id = str(note_id)
            if 'title' in update_data and update_data['title']:
                mon.schedule_evaluate_and_alert(
                    user_id=str(uid) if uid else None,
                    text=str(update_data['title']),
                    source="notes.update",
                    scope_type="user",
                    scope_id=str(uid) if uid else None,
                    source_id=src_id,
                )
            if 'content' in update_data and update_data['content']:
                mon.schedule_evaluate_and_alert(
                    user_id=str(uid) if uid else None,
                    text=str(update_data['content']),
                    source="notes.update",
                    scope_type="user",
                    scope_id=str(uid) if uid else None,
                    source_id=src_id,
                )
        except Exception:
            pass
        if update_data:
            success = db.update_note(
                note_id=note_id,
                update_data=update_data,
                expected_version=expected_version
            )
            if not success:
                raise CharactersRAGDBError("Note update reported non-success without specific exception.")

        if keywords_supplied:
            _sync_note_keywords(db, note_id=note_id, keywords=kw_list or [])

        updated_note_data = db.get_note_by_id(note_id=note_id)
        if not updated_note_data:
            logger.error(f"Note '{note_id}' not found after successful update for user (DB client_id: {db.client_id}).")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found after update.")
        updated_note_data = _attach_keywords_inline(db, updated_note_data)
        logger.info(
            f"Note '{note_id}' updated successfully for user (DB client_id: {db.client_id}) to version {updated_note_data['version']}.")
        return updated_note_data
    except Exception as e:
        handle_db_errors(e, "note")


@router.patch(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Partially update an existing note",
    tags=["notes"],
    responses={
        status.HTTP_404_NOT_FOUND: {"model": DetailResponse},
        status.HTTP_409_CONFLICT: {"model": DetailResponse}
    }
)
async def patch_note(
        note_id: str,
        note_in: NoteUpdate,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        expected_version: Optional[int] = Header(None, description="Optional expected version for optimistic locking"),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.update")),
):
    """PATCH variant that allows updates without an explicit expected-version header.
    If header is not provided, it fetches current version and applies the update."""
    keywords_supplied = _field_supplied(note_in, "keywords")
    conversation_supplied = _field_supplied(note_in, "conversation_id")
    message_supplied = _field_supplied(note_in, "message_id")
    kw_list = note_in.normalized_keywords if keywords_supplied else None
    raw_data = note_in.model_dump(exclude_unset=True)
    update_data: Dict[str, Any] = {}
    if "title" in raw_data and raw_data["title"] is not None:
        update_data["title"] = raw_data["title"]
    if "content" in raw_data and raw_data["content"] is not None:
        update_data["content"] = raw_data["content"]
    if conversation_supplied:
        update_data["conversation_id"] = raw_data.get("conversation_id")
    if message_supplied:
        update_data["message_id"] = raw_data.get("message_id")
    if "title" in update_data and isinstance(update_data["title"], str):
        stripped_title = update_data["title"].strip()
        if not stripped_title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Title cannot be empty or whitespace.")
        update_data["title"] = stripped_title
    if not update_data and not keywords_supplied:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields provided for update.")
    try:
        current_note: Optional[Dict[str, Any]] = None

        def _get_current_note() -> Dict[str, Any]:
            nonlocal current_note
            if current_note is None:
                current_note = db.get_note_by_id(note_id=note_id)
            if not current_note:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
            return current_note

        if expected_version is None:
            # Fallback to current version if not provided
            current = _get_current_note()
            expected_version = int(current.get("version", 1))
        elif not update_data and keywords_supplied:
            current = _get_current_note()
            current_version = current.get("version")
            if current_version is not None and int(current_version) != int(expected_version):
                raise ConflictError(
                    f"Note ID {note_id} update failed: version mismatch (db has {current_version}, client expected {expected_version}).",
                    entity="notes",
                    entity_id=note_id,
                )

        # Rate limit: notes.update
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.update")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.update",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        if conversation_supplied or message_supplied:
            current = _get_current_note()
            current_conversation_id = current.get("conversation_id")
            effective_conversation_id = update_data.get("conversation_id") if conversation_supplied else current_conversation_id
            if message_supplied:
                effective_message_id = update_data.get("message_id")
            else:
                # Preserve the existing message_id so a conversation change is validated
                # against the current message linkage rather than silently clearing it.
                effective_message_id = current.get("message_id")
            validated_conversation_id, validated_message_id = _validate_note_links(
                db,
                effective_conversation_id,
                effective_message_id,
            )
            if conversation_supplied:
                update_data["conversation_id"] = validated_conversation_id
            if message_supplied:
                update_data["message_id"] = validated_message_id
        data_keys = list(update_data.keys())
        if keywords_supplied:
            data_keys.append("keywords")
        logger.info(
            f"User (DB client_id: {db.client_id}) partially updating note: ID='{note_id}', Version={expected_version}, DataKeys={data_keys}")
        if update_data:
            success = db.update_note(
                note_id=note_id,
                update_data=update_data,
                expected_version=expected_version
            )
            if not success:
                raise CharactersRAGDBError("Note update reported non-success without specific exception.")

        if keywords_supplied:
            _sync_note_keywords(db, note_id=note_id, keywords=kw_list or [])

        updated_note_data = db.get_note_by_id(note_id=note_id)
        if not updated_note_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found after update.")
        updated_note_data = _attach_keywords_inline(db, updated_note_data)
        return updated_note_data
    except Exception as e:
        handle_db_errors(e, "note")


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Soft-delete a note",
    tags=["notes"],
    responses={
        status.HTTP_404_NOT_FOUND: {"model": DetailResponse},
        status.HTTP_409_CONFLICT: {"model": DetailResponse}
    }
)
async def delete_note(
        note_id: str,
        expected_version: int = Header(..., description="The expected version of the note for optimistic locking"),
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.delete")),
) -> Response:
    try:
        # Rate limit: notes.delete
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.delete")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.delete",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        logger.info(
            f"User (DB client_id: {db.client_id}) soft-deleting note: ID='{note_id}', Version={expected_version}")
        success = db.soft_delete_note(
            note_id=note_id,
            expected_version=expected_version
        )
        if not success:
            raise CharactersRAGDBError("Note soft delete reported non-success without specific exception.")
        logger.info(
            f"Note '{note_id}' soft-deleted successfully (or was already deleted) for user (DB client_id: {db.client_id}).")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        handle_db_errors(e, "note")


@router.post(
    "/{note_id}/restore",
    response_model=NoteResponse,
    summary="Restore a soft-deleted note",
    tags=["notes"],
    responses={
        status.HTTP_404_NOT_FOUND: {"model": DetailResponse},
        status.HTTP_409_CONFLICT: {"model": DetailResponse}
    }
)
async def restore_note(
        note_id: str,
        expected_version: int = Query(..., description="The expected version of the note for optimistic locking"),
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.restore")),
) -> NoteResponse:
    """
    Restores a soft-deleted note.

    Requires the `expected_version` query parameter for optimistic locking.
    Returns the restored note on success.
    """
    try:
        # Rate limit: notes.restore
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.restore")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.restore",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})

        logger.info(
            f"User (DB client_id: {db.client_id}) restoring note: ID='{note_id}', Version={expected_version}")

        success = db.restore_note(
            note_id=note_id,
            expected_version=expected_version
        )
        if not success:
            raise CharactersRAGDBError("Note restore reported non-success without specific exception.")

        logger.info(
            f"Note '{note_id}' restored successfully for user (DB client_id: {db.client_id}).")

        # Fetch the restored note to return it
        restored_note = db.get_note_by_id(note_id)
        if not restored_note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Note '{note_id}' not found after restore.")

        # Fetch keywords for the note
        keywords = db.get_keywords_for_note(note_id)
        keyword_responses = [
            KeywordResponse(id=str(kw['id']), keyword=kw['keyword'])
            for kw in keywords
        ] if keywords else []

        return NoteResponse(
            id=str(restored_note['id']),
            title=restored_note.get('title', ''),
            content=restored_note.get('content', ''),
            created_at=restored_note.get('created_at'),
            last_modified=restored_note.get('last_modified'),
            version=restored_note.get('version', 1),
            client_id=restored_note.get('client_id', ''),
            deleted=bool(restored_note.get('deleted', False)),
            keywords=keyword_responses
        )
    except Exception as e:
        handle_db_errors(e, "note")


# --- Keyword Endpoints (related to Notes) ---

@router.post(
    "/title/suggest",
    response_model=TitleSuggestResponse,
    summary="Suggest a title for provided content",
    tags=["notes"],
)
async def suggest_note_title(
        payload: TitleSuggestRequest,
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.title.suggest")),
):
    try:
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.title.suggest")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.title.suggest",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})

        opts = _build_title_opts(payload)
        title = await asyncio.to_thread(generate_note_title, payload.content, options=opts)
        return TitleSuggestResponse(title=title)
    except HTTPException:
        raise
    except Exception as e:
        handle_db_errors(e, "title suggestion")

@router.post(
    "/bulk",
    response_model=NoteBulkCreateResponse,
    summary="Bulk create notes with optional keywords",
    tags=["notes"],
    dependencies=[Depends(rbac_rate_limit("notes.bulk_create"))]
)
async def bulk_create_notes(
        request: NoteBulkCreateRequest,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user)
):
    results: List[NoteBulkCreateItemResult] = []
    created = 0
    failed = 0
    # Enforce centralized per-request rate limit (notes.bulk_create)
    try:
        allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.bulk_create")
    except Exception:
        allowed, meta = True, {}
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Rate limit exceeded for notes.bulk_create",
                            headers={"Retry-After": str(meta.get("retry_after", 60))})

    for item in request.notes:
        try:
            # Compute title per item
            effective_title = (getattr(item, 'title', None) or "").strip()
            if not effective_title:
                if getattr(item, "auto_title", False):
                    try:
                        opts = _build_title_opts(item)
                        effective_title = await asyncio.to_thread(
                            generate_note_title,
                            item.content,
                            options=opts,
                        )
                    except Exception as gen_err:
                        logger.warning(f"[Bulk] Auto-title generation failed, falling back: {gen_err}")
                        effective_title = await asyncio.to_thread(generate_note_title, item.content)
                else:
                    raise InputError("Title is required for bulk item unless auto_title=true.")

            conversation_id, message_id = _validate_note_links(
                db,
                item.conversation_id,
                item.message_id,
            )

            note_id = db.add_note(
                title=effective_title,
                content=item.content,
                note_id=item.id,
                conversation_id=conversation_id,
                message_id=message_id,
            )
            if not note_id:
                raise CharactersRAGDBError("Failed to create note (no ID returned)")

            # Topic monitoring (non-blocking) per item
            try:
                mon = get_topic_monitoring_service()
                uid = getattr(db, 'client_id', None)
                src_id = str(note_id)
                if effective_title:
                    mon.schedule_evaluate_and_alert(
                        user_id=str(uid) if uid else None,
                        text=effective_title,
                        source="notes.bulk_create",
                        scope_type="user",
                        scope_id=str(uid) if uid else None,
                        source_id=src_id,
                    )
                if getattr(item, 'content', None):
                    mon.schedule_evaluate_and_alert(
                        user_id=str(uid) if uid else None,
                        text=item.content,
                        source="notes.bulk_create",
                        scope_type="user",
                        scope_id=str(uid) if uid else None,
                        source_id=src_id,
                    )
            except Exception:
                pass

            # Attach keywords if provided
            try:
                kw_list = item.normalized_keywords if hasattr(item, 'normalized_keywords') else None
                if kw_list:
                    for kw in kw_list:
                        try:
                            kw_row = _get_or_create_keyword_row(db, kw)
                            if kw_row and kw_row.get('id') is not None:
                                db.link_note_to_keyword(note_id=note_id, keyword_id=int(kw_row['id']))
                        except Exception as kw_err:
                            logger.warning(f"[Bulk] Keyword attach failed for '{kw}' on note {note_id}: {kw_err}")
            except Exception as kw_outer_err:
                logger.warning(f"[Bulk] Keyword processing issue for note {note_id}: {kw_outer_err}")

            nd = db.get_note_by_id(note_id=note_id)
            if not nd:
                raise CharactersRAGDBError("Created note could not be retrieved.")
            nd = _attach_keywords_inline(db, nd)
            results.append(NoteBulkCreateItemResult(success=True, note=nd))
            created += 1
        except Exception as e:
            logger.warning(f"Bulk note create failed for title='{getattr(item, 'title', '')}': {e}")
            results.append(NoteBulkCreateItemResult(success=False, error=str(e)))
            failed += 1

    response_payload = NoteBulkCreateResponse(results=results, created_count=created, failed_count=failed)
    response_status = status.HTTP_200_OK if failed == 0 else status.HTTP_207_MULTI_STATUS
    return JSONResponse(content=jsonable_encoder(response_payload), status_code=response_status)


@router.post(
    "/keywords/",
    response_model=KeywordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new keyword",
    tags=["Keywords (for Notes)"]
)
async def create_keyword(
        keyword_in: KeywordCreate,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("keywords.create")),
):
    try:
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "keywords.create")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for keywords.create",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        logger.info(f"User (DB client_id: {db.client_id}) creating keyword: Text='{keyword_in.keyword}'")
        keyword_id = db.add_keyword(keyword_text=keyword_in.keyword)
        if keyword_id is None:
            raise CharactersRAGDBError("Keyword creation failed to return an ID.")

        created_keyword_data = db.get_keyword_by_id(keyword_id=keyword_id)
        if not created_keyword_data:
            logger.error(
                f"Failed to retrieve keyword '{keyword_id}' after creation for user (DB client_id: {db.client_id}).")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Keyword created but could not be retrieved.")
        logger.info(f"Keyword '{keyword_id}' created successfully for user (DB client_id: {db.client_id}).")
        return created_keyword_data
    except Exception as e:
        handle_db_errors(e, "keyword")


@router.get(
    "/keywords/{keyword_id}",
    response_model=KeywordResponse,
    summary="Get a keyword by its ID",
    tags=["Keywords (for Notes)"],
    responses={status.HTTP_404_NOT_FOUND: {"model": DetailResponse}}
)
async def get_keyword(
        keyword_id: int,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("keywords.get")),
):
    logger.debug(f"User (DB client_id: {db.client_id}) fetching keyword by ID: {keyword_id}")
    try: # Added try block
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "keywords.get")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for keywords.get",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        keyword_data = db.get_keyword_by_id(keyword_id=keyword_id)
    except Exception as e:
        handle_db_errors(e, "keyword")
        return

    if not keyword_data:
        logger.warning(f"Keyword ID '{keyword_id}' not found for user (DB client_id: {db.client_id}).")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword not found")
    return keyword_data


@router.get(
    "/keywords/text/{keyword_text}",
    response_model=KeywordResponse,
    summary="Get a keyword by its text content",
    tags=["Keywords (for Notes)"],
    responses={status.HTTP_404_NOT_FOUND: {"model": DetailResponse}}
)
async def get_keyword_by_text(
        keyword_text: str,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("keywords.get")),
):
    try:
        logger.debug(f"User (DB client_id: {db.client_id}) fetching keyword by text: '{keyword_text}'")
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "keywords.get")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for keywords.get",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        keyword_data = db.get_keyword_by_text(keyword_text=keyword_text)
        if not keyword_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword not found")
        return keyword_data
    except Exception as e:
        handle_db_errors(e, "keyword")


@router.get(
    "/keywords/",
    response_model=List[KeywordResponse],
    summary="List all keywords for the current user",
    tags=["Keywords (for Notes)"]
)
async def list_keywords_endpoint(  # Renamed to avoid conflict
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("keywords.list")),
):
    try:
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "keywords.list")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for keywords.list",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        logger.debug(f"User (DB client_id: {db.client_id}) listing keywords: limit={limit}, offset={offset}")
        keywords_data = db.list_keywords(limit=limit, offset=offset)
        return keywords_data
    except Exception as e:
        handle_db_errors(e, "keywords list")


@router.delete(
    "/keywords/{keyword_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Soft-delete a keyword",
    tags=["Keywords (for Notes)"],
    responses={
        status.HTTP_404_NOT_FOUND: {"model": DetailResponse},
        status.HTTP_409_CONFLICT: {"model": DetailResponse}
    }
)
async def delete_keyword(
        keyword_id: int,
        expected_version: int = Header(..., description="The expected version of the keyword for optimistic locking"),
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("keywords.delete")),
) -> Response:
    try:
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "keywords.delete")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for keywords.delete",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        logger.info(
            f"User (DB client_id: {db.client_id}) soft-deleting keyword: ID='{keyword_id}', Version={expected_version}")
        success = db.soft_delete_keyword(
            keyword_id=keyword_id,
            expected_version=expected_version
        )
        if not success:
            raise CharactersRAGDBError("Keyword soft delete reported non-success without specific exception.")
        logger.info(
            f"Keyword '{keyword_id}' soft-deleted successfully (or was already deleted) for user (DB client_id: {db.client_id}).")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        handle_db_errors(e, "keyword")


@router.get(
    "/keywords/search/",
    response_model=List[KeywordResponse],
    summary="Search keywords for the current user",
    tags=["Keywords (for Notes)"]
)
async def search_keywords_endpoint(  # Renamed
        query: str = Query(..., min_length=1, description="Search term for keywords"),
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        limit: int = Query(10, ge=1, le=100),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("keywords.search")),
):
    try:
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "keywords.search")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for keywords.search",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        logger.debug(f"User (DB client_id: {db.client_id}) searching keywords: query='{query}', limit={limit}")
        keywords_data = db.search_keywords(search_term=query, limit=limit)
        return keywords_data
    except Exception as e:
        handle_db_errors(e, "keywords search")


# --- Note-Keyword Linking Endpoints ---
@router.post(
    "/{note_id}/keywords/{keyword_id}",
    response_model=NoteKeywordLinkResponse,
    summary="Link a note to a keyword",
    tags=["Notes Linking"],
    responses={status.HTTP_404_NOT_FOUND: {"model": DetailResponse}}
)
async def link_note_to_keyword_endpoint(
        note_id: str,
        keyword_id: int,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.link_keyword")),
):
    try:
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.link_keyword")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.link_keyword",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        logger.info(f"User (DB client_id: {db.client_id}) linking note '{note_id}' to keyword '{keyword_id}'")
        # Check if note and keyword exist in the user's DB
        note_data = db.get_note_by_id(note_id)
        if not note_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Note with ID '{note_id}' not found.")
        keyword_data = db.get_keyword_by_id(keyword_id)
        if not keyword_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Keyword with ID '{keyword_id}' not found.")

        success = db.link_note_to_keyword(note_id=note_id, keyword_id=keyword_id)
        msg = "Note linked to keyword successfully." if success else "Link already exists or was created."
        return NoteKeywordLinkResponse(success=True, message=msg)  # True even if already exists
    except HTTPException:
        raise
    except Exception as e:
        handle_db_errors(e, "note-keyword link")


@router.delete(
    "/{note_id}/keywords/{keyword_id}",
    response_model=NoteKeywordLinkResponse,
    summary="Unlink a note from a keyword",
    tags=["Notes Linking"]
)
async def unlink_note_from_keyword_endpoint(
        note_id: str,
        keyword_id: int,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.unlink_keyword")),
):
    try:
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.unlink_keyword")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.unlink_keyword",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        logger.info(f"User (DB client_id: {db.client_id}) unlinking note '{note_id}' from keyword '{keyword_id}'")
        success = db.unlink_note_from_keyword(note_id=note_id, keyword_id=keyword_id)
        msg = "Note unlinked from keyword successfully." if success else "Link not found or no action taken."
        return NoteKeywordLinkResponse(success=success, message=msg)
    except Exception as e:
        handle_db_errors(e, "note-keyword unlink")


@router.get(
    "/{note_id}/keywords/",
    response_model=KeywordsForNoteResponse,
    summary="Get all keywords linked to a note",
    tags=["Notes Linking"],
    responses={status.HTTP_404_NOT_FOUND: {"model": DetailResponse}}
)
async def get_keywords_for_note_endpoint(
        note_id: str,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("notes.keywords.list")),
):
    try:
        logger.debug(f"User (DB client_id: {db.client_id}) fetching keywords for note '{note_id}'")
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "notes.keywords.list")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for notes.keywords.list",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        note_check = db.get_note_by_id(note_id=note_id)
        if not note_check:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Note with ID '{note_id}' not found.")

        keywords_list = db.get_keywords_for_note(note_id=note_id)
        return KeywordsForNoteResponse(note_id=note_id, keywords=keywords_list)
    except HTTPException:
        raise
    except Exception as e:
        handle_db_errors(e, "keywords for note")


@router.get(
    "/keywords/{keyword_id}/notes/",
    response_model=NotesForKeywordResponse,
    summary="Get all notes linked to a keyword",
    tags=["Notes Linking"],
    responses={status.HTTP_404_NOT_FOUND: {"model": DetailResponse}}
)
async def get_notes_for_keyword_endpoint(
        keyword_id: int,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
        current_user: User = Depends(get_request_user),
        _: None = Depends(rbac_rate_limit("keywords.notes.list")),
):
    try:
        logger.debug(f"User (DB client_id: {db.client_id}) fetching notes for keyword '{keyword_id}'")
        try:
            allowed, meta = await rate_limiter.check_user_rate_limit(int(current_user.id), "keywords.notes.list")
        except Exception:
            allowed, meta = True, {}
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Rate limit exceeded for keywords.notes.list",
                                headers={"Retry-After": str(meta.get("retry_after", 60))})
        keyword_check = db.get_keyword_by_id(keyword_id=keyword_id)
        if not keyword_check:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Keyword with ID '{keyword_id}' not found.")

        notes_list = db.get_notes_for_keyword(keyword_id=keyword_id, limit=limit, offset=offset)
        return NotesForKeywordResponse(keyword_id=keyword_id, notes=notes_list)
    except HTTPException:
        raise
    except Exception as e:
        handle_db_errors(e, "notes for keyword")

#
# --- End of Notes and Keywords Endpoints ---
########################################################################################################################
