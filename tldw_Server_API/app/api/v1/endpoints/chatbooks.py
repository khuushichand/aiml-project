# chatbooks.py
# Description: API endpoints for chatbook import/export operations
#
"""
Chatbook API Endpoints
----------------------

Provides REST API endpoints for creating, importing, and managing chatbooks.
"""

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from loguru import logger

# Unified audit service
from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user
from tldw_Server_API.app.core.Audit.unified_audit_service import AuditContext, AuditEventType
from tldw_Server_API.app.core.Logging.log_context import ensure_request_id, ensure_traceparent, get_ps_logger
from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter

from ....core.AuthNZ.User_DB_Handling import User, get_request_user
from ....core.Chatbooks.chatbook_models import ContentType, ExportJob, ExportStatus
from ....core.Chatbooks.exceptions import JobError
from ....core.Chatbooks.chatbook_service import ChatbookService
from ....core.Chatbooks.chatbook_validators import ChatbookValidator
from ....core.Chatbooks.quota_manager import QuotaManager
from ....core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from ....core.DB_Management.db_path_utils import DatabasePaths
from ..API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user as get_chacha_db
from ..schemas.chatbook_schemas import (
    CancelJobResponse,
    ChatbookManifestResponse,
    CleanupExpiredExportsResponse,
    CreateChatbookRequest,
    CreateChatbookResponse,
    ExportJobResponse,
    ImportChatbookRequest,
    ImportChatbookResponse,
    ImportJobResponse,
    ListExportJobsResponse,
    ListImportJobsResponse,
    PreviewChatbookResponse,
    RemoveJobResponse,
)
from ..schemas.chatbook_schemas import (
    ChatbookVersion as SchemaChatbookVersion,
)

_CHATBOOKS_NONCRITICAL_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    ImportError,
    IndexError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
    UnicodeDecodeError,
    HTTPException,
)

router = APIRouter(prefix="/chatbooks", tags=["chatbooks"])

# Use central limiter instance

def _safe_increment_metric(metric_name: str, labels: dict, error_context: str = "") -> None:
    """Safely increment a metric, logging failures without raising."""
    try:
        increment_counter(metric_name, labels=labels)
    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as m_err:
        logger.debug(f"metrics increment failed ({error_context}): error={m_err}")


