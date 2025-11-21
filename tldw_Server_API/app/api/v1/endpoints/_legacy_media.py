# Server_API/app/api/v1/endpoints/media.py
# Description: This code provides a FastAPI endpoint for media ingestion, processing, and
#   storage under the `/media` endpoint
#   Filetypes supported:
#       video: `.mp4`, `.mkv`, `.avi`, `.mov`, `.flv`, `.webm`,
#       audio: `.mp3`, `.aac`, `.flac`, `.wav`, `.ogg`,
#       document: `.PDF`, `.docx`, `.txt`, `.rtf`,
#       XML,
#       archive: `.zip`,
#       eBook: `.epub`,
# FIXME
#
# Imports
import os
import re
import sqlite3
from math import ceil
import aiofiles
import asyncio
import functools
import hashlib
import json
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path as FilePath
from typing import Any, Dict, List, Optional, Tuple, Callable, Literal, Union, Set
#
# 3rd-party imports
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    status,
    UploadFile
)
import httpx
from pydantic import BaseModel, ValidationError, Field
import redis
# API Rate Limiter/Caching via Redis
# Use centralized rate limiter that respects TEST_MODE
from tldw_Server_API.app.api.v1.API_Deps.rate_limiting import limiter
from starlette.responses import JSONResponse, Response, StreamingResponse
from fastapi import Response as FastAPIResponse

# Compatibility aliases for status codes across Starlette versions
try:
    HTTP_422_UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_CONTENT
except AttributeError:  # Starlette < 0.27
    HTTP_422_UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_ENTITY

try:
    HTTP_413_TOO_LARGE = status.HTTP_413_CONTENT_TOO_LARGE
except AttributeError:  # Starlette < 0.27
    HTTP_413_TOO_LARGE = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

# FastAPI router must be defined before any @router decorators are executed
router = APIRouter()

