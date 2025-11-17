from __future__ import annotations

from typing import Any, Dict, List, Optional

import logging
import json
from pathlib import Path as FilePath

from fastapi import BackgroundTasks, UploadFile
from loguru import logger

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (
    ConflictError,
    DatabaseError,
    InputError,
    MediaDatabase,
)


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

    For now this preserves the legacy `_legacy_media.add_media`
    implementation while providing a single indirection point that can
    be refactored to call the Stage 3 processors and persistence
    helpers directly.
    """
    # Imported lazily to avoid circular imports at module import time.
    from tldw_Server_API.app.api.v1.endpoints import (  # type: ignore
        _legacy_media as legacy_media,
    )

    return await legacy_media._add_media_impl(  # type: ignore[attr-defined]
        background_tasks=background_tasks,
        form_data=form_data,
        files=files,
        db=db,
        current_user=current_user,
        usage_log=usage_log,
        response=response,
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
                # If processing produced extra chunks (e.g., VLM), merge them.
                try:
                    extra_chunks = (process_result or {}).get("extra_chunks")
                    if isinstance(extra_chunks, List) and extra_chunks:
                        for ec in extra_chunks:
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

                                def _db_child_arch_worker() -> Any:
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
