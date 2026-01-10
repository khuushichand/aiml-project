import json
import pytest

from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreConfig, VectorStoreType
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.pgvector_adapter import PGVectorAdapter


@pytest.mark.unit
def test_pg_list_vectors_paginated_builds_filter(monkeypatch):
    cfg = VectorStoreConfig(
        store_type=VectorStoreType.PGVECTOR,
        connection_params={'dsn': 'postgresql://u:p@localhost:5432/db'},
        embedding_dim=8,
        user_id='1'
    )
    adapter = PGVectorAdapter(cfg)

    captured = []

    async def fake_query(sql, params=None):
        captured.append((sql, params))
        # Return two rows
        if 'COUNT(*)' in sql:
            return [(2,)]
        return [("a", "doc a", {"genre": "a"}), ("b", "doc b", {"genre": "b"})]

    monkeypatch.setattr(adapter, '_query', fake_query)

    # Invoke with a metadata filter
    import asyncio
    res = asyncio.run(
        adapter.list_vectors_paginated('store', limit=10, offset=0, filter={'genre': 'a'})
    )
    assert res['total'] == 2
    assert isinstance(res['items'], list)
    # Ensure WHERE clause was used
    assert any('WHERE metadata @> %s' in sql for (sql, _p) in captured)


@pytest.mark.unit
def test_pg_list_vectors_with_embeddings(monkeypatch):
    cfg = VectorStoreConfig(
        store_type=VectorStoreType.PGVECTOR,
        connection_params={'dsn': 'postgresql://u:p@localhost:5432/db'},
        embedding_dim=4,
        user_id='1'
    )
    adapter = PGVectorAdapter(cfg)

    async def fake_query(sql, params=None):
        if 'COUNT(*)' in sql:
            return [(1,)]
        return [("id1", "doc1", {"k": 1}, [0.1, 0.2, 0.3, 0.4])]

    monkeypatch.setattr(adapter, '_query', fake_query)

    import asyncio
    res = asyncio.run(
        adapter.list_vectors_with_embeddings_paginated('store', limit=1, offset=0)
    )
    assert res['total'] == 1
    assert res['items'][0]['id'] == 'id1'
    assert isinstance(res['items'][0]['vector'], list)
