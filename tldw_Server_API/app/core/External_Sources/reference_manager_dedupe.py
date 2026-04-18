from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from tldw_Server_API.app.core.Utils.Utils import normalize_title

from .reference_manager_types import NormalizedReferenceItem


@dataclass(slots=True)
class ReferenceItemMatch:
    reason: str | None
    media_id: int | None
    metadata_patch: dict[str, Any] | None = None


def normalize_first_author(authors: str | None) -> str | None:
    raw_authors = str(authors or "").strip()
    if not raw_authors:
        return None
    normalized_authors = re.sub(r"\s+(and|&)\s+", ", ", raw_authors, flags=re.IGNORECASE)
    normalized_authors = normalized_authors.replace(";", ",")
    first_author = normalized_authors.split(",", 1)[0].strip()
    if not first_author:
        return None
    normalized = normalize_title(first_author).lower()
    return normalized or None


def build_metadata_fingerprint(
    *,
    title: str | None,
    authors: str | None,
    year: str | None,
) -> str | None:
    normalized_title = normalize_title(str(title or "").strip()).lower()
    first_author = normalize_first_author(authors)
    normalized_year = str(year or "").strip()
    if not normalized_title or not first_author or not normalized_year:
        return None
    return f"{normalized_title}|{first_author}|{normalized_year}"


def _coerce_media_id(candidate: dict[str, Any] | None) -> int | None:
    if not candidate:
        return None
    raw_media_id = candidate.get("media_id")
    if raw_media_id is None:
        return None
    try:
        return int(raw_media_id)
    except (TypeError, ValueError):
        return None


def _build_metadata_patch(item: NormalizedReferenceItem) -> dict[str, Any] | None:
    patch = {
        "doi": item.doi,
        "title": item.title,
        "authors": item.authors,
        "publication_date": item.publication_date,
        "year": item.year,
        "journal": item.journal,
        "abstract": item.abstract,
        "source_url": item.source_url,
    }
    normalized_patch = {key: value for key, value in patch.items() if value not in (None, "")}
    return normalized_patch or None


def rank_reference_item_match(
    item: NormalizedReferenceItem,
    *,
    same_provider_item: dict[str, Any] | None,
    doi_match: dict[str, Any] | None,
    hash_match: dict[str, Any] | None,
    metadata_match: dict[str, Any] | None,
) -> ReferenceItemMatch:
    for reason, candidate in (
        ("same_provider_item", same_provider_item),
        ("doi", doi_match),
        ("file_hash", hash_match),
        ("metadata_fingerprint", metadata_match),
    ):
        media_id = _coerce_media_id(candidate)
        if media_id is not None:
            return ReferenceItemMatch(
                reason=reason,
                media_id=media_id,
                metadata_patch=_build_metadata_patch(item),
            )
    return ReferenceItemMatch(reason=None, media_id=None, metadata_patch=None)
