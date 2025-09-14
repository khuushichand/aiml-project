import types

from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import MediaDBRetriever
from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource


def _doc(i, score, text="content"):
    return Document(id=f"d{i}", content=text, metadata={}, source=DataSource.MEDIA_DB, score=score)


def test_media_rrf_merge_ranks_without_db(tmp_path):
    # Create instance with any path; we won't touch DB
    retr = MediaDBRetriever(db_path=str(tmp_path / "dummy.sqlite3"))
    fts_docs = [_doc(1, 0.0), _doc(2, 0.0), _doc(3, 0.0)]
    vector_docs = [_doc(3, 0.0), _doc(2, 0.0), _doc(4, 0.0)]

    merged = retr._reciprocal_rank_fusion(fts_docs, vector_docs, alpha=0.5, k=60)
    ids = [d.id for d in merged]
    # Doc 2 and 3 appear in both lists; should rank highest
    assert ids[0] in {"d2", "d3"}
    assert set(ids[:4]) == {"d1", "d2", "d3", "d4"}
