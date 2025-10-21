import sys
from types import ModuleType

import pytest


@pytest.mark.unit
def test_chroma_index_info_has_no_ef_search(monkeypatch):
    # Force in-memory Chroma stub and inject minimal module shims
    monkeypatch.setenv("CHROMADB_FORCE_STUB", "true")

    chroma_mod = ModuleType("chromadb")
    chroma_cfg = ModuleType("chromadb.config")

    class _Settings:  # minimal config shim
        def __init__(self, **kwargs):
            self.kw = kwargs

    class _Client:  # not used under FORCE_STUB
        def __init__(self, *a, **k):
            pass

    chroma_cfg.Settings = _Settings
    chroma_mod.config = chroma_cfg
    chroma_mod.Client = _Client
    chroma_mod.PersistentClient = _Client
    monkeypatch.setitem(sys.modules, "chromadb", chroma_mod)
    monkeypatch.setitem(sys.modules, "chromadb.config", chroma_cfg)

    from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import (
        VectorStoreConfig,
        VectorStoreType,
    )
    from tldw_Server_API.app.core.RAG.rag_service.vector_stores.chromadb_adapter import (
        ChromaDBAdapter,
    )

    cfg = VectorStoreConfig(
        store_type=VectorStoreType.CHROMADB,
        connection_params={"embedding_config": {}},
        embedding_dim=8,
        user_id="stubuser",
    )
    adapter = ChromaDBAdapter(cfg)

    import asyncio

    async def _run():
        await adapter.initialize()
        coll = "stub_index_info_shape"
        await adapter.create_collection(coll, metadata={"embedding_dimension": 8})
        info = await adapter.get_index_info(coll)
        # Shape assertions
        assert info.get("backend") == "chroma"
        assert info.get("index_type") == "managed"
        assert "ef_search" not in info

    asyncio.run(_run())
