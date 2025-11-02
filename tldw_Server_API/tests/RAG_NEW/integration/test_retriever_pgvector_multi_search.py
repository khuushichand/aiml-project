import asyncio
from typing import List, Dict, Any

import pytest

from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreConfig, VectorStoreType
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.pgvector_adapter import PGVectorAdapter
from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import MediaDBRetriever, RetrievalConfig


pytestmark = pytest.mark.pg_integration


def _demo_records(dim: int = 8):
    ids = ["a", "b", "c"]
    vecs = [[0.0] * dim, [0.1] * dim, [0.2] * dim]
    docs = ["A", "B", "C"]
    metas_base = [
        {"media_id": "1", "kind": "chunk", "num": 1},
        {"media_id": "2", "kind": "chunk", "num": 2},
        {"media_id": "3", "kind": "chunk", "num": 3},
    ]
    return ids, vecs, docs, metas_base


def test_retriever_multi_search_with_jsonb_filter(pgvector_dsn):
    dim = 8
    user_id = "42"
    coll_a = f"user_{user_id}_media_embeddings_a"
    coll_b = f"user_{user_id}_media_embeddings_b"

    async def _run():
        cfg = VectorStoreConfig(
            store_type=VectorStoreType.PGVECTOR,
            connection_params={"dsn": pgvector_dsn},
            embedding_dim=dim,
            user_id=user_id,
        )
        adapter = PGVectorAdapter(cfg)
        await adapter.initialize()
        await adapter.create_collection(coll_a, metadata={"embedding_dimension": dim})
        await adapter.create_collection(coll_b, metadata={"embedding_dimension": dim})

        ids, vecs, docs, metas_base = _demo_records(dim)
        # Tag collections differently to exercise JSONB filters
        metas_a: List[Dict[str, Any]] = [{**m, "tag": "a"} for m in metas_base]
        metas_b: List[Dict[str, Any]] = [{**m, "tag": "b"} for m in metas_base]
        await adapter.upsert_vectors(coll_a, ids, vecs, docs, metas_a)
        await adapter.upsert_vectors(coll_b, ids, vecs, docs, metas_b)

        # Wire a retriever and inject the adapter (avoid reading user-facing config)
        retr = MediaDBRetriever(
            db_path="Databases/Media_DB_v2.db",
            config=RetrievalConfig(max_results=5),
            user_id=user_id,
        )
        retr.vector_store = adapter

        # JSONB filter: match tag 'b' OR numeric num >= 2
        metadata_filter = {"$or": [{"tag": "b"}, {"num": {"$gte": 2}}]}

        docs_out = await retr._retrieve_vector(
            query="ignored",
            media_type=None,
            index_namespace=f"user_{user_id}_media_embeddings_*",
            query_vector=vecs[1],
            metadata_filter=metadata_filter,
        )

        # Expect at least one hit from the 'b' collection and/or num >= 2
        assert len(docs_out) >= 1
        assert any(
            (d.metadata.get("tag") == "b") or (float(d.metadata.get("num", 0)) >= 2)
            for d in docs_out
        )

        # Cleanup
        await adapter.delete_collection(coll_a)
        await adapter.delete_collection(coll_b)

    asyncio.run(_run())
