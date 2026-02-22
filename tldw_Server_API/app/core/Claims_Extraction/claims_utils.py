from __future__ import annotations

import asyncio
import contextlib
import functools
from sqlite3 import Error as SQLiteError
from typing import Any, Callable

from loguru import logger

from tldw_Server_API.app.core.Claims_Extraction.budget_guard import (
    ClaimsJobBudget,
    resolve_claims_job_budget,
)
from tldw_Server_API.app.core.Claims_Extraction.extractor_catalog import resolve_claims_extractor_mode
from tldw_Server_API.app.core.Claims_Extraction.ingestion_claims import (
    extract_claims_for_chunks,
    store_claims,
)
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.testing import is_truthy

_SETTINGS_LOOKUP_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_FORM_ACCESS_EXCEPTIONS = (AttributeError, RuntimeError, TypeError, ValueError)
_CLAIMS_PROCESSING_EXCEPTIONS = (
    AssertionError,
    LookupError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
)
_CLAIMS_DB_EXCEPTIONS = (
    OSError,
    RuntimeError,
    SQLiteError,
    TimeoutError,
    TypeError,
    ValueError,
)


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
    except _SETTINGS_LOOKUP_EXCEPTIONS:
        return False


def resolve_claims_parameters(form_data: Any) -> tuple[str, int]:
    """
    Resolve extractor mode and max claims per chunk from request or settings.
    """
    mode = getattr(form_data, "claims_extractor_mode", None)
    if isinstance(mode, str) and mode.strip():
        extractor_mode = mode.strip()
    else:
        try:
            extractor_mode = str(settings.get("CLAIM_EXTRACTOR_MODE", "heuristic"))
        except _SETTINGS_LOOKUP_EXCEPTIONS:
            extractor_mode = "heuristic"

    max_per = getattr(form_data, "claims_max_per_chunk", None)
    if max_per is None:
        try:
            max_per = int(settings.get("CLAIMS_MAX_PER_CHUNK", 3))
        except _SETTINGS_LOOKUP_EXCEPTIONS:
            max_per = 3
    else:
        try:
            max_per = int(max_per)
        except (TypeError, ValueError):
            max_per = 3
    if max_per <= 0:
        max_per = 1
    return extractor_mode, max_per


def prepare_claims_chunks(
    process_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[int, str]]:
    """
    Build a chunk list and index->text map suitable for claim extraction.

    Prefers existing chunks, falls back to segments, and finally full content.
    Mirrors `_legacy_media._prepare_claims_chunks`.
    """
    prepared_chunks: list[dict[str, Any]] = []
    chunk_text_map: dict[int, str] = {}

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
    process_result: dict[str, Any],
    form_data: Any,
    loop: asyncio.AbstractEventLoop,
) -> dict[str, Any] | None:
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
    detected_language = None
    if extractor_mode.strip().lower() in {"auto", "detect"}:
        combined_text = " ".join(ch.get("text", "") for ch in prepared_chunks if isinstance(ch, dict))
        extractor_mode, detected_language = resolve_claims_extractor_mode(extractor_mode, combined_text)

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

    budget: ClaimsJobBudget | None = None
    try:
        budget_usd = getattr(form_data, "claims_budget_usd", None)
    except _FORM_ACCESS_EXCEPTIONS:
        budget_usd = None
    try:
        budget_tokens = getattr(form_data, "claims_budget_tokens", None)
    except _FORM_ACCESS_EXCEPTIONS:
        budget_tokens = None
    try:
        budget_strict = getattr(form_data, "claims_budget_strict", None)
    except _FORM_ACCESS_EXCEPTIONS:
        budget_strict = None
    try:
        budget_usd = float(budget_usd) if budget_usd is not None else None
    except (TypeError, ValueError):
        budget_usd = None
    try:
        budget_tokens = int(budget_tokens) if budget_tokens is not None else None
    except (TypeError, ValueError):
        budget_tokens = None
    if isinstance(budget_strict, str):
        budget_strict = is_truthy(budget_strict)
    budget = resolve_claims_job_budget(
        settings=settings,
        max_cost_usd=budget_usd,
        max_tokens=budget_tokens,
        strict=budget_strict if isinstance(budget_strict, bool) else None,
    )

    extraction_callable: Callable[[], list[dict[str, Any]]] = functools.partial(
        extract_claims_for_chunks,
        prepared_chunks,
        extractor_mode=extractor_mode,
        max_per_chunk=max_per_chunk,
        language=detected_language,
        budget=budget,
    )

    try:
        claims = await loop.run_in_executor(None, extraction_callable)
    except _CLAIMS_PROCESSING_EXCEPTIONS as exc:  # pragma: no cover - error path
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
    if budget is not None:
        process_result.setdefault("claims_details", {})["budget"] = budget.snapshot()
    if detected_language:
        process_result.setdefault("claims_details", {})["language"] = detected_language

    return {
        "claims": claims or [],
        "chunk_text_map": chunk_text_map,
        "extractor": extractor_mode,
        "max_per_chunk": max_per_chunk,
    }


async def persist_claims_if_applicable(
    claims_context: dict[str, Any] | None,
    media_id: int | None,
    db_path: str,
    client_id: str,
    loop: asyncio.AbstractEventLoop,
    process_result: dict[str, Any],
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
        or not media_id
        or not db_path
    ):
        if details is not None:
            details.setdefault("stored_in_db", 0)
            process_result["claims_details"] = details
        return

    claims = claims_context.get("claims") or []

    def _worker() -> int:
        db = MediaDatabase(db_path=db_path, client_id=client_id)
        try:
            try:
                db.soft_delete_claims_for_media(int(media_id))
            except _CLAIMS_DB_EXCEPTIONS as e:
                logger.exception(
                    "Failed to soft delete claims for media {}: {}",
                    media_id,
                    e,
                )
            inserted = store_claims(
                db,
                media_id=int(media_id),
                chunk_texts_by_index=claims_context.get("chunk_text_map", {}),
                claims=claims,
                extractor=claims_context.get("extractor") or "heuristic",
                extractor_version="v1",
            )
            return inserted
        finally:
            with contextlib.suppress(_CLAIMS_DB_EXCEPTIONS):
                db.close_connection()

    try:
        inserted_count = await loop.run_in_executor(None, _worker)
        if details is None:
            details = {}
        details["stored_in_db"] = int(inserted_count or 0)
        process_result["claims_details"] = details
    except _CLAIMS_PROCESSING_EXCEPTIONS as exc:  # pragma: no cover - error path
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
