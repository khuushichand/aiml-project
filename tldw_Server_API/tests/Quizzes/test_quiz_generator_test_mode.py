import uuid

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.services.quiz_generator import generate_quiz_from_sources


@pytest.fixture(scope="function")
def quizzes_db(tmp_path):
    db_path = tmp_path / "quiz-generator-test-mode.db"
    db = CharactersRAGDB(str(db_path), client_id=f"test-{uuid.uuid4().hex[:6]}")
    yield db
    db.close_connection()


@pytest.fixture(scope="function")
def media_db(tmp_path):
    db_path = tmp_path / "quiz-generator-media.db"
    db = MediaDatabase(str(db_path), client_id=f"test-{uuid.uuid4().hex[:6]}")
    yield db
    db.close_connection()


@pytest.mark.asyncio
async def test_generate_quiz_from_sources_returns_deterministic_payload_in_test_mode(
    monkeypatch: pytest.MonkeyPatch,
    quizzes_db: CharactersRAGDB,
    media_db: MediaDatabase,
):
    monkeypatch.setenv("TEST_MODE", "1")
    note_id = quizzes_db.add_note(
        title="Workspace Alpha",
        content="Alpha program requires citations, review boards, and Friday freshness checks.",
    )

    result = await generate_quiz_from_sources(
        db=quizzes_db,
        media_db=media_db,
        sources=[{"source_type": "note", "source_id": note_id}],
        num_questions=2,
        question_types=["multiple_choice", "true_false"],
        workspace_tag="workspace:test",
    )

    assert result["quiz"]["workspace_tag"] == "workspace:test"
    assert len(result["questions"]) == 2
    assert result["questions"][0]["source_citations"][0]["source_type"] == "note"
    assert result["questions"][0]["source_citations"][0]["source_id"] == note_id
