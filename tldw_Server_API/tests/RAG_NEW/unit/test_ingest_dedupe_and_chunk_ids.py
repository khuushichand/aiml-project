import os
import tempfile
from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager


def test_chunk_for_embedding_assigns_stable_uid():
    from tldw_Server_API.app.core.Chunking import chunk_for_embedding

    text = "Hello world. Hello world!\nThis is a test."
    chunks = chunk_for_embedding(text, file_name="doc1.txt", method="sentences", max_size=1, overlap=0)
    assert chunks
    # chunk_uid should be present and stable for same inputs
    uid_set = set()
    for ch in chunks:
        md = ch.get("metadata") or {}
        assert "chunk_uid" in md
        uid_set.add(md["chunk_uid"])
    # running again should produce same set
    chunks2 = chunk_for_embedding(text, file_name="doc1.txt", method="sentences", max_size=1, overlap=0)
    uid_set2 = { (c.get("metadata") or {}).get("chunk_uid") for c in chunks2 }
    assert uid_set == uid_set2


def test_dedupe_removes_near_duplicates():
    # Minimal user embedding config for ChromaDBManager
    tmpdir = tempfile.mkdtemp(prefix="chromadb_test_")
    cfg = {
        "USER_DB_BASE_DIR": tmpdir,
        "embedding_config": {"default_model_id": "dummy"},
        "chroma_client_settings": {},
    }
    mgr = ChromaDBManager(user_id="test-user", user_embedding_config=cfg)
    a = {"text": "abc def ghi jkl mno", "metadata": {"chunk_uid": "u1"}}
    b = {"text": "abc def ghi jkl mno pqr", "metadata": {"chunk_uid": "u2"}}  # near-duplicate
    c = {"text": "completely different text", "metadata": {"chunk_uid": "u3"}}
    # Use a slightly more permissive threshold for short texts
    filtered, dup_map = mgr._dedupe_text_chunks([a, b, c], threshold=0.7)
    # One duplicate (u2 -> u1) should be detected
    assert any(v == "u1" for v in dup_map.values())
    # Filtered should be shorter than original
    assert len(filtered) < 3
