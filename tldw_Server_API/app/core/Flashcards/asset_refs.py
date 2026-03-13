"""Helpers for flashcard-managed asset references embedded in markdown."""

from __future__ import annotations

from html import escape
import re
from typing import Callable

FLASHCARD_ASSET_SCHEME = "flashcard-asset://"

_MARKDOWN_ASSET_IMAGE_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\("
    rf"(?P<reference>{re.escape(FLASHCARD_ASSET_SCHEME)}(?P<asset_uuid>[^)\s]+))"
    r"\)"
)


def build_flashcard_asset_reference(asset_uuid: str) -> str:
    """Return the canonical inline reference for a flashcard asset."""
    return f"{FLASHCARD_ASSET_SCHEME}{str(asset_uuid).strip()}"


def build_flashcard_asset_markdown(asset_uuid: str, alt_text: str = "") -> str:
    """Build inline markdown for a flashcard-managed asset."""
    normalized_alt = str(alt_text or "").replace("]", "").strip()
    return f"![{normalized_alt}]({build_flashcard_asset_reference(asset_uuid)})"


def extract_flashcard_asset_uuids(text: str | None) -> list[str]:
    """Extract unique asset UUIDs in encounter order from flashcard markdown."""
    if not text:
        return []

    seen: set[str] = set()
    ordered: list[str] = []
    for match in _MARKDOWN_ASSET_IMAGE_RE.finditer(text):
        asset_uuid = match.group("asset_uuid")
        if asset_uuid in seen:
            continue
        seen.add(asset_uuid)
        ordered.append(asset_uuid)
    return ordered


def sanitize_flashcard_text_for_search(text: str | None) -> str:
    """Strip managed asset refs while preserving useful alt text for search."""
    if not text:
        return ""

    sanitized = _MARKDOWN_ASSET_IMAGE_RE.sub(
        lambda match: f" {match.group('alt').strip()} ".strip(),
        text,
    )
    return re.sub(r"\s+", " ", sanitized).strip()


def replace_markdown_asset_refs_for_export(
    text: str | None,
    resolver: Callable[[str], tuple[str, str] | str],
) -> str:
    """Rewrite managed asset refs into Anki-friendly HTML image tags."""
    if not text:
        return ""

    def repl(match: re.Match[str]) -> str:
        asset_uuid = match.group("asset_uuid")
        resolved = resolver(asset_uuid)
        if isinstance(resolved, tuple | list):
            src = str(resolved[0])
        else:
            src = str(resolved)
        alt = match.group("alt") or ""
        return f'<img src="{escape(src, quote=True)}" alt="{escape(alt, quote=True)}" />'

    return _MARKDOWN_ASSET_IMAGE_RE.sub(repl, text)


__all__ = [
    "FLASHCARD_ASSET_SCHEME",
    "build_flashcard_asset_markdown",
    "build_flashcard_asset_reference",
    "extract_flashcard_asset_uuids",
    "replace_markdown_asset_refs_for_export",
    "sanitize_flashcard_text_for_search",
]
