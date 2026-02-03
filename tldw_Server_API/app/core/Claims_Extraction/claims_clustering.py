from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Claims_Extraction.claims_embeddings import claim_embedding_id
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager


@dataclass(frozen=True)
class ClaimEmbedding:
    claim_id: int
    media_id: int
    chunk_index: int
    claim_text: str
    embedding: list[float]
    norm: float


def _vector_norm(vec: Iterable[float]) -> float:
    return math.sqrt(sum((v * v) for v in vec))


def _cosine_similarity(
    vec_a: list[float],
    norm_a: float,
    vec_b: list[float],
    norm_b: float,
) -> float:
    if not vec_a or not vec_b or norm_a <= 0 or norm_b <= 0:
        return 0.0
    dot = 0.0
    for a, b in zip(vec_a, vec_b):
        dot += a * b
    return dot / (norm_a * norm_b)


def _iter_claims_for_user(db: MediaDatabase, user_id: str, page_size: int = 1000) -> Iterable[dict[str, Any]]:
    offset = 0
    while True:
        rows = db.list_claims(owner_user_id=user_id, limit=page_size, offset=offset, include_deleted=False)
        if not rows:
            break
        for row in rows:
            yield row
        offset += len(rows)
        if len(rows) < page_size:
            break


def _batched_ids(ids: list[str], batch_size: int) -> Iterable[list[str]]:
    if batch_size <= 0:
        batch_size = 200
    for i in range(0, len(ids), batch_size):
        yield ids[i : i + batch_size]


def _load_claim_embeddings(
    *,
    db: MediaDatabase,
    user_id: str,
    batch_size: int,
) -> tuple[list[ClaimEmbedding], int]:
    claim_rows = list(_iter_claims_for_user(db, user_id))
    if not claim_rows:
        return [], 0

    id_to_claim: dict[str, dict[str, Any]] = {}
    embed_ids: list[str] = []
    for row in claim_rows:
        embed_id = claim_embedding_id(
            int(row.get("media_id") or 0),
            int(row.get("chunk_index") or 0),
            str(row.get("claim_text") or ""),
        )
        embed_ids.append(embed_id)
        id_to_claim[embed_id] = row

    embedding_config = dict(settings.get("EMBEDDING_CONFIG") or {})
    embedding_config["USER_DB_BASE_DIR"] = settings.get("USER_DB_BASE_DIR")
    if not embedding_config.get("USER_DB_BASE_DIR"):
        logger.debug("Claims clustering: USER_DB_BASE_DIR missing; skipping embedding load.")
        return [], len(embed_ids)

    try:
        manager = ChromaDBManager(user_id=str(user_id), user_embedding_config=embedding_config)
    except Exception as exc:
        logger.debug(f"Claims clustering: unable to initialize ChromaDBManager: {exc}")
        return [], len(embed_ids)

    collection_name = f"claims_for_{user_id}"
    try:
        collection = manager.get_or_create_collection(collection_name)
    except Exception as exc:
        logger.debug(f"Claims clustering: unable to access claims collection '{collection_name}': {exc}")
        return [], len(embed_ids)

    embeddings: list[ClaimEmbedding] = []
    missing = 0
    for batch in _batched_ids(embed_ids, batch_size):
        try:
            result = collection.get(ids=batch, include=["embeddings"])
        except Exception as exc:
            logger.debug(f"Claims clustering: collection.get failed: {exc}")
            return [], len(embed_ids)
        result_ids = result.get("ids") or []
        result_embeddings = result.get("embeddings") or []
        for embed_id, embedding in zip(result_ids, result_embeddings):
            if embedding is None:
                continue
            row = id_to_claim.get(embed_id)
            if not row:
                continue
            try:
                vec = [float(x) for x in embedding]
            except Exception:
                continue
            norm = _vector_norm(vec)
            if norm <= 0:
                continue
            embeddings.append(
                ClaimEmbedding(
                    claim_id=int(row.get("id") or 0),
                    media_id=int(row.get("media_id") or 0),
                    chunk_index=int(row.get("chunk_index") or 0),
                    claim_text=str(row.get("claim_text") or ""),
                    embedding=vec,
                    norm=norm,
                )
            )
        missing += max(0, len(batch) - len(result_ids))
    return embeddings, missing


def _cluster_embeddings(
    embeddings: list[ClaimEmbedding],
    similarity_threshold: float,
    min_size: int,
) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for claim in sorted(embeddings, key=lambda c: c.claim_id):
        best_idx: int | None = None
        best_sim = similarity_threshold
        for idx, cluster in enumerate(clusters):
            sim = _cosine_similarity(
                claim.embedding,
                claim.norm,
                cluster["centroid"],
                cluster["centroid_norm"],
            )
            if sim >= similarity_threshold and sim > best_sim:
                best_idx = idx
                best_sim = sim
        if best_idx is None:
            clusters.append(
                {
                    "members": [claim],
                    "sum": list(claim.embedding),
                    "count": 1,
                    "centroid": list(claim.embedding),
                    "centroid_norm": claim.norm,
                }
            )
        else:
            target = clusters[best_idx]
            target["members"].append(claim)
            target["count"] += 1
            for i, val in enumerate(claim.embedding):
                target["sum"][i] += val
            target["centroid"] = [v / target["count"] for v in target["sum"]]
            target["centroid_norm"] = _vector_norm(target["centroid"])

    payload: list[dict[str, Any]] = []
    for cluster in clusters:
        members: list[ClaimEmbedding] = cluster["members"]
        if len(members) < min_size:
            continue
        centroid = cluster["centroid"]
        centroid_norm = cluster["centroid_norm"]
        rep = members[0]
        member_payload = []
        for member in members:
            similarity = _cosine_similarity(member.embedding, member.norm, centroid, centroid_norm)
            member_payload.append({"claim_id": member.claim_id, "similarity": similarity})
        payload.append(
            {
                "canonical_claim_text": rep.claim_text,
                "representative_claim_id": rep.claim_id,
                "members": member_payload,
            }
        )
    return payload


def rebuild_claim_clusters_embeddings(
    *,
    db: MediaDatabase,
    user_id: str,
    min_size: int,
    similarity_threshold: float | None = None,
) -> dict[str, Any]:
    try:
        min_size = int(min_size)
    except (TypeError, ValueError):
        min_size = 2
    min_size = max(1, min_size)

    if similarity_threshold is None:
        try:
            similarity_threshold = float(settings.get("CLAIMS_CLUSTER_SIMILARITY_THRESHOLD", 0.85))
        except Exception:
            similarity_threshold = 0.85
    try:
        similarity_threshold = float(similarity_threshold)
    except (TypeError, ValueError):
        similarity_threshold = 0.85
    similarity_threshold = max(0.0, min(1.0, similarity_threshold))

    batch_size = 200
    try:
        batch_size = int(settings.get("CLAIMS_CLUSTER_BATCH_SIZE", 200))
    except Exception:
        batch_size = 200
    batch_size = max(1, batch_size)

    embeddings, missing = _load_claim_embeddings(db=db, user_id=str(user_id), batch_size=batch_size)
    if not embeddings:
        return {
            "clusters_created": 0,
            "claims_assigned": 0,
            "method": "embeddings",
            "claims_skipped": missing,
            "status": "no_embeddings",
        }

    clusters = _cluster_embeddings(embeddings, similarity_threshold, min_size)
    result = db.rebuild_claim_clusters_from_assignments(user_id=str(user_id), clusters=clusters)
    result.update(
        {
            "method": "embeddings",
            "claims_skipped": missing,
            "similarity_threshold": similarity_threshold,
        }
    )
    return result