def _setup_secure_temp_directory(user_id: str) -> Path:
    """
    Set up a secure temporary directory for file uploads.

    This function creates a per-user temporary directory with proper security
    checks to prevent path traversal and symlink attacks.

    Args:
        user_id: The user identifier (will be hashed for directory name)

    Returns:
        Path to the secure user-specific temporary directory

    Raises:
        HTTPException: If directory setup fails or security checks fail
    """
    temp_dir = DatabasePaths.get_user_chatbooks_temp_dir(user_id)
    if temp_dir.is_symlink():
        raise HTTPException(status_code=400, detail="Insecure chatbooks temp directory")
    temp_dir = temp_dir.resolve(strict=True)
    base_dir = DatabasePaths.get_user_chatbooks_dir(user_id).resolve(strict=True)
    try:
        temp_dir.relative_to(base_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chatbooks temp directory path")

    return temp_dir


def get_chatbook_service(
    user: User = Depends(get_request_user),
    db: CharactersRAGDB = Depends(get_chacha_db)
) -> ChatbookService:
    """Get chatbook service for the current user."""
    user_int = user.id_int if hasattr(user, "id_int") else None
    return ChatbookService(user.id, db, user_id_int=user_int)


@router.get("/health", summary="Chatbooks service health")
async def chatbooks_health():
    """Lightweight health endpoint for the Chatbooks subsystem."""
    from datetime import datetime, timezone

    health = {
        "service": "chatbooks",
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {}
    }

    try:
        base_data_dir = DatabasePaths.get_user_db_base_dir()

        exists = base_data_dir.exists()
        writable = False
        if exists:
            try:
                test_file = base_data_dir / ".chatbooks_health_check"
                test_file.parent.mkdir(parents=True, exist_ok=True)
                with open(test_file, "w") as f:
                    f.write("ok")
                os.remove(test_file)
                writable = True
            except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
                writable = False

        health["components"]["storage_base"] = {
            "path": str(base_data_dir),
            "exists": exists,
            "writable": writable
        }

        if not exists or not writable:
            health["status"] = "degraded"
    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as e:
        health["status"] = "unhealthy"
        health["error"] = str(e)

    return health


@router.post("/export", response_model=CreateChatbookResponse)
async def create_chatbook(
    request_data: CreateChatbookRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    service: ChatbookService = Depends(get_chatbook_service),
    user: User = Depends(get_request_user),
    audit_service=Depends(get_audit_service_for_user),
):
    """
    Create a chatbook from selected content.

    This endpoint allows users to export their content (conversations, notes, characters, etc.)
    into a portable chatbook format. The operation can be run synchronously or asynchronously.

    Args:
        request: Chatbook creation parameters
        background_tasks: FastAPI background tasks
        service: Chatbook service instance
        user: Current authenticated user

    Returns:
        CreateChatbookResponse with job ID (async) or file path (sync)
    """
    try:
        # Validate metadata
        valid, error = ChatbookValidator.validate_chatbook_metadata(
            request_data.name,
            request_data.description,
            request_data.tags,
            request_data.categories
        )
        if not valid:
            raise HTTPException(status_code=400, detail=error)

        # Initialize quota manager (DB-backed)
        quota_manager = QuotaManager(str(user.id), getattr(user, 'tier', 'free'), db=service.db)

        # Check export quota
        allowed, message = await quota_manager.check_export_quota()
        if not allowed:
            raise HTTPException(status_code=429, detail=message)

        # Check concurrent jobs quota
        allowed, message = await quota_manager.check_concurrent_jobs()
        if not allowed:
            raise HTTPException(status_code=429, detail=message)

        # Convert content selections to use core ContentType enums
        content_selections = {}
        for content_type, ids in request_data.content_selections.items():
            # Handle both schema enums and strings robustly
            ct_val = content_type.value if hasattr(content_type, 'value') else str(content_type)
            content_selections[ContentType(ct_val)] = ids

        # Create chatbook
        rid = ensure_request_id(request)
        ensure_traceparent(request)
        success, message, result = await service.create_chatbook(
            name=request_data.name,
            description=request_data.description,
            content_selections=content_selections,
            author=request_data.author,
            include_media=request_data.include_media,
            media_quality=request_data.media_quality,
            include_embeddings=request_data.include_embeddings,
            include_generated_content=request_data.include_generated_content,
            tags=request_data.tags,
            categories=request_data.categories,
            async_mode=request_data.async_mode,
            request_id=rid
        )

        if success:
            if request_data.async_mode:
                # Async mode - return job ID
                # Audit export job creation
                try:
                    context = AuditContext(
                        user_id=str(user.id),
                        endpoint="/chatbooks/export",
                        method="POST",
                        ip_address=request.client.host if request and hasattr(request, 'client') else None,
                    )
                    await audit_service.log_event(
                        event_type=AuditEventType.DATA_EXPORT,
                        context=context,
                        resource_type="chatbook_export_job",
                        resource_id=result,
                        action="chatbook_export_started",
                        metadata={
                            "name": request_data.name,
                            "tags": request_data.tags,
                        },
                    )
                except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as audit_err:
                    logger.warning(f"Failed to log audit event for export start: {audit_err}")

                return CreateChatbookResponse(
                    success=True,
                    message=message,
                    job_id=result
                )
            else:
                # Sync mode - create a completed export job with a UUID as job_id
                import uuid
                from datetime import datetime, timezone

                job_id = str(uuid.uuid4())
                file_path = Path(result).resolve()
                expected_base = Path(service.export_dir).resolve()
                try:
                    file_path.relative_to(expected_base)
                except ValueError:
                    raise HTTPException(status_code=500, detail="Export path validation failed")
                file_size = None
                try:
                    if file_path.exists() and file_path.is_file():
                        file_size = file_path.stat().st_size
                except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
                    pass

                # Expiry and signed download URL per configuration
                now_utc = datetime.now(timezone.utc)
                expires_at = service._get_export_expiry(now_utc)
                download_expires_at = service._get_download_expiry(now_utc, expires_at)
                download_url = service._build_download_url(job_id, download_expires_at)

                # Persist the completed job so the download endpoint can serve it
                job = ExportJob(
                    job_id=job_id,
                    user_id=str(user.id),
                    status=ExportStatus.COMPLETED,
                    chatbook_name=request_data.name,
                    output_path=str(file_path),
                    created_at=now_utc,
                    started_at=now_utc,
                    completed_at=now_utc,
                    error_message=None,
                    progress_percentage=100,
                    total_items=0,
                    processed_items=0,
                    file_size_bytes=file_size,
                    download_url=download_url,
                    expires_at=expires_at,
                )
                save_ok = True
                try:
                    # Save job using the service helper
                    service._save_export_job(job)  # noqa: SLF001 (internal helper is appropriate here)
                except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as _e:
                    save_ok = False
                    logger.warning(f"Failed to persist completed export job for sync path: {_e}")
                if not save_ok:
                    # Best-effort cleanup to avoid orphaned exports
                    try:
                        if file_path and file_path.exists():
                            file_path.unlink()
                    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as cleanup_err:
                        logger.warning(f"Failed to remove export archive after job persistence failure: {cleanup_err}")
                    raise HTTPException(
                        status_code=500,
                        detail="Export completed but failed to persist job metadata",
                    )

                # Audit completed export in sync path
                try:
                    context = AuditContext(
                        user_id=str(user.id),
                        endpoint="/chatbooks/export",
                        method="POST",
                        ip_address=request.client.host if request and hasattr(request, 'client') else None,
                    )
                    await audit_service.log_event(
                        event_type=AuditEventType.DATA_EXPORT,
                        context=context,
                        resource_type="chatbook_export_job",
                        resource_id=job_id,
                        action="chatbook_export_completed_sync",
                        metadata={"filename": file_path.name if file_path else None, "file_size": file_size},
                    )
                except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as audit_err:
                    logger.warning(f"Failed to log audit event for export completion: {audit_err}")

                return CreateChatbookResponse(
                    success=True,
                    message=message,
                    job_id=job_id,
                    download_url=download_url
                )
        else:
            # For async jobs, return a failure response with job_id so clients can inspect status.
            if request_data.async_mode and result:
                return CreateChatbookResponse(
                    success=False,
                    message=message,
                    job_id=result
                )
            raise HTTPException(status_code=400, detail=message)

    except HTTPException:
        raise
    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
        # Log full traceback to aid debugging intermittent 500s in CI
        get_ps_logger(
            request_id=ensure_request_id(request),
            ps_component="endpoint",
            ps_job_kind="chatbooks",
            traceparent=ensure_traceparent(request),
        ).exception(f"Unhandled exception creating chatbook for user {user.id}")
        raise HTTPException(status_code=500, detail="An error occurred while creating the chatbook")


@router.post("/import", response_model=ImportChatbookResponse)
async def import_chatbook(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    import_request: ImportChatbookRequest = Depends(),
    service: ChatbookService = Depends(get_chatbook_service),
    user: User = Depends(get_request_user),
    audit_service=Depends(get_audit_service_for_user),
):
    """
    Import a chatbook file.

    This endpoint allows users to import content from a chatbook file. The operation
    can handle conflicts through various resolution strategies and can be run
    synchronously or asynchronously.

    Args:
        file: The chatbook file to import (ZIP format)
        request: Import configuration
        background_tasks: FastAPI background tasks
        service: Chatbook service instance
        user: Current authenticated user

    Returns:
        ImportChatbookResponse with job ID (async) or import results (sync)
    """
    temp_file: Optional[Path] = None  # Initialize for proper cleanup in finally
    try:
        # Initialize quota manager (DB-backed)
        quota_manager = QuotaManager(str(user.id), getattr(user, 'tier', 'free'), db=service.db)

        # Check import quota
        allowed, message = await quota_manager.check_import_quota()
        if not allowed:
            raise HTTPException(status_code=429, detail=message)

        # Check concurrent jobs quota
        allowed, message = await quota_manager.check_concurrent_jobs()
        if not allowed:
            raise HTTPException(status_code=429, detail=message)

        # Reject unsupported import options until implemented
        if import_request.import_media or import_request.import_embeddings:
            raise HTTPException(
                status_code=400,
                detail="Media/embedding imports are not supported yet. Set import_media=false and import_embeddings=false.",
            )
        if import_request.content_selections:
            unsupported = {"media", "embedding", "prompt", "evaluation", "generated_document"}
            requested = []
            for content_type in import_request.content_selections:
                ct_val = content_type.value if hasattr(content_type, "value") else str(content_type)
                if ct_val in unsupported:
                    requested.append(ct_val)
            if requested:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Import for content types is not supported yet: "
                        + ", ".join(sorted(set(requested)))
                    ),
                )

        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Validate and sanitize filename
        valid, error, safe_filename = ChatbookValidator.validate_filename(file.filename)
        if not valid:
            raise HTTPException(status_code=400, detail=error)

        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning

        # Check file size quota
        allowed, message = await quota_manager.check_file_size(file_size)
        if not allowed:
            raise HTTPException(status_code=413, detail=message)

        # Save uploaded file to secure temp location with sanitized name
        temp_dir = _setup_secure_temp_directory(str(user.id))
        temp_dir_resolved = temp_dir.resolve(strict=True)

        # Build the destination file path
        temp_file = temp_dir / f"import_{uuid4().hex}_{safe_filename}"
        temp_file_resolved = temp_file.resolve()
        try:
            temp_file_resolved.relative_to(temp_dir_resolved)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid file path") from None
        temp_file = temp_file_resolved

        with open(temp_file, 'wb') as f:
            shutil.copyfileobj(file.file, f)

        # Validate the uploaded ZIP file
        valid, error = ChatbookValidator.validate_zip_file(str(temp_file))
        if not valid:
            try:
                temp_file.unlink()
            except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as e:
                logger.warning(f"Failed to remove invalid uploaded file during import: path={temp_file}, user={user.id}, error={e}")
            _safe_increment_metric(
                "app_warning_events_total",
                labels={"component": "chatbooks", "event": "import_invalid_upload_cleanup_failed"},
                error_context="chatbooks import_invalid_upload_cleanup_failed",
            )
            raise HTTPException(status_code=400, detail=error)

        # Convert content selections if provided (schema enum or string keys)
        content_selections = None
        if import_request.content_selections:
            content_selections = {}
            for content_type, ids in import_request.content_selections.items():
                ct_val = content_type.value if hasattr(content_type, 'value') else str(content_type)
                content_selections[ContentType(ct_val)] = ids

        # Import chatbook
        rid = ensure_request_id(request)
        ensure_traceparent(request)
        success, message, result = await service.import_chatbook(
            file_path=str(temp_file),
            content_selections=content_selections,
            conflict_resolution=import_request.conflict_resolution,
            prefix_imported=import_request.prefix_imported,
            import_media=import_request.import_media,
            import_embeddings=import_request.import_embeddings,
            async_mode=import_request.async_mode,
            request_id=rid
        )

        if success:
            if import_request.async_mode:
                # Async mode - return job ID
                try:
                    context = AuditContext(
                        user_id=str(user.id),
                        endpoint="/chatbooks/import",
                        method="POST",
                        ip_address=request.client.host if request and hasattr(request, 'client') else None,
                    )
                    await audit_service.log_event(
                        event_type=AuditEventType.DATA_IMPORT,
                        context=context,
                        resource_type="chatbook_import_job",
                        resource_id=result,
                        action="chatbook_import_started",
                        metadata={"filename": file.filename},
                    )
                except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as audit_err:
                    logger.warning(f"Failed to log audit event for import start: {audit_err}")
                return ImportChatbookResponse(
                    success=True,
                    message=message,
                    job_id=result
                )
            else:
                # Sync mode - return import results
                # TODO: Parse message for imported item counts
                try:
                    context = AuditContext(
                        user_id=str(user.id),
                        endpoint="/chatbooks/import",
                        method="POST",
                        ip_address=request.client.host if request and hasattr(request, 'client') else None,
                    )
                    await audit_service.log_event(
                        event_type=AuditEventType.DATA_IMPORT,
                        context=context,
                        action="chatbook_import_completed_sync",
                        metadata={"filename": file.filename},
                    )
                except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as audit_err:
                    logger.warning(f"Failed to log audit event for import completion: {audit_err}")
                warnings_out = result if isinstance(result, list) else None
                return ImportChatbookResponse(
                    success=True,
                    message=message,
                    warnings=warnings_out
                )
        else:
            # For async jobs, return a failure response with job_id so clients can inspect status.
            if import_request.async_mode and result:
                # Enqueue failed; cleanup temp file since no worker will consume it.
                if temp_file is not None and temp_file.exists():
                    try:
                        temp_file.unlink()
                    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as e:
                        logger.warning(f"Cleanup of temp import file failed after enqueue failure: path={temp_file}, user={user.id}, error={e}")
                        _safe_increment_metric(
                            "app_warning_events_total",
                            labels={"component": "chatbooks", "event": "import_cleanup_failed"},
                            error_context="chatbooks import_cleanup_failed",
                        )
                return ImportChatbookResponse(
                    success=False,
                    message=message,
                    job_id=result
                )
            raise HTTPException(status_code=400, detail=message)

    except HTTPException:
        raise
    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
        get_ps_logger(
            request_id=ensure_request_id(request),
            ps_component="endpoint",
            ps_job_kind="chatbooks",
            traceparent=ensure_traceparent(request),
        ).exception(f"Error importing chatbook for user {user.id}")
        raise HTTPException(status_code=500, detail="An error occurred while importing the chatbook")
    finally:
        # Cleanup uploaded file if not async
        if temp_file is not None and not import_request.async_mode and temp_file.exists():
            try:
                temp_file.unlink()
            except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as e:
                logger.warning(f"Cleanup of temp import file failed: path={temp_file}, user={user.id}, error={e}")
                _safe_increment_metric(
                    "app_warning_events_total",
                    labels={"component": "chatbooks", "event": "import_cleanup_failed"},
                    error_context="chatbooks import_cleanup_failed",
                )


