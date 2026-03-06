"""Embedding-backed similarity scoring and Chroma sync for persona exemplars."""

from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import Any, Callable

from loguru import logger

from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

CreateEmbeddingsFn = Callable[[list[str], dict[str, Any], str | None], list[list[float]]]
GetEmbeddingConfigFn = Callable[[], dict[str, Any]]
VectorScoreFn = Callable[..., dict[str, float]]


def _is_fatal_base_exception(exc: BaseException) -> bool:
    """Return True for process-control exceptions that must not be swallowed."""
    return isinstance(exc, (KeyboardInterrupt, SystemExit))


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


@lru_cache(maxsize=1)
def _load_chroma_manager_class() -> type[Any] | None:
    """Lazy-load ChromaDB manager to keep optional dependencies optional."""
    try:
        from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import (  # noqa: PLC0415
            ChromaDBManager,
        )

        return ChromaDBManager
    except Exception as exc:  # noqa: BLE001
        logger.debug("Persona exemplar vector index unavailable: {}", exc)
        return None


def _resolve_embedding_config(embedding_config: dict[str, Any] | None) -> dict[str, Any] | None:
    if embedding_config is not None:
        return embedding_config
    _, get_config_fn = _load_embedding_helpers()
    if get_config_fn is None:
        return None
    try:
        return get_config_fn()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load embedding config for persona exemplars: {}", exc)
        return None


def _resolve_embedding_runtime(
    create_embeddings_fn: CreateEmbeddingsFn | None,
    embedding_config: dict[str, Any] | None,
) -> tuple[CreateEmbeddingsFn | None, dict[str, Any] | None]:
    embedding_fn = create_embeddings_fn
    config = _resolve_embedding_config(embedding_config)

    if embedding_fn is None:
        loaded_embedding_fn, _ = _load_embedding_helpers()
        embedding_fn = loaded_embedding_fn

    return embedding_fn, config


def _normalize_collection_segment(value: str | int) -> str:
    text = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "").strip())
    text = text.strip("_")
    return text or "unknown"


def build_character_exemplar_collection_name(user_id: str | int, character_id: int) -> str:
    """Build a stable Chroma collection name for character exemplar vectors."""
    user_segment = _normalize_collection_segment(user_id)
    character_segment = _normalize_collection_segment(character_id)
    return f"character_exemplars_{user_segment}_{character_segment}"


def _build_chroma_user_embedding_config(embedding_config: dict[str, Any]) -> dict[str, Any]:
    """Build Chroma manager config from embedding config + user DB base dir."""
    from tldw_Server_API.app.core.config import settings  # noqa: PLC0415

    config_copy = dict(embedding_config or {})
    if "embedding_config" not in config_copy:
        config_copy = {"embedding_config": config_copy}

    user_db_base_dir = settings.get("USER_DB_BASE_DIR")
    if not user_db_base_dir:
        user_db_base_dir = str(DatabasePaths.get_user_db_base_dir())
    config_copy["USER_DB_BASE_DIR"] = str(user_db_base_dir)
    return config_copy


def _create_chroma_manager(
    *,
    user_id: str,
    embedding_config: dict[str, Any],
    chroma_manager: Any | None = None,
) -> Any | None:
    if chroma_manager is not None:
        return chroma_manager

    manager_class = _load_chroma_manager_class()
    if manager_class is None:
        return None

    try:
        return manager_class(
            user_id=str(user_id),
            user_embedding_config=_build_chroma_user_embedding_config(embedding_config),
        )
    except BaseException as exc:  # noqa: BLE001
        if _is_fatal_base_exception(exc):
            raise
        logger.warning("Failed to initialize persona exemplar Chroma manager: {}", exc)
        return None


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


def _distance_to_similarity(distance: Any) -> float:
    """Normalize a Chroma distance-like value into [0, 1] similarity."""
    try:
        parsed = float(distance)
    except (TypeError, ValueError):
        return 0.0
    if parsed < 0.0:
        return 0.0
    if parsed <= 2.0:
        return max(0.0, min(1.0, 1.0 - (parsed / 2.0)))
    return max(0.0, min(1.0, 1.0 / (1.0 + parsed)))