#
# Local Imports
#
# --- Core Libraries (New) ---
# Configuration (Import settings if needed directly, else handled by dependencies)
# from tldw_Server_API.app.core.config import settings, config
# Authentication & User Identification (Primary Dependency)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.AuthNZ.permissions import PermissionChecker, MEDIA_CREATE
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit
# Database Instance Dependency (Gets DB based on User)
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user, try_get_media_db_for_user
from tldw_Server_API.app.core.AuthNZ.jwt_service import verify_token
from tldw_Server_API.app.core.DB_Management.DB_Manager import (
    get_paginated_files,
    get_full_media_details_rich2,
)
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (
    MediaDatabase,
    DatabaseError,
    InputError,
    ConflictError,
    SchemaError,
    get_document_version,
    check_media_exists,
    fetch_keywords_for_media,
)
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.Ingestion_Media_Processing.Claims.ingestion_claims import (
    extract_claims_for_chunks,
    store_claims,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.Upload_Sink import (
    process_and_validate_file,
    FileValidationError,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.input_sourcing import (
    TempDirManager,
    save_uploaded_files as _save_uploaded_files,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.result_normalization import (
    normalize_process_batch,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.persistence import (
    persist_primary_av_item,
    persist_doc_item_and_children,
)
from tldw_Server_API.app.api.v1.API_Deps.validations_deps import file_validator_instance
from tldw_Server_API.app.core.testing import is_test_mode as _is_test_mode
from tldw_Server_API.app.api.v1.API_Deps.backpressure import guard_backpressure_and_quota
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import (
    get_usage_event_logger,
    UsageEventLogger,
)
from tldw_Server_API.app.api.v1.API_Deps.media_add_deps import get_add_media_form
from tldw_Server_API.app.api.v1.API_Deps.media_code_deps import get_process_code_form
from tldw_Server_API.app.api.v1.API_Deps.media_processing_deps import (
    get_process_videos_form,
)
from tldw_Server_API.app.core.Utils.Utils import sanitize_filename

# -----------------------------
# Code processing helpers
# -----------------------------
# Rate limit tuning for search endpoint; must be defined after imports
_SEARCH_RATE_LIMIT = "600/minute" if _is_test_mode() else "30/minute"

CODE_ALLOWED_EXTENSIONS: Set[str] = {
    ".py",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cc",
    ".cxx",
    ".cs",
    ".java",
    ".kt",
    ".kts",
    ".swift",
    ".rs",
    ".go",
    ".rb",
    ".php",
    ".pl",
    ".lua",
    ".sql",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".ts",
    ".tsx",
    ".jsx",
    ".js",
}

# --------------------- Media List (GET /api/v1/media) ---------------------

@router.get(
    "",
    tags=["Media Management"],
    summary="List Media",
)
@router.get(
    "/",
    tags=["Media Management"],
    summary="List Media (slash)",
)
async def list_media_endpoint(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    results_per_page: int = Query(10, ge=1, description="Items per page"),
    db: MediaDatabase = Depends(get_media_db_for_user),
    request: Request = None,
    current_user: User = Depends(get_request_user),
    response: FastAPIResponse = None,
):
    """
    Compatibility shim for the legacy list endpoint.

    Delegates to the modular ``media.listing.list_media_endpoint`` so
    pagination and TEST_MODE behaviour are defined in one place.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.listing import (  # type: ignore  # noqa: E501
        list_media_endpoint as _list_media_impl,
    )

    # The modular implementation already accepts request/response/current_user.
    return await _list_media_impl(
        request=request,
        response=response,
        current_user=current_user,
        page=page,
        results_per_page=results_per_page,
        db=db,
        if_none_match=None,
    )

async def process_code_endpoint(
    db: MediaDatabase = Depends(get_media_db_for_user),
    form_data: "ProcessCodeForm" = Depends(get_process_code_form),
    files: Optional[List[UploadFile]] = File(None, description="Code uploads (.py, .c, .cpp, .java, .ts, etc.)"),
):
    """
    Shim for backwards compatibility.

    The actual `/process-code` implementation now lives in
    `tldw_Server_API.app.api.v1.endpoints.media.process_code`.
    This wrapper simply forwards calls so tests and imports that
    reference `_legacy_media.process_code_endpoint` continue to work.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.process_code import (  # noqa: WPS433
        process_code_endpoint as _process_code_impl,
    )

    return await _process_code_impl(
        db=db,
        form_data=form_data,
        files=files,
    )
from tldw_Server_API.app.api.v1.schemas.media_response_models import PaginationInfo, MediaListResponse, MediaListItem, \
    MediaDetailResponse, VersionDetailResponse
from tldw_Server_API.app.api.v1.schemas.media_request_models import MetadataSearchRequest, MetadataFilter, MetadataPatchRequest, AdvancedVersionUpsertRequest
from tldw_Server_API.app.core.Utils.metadata_utils import (
    normalize_safe_metadata,
    update_version_safe_metadata_in_transaction,
)
# Media Processing
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Files import process_audio_files
import tldw_Server_API.app.core.Ingestion_Media_Processing.Books.Book_Processing_Lib as books
import tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib as pdf_lib
import tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files as docs
from tldw_Server_API.app.core.Ingestion_Media_Processing.Upload_Sink import FileValidator
import tldw_Server_API.app.core.Ingestion_Media_Processing.Email.Email_Processing_Lib as email_lib
from tldw_Server_API.app.core.Security.url_validation import assert_url_safe
from tldw_Server_API.app.core.Metrics import get_metrics_registry
from tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib import process_videos
from tldw_Server_API.app.core.Ingestion_Media_Processing.video_batch import (
    run_video_batch,
)
# Expose ingestion helpers at module scope for tests to patch
try:
    process_document_content = docs.process_document_content  # type: ignore[attr-defined]
except Exception:
    async def process_document_content(*args, **kwargs):  # pragma: no cover
        raise RuntimeError("process_document_content not available")

try:
    process_pdf_task = pdf_lib.process_pdf_task  # type: ignore[attr-defined]
except Exception:
    async def process_pdf_task(*args, **kwargs):  # pragma: no cover
        raise RuntimeError("process_pdf_task not available")

try:
    process_epub = books.process_epub  # type: ignore[attr-defined]
except Exception:
    def process_epub(*args, **kwargs):  # pragma: no cover
        raise RuntimeError("process_epub not available")
#
# Document Processing
from tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib import analyze
from tldw_Server_API.app.core.Utils.Utils import (
    logging,
    sanitize_filename,
    smart_download
)
from tldw_Server_API.app.core.Utils.Utils import logging as logger
from tldw_Server_API.app.core.config import load_and_log_configs
from tldw_Server_API.app.core.Chunking.templates import TemplateClassifier
#
# Web Scraping
from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import (
    scrape_article,
    scrape_from_sitemap,
    scrape_by_url_level,
    recursive_scrape
)
from tldw_Server_API.app.api.v1.schemas.media_request_models import (
    MediaUpdateRequest,
    VersionCreateRequest,
    VersionRollbackRequest,
    IngestWebContentRequest,
    ScrapeMethod,
    MediaType,
    AddMediaForm,
    ChunkMethod,
    PdfEngine,
    OcrMode,
    ProcessVideosForm,
    ProcessAudiosForm,
    SearchRequest,
    ProcessedMediaWikiPage,
    media_wiki_global_config,
    TranscriptionModel
)
from tldw_Server_API.app.core.config import settings, config
from tldw_Server_API.app.services.web_scraping_service import (
    process_web_scraping_task,
    ingest_web_content_orchestrate,
)
#
# MediaWiki
from tldw_Server_API.app.core.Ingestion_Media_Processing.MediaWiki.Media_Wiki import (
        import_mediawiki_dump as core_import_mediawiki_dump,
        load_mediawiki_import_config,
    )
#
#
#######################################################################################################################
#
# Functions:

# All functions below are endpoints callable via HTTP requests and the corresponding code executed as a result of it.
#

# The router is a FastAPI object that allows us to define multiple endpoints under a single prefix.

# Rate Limiter is imported from centralized configuration above

# Configure Redis cache (optional based on config)
cache = None
CACHE_TTL = config['CACHE_TTL']
if config['REDIS_ENABLED']:
    try:
        cache = redis.Redis(host=config['REDIS_HOST'], port=config['REDIS_PORT'], db=config['REDIS_DB'])
        # Test connection
        cache.ping()
        logger.info(f"Redis cache enabled at {config['REDIS_HOST']}:{config['REDIS_PORT']}")
    except Exception as e:
        logger.warning(f"Failed to connect to Redis: {str(e)}. Running without cache.")
        cache = None
else:
    logger.info("Redis cache disabled by configuration")


# ---------------------------
# Caching Implementation
#
def get_cache_key(request: Request) -> str:
    """Generate unique cache key from request parameters"""
    params = dict(request.query_params)
    params.pop('token', None)  # Exclude security token
    return f"cache:{request.url.path}:{hash(frozenset(params.items()))}"

def cache_response(key: str, response: Dict) -> None:
    """Store response in cache with ETag"""
    if cache is None:
        return
    try:
        content = json.dumps(response)
        etag = hashlib.md5(content.encode()).hexdigest()
        cache.setex(key, CACHE_TTL, f"{etag}|{content}")
        # Index cache keys by media ID set for O(1) invalidation where possible
        try:
            # Key format: "cache:{path}:{hash}"
            parts = key.split(":", 2)
            if len(parts) >= 3:
                path = parts[1]
                # Target only media resource paths: /api/v1/media/{id}
                if path.startswith("/api/v1/media/"):
                    seg = path[len("/api/v1/media/"):].split("/", 1)[0]
                    try:
                        media_id_int = int(seg)
                    except Exception:
                        media_id_int = None
                    if media_id_int is not None:
                        idx_key = f"cacheidx:/api/v1/media/{media_id_int}"
                        try:
                            cache.sadd(idx_key, key)
                            cache.expire(idx_key, max(CACHE_TTL, 300))
                        except Exception:
                            pass
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"Failed to cache response: {str(e)}")

def get_cached_response(key: str) -> Optional[tuple]:
    """Retrieve cached response with ETag (synchronous Redis client)."""
    if cache is None:
        return None
    try:
        cached_value = cache.get(key)
        if not cached_value:
            return None
        try:
            decoded_string = cached_value.decode('utf-8')
            parts = decoded_string.split('|', 1)
            if len(parts) != 2:
                logger.warning(f"Cached value for key '{key}' has unexpected format")
                return None
            etag, content_str = parts
            content = json.loads(content_str)
            return (etag, content)
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, ValueError) as e:
            logger.error(f"Error processing cached value for key '{key}': {e}")
            return None
    except Exception as e:
        logger.warning(f"Failed to retrieve cached response: {str(e)}")
        return None


# -------------------------------------
# Lightweight validators (dependencies)
# -------------------------------------
async def _validate_identifier_query(
    doi: Optional[str] = Query(None),
    pmid: Optional[str] = Query(None),
    pmcid: Optional[str] = Query(None),
    arxiv_id: Optional[str] = Query(None),
    s2_paper_id: Optional[str] = Query(None),
):
    """Early validation for /by-identifier to ensure malformed IDs return 400 before auth/DB.

    Uses normalize_safe_metadata which raises ValueError for invalid DOI/PMID/PMCID.
    """
    raw: Dict[str, Any] = {}
    if doi is not None:
        raw["doi"] = doi
    if pmid is not None:
        raw["pmid"] = pmid
    if pmcid is not None:
        raw["pmcid"] = pmcid
    if arxiv_id is not None:
        raw["arxiv_id"] = arxiv_id
    # s2_paper_id has no strict validation here
    try:
        if raw:
            normalize_safe_metadata(raw)
        else:
            # Align with handler behavior
            raise HTTPException(status_code=400, detail="Provide at least one identifier")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    return True

    return None # Cache miss
# --- How to call this function ---
# You would now need to call it from within another async function:
#
# async def some_other_async_function():
#     result = await get_cached_response("some_cache_key")
#     if result:
#         etag, data = result
#         print(f"Got from cache: ETag={etag}, Data={data}")
#     else:
#         print("Cache miss or error processing cache.")
#
# # To run it:
# # import asyncio
# # asyncio.run(some_other_async_function())

# ---------------------------
# Cache Invalidation
#
def invalidate_cache(media_id: int):
    """Invalidate cache entries for a specific media item.

    Tries O(1) set-based invalidation first, then falls back to SCAN.
    """
    if cache is None:
        return
    try:
        idx_key = f"cacheidx:/api/v1/media/{media_id}"
        keys = []
        try:
            members = cache.smembers(idx_key)
            if members:
                keys = list(members)
        except Exception:
            keys = []
        total_deleted = 0
        if keys:
            try:
                total_deleted += cache.delete(*keys)
            except Exception:
                for k in keys:
                    try:
                        cache.delete(k)
                        total_deleted += 1
                    except Exception:
                        pass
            try:
                cache.delete(idx_key)
            except Exception:
                pass
        # Fallback to SCAN in case some keys weren't indexed
        pattern = f"cache:/api/v1/media/{media_id}:*"
        cursor = 0
        while True:
            cursor, scan_keys = cache.scan(cursor=cursor, match=pattern, count=500)
            if scan_keys:
                try:
                    total_deleted += cache.delete(*scan_keys)
                except Exception:
                    for k in scan_keys:
                        try:
                            cache.delete(k)
                            total_deleted += 1
                        except Exception:
                            pass
            if cursor == 0:
                break
        if total_deleted:
            logger.info(f"Invalidated {total_deleted} cache entries for media ID {media_id}")
        else:
            logger.debug(f"No cached entries found to invalidate for media ID {media_id}")
    except redis.RedisError as e:
        logger.error(f"Redis error invalidating cache for media ID {media_id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error invalidating cache for media ID {media_id}: {e}")


##################################################################
#
# Bare Media Endpoint
#
# Endpoints:
#     GET /api/v1/media - `"/"`
#     GET /api/v1/media/{media_id} - `"/{media_id}"`

# Obtain details of a single media item using its ID
@router.get(
    "/{media_id:int}",  # Restrict to ints to avoid shadowing static routes
    status_code=status.HTTP_200_OK,
    summary="Get Media Item Details",
    tags=["Media Management"],
)
async def get_media_item(
    media_id: int = Path(..., description="The ID of the media item"),
    include_content: bool = Query(
        True,
        description="Include main content text in response",
    ),
    include_versions: bool = Query(
        True,
        description="Include versions list",
    ),
    include_version_content: bool = Query(
        False,
        description="Include content for each version in versions list",
    ),
    db: MediaDatabase = Depends(get_media_db_for_user),
    request: Request = None,
    current_user: User = Depends(get_request_user),
    response: FastAPIResponse = None,
    if_none_match: Optional[str] = Header(None),
):
    """
    Compatibility shim delegating to the modular ``media.item.get_media_item``.

    The canonical implementation now lives in
    ``tldw_Server_API.app.api.v1.endpoints.media.item.get_media_item``.
    This wrapper keeps the legacy signature for direct imports while
    forwarding all work to the modular endpoint.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.item import (  # noqa: WPS433
        get_media_item as _get_media_item_impl,
    )

    if response is None:
        response = FastAPIResponse()

    return await _get_media_item_impl(
        request=request,
        response=response,
        media_id=media_id,
        include_content=include_content,
        include_versions=include_versions,
        include_version_content=include_version_content,
        db=db,
        current_user=current_user,
        if_none_match=if_none_match,
    )


##############################################################################
############################## MEDIA Versioning ##############################
#
# Endpoints:
#   POST /api/v1/media/{media_id}/versions
#   GET /api/v1/media/{media_id}/versions
#   GET /api/v1/media/{media_id}/versions/{version_number}
#   DELETE /api/v1/media/{media_id}/versions/{version_number}
#   POST /api/v1/media/{media_id}/versions/rollback
#   PUT /api/v1/media/{media_id}

@router.post(
    "/{media_id:int}/versions",
    tags=["Media Versioning"],
    summary="Create Media Version",
    status_code=status.HTTP_201_CREATED,
    response_model=MediaDetailResponse,
)
async def create_version(
    media_id: int,
    request_body: VersionCreateRequest,
    db: MediaDatabase = Depends(get_media_db_for_user),
    request: Request = None,
    current_user: User = Depends(get_request_user),
):
    """
    Shim that forwards to the modular media.versions implementation.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.versions import (  # noqa: WPS433
        create_version as _create_version_impl,
    )

    return await _create_version_impl(
        media_id=media_id,
        request_body=request_body,
        db=db,
        request=request,
        current_user=current_user,
    )


@router.get(
    "/{media_id:int}/versions",
    tags=["Media Versioning"],
    summary="List Media Versions",
    response_model=List[VersionDetailResponse],
    response_model_exclude_none=True,
)
async def list_versions(
    media_id: int = Path(..., description="The ID of the media item"),
    include_content: bool = Query(False, description="Include full content in response"),
    limit: int = Query(10, ge=1, le=100, description="Results per page"),
    page: int = Query(1, ge=1, description="Page number"), # Use page instead of offset
    # --- Use the new DB dependency ---
    db: MediaDatabase = Depends(get_media_db_for_user),
    request: Request = None,
    current_user: User = Depends(get_request_user),
):
    """
    Compatibility shim delegating to the modular media.versions implementation.

    The canonical implementation now lives in
    ``tldw_Server_API.app.api.v1.endpoints.media.versions.list_versions``.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.versions import (  # noqa: WPS433
        list_versions as _list_versions_impl,
    )

    return await _list_versions_impl(
        media_id=media_id,
        include_content=include_content,
        limit=limit,
        page=page,
        db=db,
    )


@router.get(
    "/metadata-search",
    tags=["Media Management"],
    summary="Search media by safe metadata",
)
async def search_by_metadata(
    filters: Optional[str] = Query(None, description="JSON list of {field, op, value}"),
    field: Optional[str] = Query(None, description="Single filter field"),
    op: Optional[str] = Query("icontains", description="Operator: eq|contains|icontains|startswith|endswith"),
    value: Optional[str] = Query(None, description="Single filter value"),
    match_mode: str = Query("all", description="all|any"),
    group_by_media: bool = Query(True),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: MediaDatabase = Depends(get_media_db_for_user),
):
    """
    Compatibility shim delegating to the modular metadata search implementation.

    The canonical implementation now lives in
    ``tldw_Server_API.app.api.v1.endpoints.media.listing.search_by_metadata``.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.listing import (  # noqa: WPS433
        search_by_metadata as _search_by_metadata_impl,
    )

    # The modular implementation handles all validation, normalization,
    # and ETag behaviour. For direct imports/tests we invoke it with a
    # fresh Response object and no conditional headers.
    return await _search_by_metadata_impl(
        request=None,
        response=FastAPIResponse(),
        filters=filters,
        field=field,
        op=op,
        value=value,
        match_mode=match_mode,
        group_by_media=group_by_media,
        page=page,
        per_page=per_page,
        db=db,
        if_none_match=None,
    )


@router.patch(
    "/{media_id:int}/metadata",
    tags=["Media Management"],
    summary="Update safe metadata for the latest version",
    response_model=MediaDetailResponse,
)
async def patch_metadata(
    media_id: int = Path(..., description="The ID of the media item"),
    body: MetadataPatchRequest = Body(...),
    db: MediaDatabase = Depends(get_media_db_for_user),
):
    """
    Shim that forwards to the modular media.versions implementation.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.versions import (  # noqa: WPS433
        patch_metadata as _patch_metadata_impl,
    )

    return await _patch_metadata_impl(
        media_id=media_id,
        body=body,
        db=db,
    )


@router.put(
    "/{media_id:int}/versions/{version_number:int}/metadata",
    tags=["Media Versioning"],
    summary="Set safe metadata for a specific version",
    response_model=MediaDetailResponse,
)
async def put_version_metadata(
    media_id: int = Path(..., description="The ID of the media item"),
    version_number: int = Path(..., description="The version number"),
    body: MetadataPatchRequest = Body(...),
    db: MediaDatabase = Depends(get_media_db_for_user),
):
    """
    Shim that forwards to the modular media.versions implementation.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.versions import (  # noqa: WPS433
        put_version_metadata as _put_version_metadata_impl,
    )

    return await _put_version_metadata_impl(
        media_id=media_id,
        version_number=version_number,
        body=body,
        db=db,
    )


@router.get(
    "/by-identifier",
    tags=["Media Management"],
    summary="Find media by standard identifier (DOI/PMID/PMCID/arXiv/S2)",
    # Ensure invalid IDs yield 400 before auth/DB (prevents 401 masking)
    dependencies=[Depends(_validate_identifier_query)],
)
async def get_by_identifier(
    request: Request,
    response: FastAPIResponse,
    doi: Optional[str] = Query(None),
    pmid: Optional[str] = Query(None),
    pmcid: Optional[str] = Query(None),
    arxiv_id: Optional[str] = Query(None),
    s2_paper_id: Optional[str] = Query(None),
    group_by_media: bool = Query(True),
    db: Optional[MediaDatabase] = Depends(try_get_media_db_for_user),
    if_none_match: Optional[str] = Header(None),
):
    """
    Compatibility shim delegating to the modular media.listing implementation.

    The actual identifier lookup behaviour (including normalization and ETag
    handling) now lives in
    ``tldw_Server_API.app.api.v1.endpoints.media.listing.get_by_identifier``.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.listing import (  # noqa: WPS433
        get_by_identifier as _get_by_identifier_impl,
    )

    return await _get_by_identifier_impl(
        request=request,
        response=response,
        doi=doi,
        pmid=pmid,
        pmcid=pmcid,
        arxiv_id=arxiv_id,
        s2_paper_id=s2_paper_id,
        group_by_media=group_by_media,
        db=db,
        if_none_match=if_none_match,
    )


@router.post(
    "/{media_id:int}/versions/advanced",
    tags=["Media Versioning"],
    summary="Create or update version with content + safe metadata",
    response_model=MediaDetailResponse,
)
async def create_or_update_version_advanced(
    media_id: int,
    body: AdvancedVersionUpsertRequest,
    db: MediaDatabase = Depends(get_media_db_for_user)
):
    """
    Shim that forwards to the modular media.versions implementation.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.versions import (  # noqa: WPS433
        create_or_update_version_advanced as _advanced_impl,
    )

    return await _advanced_impl(
        media_id=media_id,
        body=body,
        db=db,
    )

@router.get(
    "/{media_id:int}/versions/{version_number:int}",
    tags=["Media Versioning"],
    summary="Get Specific Media Version",
    response_model=VersionDetailResponse,
    response_model_exclude_none=True,
)
async def get_version(
    media_id: int = Path(..., description="The ID of the media item"),
    version_number: int = Path(..., description="The version number"),
    include_content: bool = Query(True, description="Include full content in response"),
    # --- Use the new DB dependency ---
    db: MediaDatabase = Depends(get_media_db_for_user)
):
    """
    Compatibility shim delegating to the modular media.versions implementation.

    The canonical implementation now lives in
    ``tldw_Server_API.app.api.v1.endpoints.media.versions.get_version``.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.versions import (  # noqa: WPS433
        get_version as _get_version_impl,
    )

    return await _get_version_impl(
        media_id=media_id,
        version_number=version_number,
        include_content=include_content,
        db=db,
    )


@router.delete(
    "/{media_id:int}/versions/{version_number:int}",
    tags=["Media Versioning"],
    summary="Soft Delete Media Version", # Changed summary: Soft Delete
    status_code=status.HTTP_204_NO_CONTENT, # Keep 204 on success
)
async def delete_version(
    media_id: int = Path(..., description="The ID of the media item"),
    version_number: int = Path(..., description="The version number"),
    # --- Use the new DB dependency ---
    db: MediaDatabase = Depends(get_media_db_for_user)
):
    """
    Shim that forwards to the modular media.versions implementation.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.versions import (  # noqa: WPS433
        delete_version as _delete_version_impl,
    )

    return await _delete_version_impl(
        media_id=media_id,
        version_number=version_number,
        db=db,
    )


@router.post(
    "/{media_id:int}/versions/rollback",
    tags=["Media Versioning"],
    summary="Rollback to Media Version",
    response_model=MediaDetailResponse,
)
async def rollback_version(
    media_id: int,
    request_body: VersionRollbackRequest, # Renamed for clarity
    # --- Use the new DB dependency ---
    db: MediaDatabase = Depends(get_media_db_for_user)
):
    """
    Shim that forwards to the modular media.versions implementation.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.versions import (  # noqa: WPS433
        rollback_version as _rollback_version_impl,
    )

    return await _rollback_version_impl(
        media_id=media_id,
        request_body=request_body,
        db=db,
    )


@router.put(
    "/{media_id:int}",
    tags=["Media Management"],
    summary="Update Media Item",
    status_code=status.HTTP_200_OK,
    response_model=MediaDetailResponse,
)
async def update_media_item(
    payload: MediaUpdateRequest,
    media_id: int = Path(..., description="The ID of the media item"),
    db: MediaDatabase = Depends(get_media_db_for_user),
):
    """
    Compatibility shim delegating to the modular media.item implementation.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.item import (  # type: ignore  # noqa: E501
        update_media_item as _update_media_item_impl,
    )

    return await _update_media_item_impl(
        payload=payload,
        media_id=media_id,
        db=db,
    )


##############################################################################
############################## MEDIA Search ##################################
#
# Search Media Endpoints

# Endpoints:


# Retrieve a listing of all media, returning a list of media items. Limited by paging and rate limiting.
@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="List All Media Items",
    tags=["Media Management"],
    response_model=MediaListResponse
)
@limiter.limit("50/minute")
async def list_all_media(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    results_per_page: int = Query(10, ge=1, le=100, description="Results per page"),
    db: MediaDatabase = Depends(get_media_db_for_user),
):
    """
    Compatibility wrapper around the main list endpoint used by tests.

    The richer list implementation now lives in the modular ``media.listing``
    module, so this endpoint simply forwards to that handler and preserves the
    response model.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.listing import (  # type: ignore  # noqa: E501
        list_media_endpoint as _list_media_impl,
    )

    # Reuse the modular list handler but adapt its dict payload into the
    # historical ``MediaListResponse`` shape.
    # Note: we intentionally do not pass if_none_match here to keep
    # behaviour aligned with legacy tests that do not use ETags.
    from fastapi import Response as _Response  # Local import to avoid cycles

    _response = _Response()
    payload = await _list_media_impl(
        request=request,
        response=_response,
        current_user=await get_request_user(),  # type: ignore[arg-type]
        page=page,
        results_per_page=results_per_page,
        db=db,
        if_none_match=None,
    )

    try:
        # Build MediaListResponse using the modular payload.
        items = [
            MediaListItem(
                id=item["id"],
                title=item["title"],
                type=item["type"],
                url=item.get("url", f"/api/v1/media/{item['id']}"),
            )
            for item in payload.get("items", [])
        ]
        pagination = payload.get("pagination") or {}
        pagination_info = PaginationInfo(
            page=pagination.get("page", 1),
            per_page=pagination.get("results_per_page", results_per_page),
            total=pagination.get("total_items", 0),
            total_pages=pagination.get("total_pages", 1),
        )
        return MediaListResponse(items=items, pagination=pagination_info)
    except ValidationError as ve:
        logger.error(
            "Pydantic validation error creating MediaListResponse: {}",
            ve.errors(),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error: Response creation failed.",
        ) from ve


@router.get(
    "/transcription-models",
    status_code=status.HTTP_200_OK,
    summary="Get Available Transcription Models",
    tags=["Media Processing"],
    response_model=Dict[str, List[Dict[str, str]]]
)
async def get_transcription_models():
    """
    Compatibility shim for the transcription models endpoint.

    Delegates to the modular ``media.transcription_models`` endpoint so
    the data definition and HTTP contract live in a single place.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.transcription_models import (  # noqa: WPS433,E501
        get_transcription_models as _get_transcription_models_impl,
    )

    return await _get_transcription_models_impl()


# FIXME - Add an 'advanced search' option for searching by date range, media type, etc. - update DB schema to add new fields
# ---------------------------
# Enhanced Search Endpoint with ETags
#

@router.post(
    "/search",
    status_code=status.HTTP_200_OK,
    summary="Search Media Items",
    tags=["Media Management"],
    response_model=MediaListResponse
)
# Use a higher rate limit during automated tests to avoid false 429s under load
@limiter.limit(_SEARCH_RATE_LIMIT)
async def search_media_items(
    request: Request,
    search_params: SearchRequest,
    page: int = Query(1, ge=1, description="Page number"),
    results_per_page: int = Query(10, ge=1, le=100, description="Results per page"),
    db: MediaDatabase = Depends(get_media_db_for_user),
    if_none_match: Optional[str] = Header(None),  # For ETag
):
    """
    Compatibility shim delegating to the modular media.listing implementation.

    The actual search behaviour (including validation and ETag handling)
    now lives in
    ``tldw_Server_API.app.api.v1.endpoints.media.listing.search_media_items``.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.listing import (  # noqa: WPS433
        search_media_items as _search_media_items_impl,
    )

    # Reuse the canonical implementation by adapting the SearchRequest
    # model into the dict payload it expects.
    payload = search_params.model_dump(exclude_unset=True)
    return await _search_media_items_impl(
        request=request,
        payload=payload,
        page=page,
        results_per_page=results_per_page,
        db=db,
        if_none_match=if_none_match,
    )

#
# End of Bare Media Endpoint Functions/Routes
#######################################################################


#######################################################################
#
# Pure Media Ingestion endpoint - for adding media to the DB with no analysis/modifications
#
# Endpoints:
#


# Per-User Media Ingestion and Analysis
# FIXME - Ensure that each function processes multiple files/URLs at once
def _validate_inputs(
    media_type: MediaType,
    urls: Optional[List[str]],
    files: Optional[List[UploadFile]],
) -> None:
    """
    Backwards-compatible shim for input validation.

    Delegates to the core ``validate_add_media_inputs`` helper so the
    actual behaviour lives under the core ingestion module while
    preserving the original name and signature.
    """
    from tldw_Server_API.app.core.Ingestion_Media_Processing.persistence import (
        validate_add_media_inputs,
    )

    validate_add_media_inputs(media_type=media_type, urls=urls, files=files)


# Backwards-compatibility alias for tests referencing old private helper name
_process_uploaded_files = _save_uploaded_files


def _prepare_chunking_options_dict(
    form_data: AddMediaForm,
) -> Optional[Dict[str, Any]]:
    """
    Backwards-compatible wrapper that delegates to the core helper.

    The actual implementation lives in
    `core.Ingestion_Media_Processing.chunking_options.prepare_chunking_options_dict`.
    """
    from tldw_Server_API.app.core.Ingestion_Media_Processing.chunking_options import (
        prepare_chunking_options_dict,
    )

    return prepare_chunking_options_dict(form_data)


def _prepare_common_options(
    form_data: AddMediaForm,
    chunk_options: Optional[Dict],
) -> Dict[str, Any]:
    """
    Backwards-compatible wrapper that delegates to the core helper.

    The actual implementation lives in
    `core.Ingestion_Media_Processing.chunking_options.prepare_common_options`.
    """
    from tldw_Server_API.app.core.Ingestion_Media_Processing.chunking_options import (
        prepare_common_options,
    )

    return prepare_common_options(form_data, chunk_options)


async def _extract_claims_if_requested(
    process_result: Dict[str, Any],
    form_data: AddMediaForm,
    loop: asyncio.AbstractEventLoop,
) -> Optional[Dict[str, Any]]:
    """
    Backwards-compatible wrapper delegating to core claims utils.
    """
    from tldw_Server_API.app.core.Ingestion_Media_Processing.claims_utils import (
        extract_claims_if_requested,
    )

    return await extract_claims_if_requested(process_result, form_data, loop)


async def _persist_claims_if_applicable(
    claims_context: Optional[Dict[str, Any]],
    media_id: Optional[int],
    db_path: str,
    client_id: str,
    loop: asyncio.AbstractEventLoop,
    process_result: Dict[str, Any],
) -> None:
    """
    Backwards-compatible wrapper delegating to core claims utils.
    """
    from tldw_Server_API.app.core.Ingestion_Media_Processing.claims_utils import (
        persist_claims_if_applicable,
    )

    await persist_claims_if_applicable(
        claims_context=claims_context,
        media_id=media_id,
        db_path=db_path,
        client_id=client_id,
        loop=loop,
        process_result=process_result,
    )

async def _process_batch_media_legacy_disabled(
    media_type: MediaType,
    urls: List[str],
    uploaded_file_paths: List[str],
    source_to_ref_map: Dict[str, Union[str, Tuple[str, str]]],
    form_data: AddMediaForm,
    chunk_options: Optional[Dict],
    loop: asyncio.AbstractEventLoop,
    db_path: str,
    client_id: str,
    temp_dir: Path,  # Pass temp_dir Path object
) -> List[Dict[str, Any]]:
    """
    LEGACY-ONLY / name-preserving stub.

    The live implementation now lives in
    ``core.Ingestion_Media_Processing.persistence.process_batch_media``.
    This placeholder exists only so historical imports of
    ``_process_batch_media_disabled`` (and the alias
    ``_process_batch_media``) continue to resolve.
    """
    raise RuntimeError(
        "_process_batch_media_disabled is no longer active; "
        "use core.Ingestion_Media_Processing.persistence.process_batch_media instead.",
    )


async def _process_document_like_item(
    item_input_ref: str,
    processing_source: str,
    media_type: MediaType,
    is_url: bool,
    form_data: AddMediaForm,
    chunk_options: Optional[Dict],
    temp_dir: FilePath,
    loop: asyncio.AbstractEventLoop,
    db_path: str,
    client_id: str,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Backwards-compatible shim that delegates document-like processing and
    persistence to the core ingestion helper.
    """
    from tldw_Server_API.app.core.Ingestion_Media_Processing.persistence import (  # type: ignore  # noqa: E501
        process_document_like_item,
    )

    return await process_document_like_item(
        item_input_ref=item_input_ref,
        processing_source=processing_source,
        media_type=str(media_type),
        is_url=is_url,
        form_data=form_data,
        chunk_options=chunk_options,
        temp_dir=FilePath(str(temp_dir)),
        loop=loop,
        db_path=db_path,
        client_id=client_id,
        user_id=user_id,
    )


def _determine_final_status(results: List[Dict[str, Any]]) -> int:
    """
    Backwards-compatible shim for HTTP status determination.

    Delegates to the core ``determine_add_media_final_status`` helper so
    the decision logic lives under the core ingestion module while
    preserving the original name and signature.
    """
    from tldw_Server_API.app.core.Ingestion_Media_Processing.persistence import (
        determine_add_media_final_status,
    )

    return determine_add_media_final_status(results)


async def _add_media_impl_legacy(
    background_tasks: BackgroundTasks,
    # # --- Required Fields ---
    # #media_type: MediaType = Form(..., description="Type of media (e.g., 'audio', 'video', 'pdf')"),
    # # --- Input Sources (Validation needed in code) ---
    # urls: Optional[List[str]] = Form(None, description="List of URLs of the media items to add"),
    # # --- Common Optional Fields ---
    # title: Optional[str] = Form(None, description="Optional title (applied if only one item processed)"),
    # author: Optional[str] = Form(None, description="Optional author (applied similarly to title)"),
    # keywords: str = Form("", description="Comma-separated keywords (applied to all processed items)"), # Receive as string
    # custom_prompt: Optional[str] = Form(None, description="Optional custom prompt (applied to all)"),
    # system_prompt: Optional[str] = Form(None, description="Optional system prompt (applied to all)"),
    # overwrite_existing: bool = Form(False, description="Overwrite existing media"),
    # keep_original_file: bool = Form(False, description="Retain original uploaded files"),
    # perform_analysis: bool = Form(True, description="Perform analysis (default=True)"),
    # # --- Integration Options ---
    # api_name: Optional[str] = Form(None, description="Optional API name"),
    # api_key: Optional[str] = Form(None, description="Optional API key"), # Consider secure handling
    # use_cookies: bool = Form(False, description="Use cookies for URL download requests"),
    # cookies: Optional[str] = Form(None, description="Cookie string if `use_cookies` is True"),
    # # --- Audio/Video Specific ---
    # transcription_model: str = Form("deepdml/faster-distil-whisper-large-v3.5", description="Transcription model"),
    # transcription_language: str = Form("en", description="Transcription language"),
    # diarize: bool = Form(False, description="Enable speaker diarization"),
    # timestamp_option: bool = Form(True, description="Include timestamps in transcription"),
    # vad_use: bool = Form(False, description="Enable VAD filter"),
    # perform_confabulation_check_of_analysis: bool = Form(False, description="Enable confabulation check"),
    # start_time: Optional[str] = Form(None, description="Optional start time (HH:MM:SS or seconds)"),
    # end_time: Optional[str] = Form(None, description="Optional end time (HH:MM:SS or seconds)"),
    # # --- PDF Specific ---
    # pdf_parsing_engine: Optional[PdfEngine] = Form("pymupdf4llm", description="PDF parsing engine"),
    # # --- Chunking Specific ---
    # perform_chunking: bool = Form(True, description="Enable chunking"),
    # chunk_method: Optional[ChunkMethod] = Form(None, description="Chunking method"),
    # use_adaptive_chunking: bool = Form(False, description="Enable adaptive chunking"),
    # use_multi_level_chunking: bool = Form(False, description="Enable multi-level chunking"),
    # chunk_language: Optional[str] = Form(None, description="Chunking language override"),
    # chunk_size: int = Form(500, description="Target chunk size"),
    # chunk_overlap: int = Form(200, description="Chunk overlap size"),
    # custom_chapter_pattern: Optional[str] = Form(None, description="Regex pattern for custom chapter splitting"),
    # # --- Deprecated/Less Common ---
    # perform_rolling_summarization: bool = Form(False, description="Perform rolling summarization"),
    # summarize_recursively: bool = Form(False, description="Perform recursive summarization"),
    # # --- Use Dependency Injection for Form Data ---
    form_data: AddMediaForm = Depends(get_add_media_form),
    # --- Keep File and Header Dependencies Separate ---
    # token: str = Header(..., description="Authentication token"), # Auth handled by get_media_db_for_user
    files: Optional[List[UploadFile]] = File(None, description="List of files to upload"),
    # --- DB Dependency ---
    db: MediaDatabase = Depends(get_media_db_for_user), # Use the correct dependency
    current_user: User = Depends(get_request_user),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
    response: FastAPIResponse = None,
) -> Any:
    """
    LEGACY-ONLY / not on any live code path; kept only as historical reference.

    The live `/media/add` pipeline now lives in
    ``core.Ingestion_Media_Processing.persistence.add_media_orchestrate``,
    and callers should use `add_media_persist` via the modular
    `media/add.py` endpoint instead.
    """
    from tldw_Server_API.app.core.Ingestion_Media_Processing.persistence import (
        add_media_orchestrate,
    )

    # Delegate to the core orchestration helper so this legacy
    # implementation is no longer on the hot path. The remaining
    # code in this function is kept only as historical reference
    # and is unreachable after this return.
    return await add_media_orchestrate(
        background_tasks=background_tasks,
        form_data=form_data,
        files=files,
        db=db,
        current_user=current_user,
        usage_log=usage_log,
        response=response,
    )

    # --- 1. Validation (Now handled by get_add_media_form dependency) ---
    # Basic check for presence of inputs still useful here
    _validate_inputs(form_data.media_type, form_data.urls, files)
    # TEST_MODE diagnostics for auth and DB context
    try:
        if str(os.getenv("TEST_MODE", "")).lower() in {"1", "true", "yes", "on"}:
            _dbp = getattr(db, 'db_path_str', getattr(db, 'db_path', '?'))
            _hdrs = getattr(__import__('builtins'), 'getattr')(locals().get('request', None), 'headers', {}) or {}
            # request is not a parameter here; rely on dependency logs elsewhere; still log user and db
            logger.info(
                f"TEST_MODE: add_media db_path={_dbp} user_id={getattr(current_user, 'id', '?')} "
            )
    except Exception:
        pass
    logger.info(f"Received request to add {form_data.media_type} media.")
    try:
        usage_log.log_event(
            "media.add",
            tags=[str(form_data.media_type or "")],
            metadata={
                "has_urls": bool(form_data.urls),
                "files_count": len(files) if files else 0,
                "perform_analysis": bool(form_data.perform_analysis),
            },
        )
    except Exception:
        pass
    # TODO: Implement actual authentication logic using the 'token' if needed

    # --- 2. Database Dependency (Handled by `db` parameter) ---
    # Ensure client_id is available (should be set by db dependency logic)
    if not hasattr(db, 'client_id') or not db.client_id:
        logger.error("CRITICAL: Database instance dependency missing client_id.")
        # Attempt to set it from settings as a fallback, but log error
        db.client_id = settings.get("SERVER_CLIENT_ID", "SERVER_API_V1_FALLBACK")
        logger.warning(f"Manually set missing client_id on DB instance to: {db.client_id}")
        # Consider raising 500 if client_id is absolutely essential and shouldn't be missing
        # raise HTTPException(status_code=500, detail="Internal server error: DB configuration issue.")

    # --- 2. Database Dependency ---
    # The line : `db = Depends(get_db)` in the func args takes care of this

    results = []
    # --- Use TempDirManager ---
    temp_dir_manager = TempDirManager(cleanup=not form_data.keep_original_file)
    temp_dir_path: Optional[Path] = None
    loop = asyncio.get_running_loop()

    try:
        # --- 3. Setup Temporary Directory ---
        with temp_dir_manager as temp_dir: # Context manager handles creation/cleanup
            temp_dir_path = temp_dir # Store the path for potential use
            logger.info(f"Using temporary directory: {temp_dir_path}")

            # --- 4. Save Uploaded Files ---
            # Restrict allowed extensions based on declared media_type to avoid mismatches
            allowed_ext_map = {
                "video": ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.wmv', '.mpg', '.mpeg'],
                "audio": ['.mp3', '.aac', '.flac', '.wav', '.ogg', '.m4a', '.wma'],
                "pdf": ['.pdf'],
                "ebook": ['.epub', '.mobi', '.azw'],
                "email": ['.eml']
                    + (['.zip'] if getattr(form_data, 'accept_archives', False) else [])
                    + (['.mbox'] if getattr(form_data, 'accept_mbox', False) else [])
                    + (['.pst', '.ost'] if getattr(form_data, 'accept_pst', False) else []),
                "json": ['.json'],
                # For 'document', allow a broad set; leave None to let validator handle
            }
            allowed_exts = allowed_ext_map.get(str(form_data.media_type).lower())
            saved_files_info, file_save_errors = await _save_uploaded_files(
                files or [],
                temp_dir_path,
                validator=file_validator_instance,
                allowed_extensions=allowed_exts,
                skip_archive_scanning=(str(form_data.media_type).lower() == 'email' and bool(getattr(form_data, 'accept_archives', False)))
            )

            # Check for file errors and return appropriate HTTP errors immediately
            for err_info in file_save_errors:
                error_msg = err_info.get("error", "")
                if "exceeds maximum allowed size" in error_msg:
                    raise HTTPException(
                       status_code=HTTP_413_TOO_LARGE,
                        detail=error_msg
                    )
                elif "not allowed for security reasons" in error_msg:
                    raise HTTPException(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        detail=error_msg
                    )
                elif "empty" in error_msg.lower():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=error_msg
                    )

            # Adapt file saving errors to the standard result format
            for err_info in file_save_errors:
                 results.append({
                      "status": "Error",
                      "input_ref": err_info.get("input_ref", "Unknown Upload"),
                      "processing_source": None, # No processing source if save failed
                      "media_type": form_data.media_type, # Assume intended type
                      "metadata": {}, "content": None, "transcript": None, "segments": None,
                      "chunks": None, "analysis": None, "summary": None,
                      "analysis_details": None, "error": err_info.get("error", "File save failed."),
                      "warnings": None, "db_id": None, "db_message": "File saving failed.",
                      "message": "File saving failed."
                  })


            # --- Quota check for uploaded files and upload metrics ---
            try:
                if saved_files_info:
                    total_uploaded_bytes = 0
                    for pf in saved_files_info:
                        try:
                            total_uploaded_bytes += Path(str(pf["path"]).strip()).stat().st_size
                        except Exception:
                            pass
                    if total_uploaded_bytes > 0:
                        from tldw_Server_API.app.services.storage_quota_service import get_storage_quota_service
                        quota_service = get_storage_quota_service()
                        has_quota, info = await quota_service.check_quota(current_user.id, total_uploaded_bytes, raise_on_exceed=False)
                        if not has_quota:
                            detail = (
                                f"Storage quota exceeded. Current: {info['current_usage_mb']}MB, "
                                f"New: {info['new_size_mb']}MB, Quota: {info['quota_mb']}MB, "
                                f"Available: {info['available_mb']}MB"
                            )
                            raise HTTPException(status_code=HTTP_413_TOO_LARGE, detail=detail)
                        # Record upload metrics
                        try:
                            reg = get_metrics_registry()
                            reg.increment("uploads_total", len(saved_files_info), labels={"user_id": str(current_user.id), "media_type": form_data.media_type})
                            reg.increment("upload_bytes_total", float(total_uploaded_bytes), labels={"user_id": str(current_user.id), "media_type": form_data.media_type})
                        except Exception:
                            pass
            except HTTPException:
                raise
            except Exception as _qerr:
                logger.warning(f"Quota check failed (non-fatal): {_qerr}")

            # --- 5. Prepare Inputs and Options ---
            uploaded_file_paths = [str(pf["path"]) for pf in saved_files_info]
            url_list = form_data.urls or []
            all_valid_input_sources = url_list + uploaded_file_paths # Only those that saved/downloaded

            # Check if any valid sources remain after potential save errors
            if not all_valid_input_sources:
                 if file_save_errors:
                      logger.warning("No valid inputs remaining after file handling errors.")
                      # Return 207 with only the file save errors
                      return JSONResponse(status_code=status.HTTP_207_MULTI_STATUS, content={"results": results})
                 else:
                      # This case should be caught by _validate_inputs earlier if BOTH urls and files are empty
                      logger.error("No input URLs or successfully saved files found.")
                      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid media sources found to process.")

            # Pass the instantiated 'form_data' object to helpers
            chunking_options_dict = _prepare_chunking_options_dict(form_data)

            # --- Auto-apply chunking template (precedence: explicit name > user settings > auto) ---
            try:
                if form_data.perform_chunking:
                    # 1) Apply explicit template by name
                    if getattr(form_data, 'chunking_template_name', None):
                        tpl = db.get_chunking_template(name=form_data.chunking_template_name)
                        if tpl and tpl.get('template_json'):
                            cfg = json.loads(tpl['template_json']) if isinstance(tpl['template_json'], str) else tpl['template_json']
                            hier_cfg = ((cfg or {}).get('chunking') or {}).get('config', {})
                            if isinstance(hier_cfg.get('hierarchical_template'), dict):
                                chunking_options_dict = chunking_options_dict or {}
                                # Only set method if not provided by user/options
                                tpl_method = (cfg.get('chunking') or {}).get('method') or 'sentences'
                                if not form_data.chunk_method:
                                    chunking_options_dict.setdefault('method', tpl_method)
                                chunking_options_dict['hierarchical'] = True
                                chunking_options_dict['hierarchical_template'] = hier_cfg['hierarchical_template']
                    # 2) Respect explicit user hierarchical/method (already set in chunking_options_dict)
                    # 3) Auto-match when requested and user didn't request hierarchical explicitly
                    elif getattr(form_data, 'auto_apply_template', False) and not getattr(form_data, 'hierarchical_chunking', False):
                        candidates = db.list_chunking_templates(include_builtin=True, include_custom=True, tags=None, user_id=None, include_deleted=False)
                        first_url = (form_data.urls or [None])[0]
                        first_filename = None
                        # saved_files_info is defined above when files were saved; guard for None
                        try:
                            if saved_files_info:
                                first_filename = saved_files_info[0]['original_filename']
                        except Exception:
                            first_filename = None
                        best_cfg = None
                        best_key = None
                        for t in candidates:
                            try:
                                cfg = json.loads(t['template_json']) if isinstance(t.get('template_json'), str) else (t.get('template_json') or {})
                            except Exception:
                                cfg = {}
                            s = TemplateClassifier.score(cfg, media_type=form_data.media_type, title=form_data.title, url=first_url, filename=first_filename)
                            if s > 0:
                                pr = ((cfg.get('classifier') or {}).get('priority') or 0)
                                key = (s, pr)
                                if best_cfg is None or key > best_key:
                                    best_cfg, best_key = cfg, key
                        if best_cfg:
                            hier_cfg = ((best_cfg.get('chunking') or {}).get('config') or {})
                            tpl = hier_cfg.get('hierarchical_template')
                            if isinstance(tpl, dict):
                                chunking_options_dict = chunking_options_dict or {}
                                if not form_data.chunk_method:
                                    chunking_options_dict.setdefault('method', (best_cfg.get('chunking') or {}).get('method', 'sentences'))
                                chunking_options_dict['hierarchical'] = True
                                chunking_options_dict['hierarchical_template'] = tpl
            except Exception as _auto_apply_err:
                logger.warning(f"Auto-apply template failed: {_auto_apply_err}")
            common_processing_options = _prepare_common_options(form_data, chunking_options_dict)

            # Map input sources back to original refs (URL or original filename)
            # This helps in reporting results against the user's input identifier
            source_to_ref_map = {src: src for src in url_list} # URLs map to themselves
            source_to_ref_map.update({str(pf["path"]): pf["original_filename"] for pf in saved_files_info})

            # --- Get DB info from the dependency ---
            db_path_for_workers = db.db_path_str
            client_id_for_workers = db.client_id

            # --- 6. Process Media based on Type ---
            logging.info(f"Processing {len(all_valid_input_sources)} items of type '{form_data.media_type}'")

            if form_data.media_type in ['video', 'audio']:
                batch_results = await _process_batch_media(
                    media_type=form_data.media_type,
                    urls=url_list,
                    uploaded_file_paths=uploaded_file_paths,
                    source_to_ref_map=source_to_ref_map,
                    form_data=form_data,
                    chunk_options=chunking_options_dict,
                    loop=loop,
                    db_path=db_path_for_workers,
                    client_id=client_id_for_workers,
                    temp_dir=temp_dir_path
                )
                results.extend(batch_results)
            else:  # PDF/Document/Ebook
                tasks = [
                    _process_document_like_item(
                        item_input_ref=source_to_ref_map.get(source, source),
                        processing_source=source,
                        media_type=form_data.media_type,
                        is_url=(source in url_list),
                        form_data=form_data,
                        chunk_options=chunking_options_dict,
                        temp_dir=temp_dir_path,
                        loop=loop,
                        db_path=db_path_for_workers,
                        client_id=client_id_for_workers,
                        user_id=current_user.id if hasattr(current_user, 'id') else None
                    )
                    for source in all_valid_input_sources
                ]
                individual_results = await asyncio.gather(*tasks)
                results.extend(individual_results)

        # --- 7. Generate Embeddings if Requested ---
        logger.info(f"generate_embeddings flag: {form_data.generate_embeddings}")
        if form_data.generate_embeddings:
            logger.info("Generating embeddings for successfully processed media items...")
            embedding_tasks = []

            for result in results:
                # Only generate embeddings for successfully stored items
                if result.get("status") == "Success" and result.get("db_id"):
                    media_id = result["db_id"]
                    logger.info(f"Scheduling embedding generation for media ID {media_id}")

                    # Add background task for embedding generation
                    async def generate_embeddings_task(media_id: int):
                        try:
                            from tldw_Server_API.app.api.v1.endpoints.media_embeddings import (
                                generate_embeddings_for_media,
                                get_media_content
                            )

                            media_content = await get_media_content(media_id, db)
                            embedding_model = form_data.embedding_model or "Qwen/Qwen3-Embedding-4B-GGUF"
                            embedding_provider = form_data.embedding_provider or "huggingface"

                            result = await generate_embeddings_for_media(
                                media_id=media_id,
                                media_content=media_content,
                                embedding_model=embedding_model,
                                embedding_provider=embedding_provider,
                                chunk_size=form_data.chunk_size or 1000,
                                chunk_overlap=form_data.overlap or 200
                            )
                            logger.info(f"Embedding generation result for media {media_id}: {result}")
                        except Exception as e:
                            logger.error(f"Failed to generate embeddings for media {media_id}: {e}")

                    # Run embedding generation in background
                    background_tasks.add_task(generate_embeddings_task, media_id)
                    result["embeddings_scheduled"] = True

        # --- 8. Determine Final Status Code and Return Response (Success Path) ---
        # TempDirManager handles cleanup automatically on exit from 'with' block
        final_status_code = _determine_final_status(results)
        # Special-case: Email container parent with children should return 200 even when
        # some children include guardrail errors. Top-level parent was processed successfully.
        try:
            if (
                isinstance(results, list)
                and len(results) == 1
                and isinstance(results[0], dict)
                and results[0].get("media_type") == "email"
                and results[0].get("status") == "Success"
                and isinstance(results[0].get("children"), list)
            ):
                final_status_code = status.HTTP_200_OK
        except Exception:
            pass
        log_level = "INFO" if final_status_code == status.HTTP_200_OK else "WARNING"
        logger.log(log_level, f"Request finished with status {final_status_code}. Results count: {len(results)}")

        # TEST_MODE: emit diagnostic headers for easier assertions in tests
        try:
            if str(os.getenv("TEST_MODE", "")).lower() in {"1", "true", "yes", "on"} and response is not None:
                try:
                    _dbp = getattr(db, 'db_path_str', getattr(db, 'db_path', '?'))
                except Exception:
                    _dbp = "?"
                response.headers["X-TLDW-DB-Path"] = str(_dbp)
                response.headers["X-TLDW-Add-Results-Len"] = str(len(results))
                # Count successes with db_id for quick triage
                try:
                    ok_with_id = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "Success" and r.get("db_id"))
                    response.headers["X-TLDW-Add-OK-With-Id"] = str(ok_with_id)
                except Exception:
                    pass
        except Exception:
            pass

        # Successfully completed processing, return results
        return JSONResponse(status_code=final_status_code, content={"results": results})

    except HTTPException as e:
        # Log and re-raise HTTP exceptions
        logging.warning(f"HTTP Exception encountered: Status={e.status_code}, Detail={e.detail}")
        # Cleanup is handled by TempDirManager context exit
        raise e
    except OSError as e:
        # Handle potential errors during temp dir creation/management
        logging.error(f"OSError during processing setup: {e}", exc_info=True)
        # Cleanup is handled by TempDirManager context exit
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OS error during setup: {e}"
        )
    except Exception as e:
        # Catch unexpected errors, ensure cleanup
        logging.error(f"Unhandled exception in add_media endpoint: {type(e).__name__} - {e}", exc_info=True)
        # Cleanup is handled by TempDirManager context exit
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected internal error: {type(e).__name__}")

    # No finally block needed for cleanup if using TempDirManager context

