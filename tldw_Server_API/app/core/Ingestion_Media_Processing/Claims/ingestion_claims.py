"""
ingestion_claims.py - Ingestion-time claim (factual statement) extraction utilities.

Stage 2 MVP: Heuristic extraction of short factual sentences from chunks,
with storage in MediaDatabase.Claims. Optional, behind config flags.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

from loguru import logger
from .claims_engine import HeuristicSentenceExtractor

try:
    # Local import for DB helper
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
except Exception:  # pragma: no cover
    MediaDatabase = None  # type: ignore




def extract_claims_for_chunks(
    chunks: List[Dict[str, Any]],
    *,
    extractor_mode: str = "heuristic",
    max_per_chunk: int = 3,
) -> List[Dict[str, Any]]:
    """
    Extract a small set of candidate factual statements per chunk.

    Returns items with: chunk_index, claim_text.
    """
    claims: List[Dict[str, Any]] = []
    for ch in chunks or []:
        txt = (ch or {}).get("text") or (ch or {}).get("content") or ""
        meta = (ch or {}).get("metadata", {}) or {}
        idx = int(meta.get("chunk_index") or meta.get("index") or 0)
        if extractor_mode != "heuristic":
            # For MVP we only implement heuristic; non-heuristic modes fall back
            logger.debug(f"Unsupported extractor_mode '{extractor_mode}', using heuristic")
        # Reuse the extractor’s logic for consistency
        sents: List[str] = []
        try:
            extractor = HeuristicSentenceExtractor()
            # Extract returns Claim objects; convert to texts
            import asyncio as _asyncio
            extracted = _asyncio.get_event_loop().run_until_complete(extractor.extract(txt, max_per_chunk))
            sents = [c.text for c in extracted]
        except Exception:
            # Fallback: simple regex split if event loop unavailable
            parts = re.split(r"(?<=[\.!?])\s+", (txt or "").strip())
            for p in parts:
                t = (p or "").strip()
                if len(t) >= 12:
                    sents.append(t)
                if len(sents) >= max_per_chunk:
                    break
        for s in sents:
            claims.append({"chunk_index": idx, "claim_text": s})
    return claims


def store_claims(
    db: "MediaDatabase",
    *,
    media_id: int,
    chunk_texts_by_index: Dict[int, str],
    claims: List[Dict[str, Any]],
    extractor: str = "heuristic",
    extractor_version: str = "v1",
) -> int:
    """
    Store extracted claims into Claims table via MediaDatabase.upsert_claims.
    Computes chunk_hash from the chunk text for linkage.
    """
    if not claims:
        return 0
    rows: List[Dict[str, Any]] = []
    for c in claims:
        idx = int(c.get("chunk_index", 0))
        ctext = str(c.get("claim_text", ""))
        chunk_txt = chunk_texts_by_index.get(idx, "")
        chash = hashlib.sha256(chunk_txt.encode()).hexdigest() if chunk_txt else hashlib.sha256(b"").hexdigest()
        rows.append({
            "media_id": int(media_id),
            "chunk_index": idx,
            "span_start": None,
            "span_end": None,
            "claim_text": ctext,
            "confidence": None,
            "extractor": extractor,
            "extractor_version": extractor_version,
            "chunk_hash": chash,
        })
    try:
        inserted = db.upsert_claims(rows)
        return inserted
    except Exception as e:  # pragma: no cover
        logger.error(f"Failed to store claims for media_id={media_id}: {e}")
        return 0