@router.post("/preview", response_model=PreviewChatbookResponse)
async def preview_chatbook(
    request: Request,
    file: UploadFile = File(...),
    service: ChatbookService = Depends(get_chatbook_service),
    user: User = Depends(get_request_user),
    audit_service=Depends(get_audit_service_for_user),
):
    """
    Preview a chatbook without importing it.

    This endpoint allows users to examine the contents of a chatbook file
    before deciding whether to import it.

    Args:
        file: The chatbook file to preview (ZIP format)
        service: Chatbook service instance
        user: Current authenticated user

    Returns:
        PreviewChatbookResponse with manifest information
    """
    temp_file: Optional[Path] = None
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Validate and sanitize filename
        valid, error, safe_filename = ChatbookValidator.validate_filename(file.filename)
        if not valid:
            raise HTTPException(status_code=400, detail=error)

        # Initialize quota manager (DB-backed) for consistent rate limiting
        quota_manager = QuotaManager(str(user.id), getattr(user, 'tier', 'free'), db=service.db)

        # Check file size (limit to 100MB for preview)
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        # Check file size against user's quota
        allowed, message = await quota_manager.check_file_size(file_size)
        if not allowed:
            raise HTTPException(status_code=413, detail=message)

        if file_size > 100 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 100MB for preview")

        # Save uploaded file to secure temp location with sanitized name
        temp_dir = _setup_secure_temp_directory(str(user.id))
        temp_dir_resolved = temp_dir.resolve(strict=True)

        # Build the preview file path
        temp_file = temp_dir / f"preview_{uuid4().hex}_{safe_filename}"
        temp_file_resolved = temp_file.resolve()
        try:
            temp_file_resolved.relative_to(temp_dir_resolved)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid file path") from None
        temp_file = temp_file_resolved

        with open(temp_file, 'wb') as f:
            shutil.copyfileobj(file.file, f)

        # Validate archive using centralized validator prior to extracting
        ok, err = ChatbookValidator.validate_zip_file(str(temp_file))
        if not ok:
            try:
                temp_file.unlink()
            except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as e:
                logger.warning(f"Failed to remove invalid uploaded file during preview: path={temp_file}, user={user.id}, error={e}")
            _safe_increment_metric(
                "app_warning_events_total",
                labels={"component": "chatbooks", "event": "preview_invalid_upload_cleanup_failed"},
                error_context="chatbooks preview_invalid_upload_cleanup_failed",
            )
            raise HTTPException(status_code=400, detail=err or "Invalid archive")

        # Preview chatbook
        manifest, error = service.preview_chatbook(str(temp_file))

        # Cleanup temp file
        try:
            temp_file.unlink()
        except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as e:
            logger.warning(f"Cleanup of preview temp file failed: path={temp_file}, user={user.id}, error={e}")
            _safe_increment_metric(
                "app_warning_events_total",
                labels={"component": "chatbooks", "event": "preview_cleanup_failed"},
                error_context="chatbooks preview_cleanup_failed",
            )

        if manifest:
            # Convert manifest to response model
            # Coerce model enum to schema enum value safely, map legacy 1.0 -> 1.0.0
            ver_str = getattr(manifest.version, 'value', str(manifest.version))
            if ver_str == "1.0":
                ver_str = "1.0.0"
            metadata_payload = dict(manifest.metadata or {})
            if manifest.binary_limits:
                metadata_payload.setdefault("binary_limits", manifest.binary_limits)
            manifest_response = ChatbookManifestResponse(
                version=SchemaChatbookVersion(ver_str),
                name=manifest.name,
                description=manifest.description,
                author=manifest.author,
                created_at=manifest.created_at,
                updated_at=manifest.updated_at,
                export_id=manifest.export_id,
                content_items=[],  # Simplified for preview
                include_media=manifest.include_media,
                include_embeddings=manifest.include_embeddings,
                include_generated_content=manifest.include_generated_content,
                media_quality=manifest.media_quality,
                max_file_size_mb=manifest.max_file_size_mb,
                total_conversations=manifest.total_conversations,
                total_notes=manifest.total_notes,
                total_characters=manifest.total_characters,
                total_media_items=manifest.total_media_items,
                total_prompts=manifest.total_prompts,
                total_evaluations=manifest.total_evaluations,
                total_embeddings=manifest.total_embeddings,
                total_world_books=manifest.total_world_books,
                total_dictionaries=manifest.total_dictionaries,
                total_documents=manifest.total_documents,
                total_size_bytes=manifest.total_size_bytes,
                tags=manifest.tags,
                categories=manifest.categories,
                language=manifest.language,
                license=manifest.license,
                metadata=metadata_payload,
                truncation=manifest.truncation or {}
            )
            # Audit successful preview
            try:
                context = AuditContext(
                    user_id=str(user.id),
                    endpoint="/chatbooks/preview",
                    method="POST",
                    ip_address=request.client.host if request and hasattr(request, 'client') else None,
                )
                await audit_service.log_event(
                    event_type=AuditEventType.DATA_READ,
                    context=context,
                    resource_type="chatbook_preview",
                    action="chatbook_preview",
                    metadata={"filename": file.filename},
                )
            except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as audit_err:
                logger.warning(f"Failed to log audit event for preview: {audit_err}")
            return PreviewChatbookResponse(manifest=manifest_response)
        else:
            return PreviewChatbookResponse(error=error)

    except HTTPException:
        raise
    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
        get_ps_logger(
            request_id=ensure_request_id(request),
            ps_component="endpoint",
            ps_job_kind="chatbooks",
            traceparent=ensure_traceparent(request),
        ).exception(f"Error previewing chatbook for user {user.id}")
        raise HTTPException(status_code=500, detail="An error occurred while previewing the chatbook")
    finally:
        # Ensure preview upload cleanup on all paths
        if temp_file is not None and temp_file.exists():
            try:
                temp_file.unlink()
            except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as e:
                logger.warning(f"Cleanup of preview temp file failed: path={temp_file}, user={user.id}, error={e}")
                _safe_increment_metric(
                    "app_warning_events_total",
                    labels={"component": "chatbooks", "event": "preview_cleanup_failed"},
                    error_context="chatbooks preview_cleanup_failed",
                )


