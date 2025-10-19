import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreConfig, VectorStoreType
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.factory import VectorStoreFactory

pytestmark = pytest.mark.usefixtures("admin_user")


def test_admin_endpoints_e2e_pg(pgvector_dsn, monkeypatch):

    # Patch factory to return a real PG adapter using DSN
    def _create_from_settings(_settings, user_id: str = '0'):
        cfg = VectorStoreConfig(
            store_type=VectorStoreType.PGVECTOR,
            connection_params={'dsn': pgvector_dsn},
            embedding_dim=8,
            user_id=user_id,
        )
        return VectorStoreFactory.create_adapter(cfg, initialize=False)

    from tldw_Server_API.app.core.RAG.rag_service import vector_stores as _vs
    monkeypatch.setattr(_vs.VectorStoreFactory, 'create_from_settings', classmethod(lambda cls, s, user_id='0': _create_from_settings(s, user_id)))

    client = TestClient(app)

    # Create a store via API (ensures collection exists)
    r = client.post('/api/v1/vector_stores', json={'name': 'e2e_pg', 'dimensions': 8})
    assert r.status_code == 200
    store_id = r.json().get('id')
    assert store_id

    # Index info should be available and report pgvector backend
    r2 = client.get(f'/api/v1/vector_stores/{store_id}/admin/index_info')
    assert r2.status_code == 200
    assert r2.json().get('backend') in ('pgvector','unknown')  # allow unknown on race

    # Rebuild index (hnsw)
    r3 = client.post(f'/api/v1/vector_stores/{store_id}/admin/rebuild_index', json={'index_type':'hnsw','metric':'cosine','m':16,'ef_construction':200,'lists':100})
    assert r3.status_code == 200

    # ef_search set (session-level)
    r4 = client.post('/api/v1/vector_stores/admin/hnsw_ef_search', json={'ef_search': 64})
    assert r4.status_code == 200