#
# End of General media ingestion and analysis
####################################################################################


async def add_media(*args: Any, **kwargs: Any) -> Any:
    """
    Compatibility shim that routes to the modular `/media/add` path.

    This preserves the historical `add_media` entry point while ensuring
    that any lingering direct imports go through the `media/add.py`
    endpoint and core persistence helpers.
    """
    from tldw_Server_API.app.core.Ingestion_Media_Processing.persistence import (  # type: ignore
        add_media_persist,
    )

    return await add_media_persist(*args, **kwargs)


async def process_videos_endpoint(
    background_tasks: BackgroundTasks,
    db: MediaDatabase = Depends(get_media_db_for_user),
    form_data: ProcessVideosForm = Depends(get_process_videos_form),
    files: Optional[List[UploadFile]] = File(None, description="Video file uploads"),
    current_user: User = Depends(get_request_user),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
) -> JSONResponse:
    """
    Shim for backwards compatibility.

    The actual `/process-videos` implementation now lives in
    `tldw_Server_API.app.api.v1.endpoints.media.process_videos`.
    This wrapper simply forwards calls so tests and imports that
    reference `_legacy_media.process_videos_endpoint` continue to work.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.process_videos import (  # noqa: WPS433
        process_videos_endpoint as _process_videos_impl,
    )

    return await _process_videos_impl(
        background_tasks=background_tasks,
        db=db,
        form_data=form_data,
        files=files,
        current_user=current_user,
        usage_log=usage_log,
    )

#
# End of Video Processing
####################################################################################


######################## Audio Processing Endpoint ###################################
# Endpoints:
#   /process-audio

from tldw_Server_API.app.api.v1.API_Deps.media_processing_deps import (  # noqa: E402
    get_process_audios_form,
)


# =============================================================================
# Audio Processing Endpoint (REFACTORED)
# =============================================================================
async def process_audios_endpoint(
    background_tasks: BackgroundTasks,
    # 1. Auth + UserID Determined through `get_db_by_user`
    # token: str = Header(None), # Use Header(None) for optional
    # 2. DB Dependency
    db: MediaDatabase = Depends(get_media_db_for_user),
    # 3. Use Dependency Injection for Form Data
    form_data: ProcessAudiosForm = Depends(get_process_audios_form),
    # 4. File uploads remain separate
    files: Optional[List[UploadFile]] = File(None, description="Audio file uploads"),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
):
    """
    Shim that preserves the legacy callable while delegating to the modular
    `/process-audios` endpoint implementation in `media.process_audios`.

    The FastAPI route decorator now lives on the modular endpoint; this
    function simply forwards the call so existing imports continue to work.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.process_audios import (  # type: ignore[import-not-found]
        process_audios_endpoint as _process_audios_impl,
    )

    return await _process_audios_impl(
        background_tasks=background_tasks,
        db=db,
        form_data=form_data,
        files=files,
        usage_log=usage_log,
    )

