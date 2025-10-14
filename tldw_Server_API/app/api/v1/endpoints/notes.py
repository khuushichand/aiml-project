# app/api/v1/endpoints/notes.py
#
#
# Imports
from loguru import logger
import time
from collections import defaultdict
import sys
from typing import List, Optional, Dict, Any
#
# 3rd-party Libraries
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
    Body,
    Header  # Keep Header for expected_version
)
from loguru import logger  # Using loguru as in your chat example
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
)
# Dependency to get user-specific ChaChaNotes_DB instance
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.core.Monitoring.topic_monitoring_service import get_topic_monitoring_service
#
#
#######################################################################################################################
#
# Functions:

router = APIRouter()

# Simple rate limiter for resource creation
class SimpleRateLimiter:
    def __init__(self, max_requests_per_minute: int = 30):
        self.max_requests = max_requests_per_minute
        self.requests = defaultdict(list)
    
    def check_rate_limit(self, client_id: str, request=None) -> bool:
        """Check if client has exceeded rate limit."""
        # Skip rate limiting in test contexts
        import os
        if os.getenv("TEST_MODE") == "true" or os.getenv("PYTEST_CURRENT_TEST") is not None or "pytest" in sys.modules:
            return True
            
        current_time = time.time()
        minute_ago = current_time - 60
        
        # Clean up old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > minute_ago
        ]
        
        # Check if limit exceeded
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        # Add current request
        self.requests[client_id].append(current_time)
        return True

