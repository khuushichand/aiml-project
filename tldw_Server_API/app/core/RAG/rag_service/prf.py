"""
Pseudo-relevance feedback (PRF) utilities for the unified RAG pipeline.

This module provides a lightweight helper that:
- Mines salient terms from the top retrieved documents (keywords, entities, numbers)
- Builds a simple expanded query string
- Returns metadata describing the expansion for observability

The unified pipeline currently uses PRF in a metadata-only fashion, so callers
can introspect suggested expansions without changing retrieval behaviour.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from loguru import logger

from .types import Document


@dataclass
class PRFConfig:
    """Configuration for pseudo-relevance feedback term mining."""

    max_terms: int = 10
    sources: List[str] = field(default_factory=lambda: ["keywords", "entities", "numbers"])
    alpha: float = 0.3
    top_n: int = 8


def _tokenize(text: str) -> List[str]:
    """Simple tokenizer for PRF term extraction."""
    if not text:
        return []
    return re.findall(r"[A-Za-z0-9_]{3,}", text.lower())


def _extract_numbers(text: str) -> List[str]:
    """Extract numeric-like tokens (years, counts, percentages, amounts)."""
    if not text:
        return []
    return re.findall(r"\d[\d,._%]*", text)


def _extract_entities(doc: Document) -> List[str]:
    """Extract simple entity-like tokens from document metadata."""
    entities: List[str] = []
    try:
        meta = getattr(doc, "metadata", {}) or {}
        title = str(meta.get("title") or "")[:200]
        section = str(meta.get("section_title") or "")[:200]
        for field in (title, section):
            for token in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", field):
                entities.append(token.lower())
    except Exception:
        return entities
    return entities


async def apply_prf(
    query: str,
    documents: List[Document],
    config: Optional[PRFConfig] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Compute a simple PRF-based expanded query from top documents.

    Args:
        query: Original user query.
        documents: Retrieved documents (typically pre-rerank top-k).
        config: PRF configuration.

    Returns:
        (expanded_query, metadata) where expanded_query may equal the original
        query when no useful terms are found.
    """
    cfg = config or PRFConfig()
    if not documents or cfg.max_terms <= 0:
        return query, {
            "enabled": False,
            "base_query": query,
            "reason": "no_documents_or_zero_max_terms",
        }

    try:
        seeds = documents[: max(1, cfg.top_n)]
        term_counts: Dict[str, int] = {}

        use_keywords = "keywords" in cfg.sources
        use_entities = "entities" in cfg.sources
        use_numbers = "numbers" in cfg.sources

        for doc in seeds:
            text = getattr(doc, "content", "") or ""
            if use_keywords:
                for tok in _tokenize(text):
                    term_counts[tok] = term_counts.get(tok, 0) + 1
            if use_numbers:
                for num in _extract_numbers(text):
                    term_counts[num] = term_counts.get(num, 0) + 1
            if use_entities:
                for ent in _extract_entities(doc):
                    term_counts[ent] = term_counts.get(ent, 0) + 1

        base_terms = set(_tokenize(query))
        # Sort by frequency (desc) then lexicographically for stability
        ranked_terms = sorted(
            (t for t in term_counts.keys() if t not in base_terms),
            key=lambda t: (-term_counts[t], t),
        )
        selected = ranked_terms[: cfg.max_terms]

        if not selected:
            return query, {
                "enabled": False,
                "base_query": query,
                "reason": "no_additional_terms",
                "doc_seed_count": len(seeds),
            }

        expanded_query = f"{query} {' '.join(selected)}".strip()
        meta: Dict[str, Any] = {
            "enabled": True,
            "base_query": query,
            "expanded_query": expanded_query,
            "terms_used": selected,
            "sources": list(cfg.sources),
            "doc_seed_count": len(seeds),
            "alpha": float(cfg.alpha),
        }
        logger.debug(f"PRF mined {len(selected)} terms from {len(seeds)} docs")  # pragma: no cover - debug log
        return expanded_query, meta
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"PRF computation failed; returning original query: {e}")
        return query, {
            "enabled": False,
            "base_query": query,
            "reason": "error",
            "error": str(e),
        }

