"""
Personalization Scorer (scaffold)

Blend BM25, vector score, personal similarity, and recency into a final score.
Provides optional lightweight explanation signals.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple


@dataclass
class ScoreWeights:
    alpha: float = 0.2  # vector
    beta: float = 0.6   # personal similarity
    gamma: float = 0.2  # recency


def rerank(
    items: Iterable[Dict[str, Any]],
    weights: ScoreWeights | None = None,
    with_explanations: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]] | None]:
    """Scaffold reranker that passes through items and attaches dummy scores.

    Args:
        items: iterable of dicts representing retrieved items
        weights: score weight config
        with_explanations: whether to return explanation signals

    Returns:
        (ranked_items, explanations?)
    """
    w = weights or ScoreWeights()
    ranked: List[Dict[str, Any]] = []
    expl: List[Dict[str, Any]] = []

    for idx, it in enumerate(items):
        base = float(it.get("bm25", 0.0))
        vec = float(it.get("vector", 0.0))
        per = float(it.get("personal", 0.0))
        rec = float(it.get("recency", 0.0))
        score = base + w.alpha * vec + w.beta * per + w.gamma * rec
        out = dict(it)
        out["score"] = score
        ranked.append(out)
        if with_explanations:
            expl.append({
                "signals": [
                    {"name": "bm25", "value": base},
                    {"name": "vector", "value": vec},
                    {"name": "personal_similarity", "value": per},
                    {"name": "recency", "value": rec},
                ]
            })

    ranked.sort(key=lambda d: d.get("score", 0.0), reverse=True)
    return ranked, (expl if with_explanations else None)