@router.get("/export/jobs", response_model=ListExportJobsResponse)
async def list_export_jobs(
    request: Request,  # Required for rate limiting
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    service: ChatbookService = Depends(get_chatbook_service),
    user: User = Depends(get_request_user)
):
    """
    List all export jobs for the current user.

    Args:
        limit: Maximum number of results
        offset: Offset for pagination
        service: Chatbook service instance
        user: Current authenticated user

    Returns:
        ListExportJobsResponse with list of export jobs
    """
    try:
        total = service.count_export_jobs()
        jobs = service.list_export_jobs(limit=limit, offset=offset)

        # Convert to response models
        job_responses = []
        now_utc = datetime.now(timezone.utc)
        for job in jobs:
            # Generate secure download URL based on job_id
            secure_download_url = None
            if job.status == ExportStatus.COMPLETED:
                export_expires_at = job.expires_at or service._get_export_expiry(now_utc)
                download_expires_at = service._get_download_expiry(now_utc, export_expires_at)
                secure_download_url = service._build_download_url(job.job_id, download_expires_at)

            job_responses.append(ExportJobResponse(
                job_id=job.job_id,
                status=job.status,
                chatbook_name=job.chatbook_name,
                output_path=None,  # Don't expose internal file paths
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                error_message=job.error_message,
                progress_percentage=job.progress_percentage,
                total_items=job.total_items,
                processed_items=job.processed_items,
                file_size_bytes=job.file_size_bytes,
                download_url=secure_download_url,  # Use secure URL based on job_id
                expires_at=job.expires_at
            ))

        return ListExportJobsResponse(jobs=job_responses, total=total)

    except HTTPException:
        raise
    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
        logger.exception(f"Error listing export jobs for user {user.id}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while retrieving export jobs",
        ) from None


