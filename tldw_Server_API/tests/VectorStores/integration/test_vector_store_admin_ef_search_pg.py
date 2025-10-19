import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreConfig, VectorStoreType
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.pgvector_adapter import PGVectorAdapter


pytestmark = pytest.mark.pg_integration


def test_admin_set_ef_search_persists_within_session(pgvector_dsn, monkeypatch, admin_user):
    # Create a single adapter instance to be returned on each call
    cfg = VectorStoreConfig(
        store_type=VectorStoreType.PGVECTOR,
        connection_params={"dsn": pgvector_dsn},
        embedding_dim=8,
        user_id="adm",
    )
    adapter = PGVectorAdapter(cfg)

    # Patch endpoint helper to reuse the same adapter object
    from tldw_Server_API.app.api.v1.endpoints import vector_stores_openai as mod

    async def _fake_get_adapter_for_user(_user, _dim):
        return adapter

    monkeypatch.setattr(mod, "_get_adapter_for_user", _fake_get_adapter_for_user)

    client = TestClient(app)

    # Create a store (ensures the collection/table exists)
    r = client.post("/api/v1/vector_stores", json={"name": "ef_pg", "dimensions": 8})
    assert r.status_code == 200
    store_id = r.json().get("id")
    assert store_id

    # Set ef_search and verify response
    r2 = client.post("/api/v1/vector_stores/admin/hnsw_ef_search", json={"ef_search": 96})
    assert r2.status_code == 200
    assert r2.json().get("ef_search") == 96

    # Read index info and assert it surfaces ef_search from the same adapter (same session)
    r3 = client.get(f"/api/v1/vector_stores/{store_id}/admin/index_info")
    assert r3.status_code == 200
    body = r3.json()
    assert body.get("backend") in ("pgvector", "unknown")
    assert int(body.get("ef_search", 0)) == 96

    # Cleanup: drop collection
    import asyncio

    async def _cleanup():
        await adapter.initialize()
        await adapter.delete_collection(store_id)

    asyncio.run(_cleanup())
