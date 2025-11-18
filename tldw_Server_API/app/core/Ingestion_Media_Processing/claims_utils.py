from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

import asyncio
import functools

from loguru import logger

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Ingestion_Media_Processing.Claims.ingestion_claims import (
    extract_claims_for_chunks,
    store_claims,
)
from tldw_Server_API.app.core.config import settings


def claims_extraction_enabled(form_data: Any) -> bool:
    """
    Determine whether claim extraction should run for this request.

    This mirrors `_legacy_media._claims_extraction_enabled` so behaviour
    remains unchanged while the logic lives in core.
    """
    value = getattr(form_data, "perform_claims_extraction", None)
    if value is not None:
        return bool(value)
    try:
        return bool(settings.get("ENABLE_INGESTION_CLAIMS", False))
    except Exception:
        return False


def resolve_claims_parameters(form_data: Any) -> Tuple[str, int]:
    """
    Resolve extractor mode and max claims per chunk from request or settings.
    """
    mode = getattr(form_data, "claims_extractor_mode", None)
    if isinstance(mode, str) and mode.strip():
        extractor_mode = mode.strip()
    else:
        try:
            extractor_mode = str(settings.get("CLAIM_EXTRACTOR_MODE", "heuristic"))
        except Exception:
            extractor_mode = "heuristic"

    max_per = getattr(form_data, "claims_max_per_chunk", None)
    if max_per is None:
        try:
            max_per = int(settings.get("CLAIMS_MAX_PER_CHUNK", 3))
        except Exception:
            max_per = 3
    else:
        try:
            max_per = int(max_per)
        except Exception:
            max_per = 3
    if max_per <= 0:
        max_per = 1
    return extractor_mode, max_per


def prepare_claims_chunks(
    process_result: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[int, str]]:
    """
    Build a chunk list and index->text map suitable for claim extraction.

    Prefers existing chunks, falls back to segments, and finally full content.
    Mirrors `_legacy_media._prepare_claims_chunks`.
    """
    prepared_chunks: List[Dict[str, Any]] = []
    chunk_text_map: Dict[int, str] = {}

    raw_chunks = process_result.get("chunks")
    if isinstance(raw_chunks, list):
        for idx, chunk in enumerate(raw_chunks):
            if not isinstance(chunk, dict):
                continue
            text = str(chunk.get("text") or "").strip()
            if not text:
                continue
            meta = {"chunk_index": idx, "source": "chunk"}
            prepared_chunks.append({"text": text, "metadata": meta})
            chunk_text_map[idx] = text

    if not prepared_chunks:
        segments = process_result.get("segments")
        if isinstance(segments, list):
            for idx, segment in enumerate(segments):
                seg_dict = segment or {}
                text = str(seg_dict.get("text") or "").strip()
                if not text:
                    continue
                meta = {
                    "chunk_index": idx,
                    "segment_start": seg_dict.get("start"),
                    "segment_end": seg_dict.get("end"),
                    "source": "segment",
                }
                prepared_chunks.append({"text": text, "metadata": meta})
                chunk_text_map[idx] = text

    if not prepared_chunks:
        content = process_result.get("content")
        if isinstance(content, str) and content.strip():
            meta = {"chunk_index": 0, "source": "content"}
            prepared_chunks.append({"text": content, "metadata": meta})
            chunk_text_map[0] = content

    return prepared_chunks, chunk_text_map


