"""Extract ``[[id:UUID]]`` wikilink references from note content."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Full UUID-4 hex pattern inside [[id:...]]
_WIKILINK_RE = re.compile(
    r"\[\[id:([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\]\]"
)


@dataclass(frozen=True, slots=True)
class WikilinkRef:
    """A resolved wikilink target (lowercase-normalized UUID)."""

    target_note_id: str


def extract_wikilinks(content: str) -> list[WikilinkRef]:
    """Return deduplicated wikilink refs in order of first occurrence.

    Only ``[[id:<UUID>]]`` syntax is matched.  Title-based ``[[Title]]``
    links are intentionally ignored (deferred to Phase 2).
    """
    if not content:
        return []

    seen: set[str] = set()
    result: list[WikilinkRef] = []
    for m in _WIKILINK_RE.finditer(content):
        normalized = m.group(1).lower()
        if normalized not in seen:
            seen.add(normalized)
            result.append(WikilinkRef(target_note_id=normalized))
    return result
