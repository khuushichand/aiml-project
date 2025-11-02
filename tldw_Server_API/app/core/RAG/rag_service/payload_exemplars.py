"""
Payload exemplars sampler for failed adaptive checks.

Writes small, redacted samples of query and contexts to a JSONL sink for
operators to debug retrieval/generation issues without leaking sensitive data.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


SINK = Path("Databases/observability/rag_payload_exemplars.jsonl")


def _safe_sink() -> Path:
    try:
        p = os.getenv("RAG_PAYLOAD_EXEMPLAR_PATH")
        sink = Path(p) if p else SINK
        sink.parent.mkdir(parents=True, exist_ok=True)
        return sink
    except Exception:
        return SINK


def _redact(text: str) -> str:
    if not isinstance(text, str):
        return ""
    t = text
    # Redact emails/URLs/numbers-long
    t = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[EMAIL]", t)
    t = re.sub(r"https?://[^\s]+", "[URL]", t)
    t = re.sub(r"\b\d{4,}\b", "[NUM]", t)
    # Collapse whitespace and truncate
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > 400:
        t = t[:400] + "…"
    return t


def maybe_record_exemplar(
    *,
    query: str,
    documents: List[Any],
    answer: str,
    reason: str,
    user_id: Optional[str] = None,
) -> None:
    """Sample and persist a redacted exemplar of the payload.

    Sampling rate is controlled by RAG_PAYLOAD_EXEMPLAR_SAMPLING (0..1, default 0.05).
    """
    try:
        rate = float(os.getenv("RAG_PAYLOAD_EXEMPLAR_SAMPLING", "0.05"))
    except Exception:
        rate = 0.05
    try:
        if random.random() > max(0.0, min(1.0, rate)):
            return
        sink = _safe_sink()
        sample = {
            "ts": time.time(),
            "reason": reason,
            "user": user_id or "",
            "query": _redact(query or ""),
            "answer": _redact(answer or ""),
            "docs": [
                {
                    "id": getattr(d, "id", None) or (d.get("id") if isinstance(d, dict) else None),
                    "score": float(getattr(d, "score", 0.0) if hasattr(d, "score") else (d.get("score", 0.0) if isinstance(d, dict) else 0.0)),
                    "content": _redact(getattr(d, "content", "") if hasattr(d, "content") else (d.get("content", "") if isinstance(d, dict) else "")),
                }
                for d in (documents[:5] if documents else [])
            ],
        }
        with sink.open("a", encoding="utf-8") as f:
            f.write(json.dumps(sample) + "\n")
    except Exception as e:
        logger.debug(f"Failed to write exemplar: {e}")
