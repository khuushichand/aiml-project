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
from tldw_Server_API.app.api.v1.API_Deps.media_processing_deps import (
    get_process_pdfs_form,
)
from tldw_Server_API.app.api.v1.API_Deps.validations_deps import (
    file_validator_instance,
)
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
from tldw_Server_API.app.core.Ingestion_Media_Processing.result_normalization import (
    normalise_pdf_result,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.chunking_options import (
    prepare_chunking_options_dict,
    apply_chunking_template_if_any,
)

from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import (
    UsageEventLogger,
    get_usage_event_logger,
)
from tldw_Server_API.app.api.v1.endpoints import media as media_mod
from tldw_Server_API.app.api.v1.schemas.media_request_models import ProcessPDFsForm

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
    form_data: ProcessPDFsForm = Depends(get_process_pdfs_form),
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
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
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
    media_mod._validate_inputs("pdf", form_data.urls, files)  # type: ignore[arg-type]

    batch: Dict[str, Any] = {"results": [], "errors": []}
    items: List[ProcessItem] = []
    saved_files_info: List[Dict[str, Any]] = []
    chunk_options_dict: Optional[Dict[str, Any]] = None

    with TempDirManager(prefix="process_pdfs_") as temp_dir:
        temp_dir_path = Path(temp_dir)

        # Preserve test-time monkeypatching of `media.file_validator_instance`
        # by resolving the validator via the shim and propagating it back into
        # the legacy module.
        validator: FileValidator = getattr(
            media_mod,
            "file_validator_instance",
            file_validator_instance,
        )

        # ---- Handle uploads via shared input_sourcing helper ----
        if files:
            saved_files, upload_errors = await save_uploaded_files(
                files,
                temp_dir=temp_dir_path,
                validator=validator,
                allowed_extensions=ALLOWED_PDF_EXTENSIONS,
            )
            saved_files_info = list(saved_files)

            for err_info in upload_errors:
                original_filename = (
                    err_info.get("original_filename") or err_info.get("input") or "Unknown Upload"
                )
                error_detail = str(err_info.get("error") or "Upload error")
                normalized_err = normalise_pdf_result(
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
            async with media_mod.httpx.AsyncClient(timeout=120) as client:
                download_tasks = [
                    media_mod._download_url_async(
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
                    normalized_err = normalise_pdf_result(
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

        # Prepare chunking options (including templates/hierarchical when requested).
        if form_data.perform_chunking:
            chunk_options_dict = prepare_chunking_options_dict(form_data)
            try:
                TemplateClassifier = getattr(media_mod, "TemplateClassifier", None)
            except Exception:
                TemplateClassifier = None

            if chunk_options_dict is not None:
                first_url = (form_data.urls or [None])[0]
                first_filename = None
                try:
                    if saved_files_info:
                        first_filename = saved_files_info[0].get("original_filename")
                except Exception:
                    first_filename = None

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
                    normalized_err = normalise_pdf_result(
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
                    raw = await media_mod.pdf_lib.process_pdf_task(
                        file_bytes=file_bytes,
                        filename=original_ref,
                        parser=str(form_data.pdf_parsing_engine or "pymupdf4llm"),
                        title_override=form_data.title,
                        author_override=form_data.author,
                        keywords=form_data.keywords,
                        perform_chunking=form_data.perform_chunking or None,
                        chunk_method=(
                            (chunk_options_dict or {}).get("method")
                            if form_data.perform_chunking
                            else None
                        ),
                        max_chunk_size=(
                            (chunk_options_dict or {}).get("max_size")
                            if form_data.perform_chunking
                            else None
                        ),
                        chunk_overlap=(
                            (chunk_options_dict or {}).get("overlap")
                            if form_data.perform_chunking
                            else None
                        ),
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
                        normalized_res = normalise_pdf_result(
                            raw,
                            original_ref=original_ref,
                        )
                    else:
                        normalized_res = normalise_pdf_result(
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
                    normalized_err = normalise_pdf_result(
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

    # Optional template/hierarchical re-chunking of results (best-effort).
    try:
        if form_data.perform_chunking and chunk_options_dict:
            logger.info(
                "Re-chunking /process-pdfs results with options: {}",
                chunk_options_dict,
            )
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

            for res in batch.get("results", []):
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
    except Exception:
        # Never fail the endpoint due to re-chunking issues.
        pass

    return JSONResponse(status_code=final_status_code, content=batch)


__all__ = ["router"]
