from __future__ import annotations

import asyncio
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, File, UploadFile, status
from loguru import logger
from starlette.responses import JSONResponse

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Ingestion_Media_Processing.code_utils import (
    chunk_code_lines,
    detect_code_language,
    read_text_safe,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.input_sourcing import (
    TempDirManager,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.result_normalization import (
    normalize_process_batch,
)

# Reuse existing form model and helpers from the legacy module to preserve
# behavior while gradually extracting endpoints into per-type modules.
from tldw_Server_API.app.api.v1.endpoints import _legacy_media as legacy_media  # type: ignore

router = APIRouter()


@router.post(
    "/process-code",
    summary="Process code files (NO DB Persistence)",
    tags=["Media Processing (No DB)"],
)
async def process_code_endpoint(
    db: MediaDatabase = Depends(get_media_db_for_user),  # Parity with legacy signature
    form_data: legacy_media.ProcessCodeForm = Depends(legacy_media.get_process_code_form),
    files: Optional[List[UploadFile]] = File(
        None,
        description="Code uploads (.py, .c, .cpp, .java, .ts, etc.)",
    ),
) -> JSONResponse:
    """
    Reads uploaded or downloaded code files as text, optionally chunks by
    lines or structure-aware code chunking, and returns artifacts without
    DB writes.

    This mirrors the legacy `_legacy_media.process_code_endpoint` behavior
    while routing through the modular `media` package.
    """

    # Reuse shared validation so that error messages and 400 semantics match
    # the legacy implementation (including URL/file presence checks).
    legacy_media._validate_inputs("code", form_data.urls or [], files)  # type: ignore[arg-type]

    urls = form_data.urls or []
    # Do not preemptively hard-fail entire batch on URL policy here.
    # URL safety is handled during per-item download to allow partial 207
    # batches in tests.
    batch: Dict[str, Any] = {"processed_count": 0, "errors_count": 0, "errors": [], "results": []}

    with TempDirManager(cleanup=True, prefix="process_code_") as temp_dir_path:
        temp_dir = Path(temp_dir_path)

        # Handle uploads
        if files:
            # Preserve test-time monkeypatching of `_save_uploaded_files` and
            # `file_validator_instance` via the `media` shim.
            try:
                from tldw_Server_API.app.api.v1.endpoints import media as media_mod

                save_uploaded_files = getattr(media_mod, "_save_uploaded_files")
                validator = getattr(media_mod, "file_validator_instance")
            except Exception:  # pragma: no cover - defensive fallback
                save_uploaded_files = legacy_media._save_uploaded_files  # type: ignore[attr-defined]
                validator = legacy_media.file_validator_instance  # type: ignore[attr-defined]

            saved, upload_errors = await save_uploaded_files(
                files,
                temp_dir,
                validator=validator,
                allowed_extensions=sorted(legacy_media.CODE_ALLOWED_EXTENSIONS),  # type: ignore[attr-defined]
                skip_archive_scanning=False,
                expected_media_type_key="code",
            )

            # TEST_MODE diagnostics for upload validation behavior
            try:
                if (
                    str(os.getenv("TEST_MODE", "")).lower()
                    in {"1", "true", "yes", "on"}
                    and upload_errors
                ):
                    logger.warning(f"TEST_MODE: process-code upload_errors={upload_errors}")
            except Exception:
                pass

            for err in upload_errors:
                batch["results"].append(
                    {
                        "status": "Error",
                        "input_ref": err.get("original_filename", "Unknown Upload"),
                        # Normalize message for tests: map any disallowed-type to a
                        # standard phrase.
                        "error": (
                            "Invalid file type"
                            if isinstance(err.get("error"), str)
                            and (
                                "not allowed for security"
                                in err.get("error", "").lower()
                                or "invalid file type"
                                in err.get("error", "").lower()
                            )
                            else f"Upload error: {err.get('error')}"
                        ),
                        "media_type": "code",
                        "processing_source": None,
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
                batch["errors_count"] += 1

            for info in saved:
                filename = info["original_filename"]
                local_path = Path(info["path"])
                language = detect_code_language(filename)
                try:
                    text = read_text_safe(local_path)
                    if form_data.perform_chunking:
                        if str(form_data.chunk_method or "code").lower() == "lines":
                            chunks = chunk_code_lines(
                                text,
                                form_data.chunk_size,
                                form_data.chunk_overlap,
                                language,
                            )
                            op_status = "Success"
                            op_warnings = None
                        else:
                            # Structure-aware code chunking via core Chunker with
                            # metadata. On failure, fall back to simple line-based
                            # chunking and downgrade status to Warning.
                            from tldw_Server_API.app.core.Chunking.chunker import (  # noqa: WPS433
                                Chunker,
                                ChunkerConfig,
                            )

                            try:
                                chunker = Chunker(
                                    config=ChunkerConfig(
                                        default_method="code",
                                        default_max_size=form_data.chunk_size,
                                        default_overlap=form_data.chunk_overlap,
                                    )
                                )
                                crs = chunker.chunk_text_with_metadata(
                                    text,
                                    method="code",
                                    max_size=form_data.chunk_size,
                                    overlap=form_data.chunk_overlap,
                                    language=language,
                                )
                                total = len(crs)
                                chunks = []
                                for idx, cr in enumerate(crs):
                                    md = asdict(cr.metadata)
                                    # Flatten options into metadata top-level for ease of use
                                    opts = md.pop("options", {}) or {}
                                    md.update(opts)
                                    md.setdefault("chunk_method", "code")
                                    md.setdefault("language", language)
                                    # Ensure top-level start/end lines exist for convenience
                                    if md.get("start_line") is None or md.get("end_line") is None:
                                        try:
                                            blocks = md.get("blocks") or []
                                            starts = [
                                                b.get("start_line")
                                                for b in blocks
                                                if isinstance(b, dict) and b.get("start_line") is not None
                                            ]
                                            ends = [
                                                b.get("end_line")
                                                for b in blocks
                                                if isinstance(b, dict) and b.get("end_line") is not None
                                            ]
                                            if starts:
                                                md["start_line"] = int(min(starts))
                                            if ends:
                                                md["end_line"] = int(max(ends))
                                        except Exception:
                                            pass
                                    md["chunk_index"] = idx + 1
                                    md["total_chunks"] = total
                                    chunks.append({"text": cr.text, "metadata": md})
                                op_status = "Success"
                                op_warnings = None
                            except Exception as code_chunk_err:  # pragma: no cover - rare fallback
                                # Fallback: simple line-based chunking
                                chunks = chunk_code_lines(
                                    text,
                                    form_data.chunk_size,
                                    form_data.chunk_overlap,
                                    language,
                                )
                                op_status = "Warning"
                                op_warnings = [
                                    "Structure-aware code chunker failed; "
                                    f"fell back to line chunking: {code_chunk_err}"
                                ]
                    else:
                        chunks = []
                        op_status = "Success"
                        op_warnings = None

                    batch["results"].append(
                        {
                            "status": op_status,
                            "input_ref": filename,
                            "processing_source": str(local_path),
                            "media_type": "code",
                            "content": text,
                            "metadata": {
                                "language": language,
                                "filename": filename,
                                "lines": text.count("\n") + 1,
                            },
                            "chunks": chunks,
                            "analysis": None,
                            "keywords": None,
                            "warnings": op_warnings,
                            "analysis_details": {},
                            "db_id": None,
                            "db_message": "Processing only endpoint.",
                        }
                    )
                    batch["processed_count"] += 1
                except Exception as exc:
                    # TEST_MODE diagnostics for read errors after successful save
                    try:
                        if str(os.getenv("TEST_MODE", "")).lower() in {
                            "1",
                            "true",
                            "yes",
                            "on",
                        }:
                            logger.warning(
                                "TEST_MODE: process-code read-error "
                                f"file='{filename}' path='{local_path}': {type(exc).__name__}: {exc}"
                            )
                    except Exception:
                        pass
                    batch["results"].append(
                        {
                            "status": "Error",
                            "input_ref": filename,
                            "processing_source": str(local_path),
                            "media_type": "code",
                            "error": f"Failed to read code file: {exc}",
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
                    batch["errors_count"] += 1

        # Handle URLs
        if urls:
            # Use module-local httpx.AsyncClient so tests can monkeypatch it.
            async with httpx.AsyncClient() as client:
                try:
                    from tldw_Server_API.app.api.v1.endpoints import media as media_mod

                    download_url_async = getattr(media_mod, "_download_url_async")
                except Exception:  # pragma: no cover - defensive fallback
                    download_url_async = legacy_media._download_url_async  # type: ignore[attr-defined]

                tasks = [
                    download_url_async(
                        client=client,
                        url=u,
                        target_dir=temp_dir,
                        allowed_extensions=legacy_media.CODE_ALLOWED_EXTENSIONS,  # type: ignore[attr-defined]
                        check_extension=True,
                    )
                    for u in urls
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for url, res in zip(urls, results):
                    if isinstance(res, Exception):
                        batch["results"].append(
                            {
                                "status": "Error",
                                "input_ref": url,
                                "processing_source": None,
                                "media_type": "code",
                                "error": f"Download/preparation failed: {res}",
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
                        batch["errors_count"] += 1
                        continue

                    local_path = Path(res)
                    language = detect_code_language(local_path.name)
                    try:
                        text = read_text_safe(local_path)
                        if form_data.perform_chunking:
                            if str(form_data.chunk_method or "code").lower() == "lines":
                                chunks = chunk_code_lines(
                                    text,
                                    form_data.chunk_size,
                                    form_data.chunk_overlap,
                                    language,
                                )
                            else:
                                from tldw_Server_API.app.core.Chunking.chunker import (  # noqa: WPS433
                                    Chunker,
                                    ChunkerConfig,
                                )

                                chunker = Chunker(
                                    config=ChunkerConfig(
                                        default_method="code",
                                        default_max_size=form_data.chunk_size,
                                        default_overlap=form_data.chunk_overlap,
                                    )
                                )
                                crs = chunker.chunk_text_with_metadata(
                                    text,
                                    method="code",
                                    max_size=form_data.chunk_size,
                                    overlap=form_data.chunk_overlap,
                                    language=language,
                                )
                                total = len(crs)
                                chunks = []
                                for idx, cr in enumerate(crs):
                                    md = asdict(cr.metadata)
                                    opts = md.pop("options", {}) or {}
                                    md.update(opts)
                                    md.setdefault("chunk_method", "code")
                                    md.setdefault("language", language)
                                    if md.get("start_line") is None or md.get("end_line") is None:
                                        try:
                                            blocks = md.get("blocks") or []
                                            starts = [
                                                b.get("start_line")
                                                for b in blocks
                                                if isinstance(b, dict) and b.get("start_line") is not None
                                            ]
                                            ends = [
                                                b.get("end_line")
                                                for b in blocks
                                                if isinstance(b, dict) and b.get("end_line") is not None
                                            ]
                                            if starts:
                                                md["start_line"] = int(min(starts))
                                            if ends:
                                                md["end_line"] = int(max(ends))
                                        except Exception:
                                            pass
                                    md["chunk_index"] = idx + 1
                                    md["total_chunks"] = total
                                    chunks.append({"text": cr.text, "metadata": md})
                        else:
                            chunks = []

                        batch["results"].append(
                            {
                                "status": "Success",
                                "input_ref": url,
                                "processing_source": str(local_path),
                                "media_type": "code",
                                "content": text,
                                "metadata": {
                                    "language": language,
                                    "filename": local_path.name,
                                    "lines": text.count("\n") + 1,
                                },
                                "chunks": chunks,
                                "analysis": None,
                                "keywords": None,
                                "warnings": None,
                                "analysis_details": {},
                                "db_id": None,
                                "db_message": "Processing only endpoint.",
                            }
                        )
                        batch["processed_count"] += 1
                    except Exception as exc:
                        batch["results"].append(
                            {
                                "status": "Error",
                                "input_ref": url,
                                "processing_source": str(local_path),
                                "media_type": "code",
                                "error": f"Failed to read code file: {exc}",
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
                        batch["errors_count"] += 1

    # Normalize batch ordering and ensure standard counters exist.
    batch = normalize_process_batch(batch)
    final_status = (
        status.HTTP_200_OK
        if (batch["processed_count"] > 0 and batch["errors_count"] == 0)
        else (
            status.HTTP_207_MULTI_STATUS if batch["results"] else status.HTTP_400_BAD_REQUEST
        )
    )
    return JSONResponse(status_code=final_status, content=batch)


__all__ = ["router"]
