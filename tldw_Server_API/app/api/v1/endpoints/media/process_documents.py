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
from tldw_Server_API.app.api.v1.API_Deps.media_processing_deps import (
    get_process_documents_form,
)
from tldw_Server_API.app.api.v1.API_Deps.validations_deps import file_validator_instance
from tldw_Server_API.app.api.v1.schemas.media_request_models import ProcessDocumentsForm
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Ingestion_Media_Processing.input_sourcing import (
    TempDirManager,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.chunking_options import (
    prepare_chunking_options_dict,
    apply_chunking_template_if_any,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.pipeline import (
    ProcessItem,
    run_batch_processor,
)
import tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files as docs
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import (
    UsageEventLogger,
    get_usage_event_logger,
)
from tldw_Server_API.app.api.v1.endpoints import media as media_mod

router = APIRouter()


ALLOWED_DOC_EXTENSIONS = [
    ".txt",
    ".md",
    ".docx",
    ".rtf",
    ".html",
    ".htm",
    ".xhtml",
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
    form_data: ProcessDocumentsForm = Depends(get_process_documents_form),
    files: Optional[List[UploadFile]] = File(
        None,
        description="Document file uploads (.txt, .md, .docx, .rtf, .html, .xml)",
    ),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
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
    logger.debug(
        "Form data for /process-documents: has_urls={}, has_files={}, "
        "perform_analysis={}, perform_chunking={}",
        bool(form_data.urls),
        bool(files),
        form_data.perform_analysis,
        form_data.perform_chunking,
    )

    # Guardrails: restrict to a known set of document extensions for this endpoint.
    media_mod._validate_inputs("document", form_data.urls, files)  # type: ignore[arg-type]

    # --- Prepare result structure ---
    batch_result: Dict[str, Any] = {
        "errors": [],
        "results": [],
    }
    saved_files_info: List[Dict[str, Any]] = []
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
            save_uploaded_files = getattr(media_mod, "_save_uploaded_files")
            validator = getattr(
                media_mod,
                "file_validator_instance",
                file_validator_instance,
            )

            saved_files, upload_errors = await save_uploaded_files(
                files,
                temp_dir,
                validator=validator,
                allowed_extensions=ALLOWED_DOC_EXTENSIONS,
            )
            saved_files_info = list(saved_files)
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

            # Use media_mod.httpx.AsyncClient so tests can monkeypatch via the media shim.
            async with media_mod.httpx.AsyncClient() as client:
                allowed_ext_set = set(ALLOWED_DOC_EXTENSIONS)

                # Preserve test-time monkeypatching of `_download_url_async`
                # via the media shim.
                download_url_async = getattr(media_mod, "_download_url_async")

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
                        batch_result["errors"].append(f"{original_url}: {err_detail}")

        # --- Check if any files are ready for processing ---
        if not local_paths_to_process:
            logger.warning(
                "No valid document sources found or prepared after handling uploads/URLs."
            )
            # When uploads/URLs were rejected, surface counts like other process-* endpoints.
            if batch_result["results"]:
                batch_result["errors_count"] = sum(
                    1
                    for r in batch_result["results"]
                    if str(r.get("status", "")).lower() == "error"
                )
                batch_result["processed_count"] = 0
                status_code = status.HTTP_207_MULTI_STATUS
            else:
                batch_result["errors_count"] = 0
                batch_result["processed_count"] = 0
                status_code = status.HTTP_400_BAD_REQUEST

            return JSONResponse(status_code=status_code, content=batch_result)

        logger.info(
            "Starting processing for {} document(s).", len(local_paths_to_process)
        )

        # --- Prepare options for the worker ---
        if form_data.perform_chunking:
            chunk_options_dict: Optional[Dict[str, Any]] = prepare_chunking_options_dict(
                form_data
            )
            TemplateClassifier = getattr(media_mod, "TemplateClassifier", None)

            if chunk_options_dict is not None:
                first_url = (form_data.urls or [None])[0]
                first_filename = None
                if saved_files_info:
                    first_filename = saved_files_info[0].get("original_filename")

                chunk_options_dict = apply_chunking_template_if_any(
                    form_data=form_data,
                    db=db,
                    chunking_options_dict=chunk_options_dict,
                    TemplateClassifier=TemplateClassifier,
                    first_url=first_url,
                    first_filename=first_filename,
                )
        else:
            chunk_options_dict = None

        # --- Build ProcessItem list and run batch processor ---
        items: List[ProcessItem] = [
            ProcessItem(
                input_ref=original_ref,
                local_path=doc_path,
                media_type="document",
                metadata={},
            )
            for original_ref, doc_path in local_paths_to_process
        ]

        async def _document_batch_processor(
            process_items: List[ProcessItem],
        ) -> List[Dict[str, Any]]:
            results: List[Dict[str, Any]] = []
            loop = asyncio.get_running_loop()

            tasks: List[asyncio.Future] = []
            for item in process_items:
                partial_func = functools.partial(
                    docs.process_document_content,
                    doc_path=item.local_path,
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
                    base_dir=temp_dir,
                )
                tasks.append(loop.run_in_executor(None, partial_func))

            task_results = await asyncio.gather(*tasks, return_exceptions=True)

            for item, res in zip(process_items, task_results):
                original_ref = item.input_ref

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

                    results.append(res)
                elif isinstance(res, Exception):
                    logger.error(
                        "Task execution failed for {} with exception: {}",
                        original_ref,
                        res,
                        exc_info=res,
                    )
                    error_detail = (
                        f"Task execution failed: {type(res).__name__}: {res}"
                    )
                    results.append(
                        {
                            "status": "Error",
                            "input_ref": original_ref,
                            "error": error_detail,
                            "media_type": "document",
                            "processing_source": str(item.local_path),
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
                else:
                    logger.error(
                        "Received unexpected result type from document worker task for {}: {}",
                        original_ref,
                        type(res),
                    )
                    error_detail = "Invalid result type from document worker."
                    results.append(
                        {
                            "status": "Error",
                            "input_ref": original_ref,
                            "error": error_detail,
                            "media_type": "document",
                            "processing_source": str(item.local_path),
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

            return results

        base_batch: Dict[str, Any] = {
            "results": list(batch_result["results"]),
            "errors": list(batch_result["errors"]),
        }
        batch_result = await run_batch_processor(
            items=items,
            processor=_document_batch_processor,
            base_batch=base_batch,
        )

    # --- Determine final status code ---
    if batch_result.get("errors_count", 0) == 0 and batch_result.get("processed_count", 0) > 0:
        final_status_code = status.HTTP_200_OK
    elif batch_result.get("errors_count", 0) > 0:
        final_status_code = status.HTTP_207_MULTI_STATUS
    elif (
        batch_result.get("processed_count", 0) == 0
        and batch_result.get("errors_count", 0) == 0
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
        batch_result.get("processed_count", 0),
        batch_result.get("errors_count", 0),
    )

    # --- Optional template/hierarchical re-chunking of results ---
    try:
        if form_data.perform_chunking and chunk_options_dict:
            from tldw_Server_API.app.core.Chunking import (  # type: ignore
                improved_chunking_process as _improved_chunking_process,
            )
            from tldw_Server_API.app.core.Chunking.chunker import (  # type: ignore
                Chunker as _Chunker,
            )

            use_hier = bool(
                chunk_options_dict.get("hierarchical")
                or isinstance(chunk_options_dict.get("hierarchical_template"), dict)
            )
            ck = _Chunker() if use_hier else None

            for res in batch_result.get("results", []):
                if not isinstance(res, dict):
                    continue
                status_value = str(res.get("status", "")).lower()
                if status_value not in {"success", "warning"}:
                    continue
                text = res.get("content")
                if not isinstance(text, str) or not text.strip():
                    continue

                if use_hier and ck is not None:
                    chunks = ck.chunk_text_hierarchical_flat(
                        text,
                        method=chunk_options_dict.get("method") or "sentences",
                        max_size=chunk_options_dict.get("max_size") or 500,
                        overlap=chunk_options_dict.get("overlap") or 200,
                        language=chunk_options_dict.get("language"),
                        template=chunk_options_dict.get("hierarchical_template")
                        if isinstance(
                            chunk_options_dict.get("hierarchical_template"), dict
                        )
                        else None,
                    )
                else:
                    chunks = _improved_chunking_process(text, chunk_options_dict)

                res["chunks"] = chunks
    except Exception as exc:
        logger.debug("Re-chunking failed during metadata normalization", exc_info=True)

    return JSONResponse(status_code=final_status_code, content=batch_result)


__all__ = ["router"]
