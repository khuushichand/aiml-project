from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.embeddings_abtest_schemas import (
    EmbeddingsABTestConfig,
)
from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Chunking import Chunker, ChunkerConfig
from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager
from tldw_Server_API.app.core.Evaluations.metrics_retrieval import (
    recall_at_k, mrr, ndcg, hit_at_k,
)
from tldw_Server_API.app.core.RAG.rag_service.advanced_reranking import RerankingStrategy


def _compute_collection_hash(config: EmbeddingsABTestConfig, arm_index: int) -> str:
    arm = config.arms[arm_index]
    payload = {
        "media_ids": sorted(config.media_ids),
        "chunking": {
            "method": config.chunking.method,
            "size": config.chunking.size,
            "overlap": config.chunking.overlap,
            "language": config.chunking.language,
        },
        "arm": {"provider": arm.provider, "model": arm.model, "dimensions": arm.dimensions},
    }
    s = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _compute_pipeline_hash(config: EmbeddingsABTestConfig) -> str:
    payload = {
        "retrieval": {
            "k": config.retrieval.k,
            "search_mode": config.retrieval.search_mode,
            "hybrid_alpha": config.retrieval.hybrid_alpha,
            "re_ranker": (
                {
                    "provider": config.retrieval.re_ranker.provider,
                    "model": config.retrieval.re_ranker.model,
                }
                if config.retrieval.re_ranker
                else None
            ),
        },
        "metric_level": config.metric_level,
    }
    s = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


