from __future__ import annotations

"""
Helpers for normalizing process-only media results.

Stage 3 of the /media refactor introduces a small set of internal models and
utilities so that process-* endpoints share a consistent response shape while
preserving the existing HTTP envelopes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class MediaItemProcessResponse:
    """
    Internal representation of a single process-only media result.

    This mirrors the dict structure returned today by the legacy media
    endpoints (status, input_ref, media_type, content, metadata, chunks,
    analysis, keywords, warnings, error, db_id, db_message, etc.) while
    remaining an internal type – HTTP responses still expose plain dicts.
    """

    status: str
    input_ref: str
    processing_source: Optional[str] = None
    media_type: Optional[str] = None
    content: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunks: Optional[Any] = None
    analysis: Optional[Any] = None
    analysis_details: Dict[str, Any] = field(default_factory=dict)
    keywords: Optional[Any] = None
    warnings: Optional[Any] = None
    error: Optional[str] = None
    db_id: Optional[int] = None
    db_message: Optional[str] = None


def sort_results_success_first(results: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return results with Success/Warning entries before Error entries.

    Several process-* endpoints rely on this ordering so that tests which
    inspect the first item see a successful or warning result when possible.
    """

    def _key(r: Dict[str, Any]) -> int:
        status_value = str(r.get("status", "")).lower()
        return 0 if status_value in {"success", "warning"} else 1

    return sorted(list(results), key=_key)


def normalize_process_batch(batch: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a process-only batch in-place.

    - Orders results with successes/warnings first.
    - Ensures standard counters and error lists are always present.
    """
    try:
        batch["results"] = sort_results_success_first(batch.get("results") or [])
    except Exception:
        # Keep batch unchanged on any sorting error; callers preserve behavior.
        pass

    # Ensure common keys exist; keep existing counts if already set.
    batch.setdefault("processed_count", int(batch.get("processed_count", 0) or 0))
    batch.setdefault("errors_count", int(batch.get("errors_count", 0) or 0))
    batch.setdefault("errors", batch.get("errors") or [])
    return batch


def normalise_pdf_result(item: Dict[str, Any], original_ref: str) -> Dict[str, Any]:
    """
    Ensure every required key is present and correctly typed for PDF results.

    This mirrors the legacy `_legacy_media.normalise_pdf_result` helper so
    that process-only PDF endpoints share a consistent, fully-populated
    result shape.
    """
    # Ensure base keys are present
    item.setdefault("status", "Error")
    item["input_ref"] = original_ref
    item.setdefault("processing_source", original_ref)
    item.setdefault("media_type", "pdf")

    # Ensure metadata is a dict (can be empty)
    metadata = item.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {"original_metadata": metadata}
    item["metadata"] = metadata

    # Keys that can be None
    item.setdefault("content", None)
    item.setdefault("chunks", None)
    item.setdefault("analysis", None)
    item.setdefault("warnings", None)
    item.setdefault("error", None)
    item.setdefault("segments", None)

    # Analysis details should be a dict
    analysis_details = item.get("analysis_details") or {}
    if not isinstance(analysis_details, dict):
        analysis_details = {"original_details": analysis_details}
    item["analysis_details"] = analysis_details

    # Normalize keywords to a list
    keywords = item.get("keywords", metadata.get("keywords"))
    if keywords is None:
        keywords_list: List[str] = []
    elif isinstance(keywords, list):
        keywords_list = keywords
    elif isinstance(keywords, str):
        keywords_list = [k.strip() for k in keywords.split(",") if k.strip()]
    else:
        keywords_list = [str(keywords)]
    item["keywords"] = keywords_list

    # No persistence on this endpoint
    item["db_id"] = None
    item.setdefault("db_message", "Processing only endpoint.")

    return item


__all__ = [
    "MediaItemProcessResponse",
    "sort_results_success_first",
    "normalize_process_batch",
    "normalise_pdf_result",
]