def score_exemplars_with_vector_index(
    user_turn: str,
    candidates: list[dict[str, Any]],
    *,
    user_id: str,
    character_id: int,
    model_id_override: str | None = None,
    embedding_config: dict[str, Any] | None = None,
    chroma_manager: Any | None = None,
) -> dict[str, float]:
    """Score candidate exemplars using persisted vectors from Chroma when available."""
    turn_text = str(user_turn or "").strip()
    if not turn_text or not candidates:
        return {}

    candidate_ids = {
        str(item.get("id") or "").strip()
        for item in candidates
        if str(item.get("id") or "").strip()
    }
    if not candidate_ids:
        return {}

    config = _resolve_embedding_config(embedding_config)
    if config is None:
        return {}

    manager = _create_chroma_manager(
        user_id=str(user_id),
        embedding_config=config,
        chroma_manager=chroma_manager,
    )
    if manager is None:
        return {}

    try:
        query_results = manager.vector_search(
            query=turn_text,
            collection_name=build_character_exemplar_collection_name(str(user_id), int(character_id)),
            k=min(max(1, len(candidate_ids)), 80),
            embedding_model_id_override=model_id_override,
            where_filter={"character_id": str(character_id)},
        )
    except BaseException as exc:  # noqa: BLE001
        if _is_fatal_base_exception(exc):
            raise
        logger.warning("Persona exemplar vector search failed: {}", exc)
        return {}

    scores: dict[str, float] = {}
    if not isinstance(query_results, list):
        return scores

    for row in query_results:
        if not isinstance(row, dict):
            continue
        exemplar_id = str(row.get("id") or "").strip()
        if not exemplar_id or exemplar_id not in candidate_ids:
            continue
        similarity = _distance_to_similarity(row.get("distance"))
        scores[exemplar_id] = round(similarity, 6)

    return scores


def upsert_character_exemplar_embeddings(
    user_id: str,
    character_id: int,
    exemplars: list[dict[str, Any]],
    *,
    model_id_override: str | None = None,
    chroma_manager: Any | None = None,
    create_embeddings_fn: CreateEmbeddingsFn | None = None,
    embedding_config: dict[str, Any] | None = None,
) -> int:
    """Best-effort upsert of character exemplar embeddings into the per-character collection."""
    if not exemplars:
        return 0

    exemplar_ids: list[str] = []
    exemplar_texts: list[str] = []
    exemplar_metadatas: list[dict[str, Any]] = []
    for exemplar in exemplars:
        exemplar_id = str(exemplar.get("id") or "").strip()
        exemplar_text = str(exemplar.get("text") or "").strip()
        if not exemplar_id or not exemplar_text:
            continue
        exemplar_ids.append(exemplar_id)
        exemplar_texts.append(exemplar_text)
        rhetorical = exemplar.get("rhetorical")
        if isinstance(rhetorical, list):
            rhetorical_values = [str(item).strip() for item in rhetorical if str(item).strip()]
        elif isinstance(rhetorical, str):
            rhetorical_values = [rhetorical.strip()] if rhetorical.strip() else []
        else:
            rhetorical_values = []

        exemplar_metadatas.append(
            {
                "character_id": str(character_id),
                "emotion": str(exemplar.get("emotion") or "other"),
                "scenario": str(exemplar.get("scenario") or "other"),
                "novelty_hint": str(exemplar.get("novelty_hint") or "unknown"),
                "rhetorical": rhetorical_values,
                "length_tokens": int(exemplar.get("length_tokens") or max(1, len(exemplar_text.split()))),
            }
        )

    if not exemplar_ids:
        return 0

    embedding_fn, config = _resolve_embedding_runtime(create_embeddings_fn, embedding_config)
    if embedding_fn is None or config is None:
        return 0

    manager = _create_chroma_manager(
        user_id=str(user_id),
        embedding_config=config,
        chroma_manager=chroma_manager,
    )
    if manager is None:
        return 0

    try:
        vectors = embedding_fn(exemplar_texts, config, model_id_override)
        if not isinstance(vectors, list) or len(vectors) != len(exemplar_ids):
            logger.warning(
                "Persona exemplar embedding upsert skipped due to malformed vectors: expected={}, got={}",
                len(exemplar_ids),
                len(vectors) if isinstance(vectors, list) else "n/a",
            )
            return 0

        embedding_cfg = config.get("embedding_config") if isinstance(config, dict) else {}
        default_model_id = (
            str(embedding_cfg.get("default_model_id")).strip()
            if isinstance(embedding_cfg, dict) and embedding_cfg.get("default_model_id") is not None
            else None
        )
        manager.store_in_chroma(
            collection_name=build_character_exemplar_collection_name(str(user_id), int(character_id)),
            texts=exemplar_texts,
            embeddings=vectors,
            ids=exemplar_ids,
            metadatas=exemplar_metadatas,
            embedding_model_id_for_dim_check=model_id_override or default_model_id,
        )
        return len(exemplar_ids)
    except BaseException as exc:  # noqa: BLE001
        if _is_fatal_base_exception(exc):
            raise
        logger.warning("Persona exemplar embedding upsert failed: {}", exc)
        return 0


