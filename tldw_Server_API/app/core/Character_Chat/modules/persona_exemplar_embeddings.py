"""Embedding-backed similarity scoring for persona exemplar selection."""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any, Callable

from loguru import logger

CreateEmbeddingsFn = Callable[[list[str], dict[str, Any], str | None], list[list[float]]]
GetEmbeddingConfigFn = Callable[[], dict[str, Any]]


@lru_cache(maxsize=1)
def _load_embedding_helpers() -> tuple[CreateEmbeddingsFn | None, GetEmbeddingConfigFn | None]:
    """Lazy-load embedding helpers and guard against missing optional deps."""
    try:
        from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import (  # noqa: PLC0415
            create_embeddings_batch,
            get_embedding_config,
        )

        return create_embeddings_batch, get_embedding_config
    except Exception as exc:  # noqa: BLE001
        logger.debug("Persona exemplar embeddings unavailable: {}", exc)
        return None, None


def _to_float_vector(value: Any) -> list[float] | None:
    """Best-effort conversion of embedding payloads into a flat float vector."""
    if not isinstance(value, list) or not value:
        return None
    vector: list[float] = []
    for item in value:
        try:
            vector.append(float(item))
        except (TypeError, ValueError):
            return None
    return vector


def _cosine_similarity(lhs: list[float], rhs: list[float]) -> float:
    """Compute cosine similarity in [-1.0, 1.0], returning 0 on invalid vectors."""
    if not lhs or not rhs or len(lhs) != len(rhs):
        return 0.0
    lhs_norm = math.sqrt(sum(item * item for item in lhs))
    rhs_norm = math.sqrt(sum(item * item for item in rhs))
    if lhs_norm == 0.0 or rhs_norm == 0.0:
        return 0.0
    dot = sum(lhs_item * rhs_item for lhs_item, rhs_item in zip(lhs, rhs))
    return dot / (lhs_norm * rhs_norm)


def _normalize_similarity(score: float) -> float:
    """Normalize cosine score from [-1, 1] to [0, 1]."""
    normalized = (score + 1.0) / 2.0
    if normalized < 0.0:
        return 0.0
    if normalized > 1.0:
        return 1.0
    return normalized


def score_exemplars_with_embeddings(
    user_turn: str,
    candidates: list[dict[str, Any]],
    *,
    model_id_override: str | None = None,
    create_embeddings_fn: CreateEmbeddingsFn | None = None,
    embedding_config: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Return per-exemplar semantic relevance scores in [0, 1]."""
    turn_text = str(user_turn or "").strip()
    if not turn_text or not candidates:
        return {}

    candidate_ids: list[str] = []
    candidate_texts: list[str] = []
    for candidate in candidates:
        exemplar_id = str(candidate.get("id") or "").strip()
        exemplar_text = str(candidate.get("text") or "").strip()
        if exemplar_id and exemplar_text:
            candidate_ids.append(exemplar_id)
            candidate_texts.append(exemplar_text)

    if not candidate_ids:
        return {}

    embedding_fn = create_embeddings_fn
    config = embedding_config
    if embedding_fn is None or config is None:
        loaded_embedding_fn, get_config_fn = _load_embedding_helpers()
        if embedding_fn is None:
            embedding_fn = loaded_embedding_fn
        if config is None and get_config_fn is not None:
            try:
                config = get_config_fn()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to load embedding config for persona exemplar scoring: {}", exc)
                return {}

    if embedding_fn is None or config is None:
        return {}

    try:
        vectors = embedding_fn(
            [turn_text, *candidate_texts],
            config,
            model_id_override,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Embedding scoring failed for persona exemplars: {}", exc)
        return {}

    if not isinstance(vectors, list) or len(vectors) < 2:
        return {}

    query_vec = _to_float_vector(vectors[0])
    if query_vec is None:
        return {}

    scores: dict[str, float] = {}
    for idx, exemplar_id in enumerate(candidate_ids, start=1):
        if idx >= len(vectors):
            break
        candidate_vec = _to_float_vector(vectors[idx])
        if candidate_vec is None:
            continue
        similarity = _cosine_similarity(query_vec, candidate_vec)
        scores[exemplar_id] = round(_normalize_similarity(similarity), 6)

    return scores


__all__ = ["score_exemplars_with_embeddings"]