#
# End of Audio Processing
##############################################################################################


######################## Ebook Processing Endpoint ###################################

# ─────────────────────── Form Model ─────────────────────────
class ProcessEbooksForm(AddMediaForm):
    media_type: Literal["ebook"] = "ebook"
    extraction_method: Literal['filtered', 'markdown', 'basic'] = Field('filtered', description="EPUB text extraction method ('filtered', 'markdown', 'basic')")
    keep_original_file: bool = False    # always cleanup tmp dir for this endpoint
    # Add any ebook specific options if needed, otherwise inherit from AddMediaForm

def _process_single_ebook(
    ebook_path: Path,
    original_ref: str, # Pass the original URL or filename
    # Pass necessary options from form_data
    title_override: Optional[str],
    author_override: Optional[str],
    keywords: Optional[List[str]],
    perform_chunking: bool,
    chunk_options: Optional[Dict[str, Any]],
    perform_analysis: bool,
    summarize_recursively: bool,
    api_name: Optional[str],
    # api_key removed - SECURITY: Never accept API keys from client
    custom_prompt: Optional[str],
    system_prompt: Optional[str],
    extraction_method: str, # Pass selected method
) -> Dict[str, Any]:
    """
    Synchronous helper function to process one EPUB file using the library.
    Designed to be run in a thread executor.
    *No DB interaction.*
    """
    try:
        logger.info(f"Worker processing ebook: {original_ref} from path {ebook_path}")
        # Call the main library processing function
        result_dict = books.process_epub(
            file_path=str(ebook_path),
            title_override=title_override,
            author_override=author_override,
            keywords=keywords,
            perform_chunking=perform_chunking,
            chunk_options=chunk_options,
            perform_analysis=perform_analysis,
            api_name=api_name,
            # Supply None; provider functions will resolve API key at call time
            api_key=None,
            custom_prompt=custom_prompt,
            system_prompt=system_prompt,
            summarize_recursively=summarize_recursively,
            extraction_method=extraction_method
        )
        # Ensure input_ref is set to the original URL/filename for consistency
        result_dict["input_ref"] = original_ref
        # processing_source is already set by process_epub to the actual path
        return result_dict

    except Exception as e:
        logger.error(f"_process_single_ebook error for {original_ref} ({ebook_path}): {e}", exc_info=True)
        # Return a standardized error dictionary consistent with process_epub
        return {
            "status": "Error",
            "input_ref": original_ref, # Use original ref for error reporting
            "processing_source": str(ebook_path),
            "media_type": "ebook",
            "error": f"Worker processing failed: {str(e)}",
            "content": None, "metadata": None, "chunks": None, "analysis": None,
            "keywords": keywords or [], "warnings": None, "analysis_details": None # Add analysis_details
        }


