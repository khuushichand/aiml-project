import asyncio
from typing import Any, Dict, List

import pytest

from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreConfig, VectorStoreType
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.chromadb_adapter import ChromaDBAdapter
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.pgvector_adapter import PGVectorAdapter


def _records(dim=8):
    return (
        ["a","b","c"],
        [[0.0]*dim, [0.1]*dim, [0.2]*dim],
        ["A","B","C"],
        [
            {"media_id":"1","kind":"chunk","score":0.1},
            {"media_id":"2","kind":"chunk","score":0.2},
            {"media_id":"3","kind":"chunk","score":0.3}
        ],
    )


@pytest.mark.parametrize("backend", ["chroma", "pgvector"])
def test_parity_basic_search_and_filter(monkeypatch, backend, request):
    dim = 8
    coll = f"parity_{backend}_demo"
    if backend == "chroma":
        monkeypatch.setenv("CHROMADB_FORCE_STUB", "true")
        adapter = ChromaDBAdapter(VectorStoreConfig(store_type=VectorStoreType.CHROMADB, connection_params={"embedding_config": {}}, embedding_dim=dim, user_id="t"))
    else:
        dsn = request.getfixturevalue("pgvector_dsn")
        adapter = PGVectorAdapter(VectorStoreConfig(store_type=VectorStoreType.PGVECTOR, connection_params={"dsn": dsn}, embedding_dim=dim, user_id="t"))

    async def _run():
        await adapter.initialize()
        await adapter.create_collection(coll, metadata={"embedding_dimension": dim})
        ids, vecs, docs, metas = _records(dim)
        await adapter.upsert_vectors(coll, ids, vecs, docs, metas)
        # Filter by kind
        res = await adapter.search(coll, vecs[0], k=2, filter={"kind":"chunk"})
        assert len(res) == 2
        # Sorted by similarity
        assert res[0].id in ("a","b")
        assert res[0].score >= res[1].score
        # k limit
        res3 = await adapter.search(coll, vecs[0], k=1)
        assert len(res3) == 1
    asyncio.run(_run())


@pytest.mark.parametrize("backend", ["pgvector"])  # $in and numeric bounds parity primarily for pgvector
def test_parity_in_and_numeric(monkeypatch, backend, pgvector_dsn):
    dim = 8
    coll = f"parity_{backend}_ops"
    adapter = PGVectorAdapter(VectorStoreConfig(store_type=VectorStoreType.PGVECTOR, connection_params={"dsn": pgvector_dsn}, embedding_dim=dim, user_id="t"))

    async def _run():
        await adapter.initialize()
        await adapter.create_collection(coll, metadata={"embedding_dimension": dim})
        ids, vecs, docs, metas = _records(dim)
        await adapter.upsert_vectors(coll, ids, vecs, docs, metas)
        # $in filter on media_id
        res = await adapter.search(coll, vecs[0], k=3, filter={"media_id": {"$in": ["1","3"]}})
        assert all(r.metadata.get("media_id") in ("1","3") for r in res)
        # Numeric >= filter
        res2 = await adapter.search(coll, vecs[0], k=3, filter={"score": {"$gte": 0.2}})
        assert all(float(r.metadata.get("score", 0.0)) >= 0.2 for r in res2)
    asyncio.run(_run())


@pytest.mark.parametrize("backend", ["pgvector"])  # boolean ops + multi_search (pg only)
def test_parity_boolean_and_multi_search(monkeypatch, backend, pgvector_dsn):
    dim = 8
    adapter = PGVectorAdapter(VectorStoreConfig(store_type=VectorStoreType.PGVECTOR, connection_params={"dsn": pgvector_dsn}, embedding_dim=dim, user_id="t"))

    async def _run():
        await adapter.initialize()
        # Create two collections
        c1, c2 = "parity_pg_bool_1", "parity_pg_bool_2"
        await adapter.create_collection(c1, metadata={"embedding_dimension": dim})
        await adapter.create_collection(c2, metadata={"embedding_dimension": dim})
        ids, vecs, docs, metas = _records(dim)
        # Tag collections differently
        metas1 = [{**m, "col": "a"} for m in metas]
        metas2 = [{**m, "col": "b"} for m in metas]
        await adapter.upsert_vectors(c1, ids, vecs, docs, metas1)
        await adapter.upsert_vectors(c2, ids, vecs, docs, metas2)
        # $and/$or filter: media_id in (1,3) OR col=b
        flt = {"$or": [
            {"media_id": {"$in": ["1","3"]}},
            {"col": "b"}
        ]}
        res = await adapter.search(c1, vecs[0], k=5, filter=flt)
        assert len(res) >= 1
        # multi_search across both collections
        res2 = await adapter.multi_search(["parity_pg_bool_*"], vecs[0], k=5, filter=flt)
        assert len(res2) >= 1
    asyncio.run(_run())
