"""
Request parsing and normalization helpers for API v1.

These utilities encapsulate common form/query coercions used by
media and related endpoints, so behavior is consistent and easy
to unit test.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence

from tldw_Server_API.app.core.TTS.utils import parse_bool as _tts_parse_bool


def to_bool(value: Any, default: Optional[bool] = False) -> bool:
    """
    Coerce a value into a boolean.

    Delegates to the shared TTS `parse_bool` helper so behavior is
    consistent across the project.
    """
    return _tts_parse_bool(value, default=default)


def to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """
    Coerce a value into an integer.

    - Returns `default` on None or empty string.
    - Returns `default` on parse failure.
    """
    if value is None:
        return default
    if isinstance(value, int):
        return value
    try:
        s = str(value).strip()
        if s == "":
            return default
        return int(s)
    except (TypeError, ValueError):
        return default


def _split_on_delimiters(raw: str) -> List[str]:
    """Split a string on commas, semicolons, or whitespace."""
    parts: List[str] = []
    current = []
    for ch in raw:
        if ch in {",", ";", " ", "\t", "\n", "\r"}:
            if current:
                parts.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def normalize_str_list(value: Any) -> List[str]:
    """
    Normalize various list representations into a clean list of strings.

    Accepts:
    - None -> []
    - List/tuple of values -> each coerced to stripped string; empties removed.
    - Single string -> split on commas/semicolons/whitespace.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        out: List[str] = []
        for item in value:
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    if isinstance(value, str):
        return [s for s in _split_on_delimiters(value.strip()) if s]
    # Fallback: treat as single scalar
    s = str(value).strip()
    return [s] if s else []


def normalize_urls(urls: Any) -> List[str]:
    """
    Normalize URL inputs coming from forms/query parameters.

    The API often accepts either:
    - repeated form fields: urls=...&urls=...
    - a single comma/newline separated string
    This helper produces a de-duplicated, order-preserving list.
    """
    raw_list = normalize_str_list(urls)
    seen = set()
    out: List[str] = []
    for url in raw_list:
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def normalize_optional_sequence(value: Optional[Iterable[Any]]) -> List[Any]:
    """
    Normalize an optional iterable into a concrete list.

    - None -> []
    - Sequence/iterable -> list(value)
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return list(value)


__all__ = [
    "to_bool",
    "to_int",
    "normalize_str_list",
    "normalize_urls",
    "normalize_optional_sequence",
]
