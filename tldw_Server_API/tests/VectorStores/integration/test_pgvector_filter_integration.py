import asyncio
import uuid

import pytest

from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreConfig, VectorStoreType
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.pgvector_adapter import PGVectorAdapter


pytestmark = pytest.mark.pg_integration


def test_search_empty_in_returns_zero(pgvector_dsn):
    dim = 8
    coll = f"it_filter_in_{uuid.uuid4().hex[:6]}"

    async def _run():
        cfg = VectorStoreConfig(
            store_type=VectorStoreType.PGVECTOR,
            connection_params={"dsn": pgvector_dsn},
            embedding_dim=dim,
            user_id="it",
        )
        adapter = PGVectorAdapter(cfg)
        await adapter.initialize()
        await adapter.create_collection(coll, metadata={"embedding_dimension": dim})
        ids = ["a", "b", "c"]
        vecs = [[0.1] * dim, [0.2] * dim, [0.3] * dim]
        docs = ["A", "B", "C"]
        metas = [
            {"media_id": "1", "kind": "chunk"},
            {"media_id": "2", "kind": "chunk"},
            {"media_id": "3", "kind": "chunk"},
        ]
        await adapter.upsert_vectors(coll, ids, vecs, docs, metas)

        # Empty $in should match no rows
        res_empty = await adapter.search(
            coll, vecs[0], k=10, filter={"media_id": {"$in": []}}
        )
        assert res_empty == []

        # Non-empty $in should match a subset
        res_subset = await adapter.search(
            coll, vecs[0], k=10, filter={"media_id": {"$in": ["1", "3"]}}
        )
        assert len(res_subset) >= 1
        assert all(r.metadata.get("media_id") in ("1", "3") for r in res_subset)

        await adapter.delete_collection(coll)

    asyncio.run(_run())


def test_search_nested_and_or_filters(pgvector_dsn):
    dim = 8
    coll = f"it_filter_bool_{uuid.uuid4().hex[:6]}"

    async def _run():
        cfg = VectorStoreConfig(
            store_type=VectorStoreType.PGVECTOR,
            connection_params={"dsn": pgvector_dsn},
            embedding_dim=dim,
            user_id="it",
        )
        adapter = PGVectorAdapter(cfg)
        await adapter.initialize()
        await adapter.create_collection(coll, metadata={"embedding_dimension": dim})

        ids = ["a", "b", "c"]
        vecs = [[0.1] * dim, [0.2] * dim, [0.3] * dim]
        docs = ["A", "B", "C"]
        metas = [
            {"media_id": "1", "kind": "chunk", "tag": "a", "num": 1},
            {"media_id": "2", "kind": "chunk", "tag": "b", "num": 2},
            {"media_id": "3", "kind": "chunk", "tag": "c", "num": 3},
        ]
        await adapter.upsert_vectors(coll, ids, vecs, docs, metas)

        flt = {
            "$and": [
                {"$or": [{"tag": "a"}, {"tag": "b"}]},
                {"num": {"$lt": 3}},
                {"kind": "chunk"},
            ]
        }

        res = await adapter.search(coll, vecs[0], k=10, filter=flt)
        assert len(res) >= 2
        assert all(
            (r.metadata.get("kind") == "chunk")
            and (r.metadata.get("tag") in ("a", "b"))
            and (float(r.metadata.get("num", 0)) < 3)
            for r in res
        )

        # Ensure an excluded candidate (tag 'c' or num >=3) is not present
        assert not any(r.metadata.get("tag") == "c" for r in res)

        await adapter.delete_collection(coll)

    asyncio.run(_run())
