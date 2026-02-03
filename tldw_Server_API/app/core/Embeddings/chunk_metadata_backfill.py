"""
Helpers for backfilling normalized chunk metadata in Chroma collections.
"""

from typing import Any, Optional

from tldw_Server_API.app.core.Chunking import Chunker


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
            try:
                return int(stripped)
            except Exception:
                return None
    return None


def normalize_chunk_metadata(
    metadata: Optional[dict[str, Any]],
    *,
    fill_offsets: bool = True,
    default_chunk_type: Optional[str] = None,
) -> tuple[dict[str, Any], bool]:
    """Normalize chunk metadata fields, returning (updated, changed)."""
    if not isinstance(metadata, dict):
        metadata = {}

    updated = dict(metadata)
    changed = False

    raw_chunk_type = (
        updated.get("chunk_type")
        or updated.get("paragraph_kind")
        or updated.get("kind")
        or updated.get("type")
    )
    normalized = Chunker.normalize_chunk_type(raw_chunk_type)
    if normalized:
        if updated.get("chunk_type") != normalized:
            updated["chunk_type"] = normalized
            changed = True
    elif default_chunk_type and not updated.get("chunk_type"):
        updated["chunk_type"] = default_chunk_type
        changed = True

    if fill_offsets:
        if updated.get("start_char") is None:
            start_val = (
                updated.get("start_index")
                or updated.get("start_offset")
                or updated.get("start")
            )
            start_int = _coerce_int(start_val)
            if start_int is not None:
                updated["start_char"] = start_int
                changed = True
        if updated.get("end_char") is None:
            end_val = (
                updated.get("end_index")
                or updated.get("end_offset")
                or updated.get("end")
            )
            end_int = _coerce_int(end_val)
            if end_int is not None:
                updated["end_char"] = end_int
                changed = True

    return updated, changed


__all__ = ["normalize_chunk_metadata"]