@router.get("/export/jobs/{job_id}", response_model=ExportJobResponse)
async def get_export_job(
    job_id: str,
    service: ChatbookService = Depends(get_chatbook_service),
    user: User = Depends(get_request_user)
):
    """
    Get status of a specific export job.

    Args:
        job_id: The export job ID
        service: Chatbook service instance
        user: Current authenticated user

    Returns:
        ExportJobResponse with job details
    """
    try:
        job = service.get_export_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Export job not found")

        # Generate secure download URL based on job_id
        secure_download_url = None
        if job.status == ExportStatus.COMPLETED:
            now_utc = datetime.now(timezone.utc)
            export_expires_at = job.expires_at or service._get_export_expiry(now_utc)
            download_expires_at = service._get_download_expiry(now_utc, export_expires_at)
            secure_download_url = service._build_download_url(job.job_id, download_expires_at)

        return ExportJobResponse(
            job_id=job.job_id,
            status=job.status,
            chatbook_name=job.chatbook_name,
            output_path=None,  # Don't expose internal file paths
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error_message=job.error_message,
            progress_percentage=job.progress_percentage,
            total_items=job.total_items,
            processed_items=job.processed_items,
            file_size_bytes=job.file_size_bytes,
            download_url=secure_download_url,  # Use secure URL based on job_id
            expires_at=job.expires_at
        )

    except HTTPException:
        raise
    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
        logger.exception(f"Error getting export job {job_id} for user {user.id}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while retrieving the export job",
        ) from None


