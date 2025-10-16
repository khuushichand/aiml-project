#!/usr/bin/env python3
"""
HYDE Backfill CLI (lightweight skeleton)

Iterates existing chunks in a vector store collection and generates HYDE
questions (doc2query) to upsert as 'hyde_q' vectors alongside chunk vectors.

This is a best-effort developer tool; it respects HYDE_* flags from settings
and can run in dry-run mode. For large collections, prefer running during
off-peak hours and consider setting HYDE_MAX_VECTORS_PER_DOC.
"""
import argparse
import asyncio
from functools import lru_cache
from typing import Any, Dict, List, Sequence

from loguru import logger

from tldw_Server_API.app.core.Metrics import increment_counter


async def _run(args: argparse.Namespace) -> int:
    # Deferred imports to avoid heavy deps unless invoked
    from tldw_Server_API.app.core.config import settings
    from tldw_Server_API.app.core.RAG.rag_service.vector_stores.factory import VectorStoreFactory
    from tldw_Server_API.app.core.Embeddings.hyde import generate_questions, question_hash
    from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import (  # noqa: E501
        create_embeddings_batch,
        HFModelCfg,
        ONNXModelCfg,
        OpenAIModelCfg,
        LocalAPICfg,
    )

    user_id = args.user_id or str(settings.get("SINGLE_USER_FIXED_ID", "1"))
    # Resolve vector store adapter from settings
    base = VectorStoreFactory.create_from_settings(settings, user_id=user_id)
    if not base:
        logger.error("No vector store configured; aborting")
        return 2
    adapter = base  # already an initialized adapter factory returns adapter
    await adapter.initialize()
    raw_store_type = getattr(getattr(adapter, "config", None), "store_type", None)
    if raw_store_type is None:
        store_label = "unknown"
    else:
        store_label = str(getattr(raw_store_type, "value", raw_store_type))
        if not store_label:
            store_label = "unknown"

    # HYDE config
    hyde_n = int(settings.get("HYDE_QUESTIONS_PER_CHUNK", 3) or 3)
    hyde_provider = settings.get("HYDE_PROVIDER")
    hyde_model = settings.get("HYDE_MODEL")
    hyde_temp = float(settings.get("HYDE_TEMPERATURE", 0.2) or 0.2)
    hyde_max_tokens = int(settings.get("HYDE_MAX_TOKENS", 96) or 96)
    hyde_lang_cfg = str(settings.get("HYDE_LANGUAGE", "auto") or "auto").lower()
    hyde_ver = settings.get("HYDE_PROMPT_VERSION", 1)
    hyde_metric_labels = {
        "provider": hyde_provider or "unknown",
        "model": hyde_model or "unknown",
        "source": "backfill",
    }

    # Build embedding app-config once per (provider, model) pair
    @lru_cache(maxsize=8)
    def _build_app_config(model_id: str, provider: str) -> Dict[str, Any]:
        provider_norm = (provider or "").lower()
        base_dir = settings.get("EMBEDDINGS_MODEL_STORAGE_DIR", "./models/embedding_models_data/")
        if provider_norm in ("huggingface", "hf"):
            cfg_obj = HFModelCfg(model_name_or_path=model_id)
        elif provider_norm == "onnx":
            cfg_obj = ONNXModelCfg(model_name_or_path=model_id)
        elif provider_norm == "openai":
            cfg_obj = OpenAIModelCfg(model_name_or_path=model_id)
        elif provider_norm == "local_api":
            api_url = settings.get("EMBEDDINGS_LOCAL_API_URL")
            if not api_url:
                raise ValueError("Local API provider requires EMBEDDINGS_LOCAL_API_URL")
            cfg_obj = LocalAPICfg(model_name_or_path=model_id, api_url=api_url, api_key=settings.get("EMBEDDINGS_LOCAL_API_KEY"))
        else:
            raise ValueError(f"Unsupported embedding provider '{provider}' for HYDE backfill")
        return {
            "embedding_config": {
                "default_model_id": model_id,
                "model_storage_base_dir": base_dir,
                "models": {model_id: cfg_obj},
            }
        }

    async def _embed_questions(
        texts: Sequence[str],
        provider: str,
        model_id: str,
    ) -> List[List[float]]:
        if not texts:
            return []
        loop = asyncio.get_event_loop()

        def _call() -> List[List[float]]:
            app_cfg = _build_app_config(model_id, provider)
            return create_embeddings_batch(list(texts), app_cfg, model_id)

        return await loop.run_in_executor(None, _call)

    store = args.collection
    logger.info(f"Backfilling HYDE for collection='{store}' user={user_id} N={hyde_n} dry_run={args.dry_run}")

    # Page through vectors (chunk only)
    limit = args.page_size
    offset = 0
    total_upserted = 0
    while True:
        page = await adapter.list_vectors_paginated(store, limit=limit, offset=offset, filter={"kind": "chunk"})
        items = (page or {}).get("items", [])
        if not items:
            break
        for it in items:
            text = it.get("content") or ""
            meta: Dict[str, Any] = dict(it.get("metadata") or {})
            chunk_id = meta.get("chunk_id") or it.get("id")
            if not text or not chunk_id:
                continue

            chunk_language = meta.get("language")
            if not chunk_language:
                # Best-effort heuristic: treat ASCII-heavy text as English
                non_ascii = sum(1 for c in text if ord(c) > 127)
                chunk_language = "english" if len(text) and (non_ascii / max(1, len(text)) <= 0.1) else "multilingual"
                meta.setdefault("language", chunk_language)

            try:
                questions: List[str] = generate_questions(
                    text=text,
                    n=hyde_n,
                    provider=hyde_provider,
                    model=hyde_model,
                    temperature=hyde_temp,
                    max_tokens=hyde_max_tokens,
                    language=chunk_language if hyde_lang_cfg == "auto" else hyde_lang_cfg,
                    prompt_version=hyde_ver,
                )
            except Exception as e:
                increment_counter(
                    "hyde_generation_failures_total",
                    1,
                    labels={**hyde_metric_labels, "reason": type(e).__name__},
                )
                logger.warning(f"HYDE generation failed for {chunk_id}: {e}")
                continue
            if not questions:
                continue
            increment_counter(
                "hyde_questions_generated_total",
                len(questions),
                labels=hyde_metric_labels,
            )
            logger.debug(f"Chunk {chunk_id}: generated {len(questions)} HYDE questions")
            if args.dry_run:
                logger.info(f"Would upsert {len(questions)} HYDE vectors for chunk {chunk_id}")
                continue

            embedder_provider = meta.get("embedder_name") or meta.get("model_provider") or settings.get("EMBEDDINGS_DEFAULT_PROVIDER") or "huggingface"
            embedder_model = meta.get("embedder_version") or meta.get("model_used") or settings.get("EMBEDDINGS_DEFAULT_MODEL_ID")
            if not embedder_model:
                logger.warning(f"Skipping chunk {chunk_id}: no embedder_version/DEFAULT provided")
                continue

            try:
                vectors = await _embed_questions(questions, embedder_provider, embedder_model)
            except Exception as e:
                logger.warning(f"Failed to embed HYDE questions for {chunk_id} ({embedder_provider}:{embedder_model}): {e}")
                continue

            if len(vectors) != len(questions):
                logger.warning(
                    f"Embedder returned {len(vectors)} vectors for {len(questions)} questions; skipping chunk {chunk_id}"
                )
                continue

            ids: List[str] = []
            docs: List[str] = []
            metas: List[Dict[str, Any]] = []
            vecs: List[List[float]] = []
            generator_label = f"{hyde_provider or ''}:{hyde_model or ''}".strip(":")

            for rank, (question, vec) in enumerate(zip(questions, vectors), start=1):
                vec_list: List[float]
                if isinstance(vec, (list, tuple)):
                    vec_list = list(vec)
                else:
                    try:
                        vec_list = list(vec)  # type: ignore[arg-type]
                    except Exception:
                        logger.warning(f"HYDE backfill: could not convert embedding for chunk {chunk_id}, skipping question")
                        continue
                q_hash = question_hash(question)
                ids.append(f"{chunk_id}:q:{q_hash[:8]}")
                docs.append(question)
                q_meta = {
                    **meta,
                    "kind": "hyde_q",
                    "parent_chunk_id": chunk_id,
                    "hyde_rank": rank - 1,
                    "hyde_prompt_version": hyde_ver,
                    "hyde_generator": generator_label,
                    "question_hash": q_hash,
                }
                if hyde_lang_cfg == "auto" and chunk_language:
                    q_meta.setdefault("language", chunk_language)
                metas.append(q_meta)
                vecs.append(vec_list)

            if not ids:
                continue
            await adapter.upsert_vectors(store, ids=ids, vectors=vecs, documents=docs, metadatas=metas)
            increment_counter(
                "hyde_vectors_written_total",
                len(ids),
                labels={"store": store_label or "unknown"},
            )
            total_upserted += len(ids)
        offset += len(items)
        if len(items) < limit:
            break
    logger.info(f"HYDE backfill complete; upserted={total_upserted}")
    return 0


def main():
    p = argparse.ArgumentParser(description="HYDE backfill CLI")
    p.add_argument("--user-id", dest="user_id", help="User ID (default single-user)")
    p.add_argument("--collection", required=True, help="Collection name (vector store)")
    p.add_argument("--page-size", type=int, default=100, help="Pagination size")
    p.add_argument("--dry-run", action="store_true", help="Do not write; just report")
    args = p.parse_args()
    rc = asyncio.run(_run(args))
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
