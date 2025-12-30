from __future__ import annotations

import hashlib


def claim_embedding_id(media_id: int, chunk_index: int, claim_text: str) -> str:
    """Return the deterministic claim embedding id used by ingestion."""
    digest = hashlib.sha256(str(claim_text).encode("utf-8")).hexdigest()[:12]
    return f"claim_{int(media_id)}_{int(chunk_index)}_{digest}"