# ────────────────────── Dependency Function ───────────────────
def get_process_ebooks_form(
    # --- Inherited Fields from AddMediaForm ---
    urls: Optional[List[str]] = Form(None, description="List of URLs of the EPUB items"),
    title: Optional[str] = Form(None, description="Optional title override"),
    author: Optional[str] = Form(None, description="Optional author override"),
    keywords: str = Form("", alias="keywords_str", description="Comma-separated keywords"),
    custom_prompt: Optional[str] = Form(None, description="Optional custom prompt for analysis"),
    system_prompt: Optional[str] = Form(None, description="Optional system prompt for analysis"),
    overwrite_existing: bool = Form(False, description="Overwrite existing media (Not used, for model validation)"),
    perform_analysis: bool = Form(True, description="Perform analysis (summarization)"),
    perform_claims_extraction: Optional[bool] = Form(
        None,
        description="Extract factual claims during analysis (defaults to server configuration)."
    ),
    claims_extractor_mode: Optional[str] = Form(
        None,
        description="Override claims extractor mode (heuristic|ner|provider id)."
    ),
    claims_max_per_chunk: Optional[int] = Form(
        None,
        description="Maximum number of claims to extract per chunk (uses config default when unset)."
    ),
    api_name: Optional[str] = Form(None, description="Optional API name for analysis"),
    # api_key removed - SECURITY: Never accept API keys from client
    use_cookies: bool = Form(False, description="Use cookies for URL download requests (Not implemented for ebooks)"),
    cookies: Optional[str] = Form(None, description="Cookie string (Not implemented for ebooks)"),
    summarize_recursively: bool = Form(False, description="Perform recursive summarization"),
    perform_rolling_summarization: bool = Form(False, description="Perform rolling summarization (Not applicable to ebooks)"),

    # --- Fields from ChunkingOptions ---
    perform_chunking: bool = Form(True, description="Enable chunking (default: by chapter)"),
    chunk_method: Optional[ChunkMethod] = Form('ebook_chapters', description="Chunking method ('semantic', 'tokens', 'paragraphs', 'sentences','words', 'ebook_chapters', 'json', 'propositions')"),
    chunk_language: Optional[str] = Form(None, description="Chunking language override (rarely needed for chapter)"),
    chunk_size: int = Form(1500, description="Target chunk size (used by non-chapter methods)"),
    chunk_overlap: int = Form(200, description="Chunk overlap size (used by non-chapter methods)"),
    custom_chapter_pattern: Optional[str] = Form(None, description="Regex pattern for custom chapter splitting (overrides method default)"),

    # --- Ebook Specific Options (Add if needed) ---
    extraction_method: Literal['filtered', 'markdown', 'basic'] = Form('filtered',
                                                                           description="EPUB text extraction method"),

    # --- Fields from other options (like AudioVideo) if needed for model validation ---
    # Include placeholders if AddMediaForm requires them, even if not used by ebooks
    start_time: Optional[str] = Form(None), end_time: Optional[str] = Form(None),
    transcription_model: Optional[str] = Form(None), transcription_language: Optional[str] = Form(None),
    diarize: Optional[bool] = Form(None), timestamp_option: Optional[bool] = Form(None),
    vad_use: Optional[bool] = Form(None), perform_confabulation_check_of_analysis: Optional[bool] = Form(None),
    # Include PDF options placeholder if AddMediaForm requires
    pdf_parsing_engine: Optional[PdfEngine] = Form(None),

    # --- Fields from ChunkingOptions - NOT used explicitly by ebooks but part of AddMediaForm ---
    use_adaptive_chunking: bool = Form(False, description="Enable adaptive chunking (Not applicable)"),
    use_multi_level_chunking: bool = Form(False, description="Enable multi-level chunking (Not applicable)"),
    # Contextual chunking (ebooks)
    enable_contextual_chunking: bool = Form(False, description="Enable contextual chunking"),
    contextual_llm_model: Optional[str] = Form(None, description="LLM model for contextualization"),
    context_window_size: Optional[int] = Form(None, description="Context window size (chars)"),
    context_strategy: Optional[str] = Form(None, description="Context strategy: auto|full|window|outline_window"),
    context_token_budget: Optional[int] = Form(None, description="Approx token budget for auto strategy"),
) -> ProcessEbooksForm:
    """
    Dependency function to parse form data and validate it
    against the ProcessEbooksForm model.
    """
    try:
        # --- MODIFIED: Only pass relevant fields explicitly ---
        ebook_form_data = {
            "media_type": "ebook", # Fixed
            "keep_original_file": False, # Fixed for this endpoint
            "urls": urls,
            "title": title,
            "author": author,
            "keywords": keywords, # Use alias mapping
            "custom_prompt": custom_prompt,
            "system_prompt": system_prompt,
            "overwrite_existing": overwrite_existing, # Keep for model validation if needed
            "perform_analysis": perform_analysis,
            "perform_claims_extraction": perform_claims_extraction,
            "claims_extractor_mode": claims_extractor_mode,
            "claims_max_per_chunk": claims_max_per_chunk,
            "api_name": api_name,
            # api_key removed - retrieved from server config
            "use_cookies": use_cookies, # Keep for model validation if needed
            "cookies": cookies, # Keep for model validation if needed
            "summarize_recursively": summarize_recursively,
            "perform_rolling_summarization": perform_rolling_summarization, # Keep for model validation
            # Chunking
            "perform_chunking": perform_chunking,
            "chunk_method": chunk_method,
            "chunk_language": chunk_language,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "custom_chapter_pattern": custom_chapter_pattern,
            # Ebook specific
            "extraction_method": extraction_method,
            # Contextual chunking
            "enable_contextual_chunking": enable_contextual_chunking,
            "contextual_llm_model": contextual_llm_model,
            "context_window_size": context_window_size,
            "context_strategy": (context_strategy.strip().lower() if isinstance(context_strategy, str) and context_strategy.strip() else context_strategy),
            "context_token_budget": (int(context_token_budget) if isinstance(context_token_budget, str) and str(context_token_budget).isdigit() else context_token_budget),

            # --- EXPLICITLY OMITTING irrelevant fields like: ---
            # "start_time": start_time,
            # "end_time": end_time,
            # "transcription_model": transcription_model, # DON'T PASS
            # "transcription_language": transcription_language, # DON'T PASS
            # "diarize": diarize, # DON'T PASS
            # "timestamp_option": timestamp_option, # DON'T PASS
            # "vad_use": vad_use, # DON'T PASS
            # "perform_confabulation_check_of_analysis": perform_confabulation_check_of_analysis, # DON'T PASS
            # "pdf_parsing_engine": pdf_parsing_engine, # DON'T PASS
            # "use_adaptive_chunking": use_adaptive_chunking, # Keep if needed by ChunkingOptions base
            # "use_multi_level_chunking": use_multi_level_chunking, # Keep if needed by ChunkingOptions base
        }

        # Filter out None values for optional fields if Pydantic requires non-None
        # (Might not be necessary if defaults are handled correctly, but safer)
        filtered_form_data = {k: v for k, v in ebook_form_data.items() if v is not None}
        # Ensure required fields are present even if None was filtered out (shouldn't happen for required ones)
        filtered_form_data["media_type"] = "ebook" # Re-add fixed fields
        filtered_form_data["keep_original_file"] = False

        form_instance = ProcessEbooksForm(**filtered_form_data)
        # ------------------------------------------------------
        return form_instance
    except ValidationError as e:
        # Keep existing detailed error handling
        serializable_errors = []
        for error in e.errors():
             serializable_error = error.copy()
             if 'ctx' in serializable_error and isinstance(serializable_error.get('ctx'), dict):
                 new_ctx = {}
                 for k, v in serializable_error['ctx'].items():
                     if isinstance(v, Exception): new_ctx[k] = str(v)
                     else: new_ctx[k] = v
                 serializable_error['ctx'] = new_ctx
             # Ensure 'input' exists for clarity, fallback to loc if missing
             serializable_error['input'] = serializable_error.get('input', serializable_error.get('loc'))
             serializable_errors.append(serializable_error)
        logger.warning(f"Pydantic validation failed for Ebook processing: {json.dumps(serializable_errors)}")
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail=serializable_errors,
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error creating ProcessEbooksForm: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error during form processing: {type(e).__name__}"
        )


# ─────────────────────── Endpoint Implementation ────────────────
@router.post(
    "/process-ebooks",
    # status_code=status.HTTP_200_OK, # Determined dynamically
    summary="Extract, chunk, analyse EPUBs (NO DB Persistence)",
    tags=["Media Processing (No DB)"], # Separate tag maybe?
)
async def process_ebooks_endpoint(
    background_tasks: BackgroundTasks,
    # 1. Auth + UserID Determined through `get_db_by_user`
    # token: str = Header(None), # Use Header(None) for optional
    # 2. DB Dependency
    db: MediaDatabase = Depends(get_media_db_for_user),
    # 3. Use Dependency Injection for Form Data
    form_data: ProcessEbooksForm = Depends(get_process_ebooks_form), # Use the dependency
    # 4. File uploads remain separate
    files: Optional[List[UploadFile]] = File(None, description="EPUB file uploads (.epub)"),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
):
    """
    **Process Ebooks (No Persistence)**

    Processes EPUB files (URLs or uploads): extract content/metadata, optional chunking and analysis.
    Returns processing artifacts without saving to the database.

    Docs: `Docs/Code_Documentation/Ingestion_Pipeline_Ebooks.md`

    Example:
    ```python
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Books.Book_Processing_Lib import process_epub
    process_epub("/abs/book.epub", perform_chunking=True, perform_analysis=True, api_name="openai")
    ```

    Supports `.epub` files.
    URL inputs must resolve to an EPUB. The server accepts URLs that either:
    - end with `.epub`, or
    - provide `Content-Disposition` with a filename ending in `.epub`, or
    - set `Content-Type: application/epub+zip`.
    Other URLs are rejected with a clear error entry in the batch response.
    """
    # Compatibility shim: delegate to the modular implementation.
    from tldw_Server_API.app.api.v1.endpoints.media.process_ebooks import (  # noqa: WPS433
        process_ebooks_endpoint as _process_ebooks_impl,
    )

    return await _process_ebooks_impl(
        background_tasks=background_tasks,
        db=db,
        form_data=form_data,
        files=files,
        usage_log=usage_log,
    )

#
# End of Ebook Processing Endpoint
#################################################################################################

######################## Email Processing Endpoint ###################################

# ─────────────────────── Form Model ─────────────────────────
class ProcessEmailsForm(AddMediaForm):
    media_type: Literal["email"] = "email"
    keep_original_file: bool = False # Always cleanup tmp dir for this endpoint

    # Chunking defaults for emails
    perform_chunking: bool = True
    chunk_method: Optional[ChunkMethod] = Field('sentences', description="Default chunking method for emails")
    chunk_size: int = Field(1000, gt=0, description="Target chunk size for emails")
    chunk_overlap: int = Field(200, ge=0, description="Chunk overlap size for emails")
    ingest_attachments: bool = Field(False, description="Parse and include nested .eml attachments as children")
    max_depth: int = Field(2, ge=1, le=5, description="Max depth for nested email parsing when ingest_attachments=true")
    accept_archives: bool = Field(False, description="Accept .zip archives of EMLs and expand/process members")
    accept_mbox: bool = Field(False, description="Accept .mbox mailboxes and expand/process messages")
    accept_pst: bool = Field(False, description="Accept .pst/.ost containers (feature-flag; parsing may require external tools)")


# ────────────────────── Dependency Function ───────────────────
def get_process_emails_form(
    urls: Optional[List[str]] = Form(None, description="List of URLs of the emails (optional)"),
    title: Optional[str] = Form(None, description="Optional title override"),
    author: Optional[str] = Form(None, description="Optional author override"),
    keywords: str = Form("", alias="keywords", description="Comma-separated keywords"),
    custom_prompt: Optional[str] = Form(None, description="Optional custom prompt for analysis"),
    system_prompt: Optional[str] = Form(None, description="Optional system prompt for analysis"),
    overwrite_existing: bool = Form(False),
    perform_analysis: bool = Form(False),
    perform_claims_extraction: Optional[bool] = Form(
        None,
        description="Extract factual claims during analysis (defaults to server configuration)."
    ),
    claims_extractor_mode: Optional[str] = Form(
        None,
        description="Override claims extractor mode (heuristic|ner|provider id)."
    ),
    claims_max_per_chunk: Optional[int] = Form(
        None,
        description="Maximum number of claims to extract per chunk (uses config default when unset)."
    ),
    api_name: Optional[str] = Form(None),
    use_cookies: bool = Form(False),
    cookies: Optional[str] = Form(None),
    summarize_recursively: bool = Form(False),
    # Chunking options
    perform_chunking: bool = Form(True),
    chunk_method: Optional[ChunkMethod] = Form('sentences'),
    chunk_language: Optional[str] = Form(None),
    chunk_size: int = Form(1000),
    chunk_overlap: int = Form(200),
    custom_chapter_pattern: Optional[str] = Form(None),
    use_adaptive_chunking: bool = Form(False),
    use_multi_level_chunking: bool = Form(False),
    # Contextual chunking (optional for emails)
    enable_contextual_chunking: bool = Form(False),
    contextual_llm_model: Optional[str] = Form(None),
    context_window_size: Optional[int] = Form(None),
    context_strategy: Optional[str] = Form(None),
    context_token_budget: Optional[int] = Form(None),
    # Attachment handling
    ingest_attachments: bool = Form(False),
    max_depth: int = Form(2),
    accept_archives: bool = Form(False),
    accept_mbox: bool = Form(False),
    accept_pst: bool = Form(False),
) -> "ProcessEmailsForm":
    try:
        form_data = {
            "media_type": "email",
            "keep_original_file": False,
            "urls": urls,
            "title": title,
            "author": author,
            "keywords": keywords,
            "custom_prompt": custom_prompt,
            "system_prompt": system_prompt,
            "overwrite_existing": overwrite_existing,
            "perform_analysis": perform_analysis,
            "perform_claims_extraction": perform_claims_extraction,
            "claims_extractor_mode": claims_extractor_mode,
            "claims_max_per_chunk": claims_max_per_chunk,
            "api_name": api_name,
            "use_cookies": use_cookies,
            "cookies": cookies,
            "summarize_recursively": summarize_recursively,
            # Chunking
            "perform_chunking": perform_chunking,
            "chunk_method": chunk_method,
            "chunk_language": chunk_language,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "custom_chapter_pattern": custom_chapter_pattern,
            "use_adaptive_chunking": use_adaptive_chunking,
            "use_multi_level_chunking": use_multi_level_chunking,
            # Contextual
            "enable_contextual_chunking": enable_contextual_chunking,
            "contextual_llm_model": contextual_llm_model,
            "context_window_size": context_window_size,
            "context_strategy": (context_strategy.strip().lower() if isinstance(context_strategy, str) and context_strategy.strip() else context_strategy),
            "context_token_budget": (int(context_token_budget) if isinstance(context_token_budget, str) and str(context_token_budget).isdigit() else context_token_budget),
            # Attachments
            "ingest_attachments": ingest_attachments,
            "max_depth": max_depth,
            "accept_archives": accept_archives,
            "accept_mbox": accept_mbox,
            "accept_pst": accept_pst,
        }
        filtered = {k: v for k, v in form_data.items() if v is not None}
        filtered["media_type"] = "email"
        filtered["keep_original_file"] = False
        return ProcessEmailsForm(**filtered)
    except ValidationError as e:
        serializable_errors = []
        for error in e.errors():
            serializable_error = error.copy()
            if 'ctx' in serializable_error and isinstance(serializable_error.get('ctx'), dict):
                serializable_error['ctx'] = {k: (str(v) if isinstance(v, Exception) else v) for k, v in serializable_error['ctx'].items()}
            serializable_error['input'] = serializable_error.get('input', serializable_error.get('loc'))
            serializable_errors.append(serializable_error)
        logger.warning(f"Pydantic validation failed for Email processing: {json.dumps(serializable_errors)}")
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE, detail=serializable_errors) from e
    except Exception as e:
        logger.error(f"Unexpected error creating ProcessEmailsForm: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error during form processing: {type(e).__name__}")


