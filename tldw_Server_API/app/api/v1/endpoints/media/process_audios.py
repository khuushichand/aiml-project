from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from loguru import logger
from starlette.responses import JSONResponse

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import (
    UsageEventLogger,
    get_usage_event_logger,
)
from tldw_Server_API.app.api.v1.API_Deps.media_processing_deps import (
    get_process_audios_form,
)
from tldw_Server_API.app.api.v1.API_Deps.validations_deps import file_validator_instance
from tldw_Server_API.app.api.v1.schemas.media_request_models import ProcessAudiosForm
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.testing import is_test_mode
from tldw_Server_API.app.core.Ingestion_Media_Processing.audio_batch import (
    run_audio_batch,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.input_sourcing import (
    TempDirManager,
    save_uploaded_files,
)

from tldw_Server_API.app.api.v1.endpoints import media as media_mod

router = APIRouter()


@router.post(
    "/process-audios",
    summary="Transcribe / chunk / analyse audio and return full artefacts (no DB write)",
    tags=["Media Processing (No DB)"],
)
async def process_audios_endpoint(
    background_tasks: BackgroundTasks,
    db: MediaDatabase = Depends(get_media_db_for_user),
    form_data: ProcessAudiosForm = Depends(get_process_audios_form),
    files: Optional[List[UploadFile]] = File(
        None,
        description="Audio file uploads",
    ),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
):
    """
    Process audio inputs (URLs and uploads) without persisting to the Media DB.

    This endpoint mirrors the legacy `/process-audios` behavior while routing
    through the modular `media` package and using shared helpers for input
    handling and batch orchestration.
    """

    logger.info(
        "Request received for /process-audios. Form data validated via dependency."
    )
    try:
        usage_log.log_event(
            "media.process.audio",
            tags=["no_db"],
            metadata={"has_urls": bool(form_data.urls), "has_files": bool(files)},
        )
    except Exception:
        # Usage logging is best-effort; do not fail the request.
        pass

    # Normalize the "urls=['']" sentinel used by some clients.
    if form_data.urls and form_data.urls == [""]:
        logger.info(
            "Received urls=[''], treating as no URLs provided for audio processing."
        )
        form_data.urls = None

    # Reuse shared validation so that error messages and 400 semantics match
    # the legacy implementation (including "No valid media sources supplied").
    try:
        media_mod._validate_inputs("audio", form_data.urls, files)  # type: ignore[arg-type]
    except HTTPException as exc:
        logger.warning("Input validation failed for /process-audios: {}", exc.detail)
        raise

    # Base batch structure used when we need to return an empty 207.
    empty_batch: Dict[str, Any] = {
        "processed_count": 0,
        "errors_count": 0,
        "errors": [],
        "results": [],
    }

    # Map temporary path -> original filename for uploads.
    temp_path_to_original_name: Dict[str, str] = {}

    with TempDirManager(cleanup=True, prefix="process_audio_") as temp_dir:
        temp_dir_path = Path(temp_dir)
        logger.info(
            "Using temporary directory for /process-audios: {}", temp_dir_path.as_posix()
        )

        # Preserve test-time monkeypatching of `media.file_validator_instance`
        # by resolving the validator via the shim and propagating it back into
        # the legacy module when available.
        validator = getattr(
            media_mod,
            "file_validator_instance",
            file_validator_instance,
        )

        # Allowed audio file extensions (mirrors legacy implementation).
        allowed_audio_extensions = [
            ".mp3",
            ".aac",
            ".flac",
            ".wav",
            ".ogg",
            ".m4a",
        ]

        saved_files, file_errors_raw = await save_uploaded_files(
            files or [],
            temp_dir=temp_dir_path,
            validator=validator,
            allowed_extensions=allowed_audio_extensions,
        )

        # Build combined input list: URLs + uploaded temp paths.
        url_list = form_data.urls or []
        uploaded_paths = [str(sf["path"]) for sf in saved_files if sf.get("path")]
        all_inputs = url_list + uploaded_paths

        # If there are no inputs after attempting to save uploads, we may still
        # need to return a 207 based on how uploads were rejected.
        if not all_inputs:
            detail = "No valid audio sources supplied (or all uploads failed)."
            logger.warning("Request processing stopped: {}", detail)

            if file_errors_raw:
                # Determine if any error is a security block. For those cases
                # we surface structured error entries; otherwise we return an
                # empty batch with 207 to indicate the request was handled.
                security_block = any(
                    isinstance(err, dict)
                    and isinstance(err.get("error"), str)
                    and "security reasons" in err.get("error")
                    for err in file_errors_raw
                )

                # Use the batch helper to normalize file errors into the
                # standard batch shape for security-blocked uploads.
                batch_result = await run_audio_batch(
                    all_inputs=[],
                    form_data=form_data,
                    temp_dir=str(temp_dir_path),
                    temp_path_to_original_name=temp_path_to_original_name,
                    saved_files=saved_files,
                    file_errors_raw=file_errors_raw,
                )

                if security_block:
                    return JSONResponse(
                        status_code=status.HTTP_207_MULTI_STATUS,
                        content=batch_result,
                    )

                return JSONResponse(
                    status_code=status.HTTP_207_MULTI_STATUS,
                    content=empty_batch,
                )

            # Otherwise, no inputs at all -> 400.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail,
            )

        # Normal path: we have at least one URL or uploaded file to process.
        batch_result = await run_audio_batch(
            all_inputs=all_inputs,
            form_data=form_data,
            temp_dir=str(temp_dir_path),
            temp_path_to_original_name=temp_path_to_original_name,
            saved_files=saved_files,
            file_errors_raw=file_errors_raw,
        )

    # Determine final HTTP status code based on the batch outcome.
    final_processed_count = batch_result.get("processed_count", 0)
    final_error_count = batch_result.get("errors_count", 0)
    total_items = len(batch_result.get("results", []))

    if total_items == 0:
        final_status_code = status.HTTP_400_BAD_REQUEST
        logger.error(
            "No results generated for /process-audios despite processing attempt."
        )
    elif final_error_count == 0 and final_processed_count > 0:
        final_status_code = status.HTTP_200_OK
        logger.info(
            "/process-audios request finished with status {}. Results: {}, Errors: {}",
            final_status_code,
            total_items,
            final_error_count,
        )
    else:
        # Mixed or all-error batches return 207.
        final_status_code = status.HTTP_207_MULTI_STATUS
        logger.warning(
            "/process-audios request finished with status {}. Results: {}, Errors: {}",
            final_status_code,
            total_items,
            final_error_count,
        )

        # In TEST_MODE, emit a more explicit debug log when the CDN-hosted
        # audio URL used in tests fails due to egress/DNS issues so that
        # environment-induced skips can be distinguished from real regressions.
        if is_test_mode():
            try:
                errors_joined = " | ".join(
                    str(e) for e in batch_result.get("errors", []) if e
                )
                if (
                    "Download failed" in errors_joined
                    or "Host could not be resolved" in errors_joined
                ):
                    logger.debug(
                        "TEST_MODE: /process-audios returned 207 due to audio "
                        "download/egress error: {}",
                        errors_joined,
                    )
            except Exception:
                # Logging must never affect endpoint behavior.
                pass

    return JSONResponse(status_code=final_status_code, content=batch_result)


__all__ = ["router"]
