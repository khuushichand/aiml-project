from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import asyncio
import functools
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, UploadFile, status
from loguru import logger
from starlette.responses import JSONResponse

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.validations_deps import file_validator_instance
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Ingestion_Media_Processing.input_sourcing import (
    TempDirManager,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.chunking_options import (
    prepare_chunking_options_dict,
)
import tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files as docs
from tldw_Server_API.app.api.v1.endpoints import _legacy_media as legacy_media  # type: ignore

router = APIRouter()


ALLOWED_DOC_EXTENSIONS = [
    ".txt",
    ".md",
    ".docx",
    ".rtf",
    ".html",
    ".htm",
    ".xml",
    ".json",
]


@router.post(
    "/process-documents",
    summary="Extract, chunk, analyse Documents (NO DB Persistence)",
    tags=["Media Processing (No DB)"],
)
async def process_documents_endpoint(
    db: MediaDatabase = Depends(get_media_db_for_user),
    form_data: legacy_media.ProcessDocumentsForm = Depends(
        legacy_media.get_process_documents_form
    ),
    files: Optional[List[UploadFile]] = File(
        None,
        description="Document file uploads (.txt, .md, .docx, .rtf, .html, .xml)",
    ),
    usage_log: legacy_media.UsageEventLogger = Depends(
        legacy_media.get_usage_event_logger
    ),
):
    """
    Process Documents (No Persistence).

    This is a modularized version of the original legacy implementation in
    `_legacy_media.process_documents_endpoint`, preserving behavior while
    routing through the `media` package and using the media shim for helpers
    that tests monkeypatch (e.g. `_save_uploaded_files`, `_download_url_async`).
    """

    logger.info("Request received for /process-documents (no persistence).")
    try:
        usage_log.log_event(
            "media.process.document",
            tags=["no_db"],
            metadata={"has_urls": bool(form_data.urls), "has_files": bool(files)},
        )
    except Exception:
        # Usage logging is best-effort; never fail the request.
        pass
    logger.debug("Form data received for /process-documents: {}", form_data.model_dump())

    # Guardrails: restrict to a known set of document extensions for this endpoint.
    legacy_media._validate_inputs("document", form_data.urls, files)  # type: ignore[arg-type]

    # --- Prepare result structure ---
    batch_result: Dict[str, Any] = {
        "processed_count": 0,
        "errors_count": 0,
        "errors": [],
        "results": [],
    }
    # Map to track original ref -> temp path
    source_map: Dict[str, Path] = {}

    loop = asyncio.get_running_loop()
    # Use TempDirManager for reliable cleanup
    with TempDirManager(
        cleanup=(not form_data.keep_original_file),
        prefix="process_doc_",
    ) as temp_dir_path:
        temp_dir = Path(temp_dir_path)
        logger.info("Using temporary directory for /process-documents: {}", temp_dir)

        local_paths_to_process: List[Tuple[str, Path]] = []

        # --- Handle Uploads ---
        if files:
            # Preserve test-time monkeypatching of `media.file_validator_instance`
            # and `_save_uploaded_files` via the `media` shim.
            try:
                from tldw_Server_API.app.api.v1.endpoints import media as media_mod

                save_uploaded_files = getattr(media_mod, "_save_uploaded_files")
                validator = getattr(
                    media_mod,
                    "file_validator_instance",
                    file_validator_instance,
                )
            except Exception:  # pragma: no cover - defensive fallback
                save_uploaded_files = legacy_media._save_uploaded_files  # type: ignore[attr-defined]
                validator = file_validator_instance

            saved_files, upload_errors = await save_uploaded_files(
                files,
                temp_dir,
                validator=validator,
                allowed_extensions=ALLOWED_DOC_EXTENSIONS,
            )
            # Add file saving/validation errors to batch_result
            for err_info in upload_errors:
                original_filename = (
                    err_info.get("input")
                    or err_info.get("original_filename", "Unknown Upload")
                )
                err_detail = f"Upload error: {err_info['error']}"
                batch_result["results"].append(
                    {
                        "status": "Error",
                        "input_ref": original_filename,
                        "error": err_detail,
                        "media_type": "document",
                        "processing_source": None,
                        "metadata": {},
                        "content": None,
                        "chunks": None,
                        "analysis": None,
                        "keywords": form_data.keywords,
                        "warnings": None,
                        "analysis_details": {},
                        "db_id": None,
                        "db_message": "Processing only endpoint.",
                        "segments": None,
                    }
                )
                batch_result["errors_count"] += 1
                batch_result["errors"].append(f"{original_filename}: {err_detail}")

            for info in saved_files:
                original_ref = info["original_filename"]
                local_path = Path(info["path"])
                local_paths_to_process.append((original_ref, local_path))
                source_map[original_ref] = local_path
                logger.debug(
                    "Prepared uploaded file for processing: {} -> {}",
                    original_ref,
                    local_path,
                )

        # --- Handle URLs (asynchronously) ---
        if form_data.urls:
            logger.info(
                "Attempting to download {} document URLs asynchronously...",
                len(form_data.urls),
            )
            download_tasks: List[asyncio.Task[Path]] = []
            url_task_map: Dict[asyncio.Task[Path], str] = {}

            # Use httpx.AsyncClient so tests can monkeypatch it if needed.
            async with httpx.AsyncClient() as client:
                allowed_ext_set = set(ALLOWED_DOC_EXTENSIONS)

                # Preserve test-time monkeypatching of `_download_url_async`
                # via the media shim.
                try:
                    from tldw_Server_API.app.api.v1.endpoints import media as media_mod

                    download_url_async = getattr(media_mod, "_download_url_async")
                except Exception:  # pragma: no cover - defensive fallback
                    download_url_async = legacy_media._download_url_async  # type: ignore[attr-defined]

                download_tasks = [
                    download_url_async(
                        client=client,
                        url=url,
                        target_dir=temp_dir,
                        allowed_extensions=allowed_ext_set,
                        check_extension=True,
                        # Disallow only clearly unsupported/generic types. Allow HTML/XHTML/XML
                        # types here because this endpoint handles .html/.htm/.xml content.
                        disallow_content_types={
                            "application/msword",
                            "application/octet-stream",
                        },
                    )
                    for url in form_data.urls
                ]

                url_task_map = {
                    task: url for task, url in zip(download_tasks, form_data.urls)
                }

                if download_tasks:
                    download_results = await asyncio.gather(
                        *download_tasks,
                        return_exceptions=True,
                    )
                else:
                    download_results: List[Any] = []

            if download_tasks:
                for task, result in zip(download_tasks, download_results):
                    original_url = url_task_map.get(task, "Unknown URL")

                    if isinstance(result, Path):
                        downloaded_path = result
                        local_paths_to_process.append((original_url, downloaded_path))
                        source_map[original_url] = downloaded_path
                        logger.debug(
                            "Prepared downloaded URL for processing: {} -> {}",
                            original_url,
                            downloaded_path,
                        )
                    elif isinstance(result, Exception):
                        error = result
                        logger.error(
                            "Download or preparation failed for URL {}: {}",
                            original_url,
                            error,
                            exc_info=False,
                        )
                        err_detail = f"Download/preparation failed: {str(error)}"
                        batch_result["results"].append(
                            {
                                "status": "Error",
                                "input_ref": original_url,
                                "error": err_detail,
                                "media_type": "document",
                                "processing_source": None,
                                "metadata": {},
                                "content": None,
                                "chunks": None,
                                "analysis": None,
                                "keywords": form_data.keywords,
                                "warnings": None,
                                "analysis_details": {},
                                "db_id": None,
                                "db_message": "Processing only endpoint.",
                                "segments": None,
                            }
                        )
                        batch_result["errors_count"] += 1
                        batch_result["errors"].append(f"{original_url}: {err_detail}")
                    else:
                        logger.error(
                            "Unexpected result type '{}' for URL download task: {}",
                            type(result),
                            original_url,
                        )
                        err_detail = (
                            f"Unexpected download result type: {type(result).__name__}"
                        )
                        batch_result["results"].append(
                            {
                                "status": "Error",
                                "input_ref": original_url,
                                "error": err_detail,
                                "media_type": "document",
                                "processing_source": None,
                                "metadata": {},
                                "content": None,
                                "chunks": None,
                                "analysis": None,
                                "keywords": form_data.keywords,
                                "warnings": None,
                                "analysis_details": {},
                                "db_id": None,
                                "db_message": "Processing only endpoint.",
                                "segments": None,
                            }
                        )
                        batch_result["errors_count"] += 1
                        batch_result["errors"].append(f"{original_url}: {err_detail}")

        # --- Check if any files are ready for processing ---
        if not local_paths_to_process:
            logger.warning(
                "No valid document sources found or prepared after handling uploads/URLs."
            )
            status_code = (
                status.HTTP_207_MULTI_STATUS
                if batch_result["errors_count"] > 0
                else status.HTTP_400_BAD_REQUEST
            )
            return JSONResponse(status_code=status_code, content=batch_result)

        logger.info(
            "Starting processing for {} document(s).", len(local_paths_to_process)
        )

        # --- Prepare options for the worker ---
        if form_data.perform_chunking:
            chunk_options_dict: Optional[Dict[str, Any]] = prepare_chunking_options_dict(
                form_data
            )
        else:
            chunk_options_dict = None

        # --- Create and run processing tasks ---
        processing_tasks: List[asyncio.Future] = []
        for original_ref, doc_path in local_paths_to_process:
            partial_func = functools.partial(
                docs.process_document_content,
                doc_path=doc_path,
                perform_chunking=form_data.perform_chunking,
                chunk_options=chunk_options_dict,
                perform_analysis=form_data.perform_analysis,
                summarize_recursively=form_data.summarize_recursively,
                api_name=form_data.api_name,
                api_key=None,
                custom_prompt=form_data.custom_prompt,
                system_prompt=form_data.system_prompt,
                title_override=form_data.title,
                author_override=form_data.author,
                keywords=form_data.keywords,
            )
            processing_tasks.append(loop.run_in_executor(None, partial_func))

        task_results = await asyncio.gather(*processing_tasks, return_exceptions=True)

    # --- Combine and finalize results (outside temp dir context) ---
    for i, res in enumerate(task_results):
        original_ref = local_paths_to_process[i][0]

        if isinstance(res, dict):
            res["input_ref"] = original_ref
            res["db_id"] = None
            res["db_message"] = "Processing only endpoint."
            res.setdefault("status", "Error")
            res.setdefault("media_type", "document")
            res.setdefault("error", None)
            res.setdefault("warnings", None)
            res.setdefault("metadata", {})
            res.setdefault("content", None)
            res.setdefault("chunks", None)
            res.setdefault("analysis", None)
            res.setdefault("keywords", [])
            res.setdefault("analysis_details", {})
            res.setdefault("segments", None)

            batch_result["results"].append(res)

            if res["status"] in ["Success", "Warning"]:
                batch_result["processed_count"] += 1
                if res["status"] == "Warning" and res.get("warnings"):
                    for warn in res["warnings"]:
                        batch_result["errors"].append(
                            f"{original_ref}: [Warning] {warn}"
                        )
            else:
                batch_result["errors_count"] += 1
                error_msg = (
                    f"{original_ref}: {res.get('error', 'Unknown processing error')}"
                )
                if error_msg not in batch_result["errors"]:
                    batch_result["errors"].append(error_msg)

        elif isinstance(res, Exception):
            logger.error(
                "Task execution failed for {} with exception: {}",
                original_ref,
                res,
                exc_info=res,
            )
            error_detail = (
                f"Task execution failed: {type(res).__name__}: {str(res)}"
            )
            batch_result["results"].append(
                {
                    "status": "Error",
                    "input_ref": original_ref,
                    "error": error_detail,
                    "media_type": "document",
                    "db_id": None,
                    "db_message": "Processing only endpoint.",
                    "processing_source": str(local_paths_to_process[i][1]),
                    "metadata": {},
                    "content": None,
                    "chunks": None,
                    "analysis": None,
                    "keywords": form_data.keywords,
                    "warnings": None,
                    "analysis_details": {},
                    "segments": None,
                }
            )
            batch_result["errors_count"] += 1
            if error_detail not in batch_result["errors"]:
                batch_result["errors"].append(f"{original_ref}: {error_detail}")
        else:
            logger.error(
                "Received unexpected result type from document worker task for {}: {}",
                original_ref,
                type(res),
            )
            error_detail = "Invalid result type from document worker."
            batch_result["results"].append(
                {
                    "status": "Error",
                    "input_ref": original_ref,
                    "error": error_detail,
                    "media_type": "document",
                    "db_id": None,
                    "db_message": "Processing only endpoint.",
                    "processing_source": str(local_paths_to_process[i][1]),
                    "metadata": {},
                    "content": None,
                    "chunks": None,
                    "analysis": None,
                    "keywords": form_data.keywords,
                    "warnings": None,
                    "analysis_details": {},
                    "segments": None,
                }
            )
            batch_result["errors_count"] += 1
            if error_detail not in batch_result["errors"]:
                batch_result["errors"].append(f"{original_ref}: {error_detail}")

    # --- Determine final status code ---
    if batch_result["errors_count"] == 0 and batch_result["processed_count"] > 0:
        final_status_code = status.HTTP_200_OK
    elif batch_result["errors_count"] > 0:
        final_status_code = status.HTTP_207_MULTI_STATUS
    elif (
        batch_result["processed_count"] == 0
        and batch_result["errors_count"] == 0
    ):
        if batch_result["results"]:
            final_status_code = status.HTTP_207_MULTI_STATUS
        else:
            final_status_code = status.HTTP_400_BAD_REQUEST
    else:
        logger.warning(
            "Reached unexpected state for final status code determination "
            "in /process-documents."
        )
        final_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    log_level = "INFO" if final_status_code == status.HTTP_200_OK else "WARNING"
    logger.log(
        log_level,
        "/process-documents request finished with status {}. "
        "Processed: {}, Errors: {}",
        final_status_code,
        batch_result["processed_count"],
        batch_result["errors_count"],
    )

    return JSONResponse(status_code=final_status_code, content=batch_result)


__all__ = ["router"]