# ─────────────────────── Endpoint Implementation ────────────────
@router.post(
    "/process-emails",
    summary="Extract, chunk, analyse Emails (NO DB Persistence)",
    tags=["Media Processing (No DB)"]
)
async def process_emails_endpoint(
    form_data: ProcessEmailsForm = Depends(get_process_emails_form),
    files: Optional[List[UploadFile]] = File(None),
):
    """
    Compatibility shim that forwards to the modular
    ``media.process_emails.process_emails_endpoint`` implementation.

    The HTTP route for ``/process-emails`` is now owned by the modular
    endpoint; this function remains for direct imports/tests.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.process_emails import (  # noqa: WPS433
        process_emails_endpoint as _process_emails_impl,
    )

    return await _process_emails_impl(
        form_data=form_data,
        files=files,
    )

    loop = asyncio.get_running_loop()
    batch_result: Dict[str, Any] = {
        "results": [],
        "processed_count": 0,
        "errors_count": 0,
        "errors": [],
    }

    temp_dir_mgr = TempDirManager(prefix="email_process_", cleanup=True)
    with temp_dir_mgr as temp_dir:
        # Save uploaded .eml files with validation
        allowed_exts = ['.eml']
        # Allow .zip when accept_archives is true; .mbox when accept_mbox is true
        allowed_exts = (
            ['.eml']
            + (['.zip'] if form_data.accept_archives else [])
            + (['.mbox'] if getattr(form_data, 'accept_mbox', False) else [])
            + (['.pst', '.ost'] if getattr(form_data, 'accept_pst', False) else [])
        )
        saved_files_info, file_errors = await _save_uploaded_files(files or [], temp_dir, validator=file_validator_instance, allowed_extensions=allowed_exts)

        for err in file_errors:
            batch_result["results"].append({
                "status": "Error",
                "input_ref": err.get("input_ref"),
                "processing_source": None,
                "media_type": "email",
                "error": err.get("error", "File save failed"),
                "metadata": {}, "content": None, "chunks": None,
                "analysis": None, "keywords": None, "warnings": None,
                "analysis_details": {}, "db_id": None, "db_message": "Processing only endpoint."
            })
            batch_result["errors_count"] += 1
            if err.get("error"): batch_result["errors"].append(err.get("error"))

        # Process saved files
        for pf in saved_files_info:
            try:
                path = FilePath(pf["path"]).resolve()
                # Read bytes
                async with aiofiles.open(path, "rb") as f:
                    file_bytes = await f.read()
                # Chunk options
                chunk_opts = {
                    "method": form_data.chunk_method if form_data.chunk_method else "sentences",
                    "max_size": form_data.chunk_size,
                    "overlap": form_data.chunk_overlap,
                }
                # If this is a supported container and accepted, expand and process members
                name_lower = (pf.get("original_filename") or path.name).lower()
                if name_lower.endswith('.zip') and form_data.accept_archives:
                    arch_name = pf.get("original_filename") or path.name
                    processor = functools.partial(
                        email_lib.process_eml_archive_bytes,
                        file_bytes=file_bytes,
                        archive_name=arch_name,
                        title_override=form_data.title,
                        author_override=form_data.author,
                        keywords=form_data.keywords,
                        perform_chunking=form_data.perform_chunking,
                        chunk_options=chunk_opts,
                        perform_analysis=form_data.perform_analysis,
                        api_name=form_data.api_name,
                        api_key=None,
                        custom_prompt=form_data.custom_prompt,
                        system_prompt=form_data.system_prompt,
                        summarize_recursively=form_data.summarize_recursively,
                        ingest_attachments=form_data.ingest_attachments,
                        max_depth=form_data.max_depth,
                    )
                    res_list = await loop.run_in_executor(None, processor)
                    # Append each child as its own result
                    for r_item in res_list:
                        r_item.setdefault("media_type", "email")
                        r_item.setdefault("processing_source", f"archive:{str(path)}")
                        r_item.setdefault("input_ref", r_item.get("input_ref") or arch_name)
                        r_item.update({"db_id": None, "db_message": "Processing only endpoint."})
                        batch_result["results"].append(r_item)
                        if r_item.get("status") in ("Success", "Warning"):
                            batch_result["processed_count"] += 1
                        else:
                            batch_result["errors_count"] += 1
                            if r_item.get("error"): batch_result["errors"].append(r_item.get("error"))
                elif name_lower.endswith('.mbox') and getattr(form_data, 'accept_mbox', False):
                    mbox_name = pf.get("original_filename") or path.name
                    processor = functools.partial(
                        email_lib.process_mbox_bytes,
                        file_bytes=file_bytes,
                        mbox_name=mbox_name,
                        title_override=form_data.title,
                        author_override=form_data.author,
                        keywords=form_data.keywords,
                        perform_chunking=form_data.perform_chunking,
                        chunk_options=chunk_opts,
                        perform_analysis=form_data.perform_analysis,
                        api_name=form_data.api_name,
                        api_key=None,
                        custom_prompt=form_data.custom_prompt,
                        system_prompt=form_data.system_prompt,
                        summarize_recursively=form_data.summarize_recursively,
                        ingest_attachments=form_data.ingest_attachments,
                        max_depth=form_data.max_depth,
                    )
                    res_list = await loop.run_in_executor(None, processor)
                    for r_item in res_list:
                        r_item.setdefault("media_type", "email")
                        r_item.setdefault("processing_source", f"mbox:{str(path)}")
                        r_item.setdefault("input_ref", r_item.get("input_ref") or mbox_name)
                        r_item.update({"db_id": None, "db_message": "Processing only endpoint."})
                        batch_result["results"].append(r_item)
                        if r_item.get("status") in ("Success", "Warning"):
                            batch_result["processed_count"] += 1
                        else:
                            batch_result["errors_count"] += 1
                            if r_item.get("error"): batch_result["errors"].append(r_item.get("error"))
                elif (name_lower.endswith('.pst') or name_lower.endswith('.ost')) and getattr(form_data, 'accept_pst', False):
                    pst_name = pf.get("original_filename") or path.name
                    processor = functools.partial(
                        email_lib.process_pst_bytes,
                        file_bytes=file_bytes,
                        pst_name=pst_name,
                        title_override=form_data.title,
                        author_override=form_data.author,
                        keywords=form_data.keywords,
                        perform_chunking=form_data.perform_chunking,
                        chunk_options=chunk_opts,
                        perform_analysis=form_data.perform_analysis,
                        api_name=form_data.api_name,
                        api_key=None,
                        custom_prompt=form_data.custom_prompt,
                        system_prompt=form_data.system_prompt,
                        summarize_recursively=form_data.summarize_recursively,
                        ingest_attachments=form_data.ingest_attachments,
                        max_depth=form_data.max_depth,
                    )
                    res_list = await loop.run_in_executor(None, processor)
                    for r_item in res_list:
                        r_item.setdefault("media_type", "email")
                        r_item.setdefault("processing_source", f"pst:{str(path)}")
                        r_item.setdefault("input_ref", r_item.get("input_ref") or pst_name)
                        r_item.update({"db_id": None, "db_message": "Processing only endpoint."})
                        batch_result["results"].append(r_item)
                        if r_item.get("status") in ("Success", "Warning"):
                            batch_result["processed_count"] += 1
                        else:
                            batch_result["errors_count"] += 1
                            if r_item.get("error"): batch_result["errors"].append(r_item.get("error"))
                else:
                    # Run processor in executor (sync function)
                    processor = functools.partial(
                        email_lib.process_email_task,
                        file_bytes=file_bytes,
                        filename=pf.get("original_filename") or path.name,
                        title_override=form_data.title,
                        author_override=form_data.author,
                        keywords=form_data.keywords,
                        perform_chunking=form_data.perform_chunking,
                        chunk_options=chunk_opts,
                        perform_analysis=form_data.perform_analysis,
                        api_name=form_data.api_name,
                        api_key=None,
                        custom_prompt=form_data.custom_prompt,
                        system_prompt=form_data.system_prompt,
                        summarize_recursively=form_data.summarize_recursively,
                        ingest_attachments=form_data.ingest_attachments,
                        max_depth=form_data.max_depth,
                    )
                    res = await loop.run_in_executor(None, processor)
                    # Normalize minimal fields
                    res.setdefault("media_type", "email")
                    res.setdefault("processing_source", str(path))
                    res.setdefault("input_ref", pf.get("original_filename") or path.name)
                    # Remove DB related fields
                    res.update({"db_id": None, "db_message": "Processing only endpoint."})
                    batch_result["results"].append(res)
                    if res.get("status") == "Success" or res.get("status") == "Warning":
                        batch_result["processed_count"] += 1
                    else:
                        batch_result["errors_count"] += 1
                        if res.get("error"): batch_result["errors"].append(res.get("error"))
            except Exception as e:
                batch_result["results"].append({
                    "status": "Error", "input_ref": pf.get("original_filename"),
                    "processing_source": str(pf.get("path")), "media_type": "email",
                    "error": f"Processing failed: {e}",
                    "metadata": {}, "content": None, "chunks": None, "analysis": None, "keywords": None,
                    "warnings": None, "analysis_details": {}, "db_id": None, "db_message": "Processing only endpoint."
                })
                batch_result["errors_count"] += 1
                batch_result["errors"].append(str(e))

    final_status = status.HTTP_200_OK if (batch_result["processed_count"] > 0 and batch_result["errors_count"] == 0) else (
        status.HTTP_207_MULTI_STATUS if batch_result["results"] else status.HTTP_400_BAD_REQUEST
    )
    return JSONResponse(status_code=final_status, content=batch_result)

#
# End of Email Processing Endpoint
#################################################################################################

######################## Document Processing Endpoint ###################################

from tldw_Server_API.app.api.v1.API_Deps.media_processing_deps import (  # noqa: E402
    get_process_documents_form,
)
from tldw_Server_API.app.api.v1.schemas.media_request_models import (  # noqa: E402
    ProcessDocumentsForm,
)


# ─────────────────────── Endpoint Implementation ────────────────
async def process_documents_endpoint(
    # background_tasks: BackgroundTasks, # Remove if unused
    # 1. Auth + UserID Determined through `get_db_by_user`
    # token: str = Header(None), # Use Header(None) for optional
    # 2. DB Dependency
    db: MediaDatabase = Depends(get_media_db_for_user),
    # 3. Form Data Dependency
    form_data: ProcessDocumentsForm = Depends(get_process_documents_form), # Use the dependency
    # 4. File Upload
    files: Optional[List[UploadFile]] = File(None, description="Document file uploads (.txt, .md, .docx, .rtf, .html, .xml)"),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
):
    """
    **Process Documents (No Persistence)**

    Compatibility shim that forwards to the modular
    `media.process_documents.process_documents_endpoint` implementation.

    The HTTP route for `/process-documents` is now owned by the modular
    endpoint; this function remains for direct imports/tests.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.process_documents import (
        process_documents_endpoint as _process_documents_impl,
    )

    return await _process_documents_impl(
        db=db,
        form_data=form_data,
        files=files,
        usage_log=usage_log,
    )

#
# End of Document Processing Endpoint
############################################################################################


######################## PDF Processing Endpoint ###################################
# Endpoints:
#

# ─────────────────────── form model (subset of AddMediaForm) ─────────────────
class ProcessPDFsForm(AddMediaForm):
    media_type: Literal["pdf"] = "pdf"
    keep_original_file: bool = False


def get_process_pdfs_form(
    # Include ALL fields defined in AddMediaForm and its parents
    # Use Form(...) for each
    urls: Optional[List[str]] = Form(None, description="List of URLs of the PDF items"),
    title: Optional[str] = Form(None, description="Optional title (applied if only one item processed)"),
    author: Optional[str] = Form(None, description="Optional author (applied similarly to title)"),
    keywords: str = Form("", alias="keywords", description="Comma-separated keywords"), # Use alias
    custom_prompt: Optional[str] = Form(None, description="Optional custom prompt"),
    system_prompt: Optional[str] = Form(None, description="Optional system prompt"),
    overwrite_existing: bool = Form(False, description="Overwrite existing media (Not used, for model)"),
    keep_original_file: bool = Form(False, description="Retain original files (fixed in model)"), # Fixed by ProcessPDFsForm
    perform_analysis: bool = Form(True, description="Perform analysis"),
    perform_claims_extraction: Optional[bool] = Form(
        None,
        description="Extract factual claims during analysis (defaults to server configuration)."
    ),
    claims_extractor_mode: Optional[str] = Form(
        None,
        description="Override claims extractor mode (heuristic|ner|provider id)."
    ),
    claims_max_per_chunk: Optional[int] = Form(
        None,
        description="Maximum number of claims to extract per chunk (uses config default when unset)."
    ),
    api_name: Optional[str] = Form(None, description="Optional API name"), # Keep this
    # api_key removed - SECURITY: Never accept API keys from client
    use_cookies: bool = Form(False, description="Use cookies for URL download requests"),
    cookies: Optional[str] = Form(None, description="Cookie string if `use_cookies` is True"),
    summarize_recursively: bool = Form(False, description="Perform recursive summarization"),
    perform_rolling_summarization: bool = Form(False, description="Perform rolling summarization"), # From AddMediaForm

    # --- Fields from PdfOptions ---
    pdf_parsing_engine: Optional[PdfEngine] = Form("pymupdf4llm", description="PDF parsing engine"),
    enable_ocr: bool = Form(False, description="Enable OCR for scanned/low-text PDFs"),
    ocr_backend: Optional[str] = Form(None, description="OCR backend (e.g., 'tesseract' or 'auto')"),
    ocr_lang: Optional[str] = Form("eng", description="OCR language (Tesseract codes, e.g., 'eng')"),
    ocr_dpi: int = Form(300, description="OCR render DPI (72-600)"),
    ocr_mode: Optional[OcrMode] = Form("fallback", description="OCR mode: 'always' or 'fallback'"),
    ocr_min_page_text_chars: int = Form(40, description="Threshold to consider page empty for fallback"),
    custom_chapter_pattern: Optional[str] = Form(None, description="Regex pattern for custom chapter splitting"),

    # --- Fields from ChunkingOptions ---
    perform_chunking: bool = Form(True, description="Enable chunking"),
    chunk_method: Optional[ChunkMethod] = Form(None, description="Chunking method"),
    use_adaptive_chunking: bool = Form(False, description="Enable adaptive chunking"),
    use_multi_level_chunking: bool = Form(False, description="Enable multi-level chunking"),
    chunk_language: Optional[str] = Form(None, description="Chunking language override"),
    chunk_size: int = Form(500, description="Target chunk size"),
    chunk_overlap: int = Form(200, description="Chunk overlap size"),

    # --- Fields from AudioVideoOptions (might be needed for AddMediaForm validation/defaults) ---
    start_time: Optional[str] = Form(None, description="Optional start time (HH:MM:SS or seconds)"),
    end_time: Optional[str] = Form(None, description="Optional end time (HH:MM:SS or seconds)"),
    transcription_model: str = Form("deepdml/faster-distil-whisper-large-v3.5", description="Transcription model"), # Get default from AddMediaForm if possible
    transcription_language: str = Form("en", description="Transcription language"),
    diarize: bool = Form(False, description="Enable speaker diarization"),
    timestamp_option: bool = Form(True, description="Include timestamps in transcription"),
    vad_use: bool = Form(False, description="Enable VAD filter"),
    perform_confabulation_check_of_analysis: bool = Form(False, description="Enable confabulation check"),

) -> ProcessPDFsForm:
    """
    Dependency function to parse form data and validate it
    against the ProcessPDFsForm model.
    """
    # Validate transcription_model against TranscriptionModel enum
    # (even though PDFs don't use transcription, it's part of the base form)
    if transcription_model:
        valid_models = [model.value for model in TranscriptionModel]
        if transcription_model not in valid_models:
            logger.warning(f"Invalid transcription model provided: {transcription_model}, using default")
            transcription_model = "whisper-large-v3"  # Default to a reliable model

    try:
        # Create the Pydantic model instance using the parsed form data.
        form_instance = ProcessPDFsForm(
            # --- Map all the parameters received by this function ---
            media_type="pdf", # Fixed by ProcessPDFsForm
            urls=urls,
            title=title,
            author=author,
            keywords=keywords, # Pydantic handles mapping this to keywords_str via alias
            custom_prompt=custom_prompt,
            system_prompt=system_prompt,
            overwrite_existing=overwrite_existing,
            keep_original_file=keep_original_file, # Use arg
            perform_analysis=perform_analysis,
            perform_claims_extraction=perform_claims_extraction,
            claims_extractor_mode=claims_extractor_mode,
            claims_max_per_chunk=claims_max_per_chunk,
            api_name=api_name,   # Pass received arg
            # api_key removed - retrieved from server config
            use_cookies=use_cookies,
            cookies=cookies,
            summarize_recursively=summarize_recursively,
            perform_rolling_summarization=perform_rolling_summarization,
            pdf_parsing_engine=pdf_parsing_engine,
            enable_ocr=enable_ocr,
            ocr_backend=ocr_backend,
            ocr_lang=ocr_lang,
            ocr_dpi=ocr_dpi,
            ocr_mode=ocr_mode,
            ocr_min_page_text_chars=ocr_min_page_text_chars,
            custom_chapter_pattern=custom_chapter_pattern,
            perform_chunking=perform_chunking,
            chunk_method=chunk_method,
            use_adaptive_chunking=use_adaptive_chunking,
            use_multi_level_chunking=use_multi_level_chunking,
            chunk_language=chunk_language,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            start_time=start_time,
            end_time=end_time,
            transcription_model=transcription_model,
            transcription_language=transcription_language,
            diarize=diarize,
            timestamp_option=timestamp_option,
            vad_use=vad_use,
            perform_confabulation_check_of_analysis=perform_confabulation_check_of_analysis,

        )
        return form_instance
    # --- Keep the exact same error handling as get_process_videos_form ---
    except ValidationError as e:
        serializable_errors = []
        for error in e.errors():
             serializable_error = error.copy()
             if 'ctx' in serializable_error and isinstance(serializable_error.get('ctx'), dict):
                 new_ctx = {}
                 for k, v in serializable_error['ctx'].items():
                     if isinstance(v, Exception):
                         new_ctx[k] = str(v)
                     else:
                         new_ctx[k] = v
                 serializable_error['ctx'] = new_ctx
             serializable_errors.append(serializable_error)
        logger.warning(f"Pydantic validation failed for PDF processing: {json.dumps(serializable_errors)}")
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail=serializable_errors,
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error creating ProcessPDFsForm: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error during form processing: {type(e).__name__}"
        )

