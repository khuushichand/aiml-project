from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import asyncio
import functools
import logging
import json
import os
import sqlite3
from pathlib import Path as FilePath

import aiofiles
import httpx
from fastapi import BackgroundTasks, HTTPException, Path, UploadFile, status
from loguru import logger
from starlette.responses import JSONResponse

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (
    ConflictError,
    DatabaseError,
    InputError,
    MediaDatabase,
)
from tldw_Server_API.app.core.Metrics import get_metrics_registry
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.Ingestion_Media_Processing.chunking_options import (
    prepare_chunking_options_dict,
    prepare_common_options,
)
from tldw_Server_API.app.core.Ingestion_Media_Processing.claims_utils import (
    extract_claims_if_requested,
    persist_claims_if_applicable,
)


try:  # Align HTTP 413 compatibility with legacy endpoint module
    HTTP_413_TOO_LARGE = status.HTTP_413_CONTENT_TOO_LARGE
except AttributeError:  # Starlette < 0.27
    HTTP_413_TOO_LARGE = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


def validate_add_media_inputs(
    media_type: Any,
    urls: Optional[List[str]],
    files: Optional[List[UploadFile]],
) -> None:
    """
    Validate basic inputs for the `/media/add` endpoint.

    This is the core implementation of the legacy `_validate_inputs`
    helper previously defined in `_legacy_media`.
    """
    if not urls and not files:
        logger.warning("No URLs or files provided in add_media request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No valid media sources supplied. At least one 'url' in the "
                "'urls' list or one 'file' in the 'files' list must be provided."
            ),
        )


def determine_add_media_final_status(results: List[Dict[str, Any]]) -> int:
    """
    Determine the overall HTTP status code for `/media/add` responses.

    Mirrors the legacy `_determine_final_status` behaviour while living
    in the core ingestion module.
    """
    if not results:
        # This case should ideally be handled earlier if no inputs were valid.
        return status.HTTP_400_BAD_REQUEST

    processing_results = results
    if not processing_results:
        return status.HTTP_200_OK

    if all(
        str(r.get("status", "")).lower() == "success"
        for r in processing_results
    ):
        return status.HTTP_200_OK
    return status.HTTP_207_MULTI_STATUS


async def add_media_orchestrate(
    background_tasks: BackgroundTasks,
    form_data: Any,
    files: Optional[List[UploadFile]],
    db: MediaDatabase,
    current_user: Any,
    usage_log: Any,
    response: Any = None,
) -> Any:
    """
    Orchestration helper for the `/media/add` endpoint.

    This function now owns the full ingestion and processing pipeline
    that previously lived in `_legacy_media._add_media_impl`, while
    reusing helper functions defined in that module and the modular
    `media` shim so tests can continue to monkeypatch helpers via
    `endpoints.media`.
    """
    # Resolve helpers via the modular `media` shim when available so
    # tests that patch `endpoints.media.*` continue to work. Fall back
    # to core implementations when the shim is unavailable.
    try:
        from tldw_Server_API.app.api.v1.endpoints import (  # type: ignore
            media as media_mod,
        )
    except Exception:  # pragma: no cover - ultra-minimal profiles
        media_mod = None  # type: ignore[assignment]

    _validate_inputs = validate_add_media_inputs
    _prepare_chunking_options_dict = prepare_chunking_options_dict
    _prepare_common_options = prepare_common_options
    _determine_final_status = determine_add_media_final_status

    from tldw_Server_API.app.core.Ingestion_Media_Processing.input_sourcing import (  # type: ignore  # noqa: E501
        TempDirManager as CoreTempDirManager,
        save_uploaded_files as core_save_uploaded_files,
    )
    from tldw_Server_API.app.api.v1.API_Deps.validations_deps import (  # type: ignore  # noqa: E501
        file_validator_instance as core_file_validator_instance,
    )

    if media_mod is not None:
        _save_uploaded_files = getattr(  # type: ignore[assignment]
            media_mod,
            "_save_uploaded_files",
            core_save_uploaded_files,
        )
        file_validator_instance = getattr(  # type: ignore[assignment]
            media_mod,
            "file_validator_instance",
            core_file_validator_instance,
        )
        TemplateClassifier = getattr(  # type: ignore[assignment]
            media_mod,
            "TemplateClassifier",
            None,
        )
        TempDirManagerCls = getattr(  # type: ignore[assignment]
            media_mod,
            "TempDirManager",
            CoreTempDirManager,
        )
        _process_doc_item_fn = getattr(  # type: ignore[assignment]
            media_mod,
            "_process_document_like_item",
            None,
        )
    else:  # pragma: no cover - fallback for minimal profiles
        _save_uploaded_files = core_save_uploaded_files  # type: ignore[assignment]
        file_validator_instance = core_file_validator_instance  # type: ignore[assignment]
        TemplateClassifier = None  # type: ignore[assignment]
        TempDirManagerCls = CoreTempDirManager  # type: ignore[assignment]
        _process_doc_item_fn = None

    if _process_doc_item_fn is None:
        # Fall back to the core helper when the modular shim is not
        # present; this still centralizes behaviour while keeping
        # resolver logic simple.
        _process_doc_item_fn = process_document_like_item  # type: ignore[assignment]

    # --- 1. Validation (form parsing handled by get_add_media_form) ---
    _validate_inputs(form_data.media_type, form_data.urls, files)

    # TEST_MODE diagnostics for auth and DB context
    try:
        if str(os.getenv("TEST_MODE", "")).lower() in {"1", "true", "yes", "on"}:
            _dbp = getattr(db, "db_path_str", getattr(db, "db_path", "?"))
            logger.info(
                "TEST_MODE: add_media db_path=%s user_id=%s",
                _dbp,
                getattr(current_user, "id", "?"),
            )
    except Exception:
        pass

    logger.info("Received request to add %s media.", form_data.media_type)
    try:
        usage_log.log_event(
            "media.add",
            tags=[str(form_data.media_type or "")],
            metadata={
                "has_urls": bool(form_data.urls),
                "files_count": len(files) if files else 0,
                "perform_analysis": bool(form_data.perform_analysis),
            },
        )
    except Exception:
        # Usage logging must never break the endpoint path.
        pass

    # --- 2. Database dependency / client_id guard ---
    if not hasattr(db, "client_id") or not db.client_id:
        logger.error("CRITICAL: Database instance dependency missing client_id.")
        db.client_id = settings.get("SERVER_CLIENT_ID", "SERVER_API_V1_FALLBACK")
        logger.warning(
            "Manually set missing client_id on DB instance to: %s", db.client_id
        )

    results: List[Dict[str, Any]] = []
    temp_dir_manager = TempDirManagerCls(  # type: ignore[call-arg]
        cleanup=not form_data.keep_original_file,
    )
    temp_dir_path: Optional[FilePath] = None
    loop = asyncio.get_running_loop()

    try:
        # --- 3. Setup Temporary Directory ---
        with temp_dir_manager as temp_dir:
            temp_dir_path = FilePath(str(temp_dir))
            logger.info("Using temporary directory: %s", temp_dir_path)

            # --- 4. Save Uploaded Files ---
            # Restrict allowed extensions based on declared media_type to avoid mismatches
            allowed_ext_map = {
                "video": [
                    ".mp4",
                    ".mkv",
                    ".avi",
                    ".mov",
                    ".flv",
                    ".webm",
                    ".wmv",
                    ".mpg",
                    ".mpeg",
                ],
                "audio": [
                    ".mp3",
                    ".aac",
                    ".flac",
                    ".wav",
                    ".ogg",
                    ".m4a",
                    ".wma",
                ],
                "pdf": [".pdf"],
                "ebook": [".epub", ".mobi", ".azw"],
                "email": [".eml"]
                + ([".zip"] if getattr(form_data, "accept_archives", False) else [])
                + ([".mbox"] if getattr(form_data, "accept_mbox", False) else [])
                + (
                    [".pst", ".ost"]
                    if getattr(form_data, "accept_pst", False)
                    else []
                ),
                "json": [".json"],
                # For "document", allow a broad set; leave None to let validator handle.
            }
            allowed_exts = allowed_ext_map.get(str(form_data.media_type).lower())

            saved_files_info, file_save_errors = await _save_uploaded_files(
                files or [],
                temp_dir_path,
                validator=file_validator_instance,
                allowed_extensions=allowed_exts,
                skip_archive_scanning=(
                    str(form_data.media_type).lower() == "email"
                    and bool(getattr(form_data, "accept_archives", False))
                ),
            )

            # Immediate HTTP errors for specific file failures
            for err_info in file_save_errors:
                error_msg = err_info.get("error", "")
                if "exceeds maximum allowed size" in error_msg:
                    raise HTTPException(
                        status_code=HTTP_413_TOO_LARGE,
                        detail=error_msg,
                    )
                if "not allowed for security reasons" in error_msg:
                    raise HTTPException(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        detail=error_msg,
                    )
                if "empty" in error_msg.lower():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=error_msg,
                    )

            # Adapt file saving errors to the standard result format
            for err_info in file_save_errors:
                results.append(
                    {
                        "status": "Error",
                        "input_ref": err_info.get("input_ref", "Unknown Upload"),
                        "processing_source": None,
                        "media_type": form_data.media_type,
                        "metadata": {},
                        "content": None,
                        "transcript": None,
                        "segments": None,
                        "chunks": None,
                        "analysis": None,
                        "summary": None,
                        "analysis_details": None,
                        "error": err_info.get("error", "File save failed."),
                        "warnings": None,
                        "db_id": None,
                        "db_message": "File saving failed.",
                        "message": "File saving failed.",
                    }
                )

            # --- Quota check for uploaded files and upload metrics ---
            try:
                if saved_files_info:
                    total_uploaded_bytes = 0
                    for pf in saved_files_info:
                        try:
                            # Use filesystem Path (not FastAPI's Path) to compute size.
                            total_uploaded_bytes += FilePath(
                                str(pf["path"]).strip()
                            ).stat().st_size
                        except Exception:
                            pass
                    if total_uploaded_bytes > 0:
                        from tldw_Server_API.app.services.storage_quota_service import (  # type: ignore
                            get_storage_quota_service,
                        )

                        quota_service = get_storage_quota_service()
                        has_quota, info = await quota_service.check_quota(
                            current_user.id,
                            total_uploaded_bytes,
                            raise_on_exceed=False,
                        )
                        if not has_quota:
                            detail = (
                                "Storage quota exceeded. "
                                f"Current: {info['current_usage_mb']}MB, "
                                f"New: {info['new_size_mb']}MB, "
                                f"Quota: {info['quota_mb']}MB, "
                                f"Available: {info['available_mb']}MB"
                            )
                            raise HTTPException(
                                status_code=HTTP_413_TOO_LARGE,
                                detail=detail,
                            )
                        # Record upload metrics
                        try:
                            reg = get_metrics_registry()
                            reg.increment(
                                "uploads_total",
                                len(saved_files_info),
                                labels={
                                    "user_id": str(current_user.id),
                                    "media_type": form_data.media_type,
                                },
                            )
                            reg.increment(
                                "upload_bytes_total",
                                float(total_uploaded_bytes),
                                labels={
                                    "user_id": str(current_user.id),
                                    "media_type": form_data.media_type,
                                },
                            )
                        except Exception:
                            pass
            except HTTPException:
                raise
            except Exception as quota_err:
                logger.warning("Quota check failed (non-fatal): %s", quota_err)

            # --- 5. Prepare Inputs and Options ---
            uploaded_file_paths = [str(pf["path"]) for pf in saved_files_info]
            url_list = form_data.urls or []
            all_valid_input_sources = url_list + uploaded_file_paths

            # Check if any valid sources remain after potential save errors
            if not all_valid_input_sources:
                if file_save_errors:
                    logger.warning(
                        "No valid inputs remaining after file handling errors."
                    )
                    return JSONResponse(
                        status_code=status.HTTP_207_MULTI_STATUS,
                        content={"results": results},
                    )
                logger.error(
                    "No input URLs or successfully saved files found for /media/add."
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No valid media sources found to process.",
                )

            # Prepare chunking options and auto-apply templates
            chunking_options_dict = _prepare_chunking_options_dict(form_data)

            # Apply explicit or auto-selected chunking templates when requested.
            try:
                from tldw_Server_API.app.core.Ingestion_Media_Processing.chunking_options import (  # type: ignore  # noqa: E501
                    apply_chunking_template_if_any as _apply_tpl,
                )

                first_url = (form_data.urls or [None])[0]
                first_filename = None
                try:
                    if saved_files_info:
                        first_filename = saved_files_info[0]["original_filename"]
                except Exception:
                    first_filename = None

                chunking_options_dict = _apply_tpl(
                    form_data=form_data,
                    db=db,
                    chunking_options_dict=chunking_options_dict,
                    TemplateClassifier=TemplateClassifier,
                    first_url=first_url,
                    first_filename=first_filename,
                )
            except Exception as auto_err:
                logger.warning("Auto-apply chunking template failed: %s", auto_err)

            # Even if not used directly here, preserve the legacy call
            # to common options preparation to keep side effects/logging.
            _prepare_common_options(form_data, chunking_options_dict)

            # Map input sources back to original refs (URL or original filename)
            source_to_ref_map: Dict[str, str] = {src: src for src in url_list}
            source_to_ref_map.update(
                {str(pf["path"]): pf["original_filename"] for pf in saved_files_info}
            )

            # --- 6. Process Media based on Type ---
            db_path_for_workers = db.db_path_str
            client_id_for_workers = db.client_id

            logging.info(
                "Processing %d items of type '%s'",
                len(all_valid_input_sources),
                form_data.media_type,
            )

            if form_data.media_type in ["video", "audio"]:
                batch_results = await process_batch_media(
                    media_type=str(form_data.media_type),
                    urls=url_list,
                    uploaded_file_paths=uploaded_file_paths,
                    source_to_ref_map=source_to_ref_map,
                    form_data=form_data,
                    chunk_options=chunking_options_dict,
                    loop=loop,
                    db_path=db_path_for_workers,
                    client_id=client_id_for_workers,
                    temp_dir=temp_dir_path,
                )
                results.extend(batch_results)
            else:
                # PDF / Document / Ebook / Email
                tasks = [
                    _process_doc_item_fn(  # type: ignore[misc]
                        item_input_ref=source_to_ref_map.get(source, source),
                        processing_source=source,
                        media_type=form_data.media_type,
                        is_url=(source in url_list),
                        form_data=form_data,
                        chunk_options=chunking_options_dict,
                        temp_dir=temp_dir_path,
                        loop=loop,
                        db_path=db_path_for_workers,
                        client_id=client_id_for_workers,
                        user_id=(
                            current_user.id
                            if hasattr(current_user, "id")
                            else None
                        ),
                    )
                    for source in all_valid_input_sources
                ]
                individual_results = await asyncio.gather(*tasks)
                results.extend(individual_results)


        # --- 7. Generate Embeddings if Requested ---
        logger.info("generate_embeddings flag: %s", form_data.generate_embeddings)
        if form_data.generate_embeddings:
            logger.info(
                "Generating embeddings for successfully processed media items..."
            )

            for result in results:
                if result.get("status") == "Success" and result.get("db_id"):
                    media_id = result["db_id"]
                    logger.info(
                        "Scheduling embedding generation for media ID %s",
                        media_id,
                    )

                    async def generate_embeddings_task(media_id: int) -> None:
                        try:
                            from tldw_Server_API.app.api.v1.endpoints.media_embeddings import (  # type: ignore
                                generate_embeddings_for_media,
                                get_media_content,
                            )

                            media_content = await get_media_content(media_id, db)
                            embedding_model = (
                                form_data.embedding_model
                                or "Qwen/Qwen3-Embedding-4B-GGUF"
                            )
                            embedding_provider = (
                                form_data.embedding_provider or "huggingface"
                            )

                            result_emb = await generate_embeddings_for_media(
                                media_id=media_id,
                                media_content=media_content,
                                embedding_model=embedding_model,
                                embedding_provider=embedding_provider,
                                chunk_size=form_data.chunk_size or 1000,
                                chunk_overlap=getattr(
                                    form_data, "overlap", None
                                )
                                or 200,
                            )
                            logger.info(
                                "Embedding generation result for media %s: %s",
                                media_id,
                                result_emb,
                            )
                        except Exception as embed_err:
                            logger.error(
                                "Failed to generate embeddings for media %s: %s",
                                media_id,
                                embed_err,
                            )

                    background_tasks.add_task(generate_embeddings_task, media_id)
                    result["embeddings_scheduled"] = True

        # --- 8. Determine Final Status Code and Return Response ---
        final_status_code = _determine_final_status(results)

        # Special-case: Email container parent with children should return 200
        # even when some children include guardrail errors.
        try:
            if (
                isinstance(results, list)
                and len(results) == 1
                and isinstance(results[0], dict)
                and results[0].get("media_type") == "email"
                and results[0].get("status") == "Success"
                and isinstance(results[0].get("children"), list)
            ):
                final_status_code = status.HTTP_200_OK
        except Exception:
            pass

        log_level = (
            "INFO"
            if final_status_code == status.HTTP_200_OK
            else "WARNING"
        )
        logger.log(
            log_level,
            "Request finished with status %s. Results count: %s",
            final_status_code,
            len(results),
        )

        # TEST_MODE: emit diagnostic headers to assist tests
        try:
            if (
                str(os.getenv("TEST_MODE", "")).lower()
                in {"1", "true", "yes", "on"}
                and response is not None
            ):
                try:
                    _dbp = getattr(
                        db, "db_path_str", getattr(db, "db_path", "?")
                    )
                except Exception:
                    _dbp = "?"
                response.headers["X-TLDW-DB-Path"] = str(_dbp)
                response.headers["X-TLDW-Add-Results-Len"] = str(len(results))
                try:
                    ok_with_id = sum(
                        1
                        for r in results
                        if isinstance(r, dict)
                        and r.get("status") == "Success"
                        and r.get("db_id")
                    )
                    response.headers["X-TLDW-Add-OK-With-Id"] = str(ok_with_id)
                except Exception:
                    pass
        except Exception:
            pass

        return JSONResponse(
            status_code=final_status_code,
            content={"results": results},
        )

    except HTTPException as exc:
        logging.warning(
            "HTTP Exception encountered in /media/add: Status=%s, Detail=%s",
            exc.status_code,
            exc.detail,
        )
        raise
    except OSError as os_err:
        logging.error(
            "OSError during /media/add setup: %s", os_err, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OS error during setup: {os_err}",
        )
    except Exception as unexpected:
        logging.error(
            "Unhandled exception in /media/add endpoint: %s - %s",
            type(unexpected).__name__,
            unexpected,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected internal error: {type(unexpected).__name__}",
        )


