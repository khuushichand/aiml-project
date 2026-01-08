from __future__ import annotations

from typing import Any, Dict, List, Optional

import asyncio
import functools
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
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

from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import (
    UsageEventLogger,
    get_usage_event_logger,
)
from tldw_Server_API.app.api.v1.API_Deps.media_processing_deps import (
    get_process_ebooks_form,
)
from tldw_Server_API.app.api.v1.schemas.media_request_models import ProcessEbooksForm
from tldw_Server_API.app.api.v1.endpoints import media as media_mod
from tldw_Server_API.app.core.Ingestion_Media_Processing.chunking_options import (
    prepare_chunking_options_dict,
    apply_chunking_template_if_any,
)

router = APIRouter()


ALLOWED_EBOOK_EXTENSIONS = [".epub"]


def _process_single_ebook(
    ebook_path: Path,
    original_ref: str,
    title_override: Optional[str],
    author_override: Optional[str],
    keywords: Optional[List[str]],
    perform_chunking: bool,
    chunk_options: Optional[Dict[str, Any]],
    perform_analysis: bool,
    summarize_recursively: bool,
    api_name: Optional[str],
    custom_prompt: Optional[str],
    system_prompt: Optional[str],
    extraction_method: str,
    base_dir: Optional[Path],
) -> Dict[str, Any]:
    """Synchronous worker for EPUB processing (mirrors legacy helper)."""
    try:
        result_dict = media_mod.books.process_epub(
            file_path=str(ebook_path),
            title_override=title_override,
            author_override=author_override,
            keywords=keywords,
            perform_chunking=perform_chunking,
            chunk_options=chunk_options,
            perform_analysis=perform_analysis,
            api_name=api_name,
            api_key=None,
            custom_prompt=custom_prompt,
            system_prompt=system_prompt,
            summarize_recursively=summarize_recursively,
            extraction_method=extraction_method,
            base_dir=base_dir,
        )
        result_dict["input_ref"] = original_ref
        # Ensure overrides and derived fields are present even if the library
        # omitted them (legacy parity expectations in tests).
        result_dict.setdefault("metadata", {})
        if title_override:
            result_dict["metadata"]["title"] = title_override
        if author_override:
            result_dict["metadata"]["author"] = author_override
        result_dict["keywords"] = keywords or result_dict.get("keywords") or []
        result_dict.setdefault("analysis", None)
        result_dict.setdefault("analysis_details", {})
        return result_dict
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.error(
            "_process_single_ebook error for %s (%s): %s",
            original_ref,
            ebook_path,
            exc,
            exc_info=True,
        )
        return {
            "status": "Error",
            "input_ref": original_ref,
            "processing_source": str(ebook_path),
            "media_type": "ebook",
            "error": f"Worker processing failed: {exc}",
            "content": None,
            "metadata": None,
            "chunks": None,
            "analysis": None,
            "keywords": keywords or [],
            "warnings": None,
            "analysis_details": {},
        }