from tldw_Server_API.app.core.Ingestion_Media_Processing.result_normalization import (
    normalise_pdf_result,
)

# ───────────────────────────── endpoint ──────────────────────────────────────
@router.post(
    "/process-pdfs",
    # status_code=status.HTTP_200_OK, # Determined dynamically
    summary="Extract, chunk, analyse PDFs (NO DB Persistence)",
    tags=["Media Processing (No DB)"],
)
async def process_pdfs_endpoint(
    background_tasks: BackgroundTasks,
    # 1. Auth + UserID Determined through `get_db_by_user`
    # token: str = Header(None), # Use Header(None) for optional
    # 2. DB Dependency
    db: MediaDatabase = Depends(get_media_db_for_user),
    form_data: ProcessPDFsForm = Depends(get_process_pdfs_form),
    files: Optional[List[UploadFile]] = File(None,  description="PDF uploads"),
    # VLM controls (separate from OCR)
    vlm_enable: bool = Form(False, description="Enable VLM detection (separate from OCR)"),
    vlm_backend: Optional[str] = Form(None, description="VLM backend (e.g., 'hf_table_transformer')"),
    vlm_detect_tables_only: bool = Form(True, description="Only keep 'table' detections"),
    vlm_max_pages: Optional[int] = Form(None, description="Max pages to scan with VLM"),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
):
    """
    Compatibility shim that forwards to the modular
    ``media.process_pdfs.process_pdfs_endpoint`` implementation.

    The HTTP route for ``/process-pdfs`` is now owned by the modular
    endpoint; this function remains for direct imports/tests.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.process_pdfs import (  # noqa: WPS433
        process_pdfs_endpoint as _process_pdfs_impl,
    )

    return await _process_pdfs_impl(
        background_tasks=background_tasks,
        db=db,
        form_data=form_data,
        files=files,
        vlm_enable=vlm_enable,
        vlm_backend=vlm_backend,
        vlm_detect_tables_only=vlm_detect_tables_only,
        vlm_max_pages=vlm_max_pages,
        usage_log=usage_log,
    )

    logger.info("Request received for /process-pdfs (no persistence).")
    try:
        usage_log.log_event(
            "media.process.pdf",
            tags=["no_db"],
            metadata={"has_urls": bool(form_data.urls), "has_files": bool(files)},
        )
    except Exception:
        pass
    ALLOWED_PDF_EXTENSIONS = ['.pdf']
    _validate_inputs("pdf", form_data.urls, files)

    batch_result: Dict[str, Any] = {
        "processed_count": 0,
        "errors_count": 0,
        "errors": [],
        "results": []
    }

    loop = asyncio.get_running_loop()
    temp_dir_manager = TempDirManager(cleanup=True)

    # We need bytes for process_pdf_task, so handle uploads/downloads differently
    pdf_inputs_to_process: List[Tuple[str, bytes]] = [] # (original_ref, file_bytes)
    # Let's store tasks along with their original refs
    tasks_with_refs: List[Tuple[str, asyncio.Task]] = []
    source_to_ref_map = {} # original_ref -> temp_path (if created) or URL
    file_errors = []
    file_errors_encountered = False # Track if any file/download errors happened

    with temp_dir_manager as temp_dir: # Temp dir needed only if downloading URLs first
        # Handle Uploads (read bytes directly)
        if files:
            saved_files, upload_errors = await _save_uploaded_files(
                files,
                temp_dir=FilePath(temp_dir),  # Need FilePath object
                validator=file_validator_instance,
                allowed_extensions=ALLOWED_PDF_EXTENSIONS
            )

            for err_info in upload_errors:
                file_errors_encountered = True
                original_filename = err_info.get("original_filename") or err_info.get("input", "Unknown Upload")
                error_detail = f"Upload error: {err_info['error']}"
                # Add formatted error to results
                batch_result["results"].append(normalise_pdf_result({
                    "status": "Error", "error": error_detail, "processing_source": original_filename
                }, original_ref=original_filename))  # Use normalise for consistency
                batch_result["errors_count"] += 1
                batch_result["errors"].append(f"{original_filename}: {error_detail}")

            # Now read bytes for successfully saved files
            for info in saved_files:
                original_ref = info["original_filename"]
                local_path = FilePath(info["path"])
                try:
                    file_bytes = local_path.read_bytes()
                    pdf_inputs_to_process.append((original_ref, file_bytes))
                except Exception as read_err:
                    logger.error(f"Failed to read prepared PDF file {original_ref} from {local_path}: {read_err}")
                    file_errors_encountered = True
                    error_detail = f"Failed to read prepared file: {read_err}"
                    batch_result["results"].append(normalise_pdf_result({
                        "status": "Error", "error": error_detail, "processing_source": original_ref
                    }, original_ref=original_ref))
                    batch_result["errors_count"] += 1
                    batch_result["errors"].append(f"{original_ref}: {error_detail}")

        # Handle URLs (download bytes) with strict extension/content-type checking
        if form_data.urls:
            # Use module-local httpx.AsyncClient so tests can monkeypatch it
            async with httpx.AsyncClient(timeout=120) as client:
                download_tasks = [
                    _download_url_async(
                        client=client,
                        url=url,
                        target_dir=FilePath(temp_dir),
                        allowed_extensions={".pdf"},
                        check_extension=True,
                    ) for url in form_data.urls
                ]
                download_results = await asyncio.gather(*download_tasks, return_exceptions=True)

            for url, result in zip(form_data.urls, download_results):
                if isinstance(result, FilePath):
                    try:
                        file_bytes = FilePath(result).read_bytes()
                        pdf_inputs_to_process.append((url, file_bytes))
                    except Exception as read_err:
                        logger.error(f"Failed to read downloaded PDF for {url} from {result}: {read_err}")
                        error_detail = f"Failed to read downloaded PDF: {read_err}"
                        batch_result["results"].append({
                            "status": "Error", "input_ref": url,
                            "processing_source": str(result),
                            "error": error_detail,
                            "media_type": "pdf", "db_id": None, "db_message": "Processing only endpoint.",
                            "metadata": {},
                            "content": None, "chunks": None,
                            "analysis": None, "keywords": None, "warnings": None,
                            "analysis_details": {}
                        })
                        batch_result["errors_count"] += 1
                        batch_result["errors"].append(error_detail)
                else:
                    logger.error(f"Download failed for {url}: {result}")
                    error_detail = f"Download/preparation failed: {result}"
                    batch_result["results"].append({
                        "status": "Error", "input_ref": url,
                        "processing_source": url,
                        "error": error_detail,
                        "media_type": "pdf", "db_id": None, "db_message": "Processing only endpoint.",
                        "metadata": {},
                        "content": None, "chunks": None,
                        "analysis": None, "keywords": None, "warnings": None,
                        "analysis_details": {}
                    })
                    batch_result["errors_count"] += 1
                    batch_result["errors"].append(error_detail)

        if not pdf_inputs_to_process:
            # Determine status based on whether *any* errors occurred during input handling
            status_code = status.HTTP_207_MULTI_STATUS if batch_result["errors_count"] > 0 else status.HTTP_400_BAD_REQUEST
            return JSONResponse(status_code=status_code, content=batch_result)

        logger.debug(f"ENDPOINT: #1 Passing to task -> api_name='{form_data.api_name}', api_provider='{form_data.api_provider}'")
        # --- Call process_pdf_task for each input ---
        for original_ref, file_bytes in pdf_inputs_to_process:
            # --- Pass chunk options correctly ---
            chunk_opts_for_task = {
                "method": form_data.chunk_method if form_data.chunk_method else "sentences",  # Use enum value or default
                "max_size": form_data.chunk_size,
                "overlap": form_data.chunk_overlap,
            }
            logger.debug(
                f"ENDPOINT: #2 Passing to task -> api_name='{form_data.api_name}', api_provider='{form_data.api_provider}'"
            )
            # Create the async task
            task = asyncio.create_task(
                pdf_lib.process_pdf_task(
                    file_bytes=file_bytes,
                    filename=original_ref,  # Use original ref as filename hint
                    parser=str(form_data.pdf_parsing_engine) or "pymupdf4llm",
                    # Pass options from form
                    title_override=form_data.title,
                    author_override=form_data.author,
                    keywords=form_data.keywords,  # Pass list
                    perform_chunking=form_data.perform_chunking or None,
                    # Pass individual chunk params from form model
                    chunk_method=chunk_opts_for_task["method"],
                    max_chunk_size=chunk_opts_for_task["max_size"],
                    chunk_overlap=chunk_opts_for_task["overlap"],
                    perform_analysis=form_data.perform_analysis,
                    api_name=form_data.api_name,
                    # api_key removed - retrieved from server config
                    custom_prompt=form_data.custom_prompt,
                    system_prompt=form_data.system_prompt,
                    summarize_recursively=form_data.summarize_recursively,
                    # VLM
                    enable_vlm=vlm_enable,
                    vlm_backend=vlm_backend,
                    vlm_detect_tables_only=vlm_detect_tables_only,
                    vlm_max_pages=vlm_max_pages,
                )
            )
            tasks_with_refs.append((original_ref, task))

        # Gather results from processing tasks
        gathered_results = await asyncio.gather(*[task for _, task in tasks_with_refs], return_exceptions=True)

        # Add processing results, ensuring no DB fields
        for i, (original_ref, _) in enumerate(tasks_with_refs):
            res = gathered_results[i]  # Get corresponding result/exception

            if isinstance(res, dict):
                # Normalize the result dictionary using the correct original_ref
                normalized_res = normalise_pdf_result(res, original_ref=original_ref)
                batch_result["results"].append(normalized_res)

                # Update counts based on normalized status
                if normalized_res["status"] in ["Success", "Warning"]:
                    batch_result["processed_count"] += 1
                    if normalized_res["status"] == "Warning" and normalized_res.get("warnings"):
                        for warn in normalized_res["warnings"]:
                            batch_result["errors"].append(f"{original_ref}: [Warning] {warn}")
                else:  # Status is Error
                    batch_result["errors_count"] += 1
                    error_msg = f"{original_ref}: {normalized_res.get('error', 'Unknown processing error')}"
                    if error_msg not in batch_result["errors"]:
                        batch_result["errors"].append(error_msg)

            elif isinstance(res, Exception):  # Handle exceptions returned by gather
                logger.error(f"PDF processing task for {original_ref} failed with exception: {res}", exc_info=res)
                error_detail = f"Task execution failed: {type(res).__name__}: {str(res)}"
                # Normalize the error result
                normalized_err = normalise_pdf_result({
                    "status": "Error", "error": error_detail, "processing_source": original_ref
                }, original_ref=original_ref)
                batch_result["results"].append(normalized_err)
                batch_result["errors_count"] += 1
                error_msg = f"{original_ref}: {error_detail}"
                if error_msg not in batch_result["errors"]:
                    batch_result["errors"].append(error_msg)
            else:  # Should not happen
                logger.error(f"Received unexpected result type from PDF worker task for {original_ref}: {type(res)}")
                error_detail = "Invalid result type from PDF worker."
                normalized_err = normalise_pdf_result({
                    "status": "Error", "error": error_detail, "processing_source": original_ref
                }, original_ref=original_ref)
                batch_result["results"].append(normalized_err)
                batch_result["errors_count"] += 1
                error_msg = f"{original_ref}: {error_detail}"
                if error_msg not in batch_result["errors"]:
                    batch_result["errors"].append(error_msg)

    # --- Determine Final Status Code & Return ---
    final_processed_count = sum(1 for r in batch_result["results"] if r.get("status") == "Success")
    final_error_count = sum(1 for r in batch_result["results"] if r.get("status") == "Error")
    batch_result["processed_count"] = final_processed_count
    batch_result["errors_count"] = final_error_count
    # Update errors list to avoid duplicates (optional)
    unique_errors = list(set(str(e) for e in batch_result["errors"] if e))
    batch_result["errors"] = unique_errors

    if batch_result["errors_count"] == 0 and batch_result["processed_count"] > 0:
        final_status_code = status.HTTP_200_OK
    elif batch_result.get("results"): # Any result (success, warning, error) -> 207
        final_status_code = status.HTTP_207_MULTI_STATUS
    else: # No results -> likely means no valid input provided
        final_status_code = status.HTTP_400_BAD_REQUEST

    log_level = "INFO" if final_status_code == status.HTTP_200_OK else "WARNING"
    logger.log(log_level,
               f"/process-pdfs request finished with status {final_status_code}. "
               f"Results: {len(batch_result['results'])}, Processed: {batch_result['processed_count']}, Errors: {batch_result['errors_count']}")

    return JSONResponse(status_code=final_status_code, content=batch_result)

#
# End of PDF Processing Endpoint
############################################################################################


######################## XML Processing Endpoint ###################################
# Endpoints:
# FIXME

#XML File handling
# /Server_API/app/api/v1/endpoints/media.py

class XMLIngestRequest(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    keywords: Optional[List[str]] = []
    system_prompt: Optional[str] = None
    custom_prompt: Optional[str] = None
    auto_summarize: bool = False
    api_name: Optional[str] = None
    # api_key removed - SECURITY: Never accept API keys from client
    mode: str = "persist"  # or "ephemeral"

# @router.post("/process-xml")
# async def process_xml_endpoint(
#     payload: XMLIngestRequest = Form(...),
#     file: UploadFile = File(...)
# ):
#     """
#     Ingest an XML file, optionally summarize it,
#     then either store ephemeral or persist in DB.
#     """
#     try:
#         file_bytes = await file.read()
#         filename = file.filename
#
#         # 1) call the service
#         result_data = await process_xml_task(
#             file_bytes=file_bytes,
#             filename=filename,
#             title=payload.title,
#             author=payload.author,
#             keywords=payload.keywords or [],
#             system_prompt=payload.system_prompt,
#             custom_prompt=payload.custom_prompt,
#             auto_summarize=payload.auto_summarize,
#             api_name=payload.api_name,
#             # api_key removed - retrieved from server config
#         )
#
#         # 2) ephemeral vs. persist
#         if payload.mode == "ephemeral":
#             ephemeral_id = ephemeral_storage.store_data(result_data)
#             return {
#                 "status": "ephemeral-ok",
#                 "media_id": ephemeral_id,
#                 "title": result_data["info_dict"]["title"]
#             }
#         else:
#             # store in DB
#             info_dict = result_data["info_dict"]
#             summary = result_data["summary"]
#             segments = result_data["segments"]
#             combined_prompt = (payload.system_prompt or "") + "\n\n" + (payload.custom_prompt or "")
#
#             media_id = add_media_with_keywords(
#                 url=filename,
#                 info_dict=info_dict,
#                 segments=segments,
#                 summary=summary,
#                 keywords=",".join(payload.keywords or []),
#                 custom_prompt_input=combined_prompt,
#                 whisper_model="xml-import",
#                 media_type="xml_document",
#                 overwrite=False
#             )
#
#             return {
#                 "status": "persist-ok",
#                 "media_id": str(media_id),
#                 "title": info_dict["title"]
#             }
#
#     except Exception as e:
#         raise HTTPException(status_code=500, detail="Internal server error")