async def add_media_persist(
    background_tasks: BackgroundTasks,
    form_data: Any,
    files: Optional[List[UploadFile]],
    db: MediaDatabase,
    current_user: Any,
    usage_log: Any,
    response: Any = None,
) -> Any:
    """
    Persistence entry point used by the modular `media/add` endpoint.

    This delegates to `add_media_orchestrate` so future refactors can
    move more orchestration logic into this module while keeping the
    FastAPI route stable.
    """
    return await add_media_orchestrate(
        background_tasks=background_tasks,
        form_data=form_data,
        files=files,
        db=db,
        current_user=current_user,
        usage_log=usage_log,
        response=response,
    )


async def persist_primary_av_item(
    *,
    process_result: Dict[str, Any],
    form_data: Any,
    media_type: Any,
    original_input_ref: str,
    chunk_options: Optional[Dict[str, Any]],
    db_path: str,
    client_id: str,
    loop: Any,
    claims_context: Optional[Dict[str, Any]],
) -> None:
    """
    Persist a single audio/video item processed by the /add orchestration.

    This helper lifts the DB write + claims persistence logic used by
    `_process_batch_media` so it can be reused and eventually migrated
    out of the legacy endpoint module entirely.
    """
    # Match legacy guard: only attempt DB writes when we have a DB path,
    # client id, and a successful or warning status.
    if not (db_path and client_id and process_result.get("status") in ["Success", "Warning"]):
        return

    # Use transcript as content for audio/video.
    content_for_db = process_result.get("transcript", process_result.get("content"))
    analysis_for_db = process_result.get("summary", process_result.get("analysis"))
    metadata_for_db = process_result.get("metadata", {}) or {}

    # Use the model reported by the processor if available, else fall back.
    transcription_model_used = metadata_for_db.get(
        "model",
        getattr(form_data, "transcription_model", None),
    )
    extracted_keywords = metadata_for_db.get("keywords", [])

    combined_keywords = set(getattr(form_data, "keywords", []) or [])
    if isinstance(extracted_keywords, list):
        combined_keywords.update(
            k.strip().lower() for k in extracted_keywords if k and isinstance(k, str) and k.strip()
        )
    final_keywords_list = sorted(list(combined_keywords))

    # Use original input ref for default title to match legacy.
    if original_input_ref:
        default_title = FilePath(str(original_input_ref)).stem
    else:
        default_title = "Untitled"

    title_for_db = metadata_for_db.get(
        "title",
        getattr(form_data, "title", None) or default_title,
    )
    author_for_db = metadata_for_db.get("author", getattr(form_data, "author", None))

    # When there is no content, mirror legacy behavior: skip DB writes but
    # still persist claims (with media_id=None) and update db_message/db_id.
    if not content_for_db:
        process_result["db_message"] = "DB persistence skipped (no content)."
        process_result["db_id"] = None
        process_result["media_uuid"] = None
        await persist_claims_if_applicable(
            claims_context=claims_context,
            media_id=None,
            db_path=db_path,
            client_id=client_id,
            loop=loop,
            process_result=process_result,
        )
        logger.warning(
            "Skipping DB persistence for %s due to missing content.",
            original_input_ref,
        )
        return

    try:
        logger.info("Attempting DB persistence for item: %s", process_result.get("input_ref"))

        # Build a safe metadata subset for persistence.
        safe_meta: Dict[str, Any] = {}
        try:
            allowed_keys = {
                "title",
                "author",
                "doi",
                "pmid",
                "pmcid",
                "arxiv_id",
                "s2_paper_id",
                "url",
                "pdf_url",
                "pmc_url",
                "date",
                "year",
                "venue",
                "journal",
                "license",
                "license_url",
                "publisher",
                "source",
                "creators",
                "rights",
            }
            for k, v in metadata_for_db.items():
                if k in allowed_keys and isinstance(v, (str, int, float, bool)):
                    safe_meta[k] = v
                elif k in allowed_keys and isinstance(v, list):
                    safe_meta[k] = [x for x in v if isinstance(x, (str, int, float, bool))]
            # Extract from externalIds if present.
            ext = metadata_for_db.get("externalIds")
            if isinstance(ext, dict):
                for kk in ("DOI", "ArXiv", "PMID", "PMCID"):
                    if ext.get(kk):
                        safe_meta[kk.lower()] = ext.get(kk)
        except Exception:
            safe_meta = {}

        safe_metadata_json: Optional[str] = None
        try:
            if safe_meta:
                from tldw_Server_API.app.core.Utils.metadata_utils import (  # type: ignore
                    normalize_safe_metadata as _norm_sm,
                )

                try:
                    safe_meta = _norm_sm(safe_meta)
                except Exception:
                    # Best-effort normalization; ignore failures here.
                    pass
                safe_metadata_json = json.dumps(safe_meta, ensure_ascii=False)
        except Exception:
            safe_metadata_json = None

        # Build plaintext chunks for chunk-level FTS if chunking is requested.
        chunks_for_sql: Optional[List[Dict[str, Any]]] = None
        try:
            _opts = chunk_options or {}
            if _opts:
                from tldw_Server_API.app.core.Chunking.chunker import (  # type: ignore
                    Chunker as _Chunker,
                )

                _ck = _Chunker()
                _flat = _ck.chunk_text_hierarchical_flat(
                    content_for_db,
                    method=_opts.get("method") or "sentences",
                    max_size=_opts.get("max_size") or 500,
                    overlap=_opts.get("overlap") or 50,
                )
                _kind_map = {
                    "paragraph": "text",
                    "list_unordered": "list",
                    "list_ordered": "list",
                    "code_fence": "code",
                    "table_md": "table",
                    "header_line": "heading",
                    "header_atx": "heading",
                }
                chunks_for_sql = []
                for _it in _flat:
                    _md = _it.get("metadata") or {}
                    _ctype = _kind_map.get(str(_md.get("paragraph_kind") or "").lower(), "text")
                    _small: Dict[str, Any] = {}
                    if _md.get("ancestry_titles"):
                        _small["ancestry_titles"] = _md.get("ancestry_titles")
                    if _md.get("section_path"):
                        _small["section_path"] = _md.get("section_path")
                    chunks_for_sql.append(
                        {
                            "text": _it.get("text", ""),
                            "start_char": _md.get("start_offset"),
                            "end_char": _md.get("end_offset"),
                            "chunk_type": _ctype,
                            "metadata": _small,
                        }
                    )
        except Exception:
            chunks_for_sql = None

        # Merge VLM extra chunks even if chunking was disabled or failed.
        try:
            extra_chunks_any = (process_result or {}).get("extra_chunks")
            if isinstance(extra_chunks_any, list) and extra_chunks_any:
                if chunks_for_sql is None:
                    chunks_for_sql = []
                for ec in extra_chunks_any:
                    if not isinstance(ec, dict) or "text" not in ec:
                        continue
                    chunks_for_sql.append(
                        {
                            "text": ec.get("text", ""),
                            "start_char": ec.get("start_char"),
                            "end_char": ec.get("end_char"),
                            "chunk_type": ec.get("chunk_type") or "vlm",
                            "metadata": ec.get("metadata")
                            if isinstance(ec.get("metadata"), dict)
                            else {},
                        }
                    )
        except Exception:
            pass

        db_add_kwargs = dict(
            url=str(original_input_ref),
            title=title_for_db,
            media_type=media_type,
            content=content_for_db,
            keywords=final_keywords_list,
            prompt=getattr(form_data, "custom_prompt", None),
            analysis_content=analysis_for_db,
            safe_metadata=safe_metadata_json,
            transcription_model=transcription_model_used,
            author=author_for_db,
            overwrite=getattr(form_data, "overwrite_existing", False),
            chunk_options=chunk_options,
            chunks=chunks_for_sql,
        )

        def _db_worker() -> Any:
            worker_db: Optional[MediaDatabase] = None
            try:
                worker_db = MediaDatabase(db_path=db_path, client_id=client_id)
                return worker_db.add_media_with_keywords(**db_add_kwargs)
            finally:
                if worker_db is not None:
                    worker_db.close_connection()

        media_id_result, media_uuid_result, db_message_result = await loop.run_in_executor(
            None,
            _db_worker,
        )

        process_result["db_id"] = media_id_result
        process_result["db_message"] = db_message_result
        process_result["media_uuid"] = media_uuid_result

        # Optionally persist a normalized STT transcript into the Transcripts table
        # for audio/video items when a transcription model is known.
        try:
            if (
                media_type in ["audio", "video"]
                and media_id_result
                and transcription_model_used
                and content_for_db
            ):
                from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import (  # type: ignore
                    to_normalized_stt_artifact,
                )
                from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.stt_provider_adapter import (  # type: ignore
                    get_stt_provider_registry,
                )
                from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (  # type: ignore
                    MediaDatabase as _MediaDBForStt,
                    upsert_transcript,
                )

                registry = get_stt_provider_registry()
                provider_name, provider_model, _ = registry.resolve_provider_for_model(
                    str(transcription_model_used)
                )
                analysis_details = process_result.get("analysis_details") or {}
                lang_for_stt = analysis_details.get("transcription_language")

                artifact = to_normalized_stt_artifact(
                    text=str(content_for_db),
                    segments=process_result.get("segments"),
                    language=lang_for_stt,
                    provider=provider_name,
                    model=provider_model or str(transcription_model_used),
                )

                def _upsert_worker() -> None:
                    db = _MediaDBForStt(db_path=db_path, client_id=client_id)
                    try:
                        upsert_transcript(
                            db_instance=db,
                            media_id=int(media_id_result),
                            transcription=artifact["text"],
                            whisper_model=artifact["metadata"]["model"],
                        )
                    finally:
                        db.close_connection()

                await loop.run_in_executor(None, _upsert_worker)
                # Attach normalized artifact to the process_result for callers
                process_result["normalized_stt"] = artifact
        except Exception as stt_err:
            logger.debug(
                "STT transcript upsert skipped/failed for %s (media_id=%s): %s",
                original_input_ref,
                media_id_result,
                stt_err,
            )

        # Optionally persist VisualDocuments for eligible media types (currently PDFs via VLM summary).
        try:
            if media_type in ["pdf"] and media_id_result:
                from tldw_Server_API.app.core.Ingestion_Media_Processing.visual_ingestion import (  # type: ignore
                    persist_visual_documents_from_analysis,
                )

                def _visual_docs_worker() -> int:
                    return persist_visual_documents_from_analysis(
                        db_path=db_path,
                        client_id=client_id,
                        media_id=int(media_id_result),
                        analysis_details=process_result.get("analysis_details") or {},
                    )

                created_visual_docs = await loop.run_in_executor(None, _visual_docs_worker)
                if created_visual_docs:
                    logger.info(
                        "Persisted %s VisualDocuments for media_id=%s (input_ref=%s)",
                        created_visual_docs,
                        media_id_result,
                        original_input_ref,
                    )
        except Exception as visual_err:
            logger.debug(
                "Visual RAG ingestion skipped/failed for %s (media_id=%s): %s",
                original_input_ref,
                media_id_result,
                visual_err,
            )

        await persist_claims_if_applicable(
            claims_context=claims_context,
            media_id=process_result.get("db_id"),
            db_path=db_path,
            client_id=client_id,
            loop=loop,
            process_result=process_result,
        )

        logger.info(
            "DB persistence result for %s: ID=%s, UUID=%s, Msg='%s'",
            original_input_ref,
            media_id_result,
            media_uuid_result,
            db_message_result,
        )

    except (DatabaseError, InputError, ConflictError) as db_err:
        logger.error(
            "Database operation failed for %s: %s",
            original_input_ref,
            db_err,
            exc_info=True,
        )
        process_result["status"] = "Warning"
        process_result["error"] = (process_result.get("error") or "") + f" | DB Error: {db_err}"
        process_result.setdefault("warnings", []).append(f"Database operation failed: {db_err}")
        process_result["db_message"] = f"DB Error: {db_err}"
        process_result["db_id"] = None
        process_result["media_uuid"] = None
        await persist_claims_if_applicable(
            claims_context=claims_context,
            media_id=None,
            db_path=db_path,
            client_id=client_id,
            loop=loop,
            process_result=process_result,
        )

    except Exception as exc:
        logger.error(
            "Unexpected error during DB persistence for %s: %s",
            original_input_ref,
            exc,
            exc_info=True,
        )
        process_result["status"] = "Warning"
        process_result["error"] = (process_result.get("error") or "")
        process_result.setdefault("warnings", []).append(
            f"Unexpected persistence error: {exc}",
        )
        process_result["db_message"] = f"Persistence Error: {type(exc).__name__}"
        process_result["db_id"] = None
        process_result["media_uuid"] = None
        await persist_claims_if_applicable(
            claims_context=claims_context,
            media_id=None,
            db_path=db_path,
            client_id=client_id,
            loop=loop,
            process_result=process_result,
        )


