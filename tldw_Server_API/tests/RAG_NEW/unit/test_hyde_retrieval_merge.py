import pytest
import asyncio

from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import MediaDBRetriever, RetrievalConfig
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorSearchResult


class _FakeVectorStore:
    def __init__(self, base_results, hyde_results):
        self._base = base_results
        self._hyde = hyde_results
        self._initialized = True
        self.calls = []  # record filters used

    async def initialize(self):
        self._initialized = True
        return None

    async def search(self, collection_name, query_vector, k=10, filter=None, include_metadata=True):
        kind = None
        if isinstance(filter, dict):
            kind = filter.get("kind")
        self.calls.append(kind)
        if kind == "chunk":
            return self._base[:k]
        if kind == "hyde_q":
            return self._hyde[:k]
        # no kind filter → return baseline
        return self._base[:k]


def _vr(id, score, media_id, kind, parent_chunk_id=None):
    md = {"media_id": media_id, "kind": kind}
    if parent_chunk_id:
        md["parent_chunk_id"] = parent_chunk_id
    return VectorSearchResult(
        id=id,
        content=f"{kind}:{id}",
        metadata=md,
        score=score,
        distance=1.0 - score,
    )


@pytest.mark.unit
def test_hyde_merge_media_vs_chunk_level(monkeypatch, tmp_path):
    # Patch settings flags
    import tldw_Server_API.app.core.RAG.rag_service.database_retrievers as retr_mod
    import tldw_Server_API.app.core.config as cfg_mod

    # Ensure HYDE path is enabled and no early exit
    cfg_mod.settings["HYDE_ENABLED"] = True
    cfg_mod.settings["HYDE_ONLY_IF_NEEDED"] = False
    cfg_mod.settings["HYDE_K_FRACTION"] = 1.0
    cfg_mod.settings["HYDE_WEIGHT_QUESTION_MATCH"] = 0.0
    cfg_mod.settings["HYDE_DEDUPE_BY_PARENT"] = False

    # Build vector results. Two base chunks for the same media m1
    base = [
        _vr("chunk1", 0.20, "m1", "chunk"),
        _vr("chunk2", 0.18, "m1", "chunk"),
    ]
    # HyDE results include two questions mapping to chunk1 and one to chunk2
    hyde = [
        _vr("chunk1:q:a1", 0.40, "m1", "hyde_q", parent_chunk_id="chunk1"),
        _vr("chunk1:q:a2", 0.35, "m1", "hyde_q", parent_chunk_id="chunk1"),
        _vr("chunk2:q:b1", 0.10, "m1", "hyde_q", parent_chunk_id="chunk2"),
    ]

    # Create retriever and inject fake vector store; avoid DB usage by pointing to tmp path
    retr = MediaDBRetriever(db_path=str(tmp_path/"Media_DB_v2.db"), config=RetrievalConfig(max_results=10), user_id="u1")
    retr.vector_store = _FakeVectorStore(base, hyde)

    # Media-level merge (default) collapses to one doc for m1
    import asyncio
    docs_media = asyncio.run(retr._retrieve_vector("q", query_vector=[0.1, 0.2, 0.3]))
    assert isinstance(docs_media, list)
    assert len(docs_media) == 1
    assert docs_media[0].metadata.get("media_id") == "m1"

    # Enable chunk-level merge → we should see two entries (two parent chunks)
    cfg_mod.settings["HYDE_DEDUPE_BY_PARENT"] = True
    docs_chunk = asyncio.run(retr._retrieve_vector("q", query_vector=[0.1, 0.2, 0.3]))
    assert len(docs_chunk) == 2
    # Both belong to the same media, but represent distinct chunk keys internally
    assert all(d.metadata.get("media_id") == "m1" for d in docs_chunk)


@pytest.mark.unit
def test_hyde_early_exit_only_if_needed(monkeypatch, tmp_path):
    import tldw_Server_API.app.core.config as cfg_mod

    # Configure early-exit ON and high baseline score
    cfg_mod.settings["HYDE_ENABLED"] = True
    cfg_mod.settings["HYDE_ONLY_IF_NEEDED"] = True
    cfg_mod.settings["HYDE_K_FRACTION"] = 1.0
    cfg_mod.settings["HYDE_SCORE_FLOOR"] = 0.5

    base = [
        _vr("chunkX", 0.95, "mX", "chunk"),
    ]
    hyde = [
        _vr("chunkX:q:z1", 0.30, "mX", "hyde_q", parent_chunk_id="chunkX"),
    ]
    retr = MediaDBRetriever(db_path=str(tmp_path/"Media_DB_v2.db"), config=RetrievalConfig(max_results=1), user_id="u1")
    fake = _FakeVectorStore(base, hyde)
    retr.vector_store = fake

    import asyncio
    docs = asyncio.run(retr._retrieve_vector("q", query_vector=[0.1, 0.2, 0.3]))
    assert len(docs) == 1
    assert docs[0].metadata.get("kind") == "chunk"
    # HYDE path should not be invoked (no hyde_q kind call) due to early exit
    assert "hyde_q" not in fake.calls


@pytest.mark.unit
def test_hyde_weight_adjusts_order(monkeypatch, tmp_path):
    import tldw_Server_API.app.core.config as cfg_mod

    cfg_mod.settings["HYDE_ENABLED"] = True
    cfg_mod.settings["HYDE_ONLY_IF_NEEDED"] = False
    cfg_mod.settings["HYDE_K_FRACTION"] = 1.0
    cfg_mod.settings["HYDE_WEIGHT_QUESTION_MATCH"] = 0.2

    # Two medias: m1 baseline lower but HYDE higher after weight; m2 baseline slightly higher, no HYDE
    base = [
        _vr("m1_chunk", 0.60, "m1", "chunk"),
        _vr("m2_chunk", 0.65, "m2", "chunk"),
    ]
    hyde = [
        _vr("m1_chunk:q:h1", 0.50, "m1", "hyde_q", parent_chunk_id="m1_chunk"),  # 0.50+0.20=0.70
    ]

    retr = MediaDBRetriever(db_path=str(tmp_path/"Media_DB_v2.db"), config=RetrievalConfig(max_results=2), user_id="u1")
    retr.vector_store = _FakeVectorStore(base, hyde)

    import asyncio
    docs = asyncio.run(retr._retrieve_vector("q", query_vector=[0.1, 0.2, 0.3]))
    assert len(docs) == 2
    # m1 should outrank m2 after HYDE weight
    assert docs[0].metadata.get("media_id") == "m1"