# Your gradio_xml_ingestion_tab.py is already set up to call import_xml_handler(...) directly. If you’d prefer to unify it with the new approach, you can simply have your Gradio UI call the new POST /process-xml route, sending the file as UploadFile plus all your form fields. The existing code is fine for a local approach, but if you want your new single endpoint approach, you might adapt the code in the click() callback to do an HTTP request to /process-xml with the “mode” param, etc.
#
# End of XML Ingestion
############################################################################################################


#######################################################################################################################
# MediaWiki Processing Endpoints
#######################################################################################################################

# Backwards-compatible alias; implementation now lives in API_Deps.
from tldw_Server_API.app.api.v1.API_Deps.media_mediawiki_deps import (  # noqa: E402
    get_mediawiki_form_data,
)


@router.post(
    "/mediawiki/ingest-dump",
    summary="Ingest and process a MediaWiki XML dump, storing results to database and vector store.",
    tags=["MediaWiki Processing"],
    dependencies=[Depends(guard_backpressure_and_quota)],
    # No specific response_model for StreamingResponse, individual yielded items can be documented.
)
async def ingest_mediawiki_dump_endpoint(
        form_data: Dict[str, Any] = Depends(get_mediawiki_form_data),
        dump_file: UploadFile = File(..., description="MediaWiki XML dump file (.xml, .xml.bz2, .xml.gz)."),
        # db: Database = Depends(get_media_db_for_user), # Required by add_media_with_keywords indirectly
        # token: str = Header(..., description="Authentication token"), # Assuming auth via get_media_db_for_user
):
    """
    **MediaWiki Ingest (Streaming)**

    Compatibility shim that delegates to the modular
    ``media.process_mediawiki.ingest_mediawiki_dump_endpoint`` implementation.

    The HTTP route for ``/mediawiki/ingest-dump`` is now owned by the
    modular endpoint; this function remains for direct imports/tests.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.process_mediawiki import (  # noqa: WPS433,E402
        ingest_mediawiki_dump_endpoint as _ingest_impl,
    )

    return await _ingest_impl(
        form_data=form_data,
        dump_file=dump_file,
    )


@router.post(
    "/mediawiki/process-dump",
    summary="Process a MediaWiki XML dump and return structured content without database storage.",
    tags=["MediaWiki Processing"],
    # No specific response_model for StreamingResponse. Each line is a JSON object.
    # Can describe the structure of yielded objects (e.g. ProcessedMediaWikiPage or error dicts)
)
async def process_mediawiki_dump_ephemeral_endpoint(
        form_data: Dict[str, Any] = Depends(get_mediawiki_form_data),
        # Can reuse the same form dep, api_name/key will be ignored
        dump_file: UploadFile = File(..., description="MediaWiki XML dump file (.xml, .xml.bz2, .xml.gz)."),
        # No db dependency, as we are not storing to the primary DB.
        # token: str = Header(..., description="Authentication token"), # Optional auth
):
    """
    **MediaWiki Process (Ephemeral, Streaming)**

    Compatibility shim that delegates to the modular
    ``media.process_mediawiki.process_mediawiki_dump_ephemeral_endpoint``
    implementation.

    The HTTP route for ``/mediawiki/process-dump`` is now owned by the
    modular endpoint; this function remains for direct imports/tests.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.process_mediawiki import (  # noqa: WPS433,E402
        process_mediawiki_dump_ephemeral_endpoint as _process_ephemeral_impl,
    )

    return await _process_ephemeral_impl(
        form_data=form_data,
        dump_file=dump_file,
    )
#
# End of MediaWiki Processing Endpoints
#################################################################################################################


######################## Web Scraping & URL Ingestion Endpoint ###################################
# Endpoints:
#

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_token_scope

@router.post(
    "/ingest-web-content",
    dependencies=[
        Depends(guard_backpressure_and_quota),
        Depends(require_token_scope("any", require_if_present=False, endpoint_id="media.ingest", count_as="call")),
    ],
)
async def ingest_web_content(
    request: IngestWebContentRequest,
    background_tasks: BackgroundTasks,
    token: str = Header(..., description="Authentication token"),
    db=Depends(get_media_db_for_user),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
):
    """
    A single endpoint that supports multiple advanced scraping methods:
      - individual: Each item in 'urls' is scraped individually
      - sitemap:    Interprets the first 'url' as a sitemap, scrapes it
      - url_level:  Scrapes all pages up to 'url_level' path segments from the first 'url'
      - recursive:  Scrapes up to 'max_pages' links, up to 'max_depth' from the base 'url'

    Also supports content analysis, translation, chunking, DB ingestion, etc.
    """

    # 1) Basic checks
    if not request.urls:
        raise HTTPException(status_code=400, detail="At least one URL is required")

    # Shared usage logging, topic monitoring, and per-method scraping are
    # handled by the service helper in `web_scraping_service`.
    raw_results: List[Dict[str, Any]] = []
    helper_results = await ingest_web_content_orchestrate(
        request=request,
        db=db,
        usage_log=usage_log,
    )
    if helper_results:
        raw_results.extend(helper_results)

    # 2) Choose the appropriate scraping method (for logging / validation)
    scrape_method = request.scrape_method
    logging.info(f"Selected scrape method: {scrape_method}")

    # For now, treat any scrape_method outside the known enum as invalid.
    if scrape_method not in (
        ScrapeMethod.INDIVIDUAL,
        ScrapeMethod.SITEMAP,
        ScrapeMethod.URL_LEVEL,
        ScrapeMethod.RECURSIVE,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scrape method: {scrape_method}"
        )

    # 4) If we have nothing so far, exit
    if not raw_results:
        return {
            "status": "warning",
            "message": "No articles were successfully scraped for this request.",
            "results": []
        }

    # 5) Perform optional translation (if the user wants it *after* scraping)
    if request.perform_translation:
        logging.info(f"Translating to {request.translation_language} (placeholder).")
        # Insert your real translation code here:
        # for item in raw_results:
        #   item["content"] = translator.translate(item["content"], to_lang=request.translation_language)
        #   if item.get("analysis"):
        #       item["analysis"] = translator.translate(item["analysis"], to_lang=request.translation_language)

    # 6) Perform optional chunking
    if request.perform_chunking:
        logging.info("Performing chunking on each article (placeholder).")
        # Insert chunking logic here. For example:
        # for item in raw_results:
        #     chunks = chunk_text(
        #         text=item["content"],
        #         chunk_size=request.chunk_size,
        #         overlap=request.chunk_overlap,
        #         method=request.chunk_method,
        #         ...
        #     )
        #     item["chunks"] = chunks

    # 7) Timestamp or Overwrite
    if request.timestamp_option:
        timestamp_str = datetime.now().isoformat()
        for item in raw_results:
            item["ingested_at"] = timestamp_str

    # If overwriting existing is set, you’d query the DB here to see if the article already exists, etc.

    # 8) Optionally store results in DB
    # For each article, do something like:
    # media_ids = []
    # for r in raw_results:
    #     media_id = ingest_article_to_db(
    #         url=r["url"],
    #         title=r.get("title", "Untitled"),
    #         author=r.get("author", "Unknown"),
    #         content=r.get("content", ""),
    #         keywords=r.get("keywords", ""),
    #         ingestion_date=r.get("ingested_at", ""),
    #         analysis=r.get("analysis", None),
    #         chunking_data=r.get("chunks", [])
    #     )
    #     media_ids.append(media_id)
    #
    # return {
    #     "status": "success",
    #     "message": "Web content processed and added to DB",
    #     "count": len(raw_results),
    #     "media_ids": media_ids
    # }

    # If you prefer to just return everything as JSON:
    return {
        "status": "success",
        "message": "Web content processed",
        "count": len(raw_results),
        "results": raw_results
    }

# Web Scraping
#     Accepts JSON body describing the scraping method, URL(s), etc.
#     Calls process_web_scraping_task(...).
#     Returns ephemeral or persistent results.
# POST /api/v1/media/process-web-scraping
# that takes a JSON body in the shape of WebScrapingRequest and uses your same “Gradio logic” behind the scenes, but in an API-friendly manner.
#
# Clients can now POST JSON like:
# {
#   "scrape_method": "Individual URLs",
#   "url_input": "https://example.com/article1\nhttps://example.com/article2",
#   "url_level": null,
#   "max_pages": 10,
#   "max_depth": 3,
#   "summarize_checkbox": true,
#   "custom_prompt": "Please summarize with bullet points only.",
#   "api_name": "openai",
#   "api_key": "sk-1234",
#   "keywords": "web, scraping, example",
#   "custom_titles": "Article 1 Title\nArticle 2 Title",
#   "system_prompt": "You are a bulleted-notes specialist...",
#   "temperature": 0.7,
#   "custom_cookies": [{"name":"mycookie", "value":"abc", "domain":".example.com"}],
#   "mode": "ephemeral"
# }
#
#     scrape_method can be "Individual URLs", "Sitemap", "URL Level", or "Recursive Scraping".
#     url_input is either:
#         Multi-line list of URLs (for "Individual URLs"),
#         A single sitemap URL (for "Sitemap"),
#         A single base URL (for "URL Level" or "Recursive Scraping"),
#     url_level only matters if scrape_method="URL Level".
#     max_pages and max_depth matter if scrape_method="Recursive Scraping".
#     summarize_checkbox indicates if you want to run summarization afterwards.
#     api_name + api_key for whichever LLM you want to do summarization.
#     custom_cookies is an optional list of cookie dicts for e.g. paywalls or login.
#     mode can be "ephemeral" or "persist".
#
# The endpoint returns a structure describing ephemeral or persisted results, consistent with your other ingestion endpoints.

# FIXME

# /Server_API/app/api/v1/endpoints/media.py
class WebScrapingRequest(BaseModel):
    scrape_method: str  # "Individual URLs", "Sitemap", "URL Level", "Recursive Scraping"
    url_input: str
    url_level: Optional[int] = None
    max_pages: int = 10
    max_depth: int = 3
    summarize_checkbox: bool = False
    custom_prompt: Optional[str] = None
    api_name: Optional[str] = None
    # api_key removed - SECURITY: Never accept API keys from client
    keywords: Optional[str] = "default,no_keyword_set"
    custom_titles: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    custom_cookies: Optional[List[Dict[str, Any]]] = None  # e.g. [{"name":"mycookie","value":"abc"}]
    mode: str = "persist"  # or "ephemeral"
    user_agent: Optional[str] = None
    custom_headers: Optional[Dict[str, str]] = None
    # Optional crawl overrides (UI toggles)
    crawl_strategy: Optional[str] = None  # e.g., "default" or "best_first"
    include_external: Optional[bool] = None
    score_threshold: Optional[float] = None

async def process_web_scraping_endpoint(
        payload: WebScrapingRequest,
        # 1. Auth + UserID Determined through `get_db_by_user`
        # token: str = Header(None), # Use Header(None) for optional
        # 2. DB Dependency
        db: MediaDatabase = Depends(get_media_db_for_user),
        usage_log: UsageEventLogger = Depends(get_usage_event_logger),
    ):
    """
    Compatibility shim that forwards to the modular
    `media.process_web_scraping.process_web_scraping_endpoint`.

    The HTTP route for `/process-web-scraping` is now owned by the
    modular endpoint; this function remains for direct imports/tests.
    """
    from tldw_Server_API.app.api.v1.endpoints.media.process_web_scraping import (  # type: ignore[import-not-found]
        process_web_scraping_endpoint as _process_web_scraping_impl,
    )

    return await _process_web_scraping_impl(
        payload=payload,
        db=db,
        usage_log=usage_log,
    )

#
# End of Web Scraping Ingestion
#####################################################################################



######################## Debugging and Diagnostics ###################################
# Backwards-compatible helper; the HTTP route lives in `media/debug.py`.
async def debug_schema(
    db: MediaDatabase = Depends(get_media_db_for_user),
):
    """Diagnostic helper retained for compatibility with legacy imports."""
    try:
        schema_info = {}

        with db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            schema_info["tables"] = [table[0] for table in cursor.fetchall()]

            cursor.execute("PRAGMA table_info(Media)")
            schema_info["media_columns"] = [col[1] for col in cursor.fetchall()]

            cursor.execute("PRAGMA table_info(MediaModifications)")
            schema_info["media_mods_columns"] = [col[1] for col in cursor.fetchall()]

            cursor.execute("SELECT COUNT(*) FROM Media")
            schema_info["media_count"] = cursor.fetchone()[0]

        return schema_info
    except Exception as e:  # pragma: no cover - legacy-only path
        logging.error({"error": str(e)})
        return {"error": "An internal error has occurred."}

#
# End of Debugging and Diagnostics
#####################################################################################

from tldw_Server_API.app.core.http_client import (
    afetch as _m_afetch,
    adownload as _m_adownload,
    RetryPolicy as _MRetryPolicy,
    create_async_client as _m_create_async_client,
    DEFAULT_MAX_REDIRECTS as _DEFAULT_MAX_REDIRECTS,
)

async def _download_url_async(
        client: Optional[httpx.AsyncClient],
        url: str,
        target_dir: Path,
        allowed_extensions: Optional[Set[str]] = None,
        check_extension: bool = True,
        disallow_content_types: Optional[Set[str]] = None,
        allow_redirects: bool = True,
) -> Path:
    """
    Backwards-compatible shim that delegates to the core helper.

    All rich behaviour (TEST_MODE stubs, content-type/extension logic,
    and redirect handling) now lives in
    `core.Ingestion_Media_Processing.download_utils.download_url_async`.
    """
    from tldw_Server_API.app.core.Ingestion_Media_Processing.download_utils import (
        download_url_async as _core_download,
    )

    return await _core_download(
        client=client,
        url=url,
        target_dir=target_dir,
        allowed_extensions=allowed_extensions,
        check_extension=check_extension,
        disallow_content_types=disallow_content_types,
        allow_redirects=allow_redirects,
    )


async def _add_media_impl_shim(
    background_tasks: BackgroundTasks,
    form_data: AddMediaForm = Depends(get_add_media_form),
    files: Optional[List[UploadFile]] = File(
        None,
        description="List of files to upload",
    ),
    db: MediaDatabase = Depends(get_media_db_for_user),
    current_user: User = Depends(get_request_user),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
    response: FastAPIResponse = None,
) -> Any:
    """
    Backwards-compatible shim for the legacy add-media implementation.

    Delegates to the core ``add_media_orchestrate`` helper so that all
    `/media/add` behaviour lives under the core ingestion module while
    preserving the original name and signature for any existing callers.
    """
    from tldw_Server_API.app.core.Ingestion_Media_Processing.persistence import (
        add_media_orchestrate,
    )

    return await add_media_orchestrate(
        background_tasks=background_tasks,
        form_data=form_data,
        files=files,
        db=db,
        current_user=current_user,
        usage_log=usage_log,
        response=response,
    )


async def _process_batch_media_shim(
    media_type: MediaType,
    urls: List[str],
    uploaded_file_paths: List[str],
    source_to_ref_map: Dict[str, Union[str, Tuple[str, str]]],
    form_data: AddMediaForm,
    chunk_options: Optional[Dict],
    loop: asyncio.AbstractEventLoop,
    db_path: str,
    client_id: str,
    temp_dir: FilePath,
) -> List[Dict[str, Any]]:
    """
    Backwards-compatible shim for audio/video batch processing.

    Delegates to the core ``process_batch_media`` helper so that the
    implementation lives under ``core.Ingestion_Media_Processing`` while
    preserving the original name and signature for any existing callers.
    """
    from tldw_Server_API.app.core.Ingestion_Media_Processing.persistence import (
        process_batch_media,
    )

    return await process_batch_media(
        media_type=media_type,
        urls=urls,
        uploaded_file_paths=uploaded_file_paths,
        source_to_ref_map=source_to_ref_map,
        form_data=form_data,
        chunk_options=chunk_options,
        loop=loop,
        db_path=db_path,
        client_id=client_id,
        temp_dir=temp_dir,
    )


# Rebind legacy helper names to shims so core implementations are used.
_add_media_impl = _add_media_impl_shim  # type: ignore[assignment]
_process_batch_media = _process_batch_media_shim  # type: ignore[assignment]


#
# End of media.py
#######################################################################################################################
