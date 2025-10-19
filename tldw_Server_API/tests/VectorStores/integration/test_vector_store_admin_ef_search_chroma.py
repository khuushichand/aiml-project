import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreConfig, VectorStoreType
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.factory import VectorStoreFactory


pytestmark = pytest.mark.integration


def test_admin_set_ef_search_is_noop_for_chroma(monkeypatch, admin_user):
    # Force Chroma via factory settings and stub manager
    from tldw_Server_API.app.core.RAG.rag_service import vector_stores as _vs
    from tldw_Server_API.app.core.RAG.rag_service.vector_stores.chromadb_adapter import ChromaDBAdapter

    monkeypatch.setenv("CHROMADB_FORCE_STUB", "true")

    def _create_from_settings(_settings, user_id: str = "0"):
        cfg = VectorStoreConfig(
            store_type=VectorStoreType.CHROMADB,
            connection_params={"use_default": True, "embedding_config": {}},
            embedding_dim=8,
            user_id=user_id,
        )
        return VectorStoreFactory.create_adapter(cfg, initialize=False)

    monkeypatch.setattr(_vs.VectorStoreFactory, "create_from_settings", classmethod(_create_from_settings))

    client = TestClient(app)

    # Create a store (Chroma backend)
    r = client.post("/api/v1/vector_stores", json={"name": "ef_chroma", "dimensions": 8})
    assert r.status_code == 200
    store_id = r.json().get("id")
    assert store_id

    # Index info should report chroma and not surface ef_search
    r2 = client.get(f"/api/v1/vector_stores/{store_id}/admin/index_info")
    assert r2.status_code == 200
    body = r2.json()
    assert body.get("backend") == "chroma"
    assert "ef_search" not in body

    # Setting ef_search is accepted but is a no-op for Chroma
    r3 = client.post("/api/v1/vector_stores/admin/hnsw_ef_search", json={"ef_search": 77})
    assert r3.status_code == 200
    assert r3.json().get("ef_search") == 77

    # Index info still does not include ef_search
    r4 = client.get(f"/api/v1/vector_stores/{store_id}/admin/index_info")
    assert r4.status_code == 200
    assert "ef_search" not in r4.json()
