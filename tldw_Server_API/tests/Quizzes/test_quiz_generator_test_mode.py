import uuid
from unittest.mock import Mock

import pytest

from tldw_Server_API.app.services import quiz_generator
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.services.quiz_generator import (
    _build_test_mode_questions,
    generate_quiz_from_sources,
)


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


def test_build_test_mode_questions_prefers_evidence_source_identity() -> None:
    questions = _build_test_mode_questions(
        evidence=[
            {
                "source_type": "note",
                "source_id": "note-b",
                "text": "Beta evidence should keep its own citation identity.",
            }
        ],
        normalized_sources=[
            {"source_type": "note", "source_id": "note-a"},
            {"source_type": "note", "source_id": "note-b"},
        ],
        num_questions=1,
        question_types=["multiple_choice"],
    )

    citation = questions[0]["source_citations"][0]
    assert citation["source_type"] == "note"
    assert citation["source_id"] == "note-b"
    assert citation["quote"] == "Beta evidence should keep its own citation identity."


@pytest.mark.asyncio
async def test_generate_quiz_from_sources_uses_test_mode_fallback_for_metadata_only_evidence(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setattr(
        quiz_generator,
        "resolve_quiz_sources",
        lambda *_args, **_kwargs: [{"source_type": "note", "source_id": "note-meta", "text": ""}],
    )
    monkeypatch.setattr(
        quiz_generator,
        "_resolve_generated_quiz_metadata",
        lambda **_kwargs: ("Metadata Fallback Quiz", "Generated from metadata-only evidence."),
    )
    monkeypatch.setattr(
        quiz_generator,
        "_persist_generated_quiz",
        lambda **kwargs: {
            "quiz": {
                "title": kwargs["quiz_title"],
                "description": kwargs["quiz_description"],
                "workspace_tag": kwargs["workspace_tag"],
            },
            "questions": kwargs["questions"],
        },
    )

    result = await generate_quiz_from_sources(
        db=Mock(),
        media_db=Mock(),
        sources=[{"source_type": "note", "source_id": "note-meta"}],
        num_questions=1,
        question_types=["multiple_choice"],
        workspace_tag="workspace:test",
    )

    assert result["quiz"]["workspace_tag"] == "workspace:test"
    assert result["questions"][0]["source_citations"][0]["quote"] == "Study point from note:note-meta."
