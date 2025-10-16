import os
import pytest

pytestmark = pytest.mark.pg_integration

try:
    import psycopg  # type: ignore
    _HAS_PSYCOPG = True
except Exception:
    _HAS_PSYCOPG = False


@pytest.fixture(scope="session")
def pg_dsn():
    dsn = os.getenv('PG_TEST_DSN')
    if not dsn:
        pytest.skip("PG_TEST_DSN not set; skipping live pgvector tests")
    if not _HAS_PSYCOPG:
        pytest.skip("psycopg not installed; skipping live pgvector tests")
    return dsn


def test_pgvector_live_smoke(pg_dsn):
    from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreConfig, VectorStoreType
    from tldw_Server_API.app.core.RAG.rag_service.vector_stores.pgvector_adapter import PGVectorAdapter
    import asyncio

    async def run():
        cfg = VectorStoreConfig(
            store_type=VectorStoreType.PGVECTOR,
            connection_params={'dsn': pg_dsn, 'hnsw_ef_search': 64, 'pool_min_size': 1, 'pool_max_size': 4},
            embedding_dim=8,
            user_id='it'
        )
        adapter = PGVectorAdapter(cfg)
        await adapter.initialize()
        await adapter.create_collection('it_store', metadata={'name': 'it_store', 'embedding_dimension': 8})
        await adapter.upsert_vectors('it_store', ids=['a','b'], vectors=[[0.1]*8, [0.2]*8], documents=['A','B'], metadatas=[{'i':1},{'i':2}])
        listed = await adapter.list_vectors_paginated('it_store', limit=10, offset=0)
        assert listed['total'] >= 2
        one = await adapter.get_vector('it_store', 'a')
        assert one and one['id'] == 'a'
        await adapter.delete_vectors('it_store', ids=['a','b'])

        # Index info and rebuild
        info = await adapter.get_index_info('it_store')
        assert 'index_type' in info
        # Adjust ef_search
        adapter.set_ef_search(128)
        info2 = await adapter.get_index_info('it_store')
        assert 'dimension' in info2
        # Try rebuild to ivfflat (ignore failures due to version)
        try:
            await adapter.rebuild_index('it_store', index_type='ivfflat', lists=10)
        except Exception:
            pass

    asyncio.get_event_loop().run_until_complete(run())