def delete_character_exemplar_embeddings(
    user_id: str,
    character_id: int,
    exemplar_ids: list[str],
    *,
    chroma_manager: Any | None = None,
    embedding_config: dict[str, Any] | None = None,
) -> int:
    """Best-effort deletion of exemplar vectors from the per-character collection."""
    normalized_ids = [str(item).strip() for item in exemplar_ids if str(item).strip()]
    if not normalized_ids:
        return 0

    config = _resolve_embedding_config(embedding_config)
    if config is None:
        return 0

    manager = _create_chroma_manager(
        user_id=str(user_id),
        embedding_config=config,
        chroma_manager=chroma_manager,
    )
    if manager is None:
        return 0

    try:
        manager.delete_from_collection(
            ids=normalized_ids,
            collection_name=build_character_exemplar_collection_name(str(user_id), int(character_id)),
        )
        return len(normalized_ids)
    except BaseException as exc:  # noqa: BLE001
        if _is_fatal_base_exception(exc):
            raise
        logger.warning("Persona exemplar embedding delete failed: {}", exc)
        return 0


def score_exemplars_with_embeddings(
    user_turn: str,
    candidates: list[dict[str, Any]],
    *,
    user_id: str | None = None,
    character_id: int | None = None,
    model_id_override: str | None = None,
    vector_score_fn: VectorScoreFn | None = None,
    chroma_manager: Any | None = None,
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

    scores: dict[str, float] = {}
    if user_id is not None and character_id is not None:
        index_score_fn = vector_score_fn or score_exemplars_with_vector_index
        try:
            index_scores = index_score_fn(
                user_turn=turn_text,
                candidates=candidates,
                user_id=str(user_id),
                character_id=int(character_id),
                model_id_override=model_id_override,
                embedding_config=embedding_config,
                chroma_manager=chroma_manager,
            ) or {}
            if isinstance(index_scores, dict):
                for exemplar_id, score_value in index_scores.items():
                    exemplar_id_normalized = str(exemplar_id).strip()
                    if exemplar_id_normalized:
                        scores[exemplar_id_normalized] = round(max(0.0, min(1.0, float(score_value))), 6)
        except BaseException as exc:  # noqa: BLE001
            if _is_fatal_base_exception(exc):
                raise
            logger.warning("Persona exemplar vector scoring callback failed: {}", exc)

        if len(scores) >= len(candidate_ids):
            return scores

    embedding_fn, config = _resolve_embedding_runtime(create_embeddings_fn, embedding_config)

    if embedding_fn is None or config is None:
        return scores

    try:
        vectors = embedding_fn(
            [turn_text, *candidate_texts],
            config,
            model_id_override,
        )
    except BaseException as exc:  # noqa: BLE001
        if _is_fatal_base_exception(exc):
            raise
        logger.warning("Embedding scoring failed for persona exemplars: {}", exc)
        return {}

    if not isinstance(vectors, list) or len(vectors) < 2:
        return {}

    query_vec = _to_float_vector(vectors[0])
    if query_vec is None:
        return scores

    for idx, exemplar_id in enumerate(candidate_ids, start=1):
        if exemplar_id in scores:
            continue
        if idx >= len(vectors):
            break
        candidate_vec = _to_float_vector(vectors[idx])
        if candidate_vec is None:
            continue
        similarity = _cosine_similarity(query_vec, candidate_vec)
        scores[exemplar_id] = round(_normalize_similarity(similarity), 6)

    return scores


__all__ = [
    "build_character_exemplar_collection_name",
    "delete_character_exemplar_embeddings",
    "score_exemplars_with_embeddings",
    "score_exemplars_with_vector_index",
    "upsert_character_exemplar_embeddings",
]
