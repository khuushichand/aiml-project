from __future__ import annotations

from typing import Any, Dict, List, Optional

import asyncio
import logging
import json
import os
from pathlib import Path as FilePath

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


try:  # Align HTTP 413 compatibility with legacy endpoint module
    HTTP_413_TOO_LARGE = status.HTTP_413_CONTENT_TOO_LARGE
except AttributeError:  # Starlette < 0.27
    HTTP_413_TOO_LARGE = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


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
    reusing helper functions defined in that module.
    """
    # Imported lazily to avoid circular imports at module import time.
    from tldw_Server_API.app.api.v1.endpoints import (  # type: ignore
        _legacy_media as legacy_media,
    )

    _validate_inputs = legacy_media._validate_inputs  # type: ignore[attr-defined]
    _prepare_chunking_options_dict = legacy_media._prepare_chunking_options_dict  # type: ignore[attr-defined]
    _prepare_common_options = legacy_media._prepare_common_options  # type: ignore[attr-defined]
    _process_batch_media = legacy_media._process_batch_media  # type: ignore[attr-defined]
    _process_document_like_item = legacy_media._process_document_like_item  # type: ignore[attr-defined]
    _determine_final_status = legacy_media._determine_final_status  # type: ignore[attr-defined]
    _save_uploaded_files = legacy_media._save_uploaded_files  # type: ignore[attr-defined]
    file_validator_instance = legacy_media.file_validator_instance  # type: ignore[attr-defined]
    TemplateClassifier = legacy_media.TemplateClassifier  # type: ignore[attr-defined]

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
    temp_dir_manager = legacy_media.TempDirManager(  # type: ignore[attr-defined]
        cleanup=not form_data.keep_original_file
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
                            # This mirrors the legacy behaviour, including its
                            # reliance on Path from FastAPI (errors are ignored).
                            total_uploaded_bytes += Path(  # type: ignore[arg-type]
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

            try:
                if form_data.perform_chunking:
                    # 1) Apply explicit template by name
                    if getattr(form_data, "chunking_template_name", None):
                        tpl = db.get_chunking_template(
                            name=form_data.chunking_template_name
                        )
                        if tpl and tpl.get("template_json"):
                            raw_cfg = tpl["template_json"]
                            cfg = (
                                json.loads(raw_cfg)
                                if isinstance(raw_cfg, str)
                                else raw_cfg
                            )
                            hier_cfg = ((cfg or {}).get("chunking") or {}).get(
                                "config", {}
                            )
                            if isinstance(
                                hier_cfg.get("hierarchical_template"), dict
                            ):
                                chunking_options_dict = chunking_options_dict or {}
                                tpl_method = (
                                    (cfg.get("chunking") or {}).get("method")
                                    or "sentences"
                                )
                                if not form_data.chunk_method:
                                    chunking_options_dict.setdefault(
                                        "method", tpl_method
                                    )
                                chunking_options_dict["hierarchical"] = True
                                chunking_options_dict["hierarchical_template"] = (
                                    hier_cfg["hierarchical_template"]
                                )
                    # 2) Respect explicit user hierarchical/method
                    # (already encoded in chunking_options_dict)
                    # 3) Auto-match when requested and user didn't request
                    #    hierarchical explicitly.
                    elif getattr(form_data, "auto_apply_template", False) and not getattr(
                        form_data, "hierarchical_chunking", False
                    ):
                        candidates = db.list_chunking_templates(
                            include_builtin=True,
                            include_custom=True,
                            tags=None,
                            user_id=None,
                            include_deleted=False,
                        )
                        first_url = (form_data.urls or [None])[0]
                        first_filename = None
                        try:
                            if saved_files_info:
                                first_filename = saved_files_info[0][
                                    "original_filename"
                                ]
                        except Exception:
                            first_filename = None
                        best_cfg = None
                        best_key = None
                        for t in candidates:
                            try:
                                cfg = json.loads(
                                    t.get("template_json") or "{}"
                                )
                                if not isinstance(cfg, dict):
                                    cfg = {}
                            except Exception:
                                cfg = {}
                            score = TemplateClassifier.score(
                                cfg,
                                media_type=form_data.media_type,
                                title=form_data.title,
                                url=first_url,
                                filename=first_filename,
                            )
                            if score <= 0:
                                continue
                            priority = (
                                (cfg.get("classifier") or {}).get(
                                    "priority"
                                )
                                or 0
                            )
                            key = (score, priority)
                            if best_cfg is None or key > best_key:
                                best_cfg, best_key = cfg, key
                        if best_cfg:
                            hier_cfg = (
                                (best_cfg.get("chunking") or {}).get(
                                    "config"
                                )
                                or {}
                            )
                            tpl = hier_cfg.get("hierarchical_template")
                            if isinstance(tpl, dict):
                                chunking_options_dict = (
                                    chunking_options_dict or {}
                                )
                                if not form_data.chunk_method:
                                    chunking_options_dict.setdefault(
                                        "method",
                                        (best_cfg.get("chunking") or {}).get(
                                            "method", "sentences"
                                        ),
                                    )
                                chunking_options_dict["hierarchical"] = True
                                chunking_options_dict[
                                    "hierarchical_template"
                                ] = tpl
            except Exception as auto_err:
                logger.warning(
                    "Auto-apply chunking template failed: %s", auto_err
                )

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
                batch_results = await _process_batch_media(
                    media_type=form_data.media_type,
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
                    _process_document_like_item(
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
        from tldw_Server_API.app.api.v1.endpoints import (  # type: ignore
            _legacy_media as legacy_media,
        )

        process_result["db_message"] = "DB persistence skipped (no content)."
        process_result["db_id"] = None
        process_result["media_uuid"] = None
        await legacy_media._persist_claims_if_applicable(  # type: ignore[attr-defined]
            claims_context,
            None,
            db_path,
            client_id,
            loop,
            process_result,
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

        from tldw_Server_API.app.api.v1.endpoints import (  # type: ignore
            _legacy_media as legacy_media,
        )

        await legacy_media._persist_claims_if_applicable(  # type: ignore[attr-defined]
            claims_context,
            process_result.get("db_id"),
            db_path,
            client_id,
            loop,
            process_result,
        )

        logger.info(
            "DB persistence result for %s: ID=%s, UUID=%s, Msg='%s'",
            original_input_ref,
            media_id_result,
            media_uuid_result,
            db_message_result,
        )

    except (DatabaseError, InputError, ConflictError) as db_err:
        from tldw_Server_API.app.api.v1.endpoints import (  # type: ignore
            _legacy_media as legacy_media,
        )

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
        await legacy_media._persist_claims_if_applicable(  # type: ignore[attr-defined]
            claims_context,
            None,
            db_path,
            client_id,
            loop,
            process_result,
        )

    except Exception as exc:
        from tldw_Server_API.app.api.v1.endpoints import (  # type: ignore
            _legacy_media as legacy_media,
        )

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
        await legacy_media._persist_claims_if_applicable(  # type: ignore[attr-defined]
            claims_context,
            None,
            db_path,
            client_id,
            loop,
            process_result,
        )


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

    from tldw_Server_API.app.api.v1.endpoints import (  # type: ignore
        _legacy_media as legacy_media,
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

                                    def _db_child_worker() -> Any:
                                        worker_db: Optional[MediaDatabase] = None
                                        try:
                                            worker_db = MediaDatabase(
                                                db_path=db_path,
                                                client_id=client_id,
                                            )
                                            return worker_db.add_media_with_keywords(
                                                url=child_url,
                                                title=child_title,
                                                media_type=media_type,
                                                content=child_content,
                                                keywords=final_keywords_list,
                                                prompt=getattr(
                                                    form_data, "custom_prompt", None
                                                ),
                                                analysis_content=None,
                                                safe_metadata=safe_child_meta_json,
                                                transcription_model=model_used,
                                                author=child_author,
                                                overwrite=getattr(
                                                    form_data, "overwrite_existing", False
                                                ),
                                                chunk_options=chunk_options,
                                                chunks=child_chunks_for_sql,
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
                                    _child_url: str,
                                    _child_title: str,
                                    _child_content: str,
                                    _final_keywords: List[str],
                                    _safe_child_meta_json: Optional[str],
                                    _model_used: Optional[str],
                                    _child_author: str,
                                    _child_chunks_for_sql: Optional[List[Dict[str, Any]]],
                                    _media_type: str,
                                    _form_data: Any,
                                    _chunk_options: Optional[Dict[str, Any]],
                                    _db_path: str,
                                    _client_id: str,
                                ) -> Any:
                                    worker_db: Optional[MediaDatabase] = None
                                    try:
                                        worker_db = MediaDatabase(
                                            db_path=_db_path,
                                            client_id=_client_id,
                                        )
                                        return worker_db.add_media_with_keywords(
                                            url=_child_url,
                                            title=_child_title,
                                            media_type=_media_type,
                                            content=_child_content,
                                            keywords=_final_keywords,
                                            prompt=getattr(
                                                _form_data, "custom_prompt", None
                                            ),
                                            analysis_content=None,
                                            safe_metadata=_safe_child_meta_json,
                                            transcription_model=_model_used,
                                            author=_child_author,
                                            overwrite=getattr(
                                                _form_data, "overwrite_existing", False
                                            ),
                                            chunk_options=_chunk_options,
                                            chunks=_child_chunks_for_sql,
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
                                    child_url,
                                    child_title,
                                    child_content,
                                    final_keywords_list,
                                    safe_child_meta_json,
                                    model_used,
                                    child_author,
                                    child_chunks_for_sql,
                                    media_type,
                                    form_data,
                                    chunk_options,
                                    db_path,
                                    client_id,
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

    await legacy_media._persist_claims_if_applicable(  # type: ignore[attr-defined]
        claims_context,
        final_result.get("db_id"),
        db_path,
        client_id,
        loop,
        final_result,
    )


__all__ = [
    "add_media_orchestrate",
    "add_media_persist",
    "persist_primary_av_item",
    "persist_doc_item_and_children",
]