async def process_batch_media(
    media_type: Any,
    urls: List[str],
    uploaded_file_paths: List[str],
    source_to_ref_map: Dict[str, Any],
    form_data: Any,
    chunk_options: Optional[Dict[str, Any]],
    loop: asyncio.AbstractEventLoop,
    db_path: str,
    client_id: str,
    temp_dir: FilePath,
) -> List[Dict[str, Any]]:
    """
    Core implementation of the audio/video batch processing helper used by `/media/add`.

    This function mirrors the legacy `_process_batch_media` behaviour while living
    in the core ingestion module so it can be reused independently of the legacy
    endpoint file.
    """
    combined_results: List[Dict[str, Any]] = []
    all_processing_sources = urls + uploaded_file_paths
    items_to_process: List[str] = []

    logger.debug(
        "Starting pre-check for %d %s items...",
        len(all_processing_sources),
        media_type,
    )

    # --- 1. Pre-check ---
    for source_path_or_url in all_processing_sources:
        input_ref_info = source_to_ref_map.get(source_path_or_url)
        input_ref = input_ref_info[0] if isinstance(input_ref_info, tuple) else input_ref_info
        if not input_ref:
            logger.error(
                "CRITICAL: Could not find original input reference for %s.",
                source_path_or_url,
            )
            input_ref = source_path_or_url

        identifier_for_check = input_ref
        should_process = True
        existing_id: Optional[int] = None
        reason = "Ready for processing."
        pre_check_warning: Optional[str] = None

        if not getattr(form_data, "overwrite_existing", False) and str(media_type) in ["video", "audio"]:
            try:
                temp_db_for_check = MediaDatabase(db_path=db_path, client_id=client_id)
                model_for_check = getattr(form_data, "transcription_model", None)
                pre_check_query = """
                                  SELECT id \
                                  FROM Media
                                  WHERE url = ?
                                    AND transcription_model = ?
                                    AND is_trash = 0 \
                                  """
                cursor = temp_db_for_check.execute_query(
                    pre_check_query,
                    (identifier_for_check, model_for_check),
                )
                existing_record = cursor.fetchone()
                temp_db_for_check.close_connection()

                if existing_record:
                    existing_id = existing_record["id"]
                    should_process = False
                    reason = (
                        "Media exists (ID: {id}) with the same URL/identifier "
                        "and transcription model ('{model}'). Overwrite is False."
                    ).format(id=existing_id, model=model_for_check)
                else:
                    should_process = True
                    reason = (
                        "Media not found with this URL/identifier and "
                        "transcription model."
                    )
            except (DatabaseError, sqlite3.Error) as check_err:
                logger.error(
                    "DB pre-check (custom query) failed for %s: %s",
                    identifier_for_check,
                    check_err,
                    exc_info=True,
                )
                should_process, existing_id, reason = (
                    True,
                    None,
                    f"DB pre-check failed: {check_err}",
                )
                pre_check_warning = f"Database pre-check failed: {check_err}"
            except Exception as check_err:
                logger.error(
                    "Unexpected error during DB pre-check (custom query) for %s: %s",
                    identifier_for_check,
                    check_err,
                    exc_info=True,
                )
                should_process, existing_id, reason = (
                    True,
                    None,
                    f"Unexpected pre-check error: {check_err}",
                )
                pre_check_warning = (
                    f"Unexpected database pre-check error: {check_err}"
                )
        else:
            should_process = True
            reason = (
                "Overwrite requested or not applicable, proceeding regardless "
                "of existence."
            )

        if not should_process:
            logger.info("Skipping processing for %s: %s", input_ref, reason)
            skipped_result = {
                "status": "Skipped",
                "input_ref": input_ref,
                "processing_source": source_path_or_url,
                "media_type": media_type,
                "message": reason,
                "db_id": existing_id,
                "metadata": {},
                "content": None,
                "transcript": None,
                "segments": None,
                "chunks": None,
                "analysis": None,
                "summary": None,
                "analysis_details": None,
                "error": None,
                "warnings": None,
                "db_message": "Skipped processing, no DB action.",
            }
            combined_results.append(skipped_result)
        else:
            items_to_process.append(source_path_or_url)
            log_msg = f"Proceeding with processing for {input_ref}: {reason}"
            if pre_check_warning:
                log_msg += f" (Pre-check Warning: {pre_check_warning})"
                source_to_ref_map[source_path_or_url] = (input_ref, pre_check_warning)
            logger.info(log_msg)

    if not items_to_process:
        logging.info("No items require processing after pre-checks.")
        return combined_results

    processing_output: Optional[Dict[str, Any]] = None
    try:
        if str(media_type) == "video":
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib import (  # type: ignore  # noqa: E501
                process_videos,
            )

            video_args = {
                "inputs": items_to_process,
                "temp_dir": str(temp_dir),
                "start_time": getattr(form_data, "start_time", None),
                "end_time": getattr(form_data, "end_time", None),
                "diarize": getattr(form_data, "diarize", False),
                "vad_use": getattr(form_data, "vad_use", False),
                "transcription_model": getattr(form_data, "transcription_model", None),
                "transcription_language": getattr(
                    form_data,
                    "transcription_language",
                    None,
                ),
                "custom_prompt": getattr(form_data, "custom_prompt", None),
                "system_prompt": getattr(form_data, "system_prompt", None),
                "perform_analysis": getattr(form_data, "perform_analysis", False),
                "perform_chunking": getattr(form_data, "perform_chunking", True),
                "chunk_method": chunk_options.get("method") if chunk_options else None,
                "max_chunk_size": (
                    chunk_options.get("max_size") if chunk_options else 500
                ),
                "chunk_overlap": (
                    chunk_options.get("overlap") if chunk_options else 200
                ),
                "use_adaptive_chunking": (
                    chunk_options.get("adaptive", False) if chunk_options else False
                ),
                "use_multi_level_chunking": (
                    chunk_options.get("multi_level", False)
                    if chunk_options
                    else False
                ),
                "chunk_language": (
                    chunk_options.get("language") if chunk_options else None
                ),
                "summarize_recursively": getattr(
                    form_data,
                    "summarize_recursively",
                    False,
                ),
                "api_name": getattr(form_data, "api_name", None)
                if getattr(form_data, "perform_analysis", False)
                else None,
                "use_cookies": getattr(form_data, "use_cookies", False),
                "cookies": getattr(form_data, "cookies", None),
                "timestamp_option": getattr(form_data, "timestamp_option", None),
                "perform_confabulation_check": getattr(
                    form_data,
                    "perform_confabulation_check_of_analysis",
                    False,
                ),
                "keep_original": getattr(form_data, "keep_original_file", False),
            }
            logging.debug(
                "Calling external process_videos with args including temp_dir: %s",
                list(video_args.keys()),
            )
            target_func = functools.partial(process_videos, **video_args)
            processing_output = await loop.run_in_executor(None, target_func)

        elif str(media_type) == "audio":
            from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Files import process_audio_files  # type: ignore  # noqa: E501

            audio_args = {
                "inputs": items_to_process,
                "temp_dir": str(temp_dir),
                "transcription_model": getattr(
                    form_data,
                    "transcription_model",
                    None,
                ),
                "transcription_language": getattr(
                    form_data,
                    "transcription_language",
                    None,
                ),
                "perform_chunking": getattr(form_data, "perform_chunking", True),
                "chunk_method": chunk_options.get("method") if chunk_options else None,
                "max_chunk_size": (
                    chunk_options.get("max_size") if chunk_options else 500
                ),
                "chunk_overlap": (
                    chunk_options.get("overlap") if chunk_options else 200
                ),
                "use_adaptive_chunking": (
                    chunk_options.get("adaptive", False) if chunk_options else False
                ),
                "use_multi_level_chunking": (
                    chunk_options.get("multi_level", False)
                    if chunk_options
                    else False
                ),
                "chunk_language": (
                    chunk_options.get("language") if chunk_options else None
                ),
                "diarize": getattr(form_data, "diarize", False),
                "vad_use": getattr(form_data, "vad_use", False),
                "timestamp_option": getattr(form_data, "timestamp_option", None),
                "perform_analysis": getattr(form_data, "perform_analysis", False),
                "api_name": getattr(form_data, "api_name", None)
                if getattr(form_data, "perform_analysis", False)
                else None,
                "custom_prompt_input": getattr(form_data, "custom_prompt", None),
                "system_prompt_input": getattr(form_data, "system_prompt", None),
                "summarize_recursively": getattr(
                    form_data,
                    "summarize_recursively",
                    False,
                ),
                "use_cookies": getattr(form_data, "use_cookies", False),
                "cookies": getattr(form_data, "cookies", None),
                "keep_original": getattr(form_data, "keep_original_file", False),
                "custom_title": getattr(form_data, "title", None),
                "author": getattr(form_data, "author", None),
            }
            logging.debug(
                "Calling external process_audio_files with args including temp_dir: %s",
                list(audio_args.keys()),
            )
            target_func = functools.partial(process_audio_files, **audio_args)
            processing_output = await loop.run_in_executor(None, target_func)
        else:
            raise ValueError(f"Invalid media type '{media_type}' for batch processing.")

    except Exception as call_e:
        logging.error(
            "Error calling external batch processor for %s: %s",
            media_type,
            call_e,
            exc_info=True,
        )
        failed_items_results = [
            {
                "status": "Error",
                "input_ref": source_to_ref_map.get(item, (item, None))[0],
                "processing_source": item,
                "media_type": media_type,
                "error": f"Failed to call processor: {type(call_e).__name__}",
                "metadata": None,
                "content": None,
                "transcript": None,
                "segments": None,
                "chunks": None,
                "analysis": None,
                "summary": None,
                "analysis_details": None,
                "warnings": None,
                "db_id": None,
                "db_message": None,
            }
            for item in items_to_process
        ]
        combined_results.extend(failed_items_results)
        return combined_results

    final_batch_results: List[Dict[str, Any]] = []
    processing_results_list: List[Dict[str, Any]] = []

    if processing_output and isinstance(processing_output.get("results"), list):
        processing_results_list = processing_output["results"]
        if processing_output.get("errors_count", 0) > 0:
            logging.warning(
                "Batch %s processor reported errors: %s",
                media_type,
                processing_output.get("errors"),
            )
    else:
        logging.error(
            "Batch %s processor returned unexpected output: %s",
            media_type,
            processing_output,
        )
        return combined_results

    for process_result in processing_results_list:
        if not isinstance(process_result, Dict):
            logging.error("Processor returned non-dict item: %s", process_result)
            malformed_result = {
                "status": "Error",
                "input_ref": "Unknown Input",
                "processing_source": "Unknown",
                "media_type": media_type,
                "error": "Processor returned invalid result format.",
                "metadata": None,
                "content": None,
                "transcript": None,
                "segments": None,
                "chunks": None,
                "analysis": None,
                "summary": None,
                "analysis_details": None,
                "warnings": None,
                "db_id": None,
                "db_message": None,
            }
            final_batch_results.append(malformed_result)
            continue

        input_ref = process_result.get("input_ref")
        processing_source = process_result.get("processing_source")
        if processing_source:
            ref_info = source_to_ref_map.get(str(processing_source))
            if isinstance(ref_info, tuple):
                original_input_ref = ref_info[0]
            elif isinstance(ref_info, str):
                original_input_ref = ref_info
            else:
                logger.warning(
                    "Could not find original input reference in source_to_ref_map "
                    "for processing_source: %s. Falling back.",
                    processing_source,
                )
                original_input_ref = (
                    process_result.get("input_ref") or processing_source or "Unknown Input"
                )
        else:
            original_input_ref = process_result.get("input_ref") or "Unknown Input (Missing Source)"
            logger.warning(
                "Processing result missing 'processing_source'. Using fallback input_ref: %s",
                original_input_ref,
            )
            process_result["processing_source"] = (
                str(original_input_ref) if original_input_ref else "Unknown"
            )

        process_result["input_ref"] = (
            str(original_input_ref) if original_input_ref else "Unknown"
        )

        pre_check_info = source_to_ref_map.get(processing_source) if processing_source else None
        pre_check_warning_msg = None
        if isinstance(pre_check_info, tuple):
            pre_check_warning_msg = pre_check_info[1]
        if pre_check_warning_msg:
            process_result.setdefault("warnings", []).append(pre_check_warning_msg)

        claims_context: Optional[Dict[str, Any]] = None
        if process_result.get("status") in ("Success", "Warning"):
            try:
                claims_context = await extract_claims_if_requested(
                    process_result,
                    form_data,
                    loop,
                )
            except Exception as claims_err:
                logger.debug(
                    "Claim extraction skipped for %s: %s",
                    original_input_ref,
                    claims_err,
                )

        await persist_primary_av_item(
            process_result=process_result,
            form_data=form_data,
            media_type=media_type,
            original_input_ref=str(original_input_ref) if original_input_ref else "",
            chunk_options=chunk_options,
            db_path=db_path,
            client_id=client_id,
            loop=loop,
            claims_context=claims_context,
        )

        final_batch_results.append(process_result)

    combined_results.extend(final_batch_results)

    final_standardized_results: List[Dict[str, Any]] = []
    processed_input_refs: set[str] = set()

    for res in combined_results:
        input_ref = res.get("input_ref", "Unknown")
        if input_ref in processed_input_refs and input_ref != "Unknown":
            continue
        processed_input_refs.add(input_ref)

        standardized = {
            "status": res.get("status", "Error"),
            "input_ref": input_ref,
            "processing_source": res.get("processing_source", "Unknown"),
            "media_type": res.get("media_type", media_type),
            "metadata": res.get("metadata", {}),
            "content": res.get("content", res.get("transcript")),
            "transcript": res.get("transcript"),
            "segments": res.get("segments"),
            "chunks": res.get("chunks"),
            "analysis": res.get("analysis", res.get("summary")),
            "summary": res.get("summary"),
            "analysis_details": res.get("analysis_details"),
            "claims": res.get("claims"),
            "claims_details": res.get("claims_details"),
            "error": res.get("error"),
            "warnings": res.get("warnings"),
            "db_id": res.get("db_id"),
            "db_message": res.get("db_message"),
            "message": res.get("message"),
            "media_uuid": res.get("media_uuid"),
        }
        if isinstance(standardized.get("warnings"), list) and not standardized["warnings"]:
            standardized["warnings"] = None

        final_standardized_results.append(standardized)

    return final_standardized_results


