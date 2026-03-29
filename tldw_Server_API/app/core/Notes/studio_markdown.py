"""Deterministic Markdown rendering helpers for Notes Studio documents."""

from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping


NOTE_STUDIO_RENDER_VERSION = 1


def stable_content_hash(content: str) -> str:
    """Return a stable sha256 hash with a Notes Studio prefix."""
    normalized = str(content or "").replace("\r\n", "\n").replace("\r", "\n")
    return f"sha256:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"


def render_studio_markdown(payload: Mapping[str, Any]) -> str:
    """Render canonical Studio payload data into deterministic Markdown."""
    meta = payload.get("meta") if isinstance(payload, Mapping) else {}
    sections = payload.get("sections") if isinstance(payload, Mapping) else []

    title = str((meta or {}).get("title") or "Untitled Study Notes").strip() or "Untitled Study Notes"
    markdown_parts: list[str] = [f"# {title}"]

    for section in _iter_sections(sections):
        section_title = str(section.get("title") or "Section").strip() or "Section"
        markdown_parts.append(f"## {section_title}")

        kind = str(section.get("kind") or "").strip().lower()
        if kind == "cue":
            items = section.get("items") or []
            bullet_items = [str(item).strip() for item in items if str(item).strip()]
            if bullet_items:
                markdown_parts.extend(f"- {item}" for item in bullet_items)
            else:
                markdown_parts.append("- Review the source excerpt.")
            continue

        content = str(section.get("content") or "").strip()
        if content:
            markdown_parts.append(content)
        else:
            markdown_parts.append("Content pending.")

    return "\n\n".join(markdown_parts).strip()


def _iter_sections(sections: Any) -> Iterable[dict[str, Any]]:
    if not isinstance(sections, list):
        return []
    normalized_sections: list[dict[str, Any]] = []
    for section in sections:
        if isinstance(section, Mapping):
            normalized_sections.append(dict(section))
    return normalized_sections
