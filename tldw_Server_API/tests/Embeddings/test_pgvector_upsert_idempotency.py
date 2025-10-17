import asyncio
import pytest

from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreConfig, VectorStoreType
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.pgvector_adapter import PGVectorAdapter


def test_pg_upsert_idempotent(pgvector_dsn, monkeypatch):
    coll = 'idempotency_demo'
    dim = 8
    adapter = PGVectorAdapter(VectorStoreConfig(store_type=VectorStoreType.PGVECTOR, connection_params={'dsn': pgvector_dsn}, embedding_dim=dim, user_id='t'))

    async def _run():
        await adapter.initialize()
        await adapter.create_collection(coll, metadata={'embedding_dimension': dim})
        ids = ['dup']
        vec = [[0.1]*dim]
        docs = ['x']
        metas = [{'kind':'chunk'}]
        await adapter.upsert_vectors(coll, ids, vec, docs, metas)
        await adapter.upsert_vectors(coll, ids, vec, docs, metas)
        stats = await adapter.get_collection_stats(coll)
        assert stats.get('count', 0) >= 1
        # Ensure no duplicates for the same id
        page = await adapter.list_vectors_paginated(coll, limit=10, offset=0)  # type: ignore[attr-defined]
        items = (page or {}).get('items', [])
        ids_seen = [it.get('id') for it in items]
        assert ids_seen.count('dup') == 1
    asyncio.run(_run())
