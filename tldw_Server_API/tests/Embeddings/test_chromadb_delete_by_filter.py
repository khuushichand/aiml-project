import asyncio
import sys
from types import ModuleType

import pytest

from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreConfig, VectorStoreType


def test_chromadb_delete_by_filter_stub(monkeypatch):
    # Force in-memory Chroma stub to avoid external dependencies
    monkeypatch.setenv("CHROMADB_FORCE_STUB", "true")
    # Provide a dummy chromadb module so that ChromaDB_Library can import it
    chroma_mod = ModuleType("chromadb")
    chroma_cfg = ModuleType("chromadb.config")
    # Minimal Settings shim
    class _Settings:
        def __init__(self, **kwargs):
            self.kw = kwargs
    chroma_cfg.Settings = _Settings
    chroma_mod.config = chroma_cfg
    # Minimal Client shim (won't be used under FORCE_STUB)
    class _Client:
        def __init__(self, *a, **k):
            pass
    chroma_mod.Client = _Client
    chroma_mod.PersistentClient = _Client
    monkeypatch.setitem(sys.modules, "chromadb", chroma_mod)
    monkeypatch.setitem(sys.modules, "chromadb.config", chroma_cfg)

    # Import adapter after injecting dummy chromadb
    from tldw_Server_API.app.core.RAG.rag_service.vector_stores.chromadb_adapter import ChromaDBAdapter

    # Build adapter
    cfg = VectorStoreConfig(
        store_type=VectorStoreType.CHROMADB,
        connection_params={"embedding_config": {}},
        embedding_dim=8,
        user_id="stubuser",
    )
    adapter = ChromaDBAdapter(cfg)

    async def _run():
        await adapter.initialize()
        coll = "stub_collection_delete"
        await adapter.create_collection(coll, metadata={"embedding_dimension": 8})

        # Insert 3 items
        ids = ["a", "b", "c"]
        vecs = [[0.0]*8, [0.1]*8, [0.2]*8]
        docs = ["", "", ""]
        metas = [
            {"media_id": "42", "kind": "chunk"},
            {"media_id": "42", "kind": "chunk"},
            {"media_id": "43", "kind": "chunk"},
        ]
        await adapter.upsert_vectors(coll, ids, vecs, docs, metas)

        # Delete by filter
        deleted = await adapter.delete_by_filter(coll, {"media_id": "42"})
        # Chroma adapter returns 0 (count unknown), but deletion should succeed
        assert isinstance(deleted, int)

        # Verify remaining id is 'c'
        page = await adapter.list_vectors_paginated(coll, limit=10, offset=0)  # type: ignore[attr-defined]
        items = (page or {}).get("items", [])
        remaining = {it.get("id") for it in items}
        assert remaining == {"c"}

    asyncio.run(_run())