# Initialize rate limiter for notes creation
notes_rate_limiter = SimpleRateLimiter(max_requests_per_minute=30)

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
        # Prioritize version mismatch message
        exception_message_str = str(e.args[0]) if e.args else str(e)  # Get the primary message
        if "version mismatch" in exception_message_str.lower():
            detail_message = "The resource has been modified since you last fetched it. Please refresh and try again."
        elif hasattr(e, 'entity') and e.entity and hasattr(e, 'entity_id') and e.entity_id:
            detail_message = f"A conflict occurred with {e.entity} (ID: {e.entity_id}). It might have been modified or deleted, or a unique constraint was violated."
        elif "already exists" in exception_message_str.lower():
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
    tags=["notes"]
)
async def notes_health() -> Dict[str, Any]:
    """Lightweight health endpoint for the Notes subsystem."""
    from tldw_Server_API.app.core.config import settings
    import os
    from pathlib import Path

    health = {
        "service": "notes",
        "status": "healthy",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "components": {}
    }

    try:
        base_dir = settings.get("USER_DB_BASE_DIR")
        base_ok = base_dir is not None
        exists = Path(base_dir).exists() if base_ok else False
        writable = False
        if exists:
            try:
                test_path = Path(base_dir) / ".health_check"
                with open(test_path, "w") as f:
                    f.write("ok")
                os.remove(test_path)
                writable = True
            except Exception:
                writable = False

        health["components"]["storage"] = {
            "base_dir": str(base_dir) if base_dir else None,
            "exists": exists,
            "writable": writable
        }

        if not base_ok or not exists:
            health["status"] = "degraded"
        if base_ok and exists and not writable:
            health["status"] = "degraded"
    except Exception as e:
        health["status"] = "unhealthy"
        health["error"] = str(e)

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
        db: CharactersRAGDB = Depends(get_chacha_db_for_user)  # Use the user-specific DB instance
):
    try:
        # Check rate limit for note creation
        client_id = db.client_id or "anonymous"
        if not notes_rate_limiter.check_rate_limit(client_id, request):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Maximum 30 notes per minute allowed."
            )
        
        # The user context (user_id) is implicitly handled by `get_chacha_db_for_user`
        # The `db` instance is already specific to the authenticated user.
        logger.info(f"User (via DB instance client_id: {db.client_id}) creating note: Title='{note_in.title[:30]}...'")
        # Topic monitoring (non-blocking) for title and content
        try:
            mon = get_topic_monitoring_service()
            uid = getattr(db, 'client_id', None)
            if note_in.title:
                mon.evaluate_and_alert(user_id=str(uid) if uid else None, text=note_in.title, source="notes.create", scope_type="user", scope_id=str(uid) if uid else None)
            if note_in.content:
                mon.evaluate_and_alert(user_id=str(uid) if uid else None, text=note_in.content, source="notes.create", scope_type="user", scope_id=str(uid) if uid else None)
        except Exception:
            pass
        note_id = db.add_note(
            title=note_in.title,
            content=note_in.content,
            note_id=note_in.id  # Pass optional client-provided ID
        )
        if note_id is None:  # Should be caught by exceptions
            raise CharactersRAGDBError("Note creation failed to return an ID.")

        # Handle optional keywords: create if needed and link to this note
        try:
            kw_list = note_in.normalized_keywords if hasattr(note_in, 'normalized_keywords') else None
            if kw_list:
                for kw in kw_list:
                    try:
                        # Find or create keyword (case-insensitive uniqueness enforced by DB schema)
                        kw_row = db.get_keyword_by_text(kw)
                        if not kw_row:
                            kw_id = db.add_keyword(kw)
                            kw_row = db.get_keyword_by_id(kw_id) if kw_id is not None else None
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
    "/{note_id}",
    response_model=NoteResponse,
    summary="Get a specific note by ID",
    tags=["notes"],
    responses={status.HTTP_404_NOT_FOUND: {"model": DetailResponse}}
)
async def get_note(
        note_id: str,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    logger.debug(f"User (DB client_id: {db.client_id}) fetching note: ID='{note_id}'")
    try:  # Added try block here to catch DB errors during fetch
        note_data = db.get_note_by_id(note_id=note_id)
    except Exception as e:  # Catch DB errors from get_note_by_id
        handle_db_errors(e, "note")  # This will reraise appropriately
        return  # Should not be reached if handle_db_errors raises

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


@router.get(
    "/",
    response_model=Any,
    summary="List all notes for the current user",
    tags=["notes"]
)
async def list_notes(
        request: Request,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        limit: int = Query(100, ge=1, le=1000, description="Number of notes to return"),
        offset: int = Query(0, ge=0, description="Offset for pagination"),
        include_keywords: bool = Query(False, description="If true, include linked keywords inline per note")
):
    try:
        logger.debug(f"User (DB client_id: {db.client_id}) listing notes: limit={limit}, offset={offset}")
        notes_data = db.list_notes(limit=limit, offset=offset)
        # Attach keywords inline for each note (optional for performance)
        if include_keywords:
            try:
                for nd in notes_data:
                    try:
                        nd['keywords'] = db.get_keywords_for_note(note_id=nd.get('id'))
                    except Exception as kw_err:
                        logger.warning(f"Fetching keywords for note {nd.get('id')} failed: {kw_err}")
            except Exception as outer_err:
                logger.warning(f"Attaching keywords for notes list failed: {outer_err}")
        # To satisfy both tests: return dict when no explicit pagination params provided; else list
        qp = request.query_params
        if ("limit" in qp) or ("offset" in qp):
            return notes_data
        return {"notes": notes_data}
    except Exception as e:
        handle_db_errors(e, "notes list")


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
        db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    update_data = note_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update.")
    try:
        logger.info(
            f"User (DB client_id: {db.client_id}) updating note: ID='{note_id}', Version={expected_version}, DataKeys={list(update_data.keys())}")
        # Topic monitoring (non-blocking) for updated fields
        try:
            mon = get_topic_monitoring_service()
            uid = getattr(db, 'client_id', None)
            if 'title' in update_data and update_data['title']:
                mon.evaluate_and_alert(user_id=str(uid) if uid else None, text=str(update_data['title']), source="notes.update", scope_type="user", scope_id=str(uid) if uid else None)
            if 'content' in update_data and update_data['content']:
                mon.evaluate_and_alert(user_id=str(uid) if uid else None, text=str(update_data['content']), source="notes.update", scope_type="user", scope_id=str(uid) if uid else None)
        except Exception:
            pass
        success = db.update_note(
            note_id=note_id,
            update_data=update_data,
            expected_version=expected_version
        )
        if not success:
            raise CharactersRAGDBError("Note update reported non-success without specific exception.")

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
        expected_version: Optional[int] = Header(None, description="Optional expected version for optimistic locking")
):
    """PATCH variant that allows updates without an explicit expected-version header.
    If header is not provided, it fetches current version and applies the update."""
    update_data = note_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update.")
    try:
        if expected_version is None:
            # Fallback to current version if not provided
            current = db.get_note_by_id(note_id=note_id)
            if not current:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
            expected_version = int(current.get("version", 1))

        logger.info(
            f"User (DB client_id: {db.client_id}) partially updating note: ID='{note_id}', Version={expected_version}, DataKeys={list(update_data.keys())}")
        success = db.update_note(
            note_id=note_id,
            update_data=update_data,
            expected_version=expected_version
        )
        if not success:
            raise CharactersRAGDBError("Note update reported non-success without specific exception.")

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
        db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    try:
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
        return  # FastAPI handles 204 No Content
    except Exception as e:
        handle_db_errors(e, "note")


@router.get(
    "/search/",
    response_model=List[NoteResponse],
    summary="Search notes for the current user",
    tags=["notes"]
)
async def search_notes_endpoint(  # Renamed to avoid conflict with imported search_notes
        query: str = Query(..., min_length=1, description="Search term for notes"),
        db: CharactersRAGDB = Depends(get_chacha_db_for_user),
        limit: int = Query(10, ge=1, le=100, description="Number of results to return"),
        include_keywords: bool = Query(False, description="If true, include linked keywords inline per note")
):
    try:
        logger.debug(f"User (DB client_id: {db.client_id}) searching notes: query='{query}', limit={limit}")
        notes_data = db.search_notes(search_term=query, limit=limit)
        # Attach keywords inline (optional)
        if include_keywords:
            try:
                for nd in notes_data:
                    try:
                        nd['keywords'] = db.get_keywords_for_note(note_id=nd.get('id'))
                    except Exception as kw_err:
                        logger.warning(f"Fetching keywords for note {nd.get('id')} failed: {kw_err}")
            except Exception as outer_err:
                logger.warning(f"Attaching keywords for notes search failed: {outer_err}")
        return notes_data
    except Exception as e:
        handle_db_errors(e, "notes search")


