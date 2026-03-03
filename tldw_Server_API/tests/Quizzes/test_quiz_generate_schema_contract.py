import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.quizzes import QuizGenerateRequest, SourceCitation


def test_quiz_generate_request_accepts_sources_array():
    payload = QuizGenerateRequest.model_validate(
        {
            "num_questions": 5,
            "sources": [{"source_type": "note", "source_id": "note-1"}],
        }
    )

    assert payload.sources is not None
    assert payload.sources[0].source_type == "note"


def test_quiz_generate_request_rejects_unknown_source_type():
    with pytest.raises(ValidationError):
        QuizGenerateRequest.model_validate(
            {
                "sources": [{"source_type": "unknown", "source_id": "1"}],
            }
        )


def test_quiz_generate_request_requires_media_id_or_sources():
    with pytest.raises(ValidationError):
        QuizGenerateRequest.model_validate({"num_questions": 5})


def test_source_citation_accepts_canonical_source_fields():
    citation = SourceCitation.model_validate(
        {
            "source_type": "flashcard_card",
            "source_id": "card-uuid",
            "quote": "sample",
        }
    )

    assert citation.source_type == "flashcard_card"
    assert citation.source_id == "card-uuid"