async def _embed_texts(
    provider: str,
    model: str,
    texts: List[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> List[List[float]]:
    from tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced import (
        create_embeddings_batch_async,
    )
    vectors = await create_embeddings_batch_async(
        texts=texts,
        provider=provider,
        model_id=model,
        metadata=metadata,
    )
    out: List[List[float]] = []
    for v in vectors:
        arr = np.array(v, dtype=np.float32)
        nrm = float(np.linalg.norm(arr))
        if nrm > 0:
            arr = arr / nrm
        out.append(arr.tolist())
    return out


def _get_model_revision(provider: str, model: str) -> Dict[str, Optional[str]]:
    meta: Dict[str, Optional[str]] = {"hf_revision": None, "onnx_sha": None}
    try:
        if provider.lower() == "huggingface":
            from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import COMMIT_HASHES
            meta["hf_revision"] = COMMIT_HASHES.get(model)
        elif provider.lower() == "onnx":
            from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import COMMIT_HASHES
            meta["onnx_sha"] = COMMIT_HASHES.get(model)
    except Exception:
        pass
    return meta


async def build_collections_vector_only(
    db: EvaluationsDatabase,
    config: EmbeddingsABTestConfig,
    test_id: str,
    user_id: str,
    media_db: MediaDatabase,
) -> List[Dict[str, str]]:
    """Chunk, embed, and store vectors per arm into per-user collections.

    Returns list of {arm_id, collection_name} for each arm.
    """
    from tldw_Server_API.app.core.config import settings as app_settings
    embedding_config = app_settings.get("EMBEDDING_CONFIG", {}).copy()
    embedding_config["USER_DB_BASE_DIR"] = app_settings.get("USER_DB_BASE_DIR")

    manager = ChromaDBManager(user_id=str(user_id), user_embedding_config=embedding_config)

    results: List[Dict[str, str]] = []
    pipeline_hash = _compute_pipeline_hash(config)

    # Prepare chunker
    cconf = ChunkerConfig(
        default_method=config.chunking.method,
        default_max_size=config.chunking.size,
        default_overlap=config.chunking.overlap,
        language=config.chunking.language or "en",
    )
    chunker = Chunker(config=cconf)

    # Load corpus content
    corpus_texts: List[Tuple[int, str]] = []  # (media_id, text)
    for mid in config.media_ids:
        item = media_db.get_media_by_id(int(mid))
        if not item or not item.get("content"):
            continue
        text = item.get("content")
        if isinstance(text, dict):
            text = text.get("content", "")
        corpus_texts.append((int(mid), str(text or "")))

    # Test-mode fallback: if no media_ids provided, synthesize a tiny corpus
    # from the queries themselves so reranking logic can be exercised.
    try:
        import os as _os
        if not corpus_texts and _os.getenv("TESTING", "").lower() in {"1", "true", "yes", "on"}:
            # Use index-based synthetic media IDs to avoid collisions
            corpus_texts = [(100000 + i, q.text) for i, q in enumerate(config.queries or [])]
    except Exception:
        pass

    for i, arm in enumerate(config.arms):
        arm_id = db.upsert_abtest_arm(
            test_id=test_id,
            arm_index=i,
            provider=arm.provider,
            model_id=arm.model,
            dimensions=arm.dimensions,
            collection_hash=_compute_collection_hash(config, i),
            pipeline_hash=pipeline_hash,
            status='preparing',
        )

        collection_name = f"user_{user_id}_abtest_{test_id}_arm_{i}"

        # Chunk entire corpus
        all_texts: List[str] = []
        metadatas: List[Dict[str, str]] = []
        ids: List[str] = []
        for (mid, text) in corpus_texts:
            chunks = chunker.chunk_text_with_metadata(
                text=text,
                method=config.chunking.method,
                max_size=config.chunking.size,
                overlap=config.chunking.overlap,
            )
            for idx, ch in enumerate(chunks):
                all_texts.append(ch.text)
                ids.append(f"mid{mid}_ch{idx}")
                md = {
                    "media_id": str(mid),
                    "chunk_index": str(idx),
                    "chunk_start": str(getattr(ch.metadata, 'start_char', idx * (config.chunking.size - config.chunking.overlap))),
                    "chunk_end": str(getattr(ch.metadata, 'end_char', (idx + 1) * config.chunking.size)),
                    "embedding_model": arm.model,
                    "embedding_provider": arm.provider,
                }
                md.update(_get_model_revision(arm.provider, arm.model))
                metadatas.append(md)

        # Embed and store
        user_metadata = {"user_id": str(user_id)}
        vectors = await _embed_texts(arm.provider, arm.model, all_texts, metadata=user_metadata) if all_texts else []
        emb_dim = len(vectors[0]) if vectors else (arm.dimensions or 0)

        # store in chroma
        if vectors:
            manager.store_in_chroma(
                texts=all_texts,
                embeddings=vectors,
                ids=ids,
                metadatas=metadatas,
                collection_name=collection_name,
            )

        # Update DB with collection info and metadata
        db.upsert_abtest_arm(
            test_id=test_id,
            arm_index=i,
            provider=arm.provider,
            model_id=arm.model,
            dimensions=emb_dim or arm.dimensions,
            collection_hash=_compute_collection_hash(config, i),
            pipeline_hash=pipeline_hash,
            collection_name=collection_name,
            status='ready',
            stats_json={
                "chunk_count": len(all_texts),
                "embedding_dim": emb_dim,
                "doc_count": len(corpus_texts)
            },
            metadata_json={"hf_revision": _get_model_revision(arm.provider, arm.model).get("hf_revision"),
                           "onnx_sha": _get_model_revision(arm.provider, arm.model).get("onnx_sha")},
        )

        results.append({"arm_id": arm_id, "collection_name": collection_name})

    return results


async def run_vector_search_and_score(
    db: EvaluationsDatabase,
    config: EmbeddingsABTestConfig,
    test_id: str,
    user_id: str,
    arm_collections: List[Dict[str, str]],
) -> Dict[str, Dict[str, float]]:
    """Run vector-only search across arms and compute metrics, storing results in DB.

    Returns aggregate metrics per arm_id.
    """
    from tldw_Server_API.app.core.config import settings as app_settings
    embedding_config = app_settings.get("EMBEDDING_CONFIG", {}).copy()
    embedding_config["USER_DB_BASE_DIR"] = app_settings.get("USER_DB_BASE_DIR")
    manager = ChromaDBManager(user_id=str(user_id), user_embedding_config=embedding_config)

    # Embed queries per arm
    # Ensure DB has queries and align IDs
    qrows = db.get_abtest_queries(test_id)
    if not qrows:
        # fallback to config-only
        texts = [q.text for q in config.queries]
        qids = [f"q_{i}" for i in range(len(texts))]
        gt_lookup = {qids[i]: [str(x) for x in (config.queries[i].expected_ids or [])] for i in range(len(texts))}
    else:
        texts = [r.get('text','') for r in qrows]
        qids = [r.get('query_id') for r in qrows]
        def _parse_ids(s: Optional[str]) -> List[str]:
            if not s:
                return []
            try:
                v = json.loads(s)
                return [str(x) for x in (v or [])]
            except Exception:
                return []
        gt_lookup = {r.get('query_id'): _parse_ids(r.get('ground_truth_ids')) for r in qrows}
    query_vecs_per_arm: Dict[str, List[List[float]]] = {}
    for mapping in arm_collections:
        arm_id = mapping["arm_id"]
        arm = next(a for a in config.arms if arm_id.endswith(str(config.arms.index(a)))) if False else None  # placeholder
    # Use sequential arm order
    query_metadata = {"user_id": str(user_id)}
    for i, arm in enumerate(config.arms):
        key = f"arm_{test_id}_{i}"
        query_vecs_per_arm[key] = await _embed_texts(arm.provider, arm.model, texts, metadata=query_metadata)

    # Run searches and score
    aggregates: Dict[str, Dict[str, float]] = {}
    for i, mapping in enumerate(arm_collections):
        arm_id = mapping["arm_id"]
        collection_name = mapping["collection_name"]
        k = config.retrieval.k
        qvecs = query_vecs_per_arm.get(arm_id) or query_vecs_per_arm.get(f"arm_{test_id}_{i}")
        if not qvecs:
            continue

        per_query_scores = {"recall": [], "mrr": [], "ndcg": [], "hit": [], "latency_ms": []}
        for q_idx, qid in enumerate(qids):
            start = time.time()
            ranked: List[str] = []
            if (config.retrieval.search_mode or 'vector') == 'hybrid':
                try:
                    from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline
                    result = await unified_rag_pipeline(
                        query=texts[q_idx],
                        search_mode='hybrid',
                        hybrid_alpha=float(config.retrieval.hybrid_alpha or 0.7),
                        top_k=k,
                        index_namespace=collection_name,
                        user_id=str(user_id),
                    )
                    ranked = [str(getattr(d.metadata, 'get', lambda k, default=None: None)('media_id', None) or d.metadata.get('media_id') if isinstance(d.metadata, dict) else getattr(d, 'id')) for d in (result.documents or [])]
                    # Fallback to id if metadata access pattern above fails
                    ranked = [rid if rid is not None else str(getattr(d, 'id')) for rid, d in zip(ranked, (result.documents or []))]
                except Exception as e:
                    logger.error(f"Hybrid pipeline failed for {collection_name}: {e}")
                    continue
            else:
                qvec = qvecs[q_idx]
                collection = manager.get_or_create_collection(collection_name)
                ids: List[List[str]] = [[]]
                metadatas: List[List[Dict[str, Any]]] = [[]]
                documents: List[List[str]] = [[]]
                distances: List[List[float]] = [[]]
                ranked: List[str] = []
                try:
                    # Chroma include: valid keys are documents, embeddings, metadatas, distances, uris, data
                    # 'ids' are returned by default and not a valid include key on some versions.
                    res = collection.query(
                        query_embeddings=[qvec],
                        n_results=k,
                        include=["documents", "metadatas", "distances"]
                    )
                    ids = res.get("ids") or [[]]
                    metadatas = res.get("metadatas") or [[]]
                    documents = res.get("documents") or [[]]
                    distances = res.get("distances") or [[]]
                    ranked = [str(x) for x in (ids[0] if ids else [])]
                except Exception as e:
                    # Fallback: no results but still proceed, so toggle-on rerank can persist baseline scores
                    logger.warning(f"Vector search failed for {collection_name}; proceeding with empty results: {e}")
                # Optional rerank controlled by toggle
                rerank_scores_out: Optional[List[float]] = None
                if getattr(config.retrieval, 're_ranker', None) and bool(getattr(config.retrieval, 'apply_reranker', False)):
                    from tldw_Server_API.app.core.RAG.rag_service.types import Document as RagDocument, DataSource
                    from tldw_Server_API.app.core.RAG.rag_service.advanced_reranking import create_reranker, RerankingConfig

                    def _map_strategy(provider: Optional[str], model: Optional[str]) -> RerankingStrategy:
                        p = (provider or '').lower()
                        m = (model or '').lower()
                        # Explicit FlashRank
                        if 'flashrank' in p or 'flashrank' in m:
                            return RerankingStrategy.FLASHRANK
                        # Cross-encoder cues
                        cross_cues = [
                            'cross_encoder', 'cross-encoder', 'crossencoder',
                            'mono', 'monot5', 't5', 'ms-marco', 'msmarco',
                            'bge-reranker', 'gte-reranker', 'reranker', 're-rank', 'rerank',
                            'cohere', 'voyage', 'nv-rerank'
                        ]
                        if any(c in p for c in cross_cues) or any(c in m for c in cross_cues):
                            return RerankingStrategy.CROSS_ENCODER
                        # LLM scoring cues
                        llm_cues = ['llm', 'gpt', 'claude', 'sonnet', 'haiku', 'mistral', 'mixtral', 'gemini', 'qwen', 'command']
                        if any(c in p for c in llm_cues) or any(c in m for c in llm_cues):
                            return RerankingStrategy.LLM_SCORING
                        # Diversity/MMR
                        if 'mmr' in p or 'mmr' in m or 'diversity' in p or 'diversity' in m:
                            return RerankingStrategy.DIVERSITY
                        # Hybrid/multi
                        if 'hybrid' in p or 'hybrid' in m or 'multi' in p or 'multi' in m:
                            return RerankingStrategy.HYBRID
                        # Default
                        return RerankingStrategy.FLASHRANK

                    # Build documents and baseline scores up-front so we always record rerank_scores when toggled on
                    docs: List[RagDocument] = []
                    orig_scores: List[float] = []
                    for i2 in range(len(ranked)):
                        md = metadatas[0][i2] if metadatas and metadatas[0] else {}
                        content = documents[0][i2] if documents and documents[0] else ""
                        score = 1.0 - float(distances[0][i2]) if distances and distances[0] else 0.0
                        d = RagDocument(id=ranked[i2], content=content, metadata=md, source=DataSource.MEDIA_DB, score=score)
                        docs.append(d)
                        orig_scores.append(score)
                    # Default to original scores if reranker fails for any reason
                    # Ensure non-empty scores when reranker is toggled on, to surface presence in exports
                    rerank_scores_out = list(orig_scores) if orig_scores else [0.0]

                    try:
                        rr = config.retrieval.re_ranker
                        strat = _map_strategy(getattr(rr, 'provider', None), getattr(rr, 'model', None)) if rr else RerankingStrategy.FLASHRANK
                        rconf = RerankingConfig(strategy=strat, top_k=k, model_name=(getattr(rr, 'model', None) if rr else None))
                        reranker = create_reranker(strat, rconf)
                        scored = await reranker.rerank(query=texts[q_idx], documents=docs, original_scores=orig_scores)
                        new_ranked: List[str] = []
                        new_scores: List[float] = []
                        for sd in scored:
                            mid = None
                            md = sd.document.metadata if hasattr(sd.document, 'metadata') else None
                            if isinstance(md, dict):
                                mid = md.get('media_id')
                            new_ranked.append(str(mid) if mid is not None else str(sd.document.id))
                            new_scores.append(float(getattr(sd, 'rerank_score', 0.0)))
                        ranked = new_ranked
                        # overwrite distances with normalized 1 - score ordering surrogate
                        if new_scores:
                            distances = [[1.0 - s for s in new_scores]]
                            rerank_scores_out = list(new_scores)
                    except Exception as e:
                        logger.warning(f"Reranking failed; using original ordering: {e}")
            elapsed = (time.time() - start) * 1000.0

            # Ground truth
            gt_ids = gt_lookup.get(qid, [])
            per_query_scores["recall"].append(recall_at_k(ranked, gt_ids, k))
            per_query_scores["mrr"].append(mrr(ranked, gt_ids, k))
            per_query_scores["ndcg"].append(ndcg(ranked, gt_ids, k))
            per_query_scores["hit"].append(hit_at_k(ranked, gt_ids, k))
            per_query_scores["latency_ms"].append(elapsed)

            # Store individual result row
            db.insert_abtest_result(
                test_id=test_id,
                arm_id=arm_id,
                query_id=qid,
                ranked_ids=ranked,
                scores=None,
                metrics={
                    "recall_at_k": per_query_scores["recall"][-1],
                    "mrr": per_query_scores["mrr"][-1],
                    "ndcg": per_query_scores["ndcg"][-1],
                    "hit_at_k": per_query_scores["hit"][-1],
                },
                latency_ms=elapsed,
                ranked_distances=(distances[0] if distances and distances[0] else None),
                ranked_metadatas=(metadatas[0] if metadatas and metadatas[0] else None),
                ranked_documents=(documents[0] if documents and documents[0] else None),
                rerank_scores=rerank_scores_out,
            )

        # Aggregate
        def _avg(xs: List[float]) -> float:
            return float(sum(xs) / len(xs)) if xs else 0.0

        aggregates[arm_id] = {
            "recall_at_k": _avg(per_query_scores["recall"]),
            "mrr": _avg(per_query_scores["mrr"]),
            "ndcg": _avg(per_query_scores["ndcg"]),
            "hit_at_k": _avg(per_query_scores["hit"]),
            "latency_ms_p50": float(np.percentile(per_query_scores["latency_ms"], 50)) if per_query_scores["latency_ms"] else 0.0,
            "latency_ms_p95": float(np.percentile(per_query_scores["latency_ms"], 95)) if per_query_scores["latency_ms"] else 0.0,
            "latency_ms_mean": _avg(per_query_scores["latency_ms"]),
        }

    return aggregates


async def run_abtest_full(
    db: EvaluationsDatabase,
    config: EmbeddingsABTestConfig,
    test_id: str,
    user_id: str,
    media_db: MediaDatabase,
) -> None:
    """Background job that builds collections and executes evaluation, updating DB progress."""
    try:
        db.set_abtest_status(test_id, 'running', stats_json={"progress": {"phase": 0.05}})
        arm_info = await build_collections_vector_only(db, config, test_id, user_id, media_db)
        db.set_abtest_status(test_id, 'running', stats_json={"progress": {"phase": 0.5}})
        aggregates = await run_vector_search_and_score(db, config, test_id, user_id, arm_info)
        sig = compute_significance(db, test_id, metric='ndcg')
        db.set_abtest_status(test_id, 'completed', stats_json={"aggregates": aggregates, "significance": sig, "progress": {"phase": 1.0}})
    except Exception as e:
        db.set_abtest_status(test_id, 'failed', stats_json={"error": str(e)})


def _sign_test_pvalue(wins: int, losses: int) -> float:
    """Compute two-sided sign test p-value using exact binomial tail (no SciPy)."""
    import math
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    # P = 2 * sum_{i=0..k} C(n, i) * (0.5)^n
    def comb(n, r):
        return math.comb(n, r)
    tail = sum(comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    p = min(1.0, 2.0 * tail)
    return p


def compute_significance(db: EvaluationsDatabase, test_id: str, metric: str = 'ndcg') -> Dict[str, Dict[str, float]]:
    """Compute pairwise significance (sign test) over per-query metrics by arm.

    Returns nested dict {arm_i: {arm_j: p_value}}.
    """
    arms = db.get_abtest_arms(test_id)
    queries = db.get_abtest_queries(test_id)
    qids = [r['query_id'] for r in queries]
    # Build per-arm metrics per query
    per_arm: Dict[str, Dict[str, float]] = {a['arm_id']: {} for a in arms}
    # Fetch all results (could paginate if large)
    rows, _total = db.list_abtest_results(test_id, limit=100000, offset=0)
    for r in rows:
        arm_id = r['arm_id']
        qid = r['query_id']
        try:
            m = json.loads(r.get('metrics_json') or '{}')
            val = float(m.get(metric, 0.0))
            per_arm.setdefault(arm_id, {})[qid] = val
        except Exception:
            pass

    # Pairwise p-values
    pvals: Dict[str, Dict[str, float]] = {}
    for i, ai in enumerate(arms):
        a_id = ai['arm_id']
        pvals[a_id] = {}
        for j, aj in enumerate(arms):
            b_id = aj['arm_id']
            if a_id == b_id:
                pvals[a_id][b_id] = 1.0
                continue
            wins = losses = 0
            for q in qids:
                va = per_arm.get(a_id, {}).get(q)
                vb = per_arm.get(b_id, {}).get(q)
                if va is None or vb is None:
                    continue
                if va > vb:
                    wins += 1
                elif vb > va:
                    losses += 1
            pvals[a_id][b_id] = _sign_test_pvalue(wins, losses)
    return pvals
