from __future__ import annotations

import hashlib
from typing import Optional


def truncate_text(value: Optional[str], limit: int = 400) -> Optional[str]:
    if not value:
        return None
    stripped = str(value).strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: max(0, limit - 3)].rstrip() + "..."


def hash_text_sha256(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    except Exception:
        return None


def word_count(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    words = [w for w in str(value).split() if w]
    return len(words) if words else None
