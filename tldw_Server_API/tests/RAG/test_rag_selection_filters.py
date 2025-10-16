import os
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.RAG.rag_service.database_retrievers import MediaDBRetriever, NotesDBRetriever, RetrievalConfig
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@pytest.mark.unit
@pytest.mark.asyncio
async def test_media_retriever_respects_allowed_ids(tmp_path: Path):
    db_path = tmp_path / "Media_DB_v2.db"
    db = MediaDatabase(db_path=str(db_path), client_id="pytest")

    mid1, _, _ = db.add_media_with_keywords(
        title="Doc One",
        media_type="text",
        content="common alpha",
        keywords=["k1"],
    )
    mid2, _, _ = db.add_media_with_keywords(
        title="Doc Two",
        media_type="text",
        content="common beta",
        keywords=["k1"],
    )

    retr = MediaDBRetriever(str(db_path), config=RetrievalConfig(max_results=10, use_fts=True, use_vector=False), user_id="0", media_db=db)

    # Query matches both docs; restrict to mid1
    docs = await retr.retrieve("common", allowed_media_ids=[mid1])
    ids = {str(d.id) for d in docs}
    assert str(mid1) in ids
    assert str(mid2) not in ids

    # Restrict to mid2
    docs = await retr.retrieve("common", allowed_media_ids=[mid2])
    ids = {str(d.id) for d in docs}
    assert str(mid2) in ids
    assert str(mid1) not in ids


@pytest.mark.unit
@pytest.mark.asyncio
async def test_notes_retriever_respects_allowed_ids(tmp_path: Path, monkeypatch):
    # ChaChaNotes DB path colocated with tmp user base
    os.environ["TESTING"] = "true"
    base_dir = tmp_path / "user_databases"
    os.environ["USER_DB_BASE_DIR"] = str(base_dir)

    chacha_db_path = base_dir / "1" / "ChaChaNotes.db"
    chacha_db_path.parent.mkdir(parents=True, exist_ok=True)
    chacha = CharactersRAGDB(db_path=str(chacha_db_path), client_id="pytest")

    kid = chacha.add_keyword("k1")
    assert kid is not None
    n1 = chacha.add_note(title="N1", content="note common one")
    n2 = chacha.add_note(title="N2", content="note common two")
    chacha.link_note_to_keyword(note_id=n1, keyword_id=kid)
    chacha.link_note_to_keyword(note_id=n2, keyword_id=kid)

    retr = NotesDBRetriever(str(chacha_db_path), config=RetrievalConfig(max_results=10))

    docs = await retr.retrieve("common", allowed_note_ids=[n1])
    ids = {str(d.id).replace("note_", "") for d in docs}
    assert n1 in ids
    assert n2 not in ids
