from fastapi.testclient import TestClient
import asyncio
import pytest

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreConfig, VectorStoreType
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.pgvector_adapter import PGVectorAdapter


def test_metrics_contains_pgvector_after_ops(pgvector_dsn):

    client = TestClient(app)
    dim = 8
    coll = 'metrics_demo'
    adapter = PGVectorAdapter(VectorStoreConfig(store_type=VectorStoreType.PGVECTOR, connection_params={'dsn': pgvector_dsn}, embedding_dim=dim, user_id='t'))

    async def _run():
        await adapter.initialize()
        await adapter.create_collection(coll, metadata={'embedding_dimension': dim})
        await adapter.upsert_vectors(coll, ['m1'], [[0.1]*dim], ['doc'], [{'kind':'chunk'}])
        await adapter.search(coll, [0.1]*dim, k=1)
        await adapter.delete_by_filter(coll, {'kind':'chunk'})
    asyncio.run(_run())

    r = client.get('/api/v1/metrics/text')
    assert r.status_code == 200
    text = r.text
    # Check for metric names
    assert 'pgvector_upsert_latency_seconds' in text
    assert 'pgvector_query_latency_seconds' in text
    assert 'pgvector_delete_latency_seconds' in text