@router.post(
    "/process-ebooks",
    summary="Extract, chunk, analyse EPUBs (NO DB Persistence)",
    tags=["Media Processing (No DB)"],
)
async def process_ebooks_endpoint(
    db: MediaDatabase = Depends(get_media_db_for_user),
    form_data: ProcessEbooksForm = Depends(get_process_ebooks_form),
    files: Optional[List[UploadFile]] = File(
        None, description="EPUB file uploads (.epub)"
    ),
    usage_log: UsageEventLogger = Depends(get_usage_event_logger),
):
    """
    Process EPUBs without persisting to the Media DB.

    This endpoint mirrors the legacy `/process-ebooks` behavior while routing
    through the modular `media` package and using the shared input_sourcing
    and pipeline helpers for input handling and batch orchestration.
    """

    logger.info("Request received for /process-ebooks (no persistence).")
    try:
        usage_log.log_event(
            "media.process.ebook",
            tags=["no_db"],
            metadata={"has_urls": bool(form_data.urls), "has_files": bool(files)},
        )
    except Exception:
        # Usage logging is best-effort; do not fail the request.
        pass

    # Legacy endpoint treats urls=[""] as "no URLs".
    if form_data.urls and form_data.urls == [""]:
        logger.info(
            "Received urls=[''], treating as no URLs provided for ebook processing."
        )
        form_data.urls = None

    # Reuse shared validation so that error messages and 400 semantics match
    # the legacy implementation (including the "At least one 'url'..." detail).
    media_mod._validate_inputs("ebook", form_data.urls, files)  # type: ignore[arg-type]

    batch: Dict[str, Any] = {"results": [], "errors": []}
    items: List[ProcessItem] = []
    saved_files_info: List[Dict[str, Any]] = []
    chunk_options_dict: Optional[Dict[str, Any]] = None

    with TempDirManager(prefix="process_ebooks_") as temp_dir:
        temp_dir_path = Path(temp_dir)

        # Preserve test-time monkeypatching of `media.file_validator_instance`
        # by resolving the validator via the shim and propagating it back into
        # the legacy module.
        validator: FileValidator = getattr(
            media_mod,
            "file_validator_instance",
            FileValidator(),
        )

        # ---- Handle uploads via shared input_sourcing helper ----
        if files:
            saved_files, upload_errors = await save_uploaded_files(
                files,
                temp_dir=temp_dir_path,
                validator=validator,
                allowed_extensions=ALLOWED_EBOOK_EXTENSIONS,
            )
            saved_files_info = list(saved_files)

            for err_info in upload_errors:
                original_filename = (
                    err_info.get("original_filename")
                    or err_info.get("input")
                    or "Unknown Upload"
                )
                error_detail = str(err_info.get("error") or "Upload error")
                batch["results"].append(
                    {
                        "status": "Error",
                        "input_ref": original_filename,
                        "processing_source": None,
                        "media_type": "ebook",
                        "error": f"Upload error: {error_detail}",
                        "metadata": {},
                        "content": None,
                        "chunks": None,
                        "analysis": None,
                        "keywords": form_data.keywords,
                        "warnings": None,
                        "analysis_details": {},
                        "db_id": None,
                        "db_message": "Processing only endpoint.",
                    }
                )
                batch["errors"].append(f"{original_filename}: {error_detail}")

            for info in saved_files:
                local_path = Path(info["path"])
                input_ref = info["original_filename"]
                items.append(
                    ProcessItem(
                        input_ref=input_ref,
                        local_path=local_path,
                        media_type="ebook",
                        metadata={"source": "upload"},
                    )
                )

        # ---- Handle URL inputs via shared downloader ----
        if form_data.urls:
            logger.info(
                "Attempting to download %d EPUB URL(s) asynchronously...",
                len(form_data.urls),
            )
            download_url_async = getattr(media_mod, "_download_url_async")
            download_tasks = [
                download_url_async(
                    client=None,
                    url=url,
                    target_dir=temp_dir_path,
                    allowed_extensions={".epub"},
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
                            media_type="ebook",
                            metadata={"source": "url"},
                        )
                    )
                else:
                    error_detail = f"Download/preparation failed: {result}"
                    batch["results"].append(
                        {
                            "status": "Error",
                            "input_ref": url,
                            "processing_source": None,
                            "media_type": "ebook",
                            "error": error_detail,
                            "metadata": {},
                            "content": None,
                            "chunks": None,
                            "analysis": None,
                            "keywords": form_data.keywords,
                            "warnings": None,
                            "analysis_details": {},
                            "db_id": None,
                            "db_message": "Processing only endpoint.",
                        }
                    )
                    batch["errors"].append(f"{url}: {error_detail}")

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

        # Prepare chunking options (with optional templates/hierarchical rules).
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

        async def _ebook_batch_processor(
            process_items: List[ProcessItem],
        ) -> List[Dict[str, Any]]:
            results: List[Dict[str, Any]] = []
            loop = asyncio.get_running_loop()

            for item in process_items:
                original_ref = item.input_ref
                ebook_path = item.local_path

                try:
                    partial_func = functools.partial(
                        _process_single_ebook,
                        ebook_path=ebook_path,
                        original_ref=original_ref,
                        title_override=form_data.title,
                        author_override=form_data.author,
                        keywords=form_data.keywords,
                        perform_chunking=form_data.perform_chunking,
                        chunk_options=chunk_options_dict,
                        perform_analysis=form_data.perform_analysis,
                        summarize_recursively=form_data.summarize_recursively,
                        api_name=form_data.api_name,
                        custom_prompt=form_data.custom_prompt,
                        system_prompt=form_data.system_prompt,
                        extraction_method=form_data.extraction_method,
                        base_dir=temp_dir,
                    )
                    res = await loop.run_in_executor(None, partial_func)
                except Exception as exc:  # pragma: no cover - defensive fallback
                    logger.error(
                        "Task execution failed for %s: %s",
                        original_ref,
                        exc,
                        exc_info=True,
                    )
                    error_detail = (
                        f"Task execution failed: {type(exc).__name__}: {exc}"
                    )
                    res = {
                        "status": "Error",
                        "input_ref": original_ref,
                        "processing_source": str(ebook_path),
                        "media_type": "ebook",
                        "error": error_detail,
                        "content": None,
                        "metadata": {},
                        "chunks": None,
                        "analysis": None,
                        "keywords": form_data.keywords or [],
                        "warnings": None,
                        "analysis_details": {},
                    }

                # Ensure mandatory fields and DB fields match the legacy endpoint.
                res["db_id"] = None
                res["db_message"] = "Processing only endpoint."
                res.setdefault("status", "Error")
                res.setdefault("input_ref", original_ref or "Unknown")
                res.setdefault("media_type", "ebook")
                res.setdefault("error", None)
                res.setdefault("warnings", None)
                res.setdefault("metadata", {})
                res.setdefault("content", None)
                res.setdefault("chunks", None)
                res.setdefault("analysis", None)
                res.setdefault("keywords", [])
                res.setdefault("analysis_details", {})

                status_value = str(res.get("status", "")).lower()
                if status_value == "warning":
                    warnings_list = res.get("warnings") or []
                    for warn in warnings_list:
                        msg = f"{res.get('input_ref', 'Unknown')}: [Warning] {warn}"
                        batch["errors"].append(msg)
                elif status_value == "error":
                    error_msg = (
                        f"{res.get('input_ref', 'Unknown')}: "
                        f"{res.get('error', 'Unknown processing error')}"
                    )
                    if error_msg not in batch["errors"]:
                        batch["errors"].append(error_msg)

                results.append(res)

            return results

        batch = await run_batch_processor(
            items=items,
            processor=_ebook_batch_processor,
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
        "/process-ebooks request finished with status {}. Results: {}, "
        "Processed: {}, Errors: {}",
        final_status_code,
        len(batch.get("results", [])),
        processed_count,
        errors_count,
    )

    # Optional template/hierarchical re-chunking of results (best-effort).
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
                        max_size=chunk_options_dict.get("max_size") or 1000,
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
    except Exception as rechunk_err:
        logger.debug("Ebook post-processing re-chunking skipped/failed: {}", rechunk_err)

    return JSONResponse(status_code=final_status_code, content=batch)


__all__ = ["router"]
