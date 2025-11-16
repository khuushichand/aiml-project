from __future__ import annotations

from typing import Any, Dict, List, Optional

import asyncio
from pathlib import Path

import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    UploadFile,
    status,
)
from loguru import logger
from starlette.responses import JSONResponse

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Ingestion_Media_Processing.Upload_Sink import FileValidator
from tldw_Server_API.app.core.Ingestion_Media_Processing.input_sourcing import (
    TempDirManager,
    save_uploaded_files,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.pipeline import (
    ProcessItem,
    run_batch_processor,
)

from tldw_Server_API.app.api.v1.endpoints import _legacy_media as legacy_media  # type: ignore

router = APIRouter()


ALLOWED_PDF_EXTENSIONS = [".pdf"]


@router.post(
    "/process-pdfs",
    summary="Extract, chunk, analyse PDFs (NO DB Persistence)",
    tags=["Media Processing (No DB)"],
)
async def process_pdfs_endpoint(
    background_tasks: BackgroundTasks,  # Parity with legacy endpoint signature
    db: MediaDatabase = Depends(get_media_db_for_user),
    form_data: legacy_media.ProcessPDFsForm = Depends(legacy_media.get_process_pdfs_form),
    files: Optional[List[UploadFile]] = File(None, description="PDF uploads"),
    vlm_enable: bool = Form(False, description="Enable VLM detection (separate from OCR)"),
    vlm_backend: Optional[str] = Form(
        None,
        description="VLM backend (e.g., 'hf_table_transformer')",
    ),
    vlm_detect_tables_only: bool = Form(
        True,
        description="Only keep 'table' detections",
    ),
    vlm_max_pages: Optional[int] = Form(
        None,
        description="Max pages to scan with VLM",
    ),
    usage_log: legacy_media.UsageEventLogger = Depends(
        legacy_media.get_usage_event_logger
    ),
):
    """
    Process PDFs without persisting to the Media DB.

    This endpoint mirrors the legacy `/process-pdfs` behavior while routing
    through the modular `media` package and using the shared
    `input_sourcing` and `pipeline` helpers for input handling and batch
    orchestration.
    """

    logger.info("Request received for /process-pdfs (no persistence).")
    try:
        usage_log.log_event(
            "media.process.pdf",
            tags=["no_db"],
            metadata={"has_urls": bool(form_data.urls), "has_files": bool(files)},
        )
    except Exception:
        # Usage logging is best-effort; do not fail the request.
        pass

    # Reuse shared validation so that error messages and 400 semantics match
    # the legacy implementation (including "No valid media sources supplied").
    legacy_media._validate_inputs("pdf", form_data.urls, files)  # type: ignore[arg-type]

    batch: Dict[str, Any] = {"results": [], "errors": []}
    items: List[ProcessItem] = []

    with TempDirManager(prefix="process_pdfs_") as temp_dir:
        temp_dir_path = Path(temp_dir)

        # Preserve test-time monkeypatching of `media.file_validator_instance`
        # by resolving the validator via the shim and propagating it back into
        # the legacy module.
        validator: FileValidator
        try:
            from tldw_Server_API.app.api.v1.endpoints import media as media_mod

            validator = getattr(
                media_mod,
                "file_validator_instance",
                legacy_media.file_validator_instance,
            )
            legacy_media.file_validator_instance = validator  # type: ignore[assignment]
        except Exception:  # pragma: no cover - defensive fallback
            validator = legacy_media.file_validator_instance

        # ---- Handle uploads via shared input_sourcing helper ----
        if files:
            saved_files, upload_errors = await save_uploaded_files(
                files,
                temp_dir=temp_dir_path,
                validator=validator,
                allowed_extensions=ALLOWED_PDF_EXTENSIONS,
            )

            for err_info in upload_errors:
                original_filename = (
                    err_info.get("original_filename") or err_info.get("input") or "Unknown Upload"
                )
                error_detail = str(err_info.get("error") or "Upload error")
                normalized_err = legacy_media.normalise_pdf_result(  # type: ignore[attr-defined]
                    {
                        "status": "Error",
                        "error": f"Upload error: {error_detail}",
                        "processing_source": original_filename,
                    },
                    original_ref=original_filename,
                )
                batch["results"].append(normalized_err)
                batch["errors"].append(f"{original_filename}: {error_detail}")

            for info in saved_files:
                local_path = Path(info["path"])
                input_ref = info["original_filename"]
                items.append(
                    ProcessItem(
                        input_ref=input_ref,
                        local_path=local_path,
                        media_type="pdf",
                        metadata={"source": "upload"},
                    )
                )

        # ---- Handle URL inputs via shared downloader ----
        if form_data.urls:
            async with httpx.AsyncClient(timeout=120) as client:
                download_tasks = [
                    legacy_media._download_url_async(  # type: ignore[attr-defined]
                        client=client,
                        url=url,
                        target_dir=temp_dir_path,
                        allowed_extensions={".pdf"},
                        check_extension=True,
                    )
                    for url in form_data.urls
                ]
                download_results = await asyncio.gather(
                    *download_tasks,
                    return_exceptions=True,
                )

            for url, result in zip(form_data.urls, download_results):
                if isinstance(result, Path):
                    items.append(
                        ProcessItem(
                            input_ref=url,
                            local_path=result,
                            media_type="pdf",
                            metadata={"source": "url"},
                        )
                    )
                else:
                    error_detail = f"Download/preparation failed: {result}"
                    normalized_err = legacy_media.normalise_pdf_result(  # type: ignore[attr-defined]
                        {
                            "status": "Error",
                            "error": error_detail,
                            "processing_source": url,
                        },
                        original_ref=url,
                    )
                    batch["results"].append(normalized_err)
                    batch["errors"].append(error_detail)

        # If we ended up with no valid inputs, mirror the legacy behavior:
        # - 207 when we have result entries (all errors)
        # - 400 when no inputs at all (handled by _validate_inputs above)
        if not items:
            async def _noop_processor(_: List[ProcessItem]) -> List[Dict[str, Any]]:
                return []

            batch = await run_batch_processor(
                items=[],
                processor=_noop_processor,
                base_batch=batch,
            )
            status_code = (
                status.HTTP_207_MULTI_STATUS
                if batch.get("results")
                else status.HTTP_400_BAD_REQUEST
            )
            return JSONResponse(status_code=status_code, content=batch)

        # Chunking options match the legacy endpoint semantics.
        chunk_opts = {
            "method": form_data.chunk_method or "sentences",
            "max_size": form_data.chunk_size,
            "overlap": form_data.chunk_overlap,
        }

        async def _pdf_batch_processor(process_items: List[ProcessItem]) -> List[Dict[str, Any]]:
            results: List[Dict[str, Any]] = []
            for item in process_items:
                original_ref = item.input_ref

                try:
                    file_bytes = item.local_path.read_bytes()
                except Exception as read_err:
                    logger.error(
                        "Failed to read prepared PDF file %s from %s: %s",
                        original_ref,
                        item.local_path,
                        read_err,
                    )
                    error_detail = f"Failed to read prepared file: {read_err}"
                    normalized_err = legacy_media.normalise_pdf_result(  # type: ignore[attr-defined]
                        {
                            "status": "Error",
                            "error": error_detail,
                            "processing_source": str(item.local_path),
                        },
                        original_ref=original_ref,
                    )
                    results.append(normalized_err)
                    continue

                try:
                    raw = await legacy_media.pdf_lib.process_pdf_task(  # type: ignore[attr-defined]
                        file_bytes=file_bytes,
                        filename=original_ref,
                        parser=str(form_data.pdf_parsing_engine or "pymupdf4llm"),
                        title_override=form_data.title,
                        author_override=form_data.author,
                        keywords=form_data.keywords,
                        perform_chunking=form_data.perform_chunking or None,
                        chunk_method=chunk_opts["method"],
                        max_chunk_size=chunk_opts["max_size"],
                        chunk_overlap=chunk_opts["overlap"],
                        perform_analysis=form_data.perform_analysis,
                        api_name=form_data.api_name,
                        # api_key is resolved from server-side config only
                        custom_prompt=form_data.custom_prompt,
                        system_prompt=form_data.system_prompt,
                        summarize_recursively=form_data.summarize_recursively,
                        enable_vlm=vlm_enable,
                        vlm_backend=vlm_backend,
                        vlm_detect_tables_only=vlm_detect_tables_only,
                        vlm_max_pages=vlm_max_pages,
                    )
                    if isinstance(raw, dict):
                        normalized_res = legacy_media.normalise_pdf_result(  # type: ignore[attr-defined]
                            raw,
                            original_ref=original_ref,
                        )
                    else:
                        normalized_res = legacy_media.normalise_pdf_result(  # type: ignore[attr-defined]
                            {
                                "status": "Error",
                                "error": f"Unexpected return type: {type(raw).__name__}",
                                "processing_source": str(item.local_path),
                            },
                            original_ref=original_ref,
                        )
                    results.append(normalized_res)
                except Exception as exc:
                    logger.error(
                        "PDF processing failed for %s: %s",
                        original_ref,
                        exc,
                        exc_info=True,
                    )
                    error_detail = f"PDF processing failed: {exc}"
                    normalized_err = legacy_media.normalise_pdf_result(  # type: ignore[attr-defined]
                        {
                            "status": "Error",
                            "error": error_detail,
                            "processing_source": str(item.local_path),
                        },
                        original_ref=original_ref,
                    )
                    results.append(normalized_err)

            return results

        batch = await run_batch_processor(
            items=items,
            processor=_pdf_batch_processor,
            base_batch=batch,
        )

    # Final HTTP status logic matches the legacy endpoint.
    processed_count = int(batch.get("processed_count") or 0)
    errors_count = int(batch.get("errors_count") or 0)
    if errors_count == 0 and processed_count > 0:
        final_status_code = status.HTTP_200_OK
    elif batch.get("results"):
        final_status_code = status.HTTP_207_MULTI_STATUS
    else:
        final_status_code = status.HTTP_400_BAD_REQUEST

    log_level = "INFO" if final_status_code == status.HTTP_200_OK else "WARNING"
    logger.log(
        log_level,
        "/process-pdfs request finished with status {}. Results: {}, Processed: {}, Errors: {}",
        final_status_code,
        len(batch.get("results", [])),
        processed_count,
        errors_count,
    )

    return JSONResponse(status_code=final_status_code, content=batch)


__all__ = ["router"]

