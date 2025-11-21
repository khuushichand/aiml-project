from __future__ import annotations

from typing import Any, Dict, List, Optional

from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    UploadFile,
    HTTPException,
    status,
)
from loguru import logger
from starlette.responses import JSONResponse

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import (
    UsageEventLogger,
    get_usage_event_logger,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.api.v1.API_Deps.media_processing_deps import (
    get_process_videos_form,
)
from tldw_Server_API.app.api.v1.API_Deps.validations_deps import file_validator_instance
from tldw_Server_API.app.api.v1.schemas.media_request_models import ProcessVideosForm
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Ingestion_Media_Processing.input_sourcing import (
    TempDirManager,
    save_uploaded_files,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.video_batch import (
    run_video_batch,
)

from tldw_Server_API.app.api.v1.endpoints import media as media_mod

router = APIRouter()


@router.post(
    "/process-videos",
    summary="Transcribe / chunk / analyse videos and return the full artefacts (no DB write)",
    tags=["Media Processing (No DB)"],
)
async def process_videos_endpoint(
    background_tasks: BackgroundTasks,
    db: MediaDatabase = Depends(get_media_db_for_user),
    form_data: ProcessVideosForm = Depends(get_process_videos_form),
    files: Optional[List[UploadFile]] = File(
        None,
        description="Video file uploads",
    ),
    current_user: User = Depends(get_request_user),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
):
    """
    Process videos without persisting to the Media DB.

    This endpoint mirrors the legacy `/process-videos` behavior while routing
    through the modular `media` package and using shared helpers for input
    handling and batch orchestration.
    """

    # --- Validation and Logging ---
    logger.info(
        "Request received for /process-videos. Form data validated via dependency."
    )
    try:
        usage_log.log_event(
            "media.process.video",
            tags=["no_db"],
            metadata={"has_urls": bool(form_data.urls), "has_files": bool(files)},
        )
    except Exception:
        # Usage logging is best-effort; do not fail the request.
        pass

    if form_data.urls and form_data.urls == [""]:
        logger.info(
            "Received urls=[''], treating as no URLs provided for video processing."
        )
        form_data.urls = None

    # Reuse shared validation so that error messages and 400 semantics match
    # the legacy implementation (including "No valid media sources supplied").
    media_mod._validate_inputs("video", form_data.urls, files)  # type: ignore[arg-type]

    batch_result: Dict[str, Any] = {
        "processed_count": 0,
        "errors_count": 0,
        "errors": [],
        "results": [],
        "confabulation_results": None,
    }
    file_handling_errors_structured: List[Dict[str, Any]] = []
    # Map temporary path -> original filename
    temp_path_to_original_name: Dict[str, str] = {}

    # --- Use TempDirManager for reliable cleanup ---
    with TempDirManager(cleanup=True, prefix="process_video_") as temp_dir:
        logger.info(f"Using temporary directory for /process-videos: {temp_dir}")
        temp_dir_path = Path(temp_dir)

        # Preserve test-time monkeypatching of `media.file_validator_instance`
        # by resolving the validator via the shim and propagating it back into
        # the legacy module when available.
        validator = getattr(
            media_mod,
            "file_validator_instance",
            file_validator_instance,
        )

        # --- Save Uploads ---
        saved_files_info, file_handling_errors_raw = await save_uploaded_files(
            files or [],
            temp_dir=temp_dir_path,
            validator=validator,
        )

        # Populate the temp path to original name map.
        for sf in saved_files_info:
            if sf.get("path") and sf.get("original_filename"):
                temp_path_to_original_name[str(sf["path"])] = sf["original_filename"]
            else:
                logger.warning(
                    f"Missing path or original_filename in saved_files_info item: {sf}"
                )

        # Process file-handling errors into the response structure.
        if file_handling_errors_raw:
            batch_result["errors_count"] += len(file_handling_errors_raw)
            batch_result["errors"].extend(
                [
                    err.get("error", "Unknown file save error")
                    for err in file_handling_errors_raw
                ]
            )
            for err in file_handling_errors_raw:
                input_ref = (
                    err.get("input_ref")
                    or err.get("original_filename")
                    or err.get("input")
                    or "Unknown Upload"
                )
                file_handling_errors_structured.append(
                    {
                        "status": "Error",
                        "input_ref": input_ref,
                        "processing_source": "N/A - File Save Failed",
                        "media_type": "video",
                        "metadata": {},
                        "content": "",
                        "segments": None,
                        "chunks": None,
                        "analysis": None,
                        "analysis_details": {},
                        "error": err.get(
                            "error", "Failed to save uploaded file."
                        ),
                        "warnings": None,
                        "db_id": None,
                        "db_message": "Processing only endpoint.",
                        "message": None,
                    }
                )
            batch_result["results"].extend(file_handling_errors_structured)

        # --- Prepare Inputs for Processing ---
        url_list = form_data.urls or []
        uploaded_paths = [str(sf["path"]) for sf in saved_files_info if sf.get("path")]
        all_inputs_to_process = url_list + uploaded_paths

        # Check if there's anything left to process.
        if not all_inputs_to_process:
            if file_handling_errors_raw:
                logger.warning(
                    "No valid video sources to process after file saving errors."
                )
                # Return 207 with the structured file errors.
                return JSONResponse(
                    status_code=status.HTTP_207_MULTI_STATUS,
                    content=batch_result,
                )

            logger.warning("No video sources provided.")
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No valid video sources supplied.",
            )

        # --- Call process_videos via helper ---
        batch_result = await run_video_batch(
            all_inputs_to_process=all_inputs_to_process,
            form_data=form_data,
            current_user=current_user,
            temp_dir=str(temp_dir_path),
            temp_path_to_original_name=temp_path_to_original_name,
            file_handling_errors_structured=file_handling_errors_structured,
        )

    # --- Determine Final Status Code & Return ---
    final_error_count = batch_result.get("errors_count", 0)
    final_success_count = batch_result.get("processed_count", 0)
    total_items = len(batch_result.get("results", []))
    has_warnings = any(
        r.get("status") == "Warning" for r in batch_result.get("results", [])
    )
    # NOTE: `has_warnings` is currently unused but kept for parity/debugging.
    _ = has_warnings

    if total_items == 0:
        # Should not happen if validation passed, but handle defensively.
        final_status_code = status.HTTP_400_BAD_REQUEST
        logger.error("No results generated despite processing attempt.")
    elif final_error_count == 0:
        final_status_code = status.HTTP_200_OK
    elif final_error_count == total_items:
        # All errors, could also be 4xx/5xx depending on cause; keep legacy 207.
        final_status_code = status.HTTP_207_MULTI_STATUS
    else:
        # Mix of success/warnings/errors.
        final_status_code = status.HTTP_207_MULTI_STATUS

    log_level = "INFO" if final_status_code == status.HTTP_200_OK else "WARNING"
    logger.log(
        log_level,
        "/process-videos request finished with status {}. Results count: {}, "
        "Errors: {}",
        final_status_code,
        total_items,
        final_error_count,
    )

    # TEMPORARY DEBUG (kept for parity with legacy implementation).
    try:
        logger.debug("Final batch_result before JSONResponse:")
        logged_result = batch_result.copy()
        if len(logged_result.get("results", [])) > 5:
            logged_result["results"] = logged_result["results"][
                :5
            ] + [{"message": "... remaining results truncated for logging ..."}]
        logger.debug(
            "{}",
            logged_result,
        )

        success_item_debug = next(
            (r for r in batch_result.get("results", []) if r.get("status") == "Success"),
            None,
        )
        if success_item_debug:
            logger.debug(
                "Value of input_ref for success item before return: {}",
                success_item_debug.get("input_ref"),
            )
        else:
            logger.debug("No success item found in final results before return.")
    except Exception as debug_err:  # pragma: no cover - defensive logging
        logger.error(f"Error during debug logging: {debug_err}")

    return JSONResponse(status_code=final_status_code, content=batch_result)


__all__ = ["router"]