async def extract_claims_if_requested(
    process_result: Dict[str, Any],
    form_data: Any,
    loop: asyncio.AbstractEventLoop,
) -> Optional[Dict[str, Any]]:
    """
    Optionally extract claims for a processing result.

    This is the core implementation used by ingestion helpers; it
    mirrors `_legacy_media._extract_claims_if_requested`.
    """
    process_result.setdefault("claims", None)
    process_result.setdefault("claims_details", None)

    if not claims_extraction_enabled(form_data):
        return None

    prepared_chunks, chunk_text_map = prepare_claims_chunks(process_result)
    extractor_mode, max_per_chunk = resolve_claims_parameters(form_data)

    if not prepared_chunks:
        process_result["claims"] = None
        process_result["claims_details"] = {
            "enabled": True,
            "extractor": extractor_mode,
            "claim_count": 0,
            "chunks_evaluated": 0,
            "reason": "no_chunks_available",
        }
        return {
            "claims": [],
            "chunk_text_map": chunk_text_map,
            "extractor": extractor_mode,
            "max_per_chunk": max_per_chunk,
        }

    extraction_callable: Callable[[], List[Dict[str, Any]]] = functools.partial(
        extract_claims_for_chunks,
        prepared_chunks,
        extractor_mode=extractor_mode,
        max_per_chunk=max_per_chunk,
    )

    try:
        claims = await loop.run_in_executor(None, extraction_callable)
    except Exception as exc:  # pragma: no cover - error path
        process_result["claims"] = None
        process_result["claims_details"] = {
            "enabled": True,
            "extractor": extractor_mode,
            "error": str(exc),
            "chunks_evaluated": len(prepared_chunks),
        }
        return None

    claim_count = len(claims or [])
    if claim_count == 0:
        process_result["claims"] = None
        process_result["claims_details"] = {
            "enabled": True,
            "extractor": extractor_mode,
            "claim_count": 0,
            "max_per_chunk": max_per_chunk,
            "chunks_evaluated": len(prepared_chunks),
        }
    else:
        process_result["claims"] = claims
        process_result["claims_details"] = {
            "enabled": True,
            "extractor": extractor_mode,
            "claim_count": claim_count,
            "max_per_chunk": max_per_chunk,
            "chunks_evaluated": len(prepared_chunks),
        }

    return {
        "claims": claims or [],
        "chunk_text_map": chunk_text_map,
        "extractor": extractor_mode,
        "max_per_chunk": max_per_chunk,
    }


async def persist_claims_if_applicable(
    claims_context: Optional[Dict[str, Any]],
    media_id: Optional[int],
    db_path: str,
    client_id: str,
    loop: asyncio.AbstractEventLoop,
    process_result: Dict[str, Any],
) -> None:
    """
    Persist extracted claims to the database when a media id is available.

    Shared between legacy ingestion and core helpers so behaviour remains
    consistent regardless of the entrypoint.
    """
    details = process_result.get("claims_details")
    if not isinstance(details, dict):
        details = None

    if (
        not claims_context
        or not claims_context.get("claims")
        or not media_id
        or not db_path
    ):
        if details is not None:
            details.setdefault("stored_in_db", 0)
            process_result["claims_details"] = details
        return

    def _worker() -> int:
        db = MediaDatabase(db_path=db_path, client_id=client_id)
        try:
            try:
                db.soft_delete_claims_for_media(int(media_id))
            except Exception:
                pass
            inserted = store_claims(
                db,
                media_id=int(media_id),
                chunk_texts_by_index=claims_context.get("chunk_text_map", {}),
                claims=claims_context.get("claims", []),
                extractor=claims_context.get("extractor") or "heuristic",
                extractor_version="v1",
            )
            return inserted
        finally:
            try:
                db.close_connection()
            except Exception:
                pass

    try:
        inserted_count = await loop.run_in_executor(None, _worker)
        if details is None:
            details = {}
        details["stored_in_db"] = int(inserted_count or 0)
        process_result["claims_details"] = details
    except Exception as exc:  # pragma: no cover - error path
        if details is None:
            details = {}
        details["stored_in_db"] = 0
        details["storage_error"] = str(exc)
        process_result["claims_details"] = details


__all__ = [
    "claims_extraction_enabled",
    "resolve_claims_parameters",
    "prepare_claims_chunks",
    "extract_claims_if_requested",
    "persist_claims_if_applicable",
]