@router.get("/import/jobs", response_model=ListImportJobsResponse)
async def list_import_jobs(
    request: Request,  # Required for rate limiting
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    service: ChatbookService = Depends(get_chatbook_service),
    user: User = Depends(get_request_user)
):
    """
    List all import jobs for the current user.

    Args:
        limit: Maximum number of results
        offset: Offset for pagination
        service: Chatbook service instance
        user: Current authenticated user

    Returns:
        ListImportJobsResponse with list of import jobs
    """
    try:
        total = service.count_import_jobs()
        jobs = service.list_import_jobs(limit=limit, offset=offset)

        # Convert to response models
        job_responses = []
        for job in jobs:
            job_responses.append(ImportJobResponse(
                job_id=job.job_id,
                status=job.status,
                chatbook_path=job.chatbook_path,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                error_message=job.error_message,
                progress_percentage=job.progress_percentage,
                total_items=job.total_items,
                processed_items=job.processed_items,
                successful_items=job.successful_items,
                failed_items=job.failed_items,
                skipped_items=job.skipped_items,
                conflicts=job.conflicts,
                warnings=job.warnings
            ))

        return ListImportJobsResponse(jobs=job_responses, total=total)

    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
        logger.exception(f"Error listing import jobs for user {user.id}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while retrieving import jobs",
        ) from None


@router.get("/import/jobs/{job_id}", response_model=ImportJobResponse)
async def get_import_job(
    job_id: str,
    service: ChatbookService = Depends(get_chatbook_service),
    user: User = Depends(get_request_user)
):
    """
    Get status of a specific import job.

    Args:
        job_id: The import job ID
        service: Chatbook service instance
        user: Current authenticated user

    Returns:
        ImportJobResponse with job details
    """
    try:
        job = service.get_import_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Import job not found")

        return ImportJobResponse(
            job_id=job.job_id,
            status=job.status,
            chatbook_path=job.chatbook_path,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error_message=job.error_message,
            progress_percentage=job.progress_percentage,
            total_items=job.total_items,
            processed_items=job.processed_items,
            successful_items=job.successful_items,
            failed_items=job.failed_items,
            skipped_items=job.skipped_items,
            conflicts=job.conflicts,
            warnings=job.warnings
        )

    except HTTPException:
        raise
    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
        logger.exception(f"Error getting import job {job_id} for user {user.id}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while retrieving the import job",
        ) from None


