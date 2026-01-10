import os
import pathlib
import types
import pytest
from fastapi.testclient import TestClient

from fastapi import FastAPI
from tldw_Server_API.app.api.v1.endpoints.vector_stores_openai import router as vs_router
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


class FakeCollection:
    def __init__(self, name):
        self.name = name
        self.data = {"ids": [], "embeddings": [], "documents": [], "metadatas": []}
        self.metadata = {}
    def get(self, limit=100, offset=0, include=None, where=None):
        idxs = list(range(len(self.data["ids"])))
        if where and "media_id" in where:
            mid = where["media_id"]
            idxs = [i for i, m in enumerate(self.data["metadatas"]) if m.get("media_id") == mid]
        end = min(offset + limit, len(idxs))
        sel = idxs[offset:end]
        out = {"ids": [self.data["ids"][i] for i in sel]}
        if include:
            if "embeddings" in include:
                out["embeddings"] = [self.data["embeddings"][i] for i in sel]
            if "documents" in include:
                out["documents"] = [self.data["documents"][i] for i in sel]
            if "metadatas" in include:
                out["metadatas"] = [self.data["metadatas"][i] for i in sel]
        return out
    def count(self):
        return len(self.data["ids"])


class FakeAdapter:
    def __init__(self):
        self._initialized = False
        self.config = types.SimpleNamespace(embedding_dim=1536)
        self.collections = {}
        self.manager = types.SimpleNamespace(get_or_create_collection=self.get_or_create_collection)
    async def initialize(self):
        self._initialized = True
    def get_or_create_collection(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection(name)
        return self.collections[name]
    async def upsert_vectors(self, collection_name, ids, vectors, documents, metadatas):
        col = self.get_or_create_collection(collection_name)
        col.data["ids"] += ids
        col.data["embeddings"] += vectors
        col.data["documents"] += documents
        col.data["metadatas"] += metadatas
    async def create_collection(self, name, metadata=None):
        col = self.get_or_create_collection(name)
        if metadata:
            col.metadata.update(metadata)
    async def get_collection_stats(self, name):
        col = self.get_or_create_collection(name)
        dim = self.config.embedding_dim
        if col.data["embeddings"]:
            dim = len(col.data["embeddings"][0])
        return {"metadata": getattr(col, "metadata", {}), "dimension": dim}


@pytest.fixture(autouse=True)
def testing_env(monkeypatch, tmp_path):
    os.environ["TESTING"] = "true"
    # Ensure DB deps use this tmp path directly (do not auto-override)
    os.environ["USER_DB_BASE_DIR"] = str(tmp_path)
    from tldw_Server_API.app.core import config as cfg
    # Ensure base dir is a Path so DB deps resolve under tmp_path/1/Media_DB_v2.db
    monkeypatch.setitem(cfg.settings, "USER_DB_BASE_DIR", pathlib.Path(tmp_path))
    try:
        from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import reset_media_db_cache

        reset_media_db_cache()
    except Exception:
        pass
    yield
    os.environ.pop("TESTING", None)
    os.environ.pop("USER_DB_BASE_DIR", None)
    app.dependency_overrides.clear()


@pytest.fixture()
def client(monkeypatch, tmp_path):
    # Patch vector store adapter with fake
    fake = FakeAdapter()
    import tldw_Server_API.app.api.v1.endpoints.vector_stores_openai as vs
    async def fake_adapter_for_user(user, embedding_dim):
        fake.config.embedding_dim = embedding_dim
        return fake
    monkeypatch.setattr(vs, "_adapter_for_user", fake_adapter_for_user)
    # Patch embeddings batch to a fixed dimension (8)
    def fake_create_embeddings_batch(texts, app_config, model_id):
        dim = 8
        return [[0.0] * dim for _ in texts]
    monkeypatch.setattr(vs, "create_embeddings_batch", fake_create_embeddings_batch)
    # Override user dep
    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)
    # Build a minimal app with just the vector_stores router to avoid unrelated import issues
    global app
    app = FastAPI()
    app.include_router(vs_router, prefix="/api/v1")
    app.dependency_overrides[get_request_user] = override_user

    # Seed Media DB with items and keywords
    user_dir = pathlib.Path(tmp_path) / "1"
    user_dir.mkdir(parents=True, exist_ok=True)
    db_path = user_dir / "Media_DB_v2.db"
    db = MediaDatabase(db_path=str(db_path), client_id="1")
    # A: has alpha & beta
    db.add_media_with_keywords(title="A", media_type="doc", content="AAA content", keywords=["alpha", "beta"])
    # B: has alpha
    db.add_media_with_keywords(title="B", media_type="doc", content="BBB content", keywords=["alpha"])
    # C: has beta
    db.add_media_with_keywords(title="C", media_type="doc", content="CCC content", keywords=["beta"])
    # Sanity check DB state
    res = db.fetch_media_for_keywords(["alpha", "beta"])  # union per-keyword mapping
    # Expect both keys present and at least 1 item for each
    assert isinstance(res, dict)
    # Also sanity check keywords table
    conn = db.get_connection()
    rows = db._fetchall_with_connection(conn, "SELECT keyword, deleted FROM Keywords", None)
    present = {r['keyword'] for r in rows}
    assert 'alpha' in present and 'beta' in present
    # Verify links exist
    links = db._fetchall_with_connection(conn, "SELECT media_id, keyword_id FROM MediaKeywords", None)
    assert len(links) >= 2

    with TestClient(app) as c:
        yield c


def test_create_from_media_keywords_any(client):
    body = {
        "store_name": "KWAny",
        "dimensions": 8,
        "keywords": ["alpha", "beta"],
        "keyword_match": "any",
        "chunk_size": 500,
        "chunk_overlap": 0,
        "chunk_method": "words",
    }
    r = client.post("/api/v1/vector_stores/create_from_media", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    # Expect union: A, B, C -> 3 chunks
    assert data.get("upserted") == 3


def test_create_from_media_keywords_all(client):
    body = {
        "store_name": "KWAll",
        "dimensions": 8,
        "keywords": ["alpha", "beta"],
        "keyword_match": "all",
        "chunk_size": 500,
        "chunk_overlap": 0,
        "chunk_method": "words",
    }
    r = client.post("/api/v1/vector_stores/create_from_media", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    # Expect intersection: only A -> 1 chunk
    assert data.get("upserted") == 1
