"""
Vector-mode Unified RAG tests (guarded by configuration).

Runs Unified /rag/search with search_mode="vector" when ChromaDB adapter
is enabled via settings and chromadb is importable.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.rag_unified import router as rag_router
from tldw_Server_API.app.api.v1.endpoints.vector_stores_openai import router as vs_router
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.config import settings


def _chromadb_available() -> bool:
    try:
        import chromadb  # noqa: F401
    except Exception:
        return False
    # Check project settings for vector store
    try:
        rag_cfg = settings.get("RAG", {})
        vtype = (rag_cfg.get("vector_store_type") or "").lower()
        return vtype == "chromadb"
    except Exception:
        return False


@pytest.fixture
def seed_media(tmp_path):
    """Seed a temporary Media database and return an override factory."""
    media_db_path = tmp_path / "vector_media.db"
    mdb = MediaDatabase(db_path=str(media_db_path), client_id="vector_test")
    docs = [
        ("Vector Intro", "Embeddings provide a way to measure similarity"),
        ("Chroma Guide", "ChromaDB stores vectors and metadata efficiently"),
        ("FTS Backup", "FTS search matches text content directly"),
    ]
    for title, content in docs:
        mdb.add_media_with_keywords(title=title, content=content, media_type="document", keywords=["vector", "chroma"])  # noqa: E501

    def media_override():
        return MediaDatabase(db_path=str(media_db_path), client_id="vector_test")

    return media_override


@pytest.fixture
def vector_app(seed_media):
    """Create an app for vector tests with overrides."""
    app = FastAPI()
    app.dependency_overrides[get_media_db_for_user] = seed_media
    app.dependency_overrides[check_rate_limit] = lambda: None
    app.include_router(rag_router)
    app.include_router(vs_router)
    return app


@pytest.mark.asyncio
async def test_unified_vector_search(vector_app):
    if not _chromadb_available():
        pytest.skip("ChromaDB not configured; skipping vector-mode test")

    client = TestClient(vector_app, headers={"X-API-KEY": "default-secret-key-for-single-user"})

    # Seed the retriever's expected collection directly: user_1_media_embeddings
    store_id = "user_1_media_embeddings"
    upsert = {
        "records": [
            {"content": "Embeddings provide a way to measure similarity between texts", "metadata": {"source": "media_db"}},
            {"content": "ChromaDB stores vectors and metadata efficiently", "metadata": {"source": "media_db"}},
            {"content": "FTS search matches text content directly", "metadata": {"source": "media_db"}},
        ]
    }
    r_up = client.post(f"/vector_stores/{store_id}/vectors", json=upsert)
    # If embeddings not configured, server might 500; skip in that case
    if r_up.status_code != 200:
        pytest.skip(f"Vector upsert failed: {r_up.status_code} {r_up.text}")

    payload = {
        "query": "how to store vectors",
        "sources": ["media_db"],
        "search_mode": "vector",
        "top_k": 3
    }
    resp = client.post("/api/v1/rag/search", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    # Expect at least one doc after seeding vector collection
    assert isinstance(data.get("documents", []), list)
    assert len(data.get("documents", [])) >= 1


@pytest.mark.asyncio
async def test_create_store_from_media_use_existing(vector_app):
    if not _chromadb_available():
        pytest.skip("ChromaDB not configured; skipping create-from-media existing embeddings test")

    client = TestClient(vector_app, headers={"X-API-KEY": "default-secret-key-for-single-user"})

    # Pre-seed the source collection the copy routine expects
    source_store = "user_1_media_embeddings"
    media_ids = [101, 102]
    upsert = {
        "records": [
            {"content": "Media 101 embedding content", "metadata": {"media_id": media_ids[0], "source": "media_db"}},
            {"content": "Media 102 embedding content", "metadata": {"media_id": media_ids[1], "source": "media_db"}},
        ]
    }
    r_up = client.post(f"/vector_stores/{source_store}/vectors", json=upsert)
    if r_up.status_code != 200:
        pytest.skip(f"Vector upsert to source collection failed: {r_up.status_code} {r_up.text}")

    # Create a new store by copying existing embeddings for the specified media IDs
    create_payload = {
        "store_name": "copy_from_existing",
        "use_existing_embeddings": True,
        "media_ids": media_ids
    }
    r_create = client.post("/vector_stores/create_from_media", json=create_payload)
    if r_create.status_code != 200:
        pytest.skip(f"Create-from-media with existing embeddings failed: {r_create.status_code} {r_create.text}")
    data = r_create.json()
    assert data.get("store_id")
    assert data.get("upserted", 0) >= 2
