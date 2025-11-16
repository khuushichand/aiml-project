from __future__ import annotations

from typing import Any, Dict, List, Optional

import asyncio
import functools
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Depends, status
from loguru import logger
from starlette.responses import JSONResponse

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


@router.post(
    "/process-emails",
    summary="Extract, chunk, analyse Emails (NO DB Persistence)",
    tags=["Media Processing (No DB)"],
)
async def process_emails_endpoint(
    form_data: legacy_media.ProcessEmailsForm = Depends(
        legacy_media.get_process_emails_form
    ),
    files: Optional[List[UploadFile]] = File(None),
):
    """
    Modularized wrapper for the legacy /process-emails endpoint.

    Uses TempDirManager, save_uploaded_files, and run_batch_processor for input
    handling and batch orchestration while preserving the legacy response shape
    and status-code semantics.
    """

    if not files:
        # Preserve legacy 400 behavior when no files are provided.
        raise legacy_media.HTTPException(  # type: ignore[attr-defined]
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one EML file must be uploaded.",
        )

    logger.info("Request received for /process-emails (no persistence).")

    batch: Dict[str, Any] = {
        "results": [],
        "errors": [],
    }
    items: List[ProcessItem] = []

    # Resolve validator via the media shim so tests that monkeypatch
    # media.file_validator_instance continue to work.
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

    # Determine allowed extensions based on form toggles.
    allowed_exts: List[str] = [".eml"]
    if form_data.accept_archives:
        allowed_exts.append(".zip")
    if getattr(form_data, "accept_mbox", False):
        allowed_exts.append(".mbox")
    if getattr(form_data, "accept_pst", False):
        allowed_exts.extend([".pst", ".ost"])

    with TempDirManager(prefix="email_process_", cleanup=True) as temp_dir:
        temp_dir_path = Path(temp_dir)

        # Save uploaded files via shared helper.
        saved_files_info, file_errors = await save_uploaded_files(
            files or [],
            temp_dir=temp_dir_path,
            validator=validator,
            allowed_extensions=allowed_exts,
        )

        for err in file_errors:
            batch["results"].append(
                {
                    "status": "Error",
                    "input_ref": err.get("input_ref"),
                    "processing_source": None,
                    "media_type": "email",
                    "error": err.get("error", "File save failed"),
                    "metadata": {},
                    "content": None,
                    "chunks": None,
                    "analysis": None,
                    "keywords": None,
                    "warnings": None,
                    "analysis_details": {},
                    "db_id": None,
                    "db_message": "Processing only endpoint.",
                }
            )
            if err.get("error"):
                batch["errors"].append(err.get("error"))

        for pf in saved_files_info:
            path = Path(pf["path"])
            items.append(
                ProcessItem(
                    input_ref=pf.get("original_filename") or path.name,
                    local_path=path,
                    media_type="email",
                    metadata={},
                )
            )

        async def _email_batch_processor(
            process_items: List[ProcessItem],
        ) -> List[Dict[str, Any]]:
            results: List[Dict[str, Any]] = []
            loop = asyncio.get_running_loop()

            for item in process_items:
                pf = {
                    "path": str(item.local_path),
                    "original_filename": item.input_ref,
                }
                try:
                    path = Path(pf["path"]).resolve()
                    # Read bytes
                    async with legacy_media.aiofiles.open(  # type: ignore[attr-defined]
                        path, "rb"
                    ) as f:
                        file_bytes = await f.read()

                    chunk_opts = {
                        "method": (
                            form_data.chunk_method
                            if form_data.chunk_method
                            else "sentences"
                        ),
                        "max_size": form_data.chunk_size,
                        "overlap": form_data.chunk_overlap,
                    }

                    name_lower = (pf.get("original_filename") or path.name).lower()

                    if name_lower.endswith(".zip") and form_data.accept_archives:
                        arch_name = pf.get("original_filename") or path.name
                        processor = functools.partial(
                            legacy_media.email_lib.process_eml_archive_bytes,  # type: ignore[attr-defined]
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
                        for r_item in res_list:
                            r_item.setdefault("media_type", "email")
                            r_item.setdefault(
                                "processing_source", f"archive:{str(path)}"
                            )
                            r_item.setdefault(
                                "input_ref",
                                r_item.get("input_ref") or arch_name,
                            )
                            r_item.update(
                                {
                                    "db_id": None,
                                    "db_message": "Processing only endpoint.",
                                }
                            )
                            results.append(r_item)
                    elif name_lower.endswith(".mbox") and getattr(
                        form_data, "accept_mbox", False
                    ):
                        mbox_name = pf.get("original_filename") or path.name
                        processor = functools.partial(
                            legacy_media.email_lib.process_mbox_bytes,  # type: ignore[attr-defined]
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
                            r_item.setdefault(
                                "input_ref",
                                r_item.get("input_ref") or mbox_name,
                            )
                            r_item.update(
                                {
                                    "db_id": None,
                                    "db_message": "Processing only endpoint.",
                                }
                            )
                            results.append(r_item)
                    elif (
                        name_lower.endswith(".pst") or name_lower.endswith(".ost")
                    ) and getattr(form_data, "accept_pst", False):
                        pst_name = pf.get("original_filename") or path.name
                        processor = functools.partial(
                            legacy_media.email_lib.process_pst_bytes,  # type: ignore[attr-defined]
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
                            r_item.setdefault(
                                "input_ref",
                                r_item.get("input_ref") or pst_name,
                            )
                            r_item.update(
                                {
                                    "db_id": None,
                                    "db_message": "Processing only endpoint.",
                                }
                            )
                            results.append(r_item)
                    else:
                        processor = functools.partial(
                            legacy_media.email_lib.process_email_task,  # type: ignore[attr-defined]
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
                        res.setdefault("media_type", "email")
                        res.setdefault("processing_source", str(path))
                        res.setdefault(
                            "input_ref",
                            pf.get("original_filename") or path.name,
                        )
                        res.update(
                            {
                                "db_id": None,
                                "db_message": "Processing only endpoint.",
                            }
                        )
                        results.append(res)
                except Exception as exc:  # pragma: no cover - defensive
                    results.append(
                        {
                            "status": "Error",
                            "input_ref": pf.get("original_filename"),
                            "processing_source": str(pf.get("path")),
                            "media_type": "email",
                            "error": f"Processing failed: {exc}",
                            "metadata": {},
                            "content": None,
                            "chunks": None,
                            "analysis": None,
                            "keywords": None,
                            "warnings": None,
                            "analysis_details": {},
                            "db_id": None,
                            "db_message": "Processing only endpoint.",
                        }
                    )

            return results

        batch = await run_batch_processor(
            items=items,
            processor=_email_batch_processor,
            base_batch=batch,
        )

    processed_count = int(batch.get("processed_count") or 0)
    errors_count = int(batch.get("errors_count") or 0)
    if processed_count > 0 and errors_count == 0:
        final_status = status.HTTP_200_OK
    elif batch.get("results"):
        final_status = status.HTTP_207_MULTI_STATUS
    else:
        final_status = status.HTTP_400_BAD_REQUEST

    return JSONResponse(status_code=final_status, content=batch)


__all__ = ["router"]