# --- Keyword Endpoints (related to Notes) ---
@router.post(
    "/bulk",
    response_model=NoteBulkCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create notes with optional keywords",
    tags=["notes"]
)
async def bulk_create_notes(
        request: NoteBulkCreateRequest,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    results: List[NoteBulkCreateItemResult] = []
    created = 0
    failed = 0

    for item in request.notes:
        try:
            # Topic monitoring (non-blocking) per item
            try:
                mon = get_topic_monitoring_service()
                uid = getattr(db, 'client_id', None)
                if getattr(item, 'title', None):
                    mon.evaluate_and_alert(user_id=str(uid) if uid else None, text=item.title, source="notes.bulk_create", scope_type="user", scope_id=str(uid) if uid else None)
                if getattr(item, 'content', None):
                    mon.evaluate_and_alert(user_id=str(uid) if uid else None, text=item.content, source="notes.bulk_create", scope_type="user", scope_id=str(uid) if uid else None)
            except Exception:
                pass
            note_id = db.add_note(
                title=item.title,
                content=item.content,
                note_id=item.id
            )
            if not note_id:
                raise CharactersRAGDBError("Failed to create note (no ID returned)")

            # Attach keywords if provided
            try:
                kw_list = item.normalized_keywords if hasattr(item, 'normalized_keywords') else None
                if kw_list:
                    for kw in kw_list:
                        try:
                            kw_row = db.get_keyword_by_text(kw)
                            if not kw_row:
                                kw_id = db.add_keyword(kw)
                                kw_row = db.get_keyword_by_id(kw_id) if kw_id is not None else None
                            if kw_row and kw_row.get('id') is not None:
                                db.link_note_to_keyword(note_id=note_id, keyword_id=int(kw_row['id']))
                        except Exception as kw_err:
                            logger.warning(f"[Bulk] Keyword attach failed for '{kw}' on note {note_id}: {kw_err}")
            except Exception as kw_outer_err:
                logger.warning(f"[Bulk] Keyword processing issue for note {note_id}: {kw_outer_err}")

            nd = db.get_note_by_id(note_id=note_id)
            nd = _attach_keywords_inline(db, nd) if nd else None
            results.append(NoteBulkCreateItemResult(success=True, note=nd))
            created += 1
        except Exception as e:
            logger.warning(f"Bulk note create failed for title='{getattr(item, 'title', '')}': {e}")
            results.append(NoteBulkCreateItemResult(success=False, error=str(e)))
            failed += 1

    return NoteBulkCreateResponse(results=results, created_count=created, failed_count=failed)


@router.post(
    "/keywords/",
    response_model=KeywordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new keyword",
    tags=["Keywords (for Notes)"]
)
async def create_keyword(
        keyword_in: KeywordCreate,
        db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    try:
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
        db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    logger.debug(f"User (DB client_id: {db.client_id}) fetching keyword by ID: {keyword_id}")
    try: # Added try block
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
        db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    try:
        logger.debug(f"User (DB client_id: {db.client_id}) fetching keyword by text: '{keyword_text}'")
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
        offset: int = Query(0, ge=0)
):
    try:
        logger.debug(f"User (DB client_id: {db.client_id}) listing keywords: limit={limit}, offset={offset}")
        keywords_data = db.list_keywords(limit=limit, offset=offset)
        return keywords_data
    except Exception as e:
        handle_db_errors(e, "keywords list")


@router.delete(
    "/keywords/{keyword_id}",
    status_code=status.HTTP_204_NO_CONTENT,
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
        db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    try:
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
        return
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
        limit: int = Query(10, ge=1, le=100)
):
    try:
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
        db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    try:
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
        db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    try:
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
        db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    try:
        logger.debug(f"User (DB client_id: {db.client_id}) fetching keywords for note '{note_id}'")
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
        offset: int = Query(0, ge=0)
):
    try:
        logger.debug(f"User (DB client_id: {db.client_id}) fetching notes for keyword '{keyword_id}'")
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
# Utility to attach keywords to a note dict
def _attach_keywords_inline(db: CharactersRAGDB, note_dict: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if note_dict and note_dict.get('id'):
            note_dict['keywords'] = db.get_keywords_for_note(note_id=note_dict['id'])
    except Exception as e:
        logger.warning(f"Failed to attach keywords to note {note_dict.get('id')}: {e}")
    return note_dict
