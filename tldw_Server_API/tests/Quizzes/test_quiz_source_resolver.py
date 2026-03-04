import uuid

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.services.quiz_source_resolver import resolve_quiz_sources


@pytest.fixture(scope="function")
def quizzes_db(tmp_path):
    db_path = tmp_path / "quiz_sources.db"
    db = CharactersRAGDB(str(db_path), client_id=f"test-{uuid.uuid4().hex[:6]}")
    yield db
    db.close_connection()


@pytest.fixture(scope="function")
def media_db(tmp_path):
    db_path = tmp_path / "media_sources.db"
    db = MediaDatabase(str(db_path), client_id=f"test-{uuid.uuid4().hex[:6]}")
    yield db
    db.close_connection()


def test_resolves_note_source_to_evidence_chunks(quizzes_db: CharactersRAGDB, media_db: MediaDatabase):
    note_id = quizzes_db.add_note(title="Cell Theory", content="All living things are made of cells.")

    evidence = resolve_quiz_sources(
        [{"source_type": "note", "source_id": note_id}],
        db=quizzes_db,
        media_db=media_db,
    )

    assert evidence[0]["source_type"] == "note"
    assert evidence[0]["source_id"] == note_id
    assert evidence[0]["text"]


def test_resolves_flashcard_deck_to_card_evidence_chunks(
    quizzes_db: CharactersRAGDB,
    media_db: MediaDatabase,
):
    deck_id = quizzes_db.add_deck(name="Biology")
    quizzes_db.add_flashcard({"deck_id": deck_id, "front": "Mitochondria", "back": "Powerhouse of the cell"})
    quizzes_db.add_flashcard({"deck_id": deck_id, "front": "Ribosome", "back": "Synthesizes proteins"})

    evidence = resolve_quiz_sources(
        [{"source_type": "flashcard_deck", "source_id": str(deck_id)}],
        db=quizzes_db,
        media_db=media_db,
    )

    assert len(evidence) >= 2


def test_resolves_flashcard_card_source(quizzes_db: CharactersRAGDB, media_db: MediaDatabase):
    card_uuid = quizzes_db.add_flashcard({"front": "ATP", "back": "Cell energy currency"})

    evidence = resolve_quiz_sources(
        [{"source_type": "flashcard_card", "source_id": card_uuid}],
        db=quizzes_db,
        media_db=media_db,
    )

    assert evidence[0]["source_id"] == card_uuid


def test_deduplicates_duplicate_source_entries(quizzes_db: CharactersRAGDB, media_db: MediaDatabase):
    note_id = quizzes_db.add_note(title="DNA", content="DNA stores genetic information.")

    evidence = resolve_quiz_sources(
        [
            {"source_type": "note", "source_id": note_id},
            {"source_type": "note", "source_id": note_id},
        ],
        db=quizzes_db,
        media_db=media_db,
    )

    assert len(evidence) == 1
    assert evidence[0]["source_type"] == "note"
    assert evidence[0]["source_id"] == note_id