@router.get("/download/{job_id}")
async def download_chatbook(
    job_id: str,
    request: Request,
    service: ChatbookService = Depends(get_chatbook_service),
    user: User = Depends(get_request_user),
    audit_service=Depends(get_audit_service_for_user),
):
    """
    Download an exported chatbook file by job ID.

    Args:
        job_id: The export job ID
        service: Chatbook service instance
        user: Current authenticated user

    Returns:
        FileResponse with the chatbook file
    """
    try:
        # Validate job_id format
        # Accept UUIDs. If using Prompt Studio backend, also accept numeric IDs.
        backend = getattr(service, "_jobs_backend", "core")
        is_uuid = ChatbookValidator.validate_job_id(job_id)
        is_ps_valid = backend == "prompt_studio" and job_id.isdigit()
        if not (is_uuid or is_ps_valid):
            raise HTTPException(status_code=400, detail="Invalid job ID format")

        # Get job from service (validates ownership)
        job = service.get_export_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Export job not found")

        # Verify job belongs to current user (double check)
        if job.user_id != str(user.id):
            raise HTTPException(status_code=403, detail="Access denied")

        # Verify job is completed
        if job.status != ExportStatus.COMPLETED:
            raise HTTPException(status_code=400, detail=f"Export job is {job.status.value}, not completed")

        # Enforce expiration (config-gated)
        enforce_expiry = str(os.getenv("CHATBOOKS_ENFORCE_EXPIRY", "true")).lower() in {"1","true","yes"}
        if enforce_expiry and getattr(job, 'expires_at', None) is not None:
            from datetime import datetime as _dt
            from datetime import timezone as _tz
            now_utc = _dt.now(_tz.utc)
            expires_at = job.expires_at
            # Handle naive datetime from database by assuming UTC
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=_tz.utc)
            if now_utc > expires_at:
                raise HTTPException(status_code=410, detail="Download link has expired")

        # Validate signed URL if configured
        use_signed = str(os.getenv("CHATBOOKS_SIGNED_URLS", "false")).lower() in {"1","true","yes"}
        secret = os.getenv("CHATBOOKS_SIGNING_SECRET", "")
        if use_signed and secret:
            token = request.query_params.get("token")
            exp = request.query_params.get("exp")
            if not token or not exp:
                raise HTTPException(status_code=403, detail="Missing signature")
            try:
                exp_int = int(exp)
            except ValueError as e:
                logger.warning(f"Invalid exp parameter in signed URL: exp={exp!r}, error={e}")
                raise HTTPException(status_code=400, detail="Invalid exp")
            # Check exp against current time
            import time
            if time.time() > exp_int:
                raise HTTPException(status_code=410, detail="Signed URL expired")
            # Verify signature
            import hashlib
            import hmac
            msg = f"{job_id}:{exp_int}".encode()
            expected = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, token):
                raise HTTPException(status_code=403, detail="Invalid signature")

        # Get secure file path from job
        if not job.output_path:
            raise HTTPException(status_code=404, detail="Export file not found")

        file_path = Path(job.output_path).resolve()

        # Additional path containment check - ensure file is in expected user directory
        # The file should be within the user's export directory
        expected_base = Path(service.export_dir).resolve()
        try:
            file_path.relative_to(expected_base)
        except ValueError:
            logger.warning(f"Path traversal attempt detected for user {user.id}")
            # Log security event via unified audit service
            try:
                context = AuditContext(
                    user_id=str(user.id),
                    endpoint="/chatbooks/download",
                    method="GET",
                    ip_address=request.client.host if request and hasattr(request, 'client') else None,
                )
                await audit_service.log_event(
                    event_type=AuditEventType.SECURITY_VIOLATION,
                    context=context,
                    action="chatbook_download_path_traversal",
                    result="failure",
                    metadata={
                        "job_id": job_id,
                        "attempted_path": str(file_path)[:100]
                    }
                )
            except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as audit_err:
                logger.warning(f"Failed to log audit event for path traversal: {audit_err}")
            raise HTTPException(status_code=403, detail="Access denied")

        # Verify file exists (containment already validated above)
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="Export file no longer exists")

        # Get filename from path
        filename = file_path.name

        # Log successful download via unified audit service
        try:
            context = AuditContext(
                user_id=str(user.id),
                endpoint="/chatbooks/download",
                method="GET",
                ip_address=request.client.host if request and hasattr(request, 'client') else None,
            )
            await audit_service.log_event(
                event_type=AuditEventType.DATA_EXPORT,
                context=context,
                resource_type="chatbook",
                resource_id=job_id,
                action="chatbook_download",
                metadata={
                    "filename": filename,
                    "file_size": file_path.stat().st_size
                }
            )
        except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as audit_err:
            logger.warning(f"Failed to log audit event for download: {audit_err}")

        # Build safe Content-Disposition (ASCII fallback + RFC 5987 filename*)
        def _safe_disp_parts(name: str) -> tuple[str, Optional[str]]:
            try:
                name.encode("ascii")
                return name, None
            except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
                try:
                    import urllib.parse as _u
                    return "download", _u.quote(name)
                except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
                    return "download", None
        ascii_name, encoded_name = _safe_disp_parts(filename)
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Download-Options": "noopen",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Content-Disposition": (
                f"attachment; filename={ascii_name}" + (f"; filename*=UTF-8''{encoded_name}" if encoded_name else "")
            ),
        }

        # Return file with security headers
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/zip",
            headers=headers,
        )

    except HTTPException:
        raise
    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
        logger.exception(f"Error downloading chatbook {job_id} for user {user.id}")
        raise HTTPException(status_code=500, detail="An error occurred while downloading the file")


@router.post("/cleanup", response_model=CleanupExpiredExportsResponse)
async def cleanup_expired_exports(
    service: ChatbookService = Depends(get_chatbook_service),
    user: User = Depends(get_request_user),
    audit_service=Depends(get_audit_service_for_user),
):
    """
    Clean up expired export files.

    This endpoint removes export files that have passed their expiration date.

    Args:
        service: Chatbook service instance
        user: Current authenticated user

    Returns:
        CleanupExpiredExportsResponse with count of deleted files
    """
    try:
        deleted_count = service.cleanup_expired_exports()

        # Audit cleanup action for traceability
        try:
            context = AuditContext(
                user_id=str(user.id),
                endpoint="/chatbooks/cleanup",
                method="POST",
            )
            await audit_service.log_event(
                event_type=AuditEventType.DATA_DELETE,
                context=context,
                resource_type="chatbook_exports",
                action="chatbook_cleanup_expired_exports",
                metadata={"deleted_count": deleted_count},
            )
        except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as audit_err:
            logger.warning(f"Failed to log audit event for cleanup: {audit_err}")

        return CleanupExpiredExportsResponse(
            deleted_count=deleted_count
        )

    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
        logger.exception(f"Error cleaning up expired exports for user {user.id}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while cleaning up expired exports",
        ) from None