async def process_document_like_item(
    item_input_ref: str,
    processing_source: str,
    media_type: Any,
    is_url: bool,
    form_data: Any,
    chunk_options: Optional[Dict[str, Any]],
    temp_dir: FilePath,
    loop: asyncio.AbstractEventLoop,
    db_path: str,
    client_id: str,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Core helper that handles download/prep, processing, and DB persistence for
    document-like items (PDF, generic documents/JSON, ebooks, and emails)
    used by the `/media/add` endpoint.

    This mirrors the behaviour of the legacy `_process_document_like_item`
    implementation while living in the core ingestion module.
    """
    # Resolve shimmed helpers via the modular `media` package when
    # available so tests that patch `endpoints.media.*` continue to
    # observe calls, while keeping this implementation canonical.
    try:  # type: ignore[assignment]
        from tldw_Server_API.app.api.v1.endpoints import (  # type: ignore
            media as _media_mod,
        )
    except Exception:  # pragma: no cover - ultra-minimal profiles
        _media_mod = None  # type: ignore[assignment]

    final_result: Dict[str, Any] = {
        "status": "Pending",
        "input_ref": item_input_ref,
        "processing_source": processing_source,
        "media_type": media_type,
        "metadata": {},
        "content": None,
        "segments": None,
        "chunks": None,
        "analysis": None,
        "summary": None,
        "analysis_details": None,
        "error": None,
        "warnings": [],
        "db_id": None,
        "db_message": None,
        "message": None,
    }
    claims_context: Optional[Dict[str, Any]] = None

    # --- 2. Download/Prepare File ---
    file_bytes: Optional[bytes] = None
    processing_filepath: Optional[FilePath] = None
    processing_filename: Optional[str] = None

    try:
        if is_url:
            logger.info("Downloading URL: %s", processing_source)
            # SSRF guard for individual item
            try:
                from tldw_Server_API.app.core.Security.url_validation import (  # type: ignore
                    assert_url_safe,
                )

                assert_url_safe(processing_source)
            except HTTPException as exc:
                # In TEST_MODE, treat host resolution failures as an
                # environment quirk so tests that stub downloads can
                # still execute the ingestion path.
                detail = getattr(exc, "detail", "")
                if (
                    str(os.getenv("TEST_MODE", "")).lower()
                    in {"1", "true", "yes", "on"}
                    and isinstance(detail, str)
                    and "Host could not be resolved" in detail
                ):
                    logger.warning(
                        "TEST_MODE: ignoring host resolution error for %s: %s",
                        processing_source,
                        detail,
                    )
                else:
                    get_metrics_registry().increment(
                        "security_ssrf_block_total",
                        1,
                    )
                    raise exc

            from tldw_Server_API.app.core.Utils.Utils import (  # type: ignore
                smart_download as _default_smart_download,
            )

            # Allow tests to patch `media.smart_download` while falling
            # back to the core helper in normal operation.
            if _media_mod is not None:
                try:
                    smart_download_func = getattr(  # type: ignore[assignment]
                        _media_mod,
                        "smart_download",
                        _default_smart_download,
                    )
                except Exception:  # pragma: no cover - defensive fallback
                    smart_download_func = _default_smart_download
            else:  # pragma: no cover - minimal profiles
                smart_download_func = _default_smart_download

            download_func = functools.partial(
                smart_download_func,
                processing_source,
                temp_dir,
            )
            downloaded_path = await loop.run_in_executor(None, download_func)
            if (
                downloaded_path
                and isinstance(downloaded_path, FilePath)
                and downloaded_path.exists()
            ):
                processing_filepath = downloaded_path
                processing_filename = downloaded_path.name

                if user_id is not None:
                    try:
                        from tldw_Server_API.app.services.storage_quota_service import (  # type: ignore  # noqa: E501
                            get_storage_quota_service,
                        )

                        quota_service = get_storage_quota_service()
                        size_bytes = downloaded_path.stat().st_size
                        has_quota, info = await quota_service.check_quota(
                            user_id,
                            size_bytes,
                            raise_on_exceed=False,
                        )
                        if not has_quota:
                            raise HTTPException(
                                status_code=HTTP_413_TOO_LARGE,
                                detail=(
                                    "Storage quota exceeded. Current: "
                                    f"{info['current_usage_mb']}MB, "
                                    f"New: {info['new_size_mb']}MB, "
                                    f"Quota: {info['quota_mb']}MB, "
                                    f"Available: {info['available_mb']}MB"
                                ),
                            )
                        try:
                            reg = get_metrics_registry()
                            reg.increment(
                                "uploads_total",
                                1,
                                labels={
                                    "user_id": str(user_id),
                                    "media_type": str(media_type),
                                },
                            )
                            reg.increment(
                                "upload_bytes_total",
                                float(size_bytes),
                                labels={
                                    "user_id": str(user_id),
                                    "media_type": str(media_type),
                                },
                            )
                        except Exception:
                            # Metrics must never break ingestion.
                            pass
                    except HTTPException:
                        raise
                    except Exception as quota_err:
                        logger.warning(
                            "Per-item quota check failed (non-fatal): %s",
                            quota_err,
                        )

                # Read bytes for types that operate on raw content.
                if str(media_type) in {"pdf", "email"}:
                    async with aiofiles.open(processing_filepath, "rb") as file_obj:
                        file_bytes = await file_obj.read()

                final_result["processing_source"] = str(processing_filepath)
            else:
                raise IOError(
                    f"Download failed or did not return a valid path for {processing_source}",
                )
        else:
            path_obj = FilePath(processing_source)
            if not path_obj.is_file():
                raise FileNotFoundError(
                    f"Uploaded file path not found or is not a file: {processing_source}",
                )
            processing_filepath = path_obj
            processing_filename = path_obj.name

            if str(media_type) in {"pdf", "email"}:
                async with aiofiles.open(processing_filepath, "rb") as file_obj:
                    file_bytes = await file_obj.read()

            final_result["processing_source"] = processing_source

    except (
        httpx.HTTPStatusError,
        httpx.RequestError,
        IOError,
        OSError,
        FileNotFoundError,
    ) as prep_err:
        logging.error(
            "File preparation/download error for %s: %s",
            item_input_ref,
            prep_err,
            exc_info=True,
        )
        final_result.update(
            {
                "status": "Error",
                "error": f"File preparation/download failed: {prep_err}",
            },
        )
        if not final_result.get("warnings"):
            final_result["warnings"] = None
        return final_result

    # --- 3. Select and Call Processing Function ---
    process_result_dict: Optional[Dict[str, Any]] = None

    try:
        processing_func: Optional[Callable[..., Any]] = None
        common_args: Dict[str, Any] = {
            "title_override": getattr(form_data, "title", None),
            "author_override": getattr(form_data, "author", None),
            "keywords": getattr(form_data, "keywords", None),
            "perform_chunking": getattr(form_data, "perform_chunking", True),
            "chunk_options": chunk_options,
            "perform_analysis": getattr(form_data, "perform_analysis", True),
            "api_name": getattr(form_data, "api_name", None),
            "api_key": None,
            "custom_prompt": getattr(form_data, "custom_prompt", None),
            "system_prompt": getattr(form_data, "system_prompt", None),
            "summarize_recursively": getattr(
                form_data,
                "summarize_recursively",
                False,
            ),
        }
        specific_args: Dict[str, Any] = {}
        run_in_executor = True

        media_type_str = str(media_type)

        if media_type_str == "pdf":
            if file_bytes is None:
                raise ValueError(
                    "PDF processing requires file bytes, but they were not read.",
                )
            from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import (  # type: ignore  # noqa: E501
                process_pdf_task,
            )

            processing_func = process_pdf_task
            run_in_executor = False
            specific_args = {
                "file_bytes": file_bytes,
                "filename": processing_filename or item_input_ref,
                "parser": str(
                    getattr(form_data, "pdf_parsing_engine", "pymupdf4llm"),
                ),
                "chunk_method": (chunk_options or {}).get("method"),
                "max_chunk_size": (chunk_options or {}).get("max_size"),
                "chunk_overlap": (chunk_options or {}).get("overlap"),
            }
            common_args.pop("chunk_options", None)

        elif media_type_str == "document":
            if processing_filepath is None:
                raise ValueError("Document processing requires a file path.")
            import tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files as docs  # type: ignore  # noqa: E501

            # Prefer the shimmed `media.process_document_content` so
            # tests can patch it; fall back to the core implementation.
            if _media_mod is not None:
                try:
                    processing_func = getattr(  # type: ignore[assignment]
                        _media_mod,
                        "process_document_content",
                        docs.process_document_content,
                    )
                except Exception:  # pragma: no cover - defensive
                    processing_func = docs.process_document_content
            else:  # pragma: no cover - minimal profiles
                processing_func = docs.process_document_content

            specific_args = {"doc_path": processing_filepath}

        elif media_type_str == "json":
            if processing_filepath is None:
                raise ValueError("JSON processing requires a file path.")
            import tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files as docs  # type: ignore  # noqa: E501

            if _media_mod is not None:
                try:
                    processing_func = getattr(  # type: ignore[assignment]
                        _media_mod,
                        "process_document_content",
                        docs.process_document_content,
                    )
                except Exception:  # pragma: no cover - defensive
                    processing_func = docs.process_document_content
            else:  # pragma: no cover
                processing_func = docs.process_document_content

            specific_args = {"doc_path": processing_filepath}

        elif media_type_str == "ebook":
            if processing_filepath is None:
                raise ValueError("Ebook processing requires a file path.")
            import tldw_Server_API.app.core.Ingestion_Media_Processing.Books.Book_Processing_Lib as books  # type: ignore  # noqa: E501

            def _sync_process_ebook_wrapper(**kwargs: Any) -> Any:
                return books.process_epub(**kwargs)

            processing_func = _sync_process_ebook_wrapper
            specific_args = {
                "file_path": str(processing_filepath),
                "extraction_method": "filtered",
            }
            custom_pattern = getattr(form_data, "custom_chapter_pattern", None)
            if custom_pattern:
                specific_args["custom_chapter_pattern"] = custom_pattern

        elif media_type_str == "email":
            if file_bytes is None and processing_filepath is not None:
                try:
                    async with aiofiles.open(
                        processing_filepath,
                        "rb",
                    ) as file_obj:
                        file_bytes = await file_obj.read()
                except Exception as read_err:
                    raise ValueError(
                        f"Email processing requires file bytes: {read_err}",
                    ) from read_err
            if file_bytes is None:
                raise ValueError(
                    "Email processing requires file bytes, but they were not available.",
                )

            import tldw_Server_API.app.core.Ingestion_Media_Processing.Email.Email_Processing_Lib as email_lib  # type: ignore  # noqa: E501

            name_lower = (processing_filename or item_input_ref).lower()
            if name_lower.endswith(".zip") and getattr(
                form_data,
                "accept_archives",
                False,
            ):
                processing_func = email_lib.process_eml_archive_bytes
                specific_args = {
                    "file_bytes": file_bytes,
                    "archive_name": processing_filename or item_input_ref,
                    "ingest_attachments": getattr(
                        form_data,
                        "ingest_attachments",
                        False,
                    ),
                    "max_depth": getattr(form_data, "max_depth", 2),
                }
            elif name_lower.endswith(".mbox") and getattr(
                form_data,
                "accept_mbox",
                False,
            ):
                processing_func = email_lib.process_mbox_bytes
                specific_args = {
                    "file_bytes": file_bytes,
                    "mbox_name": processing_filename or item_input_ref,
                    "ingest_attachments": getattr(
                        form_data,
                        "ingest_attachments",
                        False,
                    ),
                    "max_depth": getattr(form_data, "max_depth", 2),
                }
            elif (name_lower.endswith(".pst") or name_lower.endswith(".ost")) and getattr(  # noqa: E501
                form_data,
                "accept_pst",
                False,
            ):
                processing_func = email_lib.process_pst_bytes
                specific_args = {
                    "file_bytes": file_bytes,
                    "pst_name": processing_filename or item_input_ref,
                    "ingest_attachments": getattr(
                        form_data,
                        "ingest_attachments",
                        False,
                    ),
                    "max_depth": getattr(form_data, "max_depth", 2),
                }
            else:
                processing_func = email_lib.process_email_task
                specific_args = {
                    "file_bytes": file_bytes,
                    "filename": processing_filename or item_input_ref,
                    "ingest_attachments": getattr(
                        form_data,
                        "ingest_attachments",
                        False,
                    ),
                    "max_depth": getattr(form_data, "max_depth", 2),
                }

        else:
            raise NotImplementedError(
                f"Processor not implemented for media type: '{media_type}'",
            )

        all_args = {**common_args, **specific_args}
        final_args = all_args

        if processing_func is not None:
            func_name = getattr(
                processing_func,
                "__name__",
                str(processing_func),
            )
            logging.info(
                "Calling document-like processor '%s' for '%s' %s",
                func_name,
                item_input_ref,
                "in executor" if run_in_executor else "directly",
            )
            if run_in_executor:
                target_func = functools.partial(processing_func, **final_args)
                process_result_dict = await loop.run_in_executor(
                    None,
                    target_func,
                )
            else:
                process_result_dict = await processing_func(**final_args)

            # Email containers may return a list of children.
            if media_type_str == "email" and isinstance(
                process_result_dict,
                list,
            ) and (
                getattr(form_data, "accept_archives", False)
                or getattr(form_data, "accept_mbox", False)
                or getattr(form_data, "accept_pst", False)
            ):
                final_result.update(
                    {
                        "status": "Success",
                        "media_type": "email",
                        "content": None,
                        "metadata": {
                            "title": (
                                getattr(form_data, "title", None)
                                or (processing_filename or item_input_ref)
                            ),
                            "parser_used": "builtin-email",
                        },
                        "children": process_result_dict,
                    },
                )
                try:
                    archive_name = processing_filename or item_input_ref
                    archive_keyword: Optional[str] = None
                    if archive_name:
                        lower_name = str(archive_name).lower()
                        if lower_name.endswith(".zip"):
                            archive_keyword = (
                                f"email_archive:{FilePath(archive_name).stem}"
                            )
                        elif lower_name.endswith(".mbox"):
                            archive_keyword = (
                                f"email_mbox:{FilePath(archive_name).stem}"
                            )
                        elif lower_name.endswith(".pst") or lower_name.endswith(
                            ".ost",
                        ):
                            archive_keyword = (
                                f"email_pst:{FilePath(archive_name).stem}"
                            )
                    if archive_keyword:
                        base_keywords: List[str] = []
                        try:
                            keywords_from_form = getattr(
                                form_data,
                                "keywords",
                                None,
                            )
                            if isinstance(keywords_from_form, list):
                                base_keywords = [
                                    str(keyword).strip().lower()
                                    for keyword in keywords_from_form
                                    if keyword
                                ]
                        except Exception:
                            base_keywords = []
                        merged = sorted(
                            set(
                                (final_result.get("keywords") or [])
                                + base_keywords
                                + [archive_keyword],
                            ),
                        )
                        final_result["keywords"] = merged
                except Exception:
                    # Keyword enrichment is best-effort only.
                    pass
            else:
                if not isinstance(process_result_dict, dict):
                    raise TypeError(
                        f"Processor '{func_name}' returned non-dict: "
                        f"{type(process_result_dict)}",
                    )
                final_result.update(process_result_dict)
                final_result["status"] = process_result_dict.get(
                    "status",
                    "Error"
                    if process_result_dict.get("error")
                    else "Success",
                )

            proc_warnings: Optional[Any] = None
            if isinstance(process_result_dict, dict):
                proc_warnings = process_result_dict.get("warnings")
            elif isinstance(process_result_dict, list):
                try:
                    aggregated: List[str] = []
                    for child in process_result_dict:
                        if isinstance(child, dict):
                            warnings_value = child.get("warnings")
                            if isinstance(warnings_value, list):
                                aggregated.extend(warnings_value)
                            elif warnings_value:
                                aggregated.append(str(warnings_value))
                    proc_warnings = aggregated or None
                except Exception:
                    proc_warnings = None

            if isinstance(proc_warnings, list):
                if not isinstance(final_result.get("warnings"), list):
                    final_result["warnings"] = []
                final_result["warnings"].extend(proc_warnings)
            elif proc_warnings:
                if not isinstance(final_result.get("warnings"), list):
                    final_result["warnings"] = []
                final_result["warnings"].append(str(proc_warnings))
        else:
            final_result.update(
                {
                    "status": "Error",
                    "error": "No processing function selected.",
                },
            )

    except Exception as proc_err:
        logging.error(
            "Error during processing call for %s: %s",
            item_input_ref,
            proc_err,
            exc_info=True,
        )
        final_result.update(
            {
                "status": "Error",
                "error": (
                    "Processing error: "
                    f"{type(proc_err).__name__}: {proc_err}"
                ),
            },
        )

    # --- 4. Post-Processing DB Logic ---
    final_result.setdefault("status", "Error")
    final_result["input_ref"] = item_input_ref
    final_result["media_type"] = media_type

    if final_result.get("status") in ["Success", "Warning"]:
        claims_context = await extract_claims_if_requested(
            final_result,
            form_data,
            loop,
        )
        await persist_doc_item_and_children(
            final_result=final_result,
            form_data=form_data,
            media_type=str(media_type),
            item_input_ref=item_input_ref,
            processing_filename=processing_filename,
            chunk_options=chunk_options,
            db_path=db_path,
            client_id=client_id,
            loop=loop,
            claims_context=claims_context,
        )
    else:
        final_result["db_message"] = (
            "DB operation skipped (processing failed)."
        )
        final_result["db_id"] = None
        final_result["media_uuid"] = None

    if not final_result.get("warnings"):
        final_result["warnings"] = None

    final_result["content"] = final_result.get("content")
    final_result["transcript"] = final_result.get("content")
    final_result["analysis"] = final_result.get("analysis")
    if "claims" not in final_result:
        final_result["claims"] = None
    if "claims_details" not in final_result:
        final_result["claims_details"] = None

    return final_result


async def persist_doc_item_and_children(
    *,
    final_result: Dict[str, Any],
    form_data: Any,
    media_type: str,
    item_input_ref: str,
    processing_filename: Optional[str],
    chunk_options: Optional[Dict[str, Any]],
    db_path: str,
    client_id: str,
    loop: Any,
    claims_context: Optional[Dict[str, Any]],
) -> None:
    """
    Persist a single document/email item (and any children) produced by the /add
    orchestration, mirroring the legacy post-processing DB logic.
    """
    content_for_db = final_result.get("content", "")
    analysis_for_db = final_result.get("summary") or final_result.get("analysis")
    metadata_for_db = final_result.get("metadata", {}) or {}

    extracted_keywords = final_result.get("keywords", [])
    combined_keywords = set(getattr(form_data, "keywords", None) or [])
    if isinstance(extracted_keywords, list):
        combined_keywords.update(
            k.strip().lower()
            for k in extracted_keywords
            if isinstance(k, str) and k.strip()
        )

    try:
        if media_type == "email":
            children = final_result.get("children")
            if isinstance(children, list):
                for child in children:
                    if isinstance(child, Dict):
                        child_keywords = child.get("keywords") or []
                        for kw in child_keywords:
                            if isinstance(kw, str) and kw.strip():
                                combined_keywords.add(kw.strip())
    except Exception:
        pass

    try:
        if media_type == "email" and getattr(form_data, "ingest_attachments", False):
            parent_msg_id = None
            try:
                parent_msg_id = ((metadata_for_db or {}).get("email") or {}).get(
                    "message_id"
                )
            except Exception:
                parent_msg_id = None
            if parent_msg_id:
                combined_keywords.add(f"email_group:{str(parent_msg_id)}")
        if media_type == "email" and (
            getattr(form_data, "accept_archives", False)
            or getattr(form_data, "accept_mbox", False)
            or getattr(form_data, "accept_pst", False)
        ):
            try:
                arch_name = processing_filename or item_input_ref
                if arch_name:
                    lower = str(arch_name).lower()
                    if lower.endswith(".zip"):
                        arch_tag = f"email_archive:{FilePath(arch_name).stem}"
                        combined_keywords.add(arch_tag)
                    elif lower.endswith(".mbox"):
                        arch_tag = f"email_mbox:{FilePath(arch_name).stem}"
                        combined_keywords.add(arch_tag)
                    elif lower.endswith(".pst") or lower.endswith(".ost"):
                        pst_tag = f"email_pst:{FilePath(arch_name).stem}"
                        combined_keywords.add(pst_tag)
            except Exception:
                pass
    except Exception:
        pass

    final_keywords_list = sorted(list(combined_keywords))
    try:
        final_result["keywords"] = final_keywords_list
        logging.info(
            "Archive parent keywords set for %s: %s",
            item_input_ref,
            final_keywords_list,
        )
    except Exception as kw_err:
        logging.warning("Failed to set parent keywords for %s: %s", item_input_ref, kw_err)

    model_used = metadata_for_db.get("parser_used", "Imported")
    if not model_used and media_type == "pdf":
        model_used = (final_result.get("analysis_details") or {}).get(
            "parser", "Imported"
        )

    if item_input_ref:
        default_title = FilePath(item_input_ref).stem
    else:
        default_title = "Untitled"

    title_for_db = (
        getattr(form_data, "title", None)
        or metadata_for_db.get("title")
        or default_title
    )
    author_for_db = metadata_for_db.get(
        "author",
        getattr(form_data, "author", None) or "Unknown",
    )

    if content_for_db:
        try:
            logger.info(
                "Attempting DB persistence for item: %s using user DB",
                item_input_ref,
            )
            safe_meta: Dict[str, Any] = {}
            try:
                allowed_keys = {
                    "title",
                    "author",
                    "doi",
                    "pmid",
                    "pmcid",
                    "arxiv_id",
                    "s2_paper_id",
                    "url",
                    "pdf_url",
                    "pmc_url",
                    "date",
                    "year",
                    "venue",
                    "journal",
                    "license",
                    "license_url",
                    "publisher",
                    "source",
                    "creators",
                    "rights",
                }
                for key, value in (metadata_for_db or {}).items():
                    if key in allowed_keys and isinstance(
                        value, (str, int, float, bool)
                    ):
                        safe_meta[key] = value
                    elif key in allowed_keys and isinstance(value, list):
                        safe_meta[key] = [
                            x
                            for x in value
                            if isinstance(x, (str, int, float, bool))
                        ]
                ext_ids = (metadata_for_db or {}).get("externalIds")
                if isinstance(ext_ids, dict):
                    for ext_key in ("DOI", "ArXiv", "PMID", "PMCID"):
                        if ext_ids.get(ext_key):
                            safe_meta[ext_key.lower()] = ext_ids.get(ext_key)
            except Exception:
                safe_meta = {}

            safe_metadata_json: Optional[str] = None
            try:
                if safe_meta:
                    from tldw_Server_API.app.core.Utils.metadata_utils import (  # type: ignore
                        normalize_safe_metadata,
                    )

                    try:
                        safe_meta = normalize_safe_metadata(safe_meta)
                    except Exception:
                        pass
                    safe_metadata_json = json.dumps(safe_meta, ensure_ascii=False)
            except Exception:
                safe_metadata_json = None

            chunks_for_sql: Optional[List[Dict[str, Any]]] = None
            try:
                opts = chunk_options or {}
                if opts:
                    from tldw_Server_API.app.core.Chunking.chunker import (  # type: ignore
                        Chunker as _Chunker,
                    )

                    chunker = _Chunker()
                    flat_chunks = chunker.chunk_text_hierarchical_flat(
                        content_for_db,
                        method=opts.get("method") or "sentences",
                        max_size=opts.get("max_size") or 500,
                        overlap=opts.get("overlap") or 50,
                    )
                    kind_map = {
                        "paragraph": "text",
                        "list_unordered": "list",
                        "list_ordered": "list",
                        "code_fence": "code",
                        "table_md": "table",
                        "header_line": "heading",
                        "header_atx": "heading",
                    }
                    chunks_for_sql = []
                    for item in flat_chunks:
                        meta = item.get("metadata") or {}
                        chunk_type = kind_map.get(
                            str(meta.get("paragraph_kind") or "").lower(), "text"
                        )
                        small_meta: Dict[str, Any] = {}
                        if meta.get("ancestry_titles"):
                            small_meta["ancestry_titles"] = meta.get("ancestry_titles")
                        if meta.get("section_path"):
                            small_meta["section_path"] = meta.get("section_path")
                        chunks_for_sql.append(
                            {
                                "text": item.get("text", ""),
                                "start_char": meta.get("start_offset"),
                                "end_char": meta.get("end_offset"),
                                "chunk_type": chunk_type,
                                "metadata": small_meta,
                            }
                        )
            except Exception:
                chunks_for_sql = None

            db_add_kwargs = dict(
                url=item_input_ref,
                title=title_for_db,
                media_type=media_type,
                content=content_for_db,
                keywords=final_keywords_list,
                prompt=getattr(form_data, "custom_prompt", None),
                analysis_content=analysis_for_db,
                safe_metadata=safe_metadata_json,
                transcription_model=model_used,
                author=author_for_db,
                overwrite=getattr(form_data, "overwrite_existing", False),
                chunk_options=chunk_options,
                chunks=chunks_for_sql,
            )

            def _db_worker() -> Any:
                worker_db: Optional[MediaDatabase] = None
                try:
                    worker_db = MediaDatabase(db_path=db_path, client_id=client_id)
                    return worker_db.add_media_with_keywords(**db_add_kwargs)
                finally:
                    if worker_db is not None:
                        worker_db.close_connection()

            media_id_result, media_uuid_result, db_message_result = await loop.run_in_executor(  # type: ignore[arg-type]
                None,
                _db_worker,
            )

            final_result["db_id"] = media_id_result
            final_result["db_message"] = db_message_result
            final_result["media_uuid"] = media_uuid_result
            logger.info(
                "DB persistence result for %s: ID=%s, UUID=%s, Msg='%s'",
                item_input_ref,
                media_id_result,
                media_uuid_result,
                db_message_result,
            )

            try:
                if media_type == "email" and getattr(
                    form_data, "ingest_attachments", False
                ):
                    children = final_result.get("children") or []
                    if isinstance(children, list) and children:
                        if any(
                            isinstance(child, dict)
                            and child.get("status") != "Success"
                            for child in children
                        ):
                            final_result["child_db_results"] = None
                        else:
                            child_db_results: List[Dict[str, Any]] = []
                            for child in children:
                                try:
                                    child_content = child.get("content")
                                    child_meta = child.get("metadata") or {}
                                    if not child_content:
                                        continue
                                    allowed_keys_child = {
                                        "title",
                                        "author",
                                        "doi",
                                        "pmid",
                                        "pmcid",
                                        "arxiv_id",
                                        "s2_paper_id",
                                        "url",
                                        "pdf_url",
                                        "pmc_url",
                                        "date",
                                        "year",
                                        "venue",
                                        "journal",
                                        "license",
                                        "license_url",
                                        "publisher",
                                        "source",
                                        "creators",
                                        "rights",
                                        "parent_media_uuid",
                                    }
                                    safe_child_meta = {
                                        key: value
                                        for key, value in child_meta.items()
                                        if key in allowed_keys_child
                                        and isinstance(
                                            value, (str, int, float, bool, list)
                                        )
                                    }
                                    safe_child_meta["parent_media_uuid"] = media_uuid_result
                                    try:
                                        from tldw_Server_API.app.core.Utils.metadata_utils import (  # type: ignore
                                            normalize_safe_metadata,
                                        )

                                        safe_child_meta = normalize_safe_metadata(
                                            safe_child_meta
                                        )
                                        safe_child_meta_json = json.dumps(
                                            safe_child_meta, ensure_ascii=False
                                        )
                                    except Exception:
                                        safe_child_meta_json = None

                                    child_chunks_for_sql: Optional[
                                        List[Dict[str, Any]]
                                    ] = None
                                    try:
                                        opts_child = chunk_options or {}
                                        if opts_child:
                                            from tldw_Server_API.app.core.Chunking.chunker import (  # type: ignore
                                                Chunker as _Chunker,
                                            )

                                            chunker_child = _Chunker()
                                            flat_child = (
                                                chunker_child.chunk_text_hierarchical_flat(
                                                    child_content,
                                                    method=opts_child.get("method")
                                                    or "sentences",
                                                    max_size=opts_child.get("max_size")
                                                    or 500,
                                                    overlap=opts_child.get("overlap")
                                                    or 50,
                                                )
                                            )
                                            kind_map_child = {
                                                "paragraph": "text",
                                                "list_unordered": "list",
                                                "list_ordered": "list",
                                                "code_fence": "code",
                                                "table_md": "table",
                                                "header_line": "heading",
                                                "header_atx": "heading",
                                            }
                                            child_chunks_for_sql = []
                                            for item in flat_child:
                                                meta = item.get("metadata") or {}
                                                chunk_type = kind_map_child.get(
                                                    str(
                                                        meta.get("paragraph_kind") or ""
                                                    ).lower(),
                                                    "text",
                                                )
                                                small_meta: Dict[str, Any] = {}
                                                if meta.get("ancestry_titles"):
                                                    small_meta["ancestry_titles"] = meta.get(
                                                        "ancestry_titles"
                                                    )
                                                if meta.get("section_path"):
                                                    small_meta["section_path"] = meta.get(
                                                        "section_path"
                                                    )
                                                child_chunks_for_sql.append(
                                                    {
                                                        "text": item.get("text", ""),
                                                        "start_char": meta.get(
                                                            "start_offset"
                                                        ),
                                                        "end_char": meta.get(
                                                            "end_offset"
                                                        ),
                                                        "chunk_type": chunk_type,
                                                        "metadata": small_meta,
                                                    }
                                                )
                                    except Exception:
                                        child_chunks_for_sql = None

                                    child_title = (
                                        getattr(form_data, "title", None)
                                        or child_meta.get("title")
                                        or f"{FilePath(item_input_ref).stem} (child)"
                                    )
                                    child_author = child_meta.get(
                                        "author",
                                        getattr(form_data, "author", None) or "Unknown",
                                    )
                                    child_url = (
                                        f"{item_input_ref}::child::"
                                        f"{child_meta.get('filename') or child_title}"
                                    )

                                    def _db_child_worker(
                                        child_url: str = child_url,
                                        child_title: str = child_title,
                                        child_content: str = child_content,
                                        final_keywords: List[str] = final_keywords_list,
                                        safe_child_meta_json_local: Optional[str] = safe_child_meta_json,
                                        model_used_local: Optional[str] = model_used,
                                        child_author_local: str = child_author,
                                        child_chunks_for_sql_local: Optional[
                                            List[Dict[str, Any]]
                                        ] = child_chunks_for_sql,
                                        chunk_options_local: Optional[
                                            Dict[str, Any]
                                        ] = chunk_options,
                                        form_data_local: Any = form_data,
                                        media_type_local: str = media_type,
                                        client_id_local: str = client_id,
                                        db_path_local: str = db_path,
                                    ) -> Any:
                                        worker_db: Optional[MediaDatabase] = None
                                        try:
                                            worker_db = MediaDatabase(
                                                db_path=db_path_local,
                                                client_id=client_id_local,
                                            )
                                            return worker_db.add_media_with_keywords(
                                                url=child_url,
                                                title=child_title,
                                                media_type=media_type_local,
                                                content=child_content,
                                                keywords=final_keywords,
                                                prompt=getattr(
                                                    form_data_local, "custom_prompt", None
                                                ),
                                                analysis_content=None,
                                                safe_metadata=safe_child_meta_json_local,
                                                transcription_model=model_used_local,
                                                author=child_author_local,
                                                overwrite=getattr(
                                                    form_data_local, "overwrite_existing", False
                                                ),
                                                chunk_options=chunk_options_local,
                                                chunks=child_chunks_for_sql_local,
                                            )
                                        finally:
                                            if worker_db is not None:
                                                worker_db.close_connection()

                                    (
                                        child_id,
                                        child_uuid,
                                        child_msg,
                                    ) = await loop.run_in_executor(  # type: ignore[arg-type]
                                        None,
                                        _db_child_worker,
                                    )
                                    child_db_results.append(
                                        {
                                            "db_id": child_id,
                                            "media_uuid": child_uuid,
                                            "message": child_msg,
                                            "title": child_title,
                                        }
                                    )
                                except Exception as child_db_err:
                                    logging.warning(
                                        "Child email persistence failed: %s",
                                        child_db_err,
                                    )
                            if child_db_results:
                                final_result["child_db_results"] = child_db_results
            except Exception:
                pass

        except (DatabaseError, InputError, ConflictError) as db_err:
            logger.error(
                "Database operation failed for %s: %s",
                item_input_ref,
                db_err,
                exc_info=True,
            )
            final_result["status"] = "Warning"
            final_result["error"] = (final_result.get("error") or "") + f" | DB Error: {db_err}"
            if not isinstance(final_result.get("warnings"), list):
                final_result["warnings"] = []
            final_result["warnings"].append(f"Database operation failed: {db_err}")
            final_result["db_message"] = f"DB Error: {db_err}"
            final_result["db_id"] = None
            final_result["media_uuid"] = None
        except Exception as exc:
            logger.error(
                "Unexpected error during DB persistence for %s: %s",
                item_input_ref,
                exc,
                exc_info=True,
            )
            final_result["status"] = "Warning"
            final_result["error"] = (final_result.get("error") or "")
            if not isinstance(final_result.get("warnings"), list):
                final_result["warnings"] = []
            final_result["warnings"].append(f"Unexpected persistence error: {exc}")
            final_result["db_message"] = f"Persistence Error: {type(exc).__name__}"
            final_result["db_id"] = None
            final_result["media_uuid"] = None
    else:
        persisted_any_children = False
        if media_type == "email" and (
            getattr(form_data, "accept_archives", False)
            or getattr(form_data, "accept_mbox", False)
            or getattr(form_data, "accept_pst", False)
        ):
            try:
                children = final_result.get("children") or []
                if isinstance(children, list) and children:
                    if any(
                        isinstance(child, dict) and child.get("status") != "Success"
                        for child in children
                    ):
                        final_result["child_db_results"] = None
                        persisted_any_children = False
                    else:
                        child_db_results = []
                        for child in children:
                            try:
                                child_content = child.get("content")
                                child_meta = child.get("metadata") or {}
                                if not child_content:
                                    continue
                                allowed_keys_child = {
                                    "title",
                                    "author",
                                    "doi",
                                    "pmid",
                                    "pmcid",
                                    "arxiv_id",
                                    "s2_paper_id",
                                    "url",
                                    "pdf_url",
                                    "pmc_url",
                                    "date",
                                    "year",
                                    "venue",
                                    "journal",
                                    "license",
                                    "license_url",
                                    "publisher",
                                    "source",
                                    "creators",
                                    "rights",
                                }
                                safe_child_meta = {
                                    key: value
                                    for key, value in child_meta.items()
                                    if key in allowed_keys_child
                                    and isinstance(
                                        value, (str, int, float, bool, list)
                                    )
                                }
                                safe_child_meta_json: Optional[str] = None
                                try:
                                    from tldw_Server_API.app.core.Utils.metadata_utils import (  # type: ignore
                                        normalize_safe_metadata,
                                    )

                                    safe_child_meta = normalize_safe_metadata(
                                        safe_child_meta
                                    )
                                    safe_child_meta_json = json.dumps(
                                        safe_child_meta, ensure_ascii=False
                                    )
                                except Exception:
                                    pass

                                child_chunks_for_sql: Optional[
                                    List[Dict[str, Any]]
                                ] = None
                                try:
                                    opts_child = chunk_options or {}
                                    if opts_child:
                                        from tldw_Server_API.app.core.Chunking.chunker import (  # type: ignore
                                            Chunker as _Chunker,
                                        )

                                        chunker_child = _Chunker()
                                        flat_child = (
                                            chunker_child.chunk_text_hierarchical_flat(
                                                child_content,
                                                method=opts_child.get("method")
                                                or "sentences",
                                                max_size=opts_child.get("max_size")
                                                or 500,
                                                overlap=opts_child.get("overlap") or 50,
                                            )
                                        )
                                        kind_map_child = {
                                            "paragraph": "text",
                                            "list_unordered": "list",
                                            "list_ordered": "list",
                                            "code_fence": "code",
                                            "table_md": "table",
                                            "header_line": "heading",
                                            "header_atx": "heading",
                                        }
                                        child_chunks_for_sql = []
                                        for item in flat_child:
                                            meta = item.get("metadata") or {}
                                            chunk_type = kind_map_child.get(
                                                str(meta.get("paragraph_kind") or "").lower(),
                                                "text",
                                            )
                                            small_meta: Dict[str, Any] = {}
                                            if meta.get("ancestry_titles"):
                                                small_meta["ancestry_titles"] = meta.get(
                                                    "ancestry_titles"
                                                )
                                            if meta.get("section_path"):
                                                small_meta["section_path"] = meta.get(
                                                    "section_path"
                                                )
                                            child_chunks_for_sql.append(
                                                {
                                                    "text": item.get("text", ""),
                                                    "start_char": meta.get(
                                                        "start_offset"
                                                    ),
                                                    "end_char": meta.get("end_offset"),
                                                    "chunk_type": chunk_type,
                                                    "metadata": small_meta,
                                                }
                                            )
                                except Exception:
                                    child_chunks_for_sql = None

                                child_title = (
                                    getattr(form_data, "title", None)
                                    or child_meta.get("title")
                                    or f"{FilePath(item_input_ref).stem} (archive child)"
                                )
                                child_author = child_meta.get(
                                    "author",
                                    getattr(form_data, "author", None) or "Unknown",
                                )
                                child_url = (
                                    f"{item_input_ref}::archive::"
                                    f"{child_meta.get('filename') or child_title}"
                                )

                                def _db_child_arch_worker(
                                    child_url_local: str = child_url,
                                    child_title_local: str = child_title,
                                    child_content_local: str = child_content,
                                    final_keywords_local: List[str] = final_keywords_list,
                                    safe_child_meta_json_local: Optional[str] = safe_child_meta_json,
                                    model_used_local: Optional[str] = model_used,
                                    child_author_local: str = child_author,
                                    child_chunks_for_sql_local: Optional[
                                        List[Dict[str, Any]]
                                    ] = child_chunks_for_sql,
                                    media_type_local: str = media_type,
                                    form_data_local: Any = form_data,
                                    chunk_options_local: Optional[
                                        Dict[str, Any]
                                    ] = chunk_options,
                                    db_path_local: str = db_path,
                                    client_id_local: str = client_id,
                                ) -> Any:
                                    worker_db: Optional[MediaDatabase] = None
                                    try:
                                        worker_db = MediaDatabase(
                                            db_path=db_path_local,
                                            client_id=client_id_local,
                                        )
                                        return worker_db.add_media_with_keywords(
                                            url=child_url_local,
                                            title=child_title_local,
                                            media_type=media_type_local,
                                            content=child_content_local,
                                            keywords=final_keywords_local,
                                            prompt=getattr(
                                                form_data_local, "custom_prompt", None
                                            ),
                                            analysis_content=None,
                                            safe_metadata=safe_child_meta_json_local,
                                            transcription_model=model_used_local,
                                            author=child_author_local,
                                            overwrite=getattr(
                                                form_data_local, "overwrite_existing", False
                                            ),
                                            chunk_options=chunk_options_local,
                                            chunks=child_chunks_for_sql_local,
                                        )
                                    finally:
                                        if worker_db is not None:
                                            worker_db.close_connection()

                                (
                                    child_id,
                                    child_uuid,
                                    child_msg,
                                ) = await loop.run_in_executor(  # type: ignore[arg-type]
                                    None,
                                    _db_child_arch_worker,
                                )
                                child_db_results.append(
                                    {
                                        "db_id": child_id,
                                        "media_uuid": child_uuid,
                                        "message": child_msg,
                                        "title": child_title,
                                    }
                                )
                                persisted_any_children = True
                            except Exception as child_db_err:
                                logging.warning(
                                    "Archive child email persistence failed: %s",
                                    child_db_err,
                                )
                        try:
                            if child_db_results:
                                final_result["child_db_results"] = child_db_results
                        except Exception:
                            pass
            except Exception:
                pass

        if not persisted_any_children:
            logger.warning(
                "Skipping DB persistence for %s due to missing content.",
                item_input_ref,
            )
            final_result["db_message"] = "DB persistence skipped (no content)."
            final_result["db_id"] = None
            final_result["media_uuid"] = None
        else:
            final_result["db_message"] = "Persisted archive children."

    await persist_claims_if_applicable(
        claims_context=claims_context,
        media_id=final_result.get("db_id"),
        db_path=db_path,
        client_id=client_id,
        loop=loop,
        process_result=final_result,
    )


__all__ = [
    "add_media_orchestrate",
    "add_media_persist",
    "persist_primary_av_item",
    "persist_doc_item_and_children",
]