@router.delete("/export/jobs/{job_id}", response_model=CancelJobResponse)
async def cancel_export_job(
    job_id: str,
    request: Request,
    service: ChatbookService = Depends(get_chatbook_service),
    user: User = Depends(get_request_user),
    audit_service=Depends(get_audit_service_for_user),
):
    """
    Cancel an export job.

    Args:
        job_id: The export job ID to cancel
        request: FastAPI request object
        service: Chatbook service instance
        user: Current authenticated user

    Returns:
        CancelJobResponse with success status
    """
    try:
        ok = service.cancel_export_job(job_id)
        if not ok:
            raise HTTPException(status_code=400, detail="Cannot cancel completed or failed job")
        try:
            context = AuditContext(
                user_id=str(user.id),
                endpoint="/chatbooks/export/jobs/{job_id}",
                method="DELETE",
                ip_address=request.client.host if request and hasattr(request, 'client') else None,
            )
            await audit_service.log_event(
                event_type=AuditEventType.DATA_DELETE,
                context=context,
                resource_type="chatbook_export_job",
                resource_id=job_id,
                action="chatbook_export_job_cancelled",
            )
        except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as audit_err:
            logger.warning(f"Failed to log audit event for export job cancellation: {audit_err}")
        return CancelJobResponse(
            success=True,
            message=f"Export job {job_id} cancelled",
            job_id=job_id,
        )

    except HTTPException:
        raise
    except JobError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
        logger.exception(f"Error cancelling export job {job_id} for user {user.id}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while cancelling the export job",
        ) from None


@router.delete("/import/jobs/{job_id}", response_model=CancelJobResponse)
async def cancel_import_job(
    job_id: str,
    request: Request,
    service: ChatbookService = Depends(get_chatbook_service),
    user: User = Depends(get_request_user),
    audit_service=Depends(get_audit_service_for_user),
):
    """
    Cancel an import job.

    Args:
        job_id: The import job ID to cancel
        request: FastAPI request object
        service: Chatbook service instance
        user: Current authenticated user

    Returns:
        CancelJobResponse with success status
    """
    try:
        ok = service.cancel_import_job(job_id)
        if not ok:
            raise HTTPException(status_code=400, detail="Cannot cancel completed or failed job")
        try:
            context = AuditContext(
                user_id=str(user.id),
                endpoint="/chatbooks/import/jobs/{job_id}",
                method="DELETE",
                ip_address=request.client.host if request and hasattr(request, 'client') else None,
            )
            await audit_service.log_event(
                event_type=AuditEventType.DATA_DELETE,
                context=context,
                resource_type="chatbook_import_job",
                resource_id=job_id,
                action="chatbook_import_job_cancelled",
            )
        except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as audit_err:
            logger.warning(f"Failed to log audit event for import job cancellation: {audit_err}")
        return CancelJobResponse(
            success=True,
            message=f"Import job {job_id} cancelled",
            job_id=job_id,
        )

    except HTTPException:
        raise
    except JobError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
        logger.exception(f"Error cancelling import job {job_id} for user {user.id}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while cancelling the import job",
        ) from None


@router.delete("/export/jobs/{job_id}/remove", response_model=RemoveJobResponse)
async def remove_export_job(
    job_id: str,
    request: Request,
    service: ChatbookService = Depends(get_chatbook_service),
    user: User = Depends(get_request_user),
    audit_service=Depends(get_audit_service_for_user),
):
    """
    Remove a completed or cancelled export job.

    Args:
        job_id: The export job ID to remove
    """
    try:
        ok = service.delete_export_job(job_id)
        if not ok:
            raise HTTPException(status_code=400, detail="Only cancelled or completed jobs can be removed")
        try:
            context = AuditContext(
                user_id=str(user.id),
                endpoint="/chatbooks/export/jobs/{job_id}/remove",
                method="DELETE",
                ip_address=request.client.host if request and hasattr(request, 'client') else None,
            )
            await audit_service.log_event(
                event_type=AuditEventType.DATA_DELETE,
                context=context,
                resource_type="chatbook_export_job",
                resource_id=job_id,
                action="chatbook_export_job_removed",
            )
        except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as audit_err:
            logger.warning(f"Failed to log audit event for export job removal: {audit_err}")
        return RemoveJobResponse(
            success=True,
            message=f"Export job {job_id} removed",
            job_id=job_id,
        )
    except HTTPException:
        raise
    except JobError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
        logger.exception(f"Error removing export job {job_id} for user {user.id}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while removing the export job",
        ) from None


@router.delete("/import/jobs/{job_id}/remove", response_model=RemoveJobResponse)
async def remove_import_job(
    job_id: str,
    request: Request,
    service: ChatbookService = Depends(get_chatbook_service),
    user: User = Depends(get_request_user),
    audit_service=Depends(get_audit_service_for_user),
):
    """
    Remove a completed or cancelled import job.

    Args:
        job_id: The import job ID to remove
    """
    try:
        ok = service.delete_import_job(job_id)
        if not ok:
            raise HTTPException(status_code=400, detail="Only cancelled or completed jobs can be removed")
        try:
            context = AuditContext(
                user_id=str(user.id),
                endpoint="/chatbooks/import/jobs/{job_id}/remove",
                method="DELETE",
                ip_address=request.client.host if request and hasattr(request, 'client') else None,
            )
            await audit_service.log_event(
                event_type=AuditEventType.DATA_DELETE,
                context=context,
                resource_type="chatbook_import_job",
                resource_id=job_id,
                action="chatbook_import_job_removed",
            )
        except _CHATBOOKS_NONCRITICAL_EXCEPTIONS as audit_err:
            logger.warning(f"Failed to log audit event for import job removal: {audit_err}")
        return RemoveJobResponse(
            success=True,
            message=f"Import job {job_id} removed",
            job_id=job_id,
        )
    except HTTPException:
        raise
    except JobError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except _CHATBOOKS_NONCRITICAL_EXCEPTIONS:
        logger.exception(f"Error removing import job {job_id} for user {user.id}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while removing the import job",
        ) from None
