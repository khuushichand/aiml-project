import pytest

from tldw_Server_API.app.services.quiz_generator import (
    QuizProvenanceValidationError,
    _validate_strict_provenance,
)


def test_rejects_questions_without_source_citations():
    with pytest.raises(QuizProvenanceValidationError, match="missing required source_citations"):
        _validate_strict_provenance(
            [{"question_text": "Q1", "source_citations": []}],
            [{"source_type": "note", "source_id": "n1"}],
        )


def test_rejects_citations_not_in_selected_sources():
    with pytest.raises(QuizProvenanceValidationError, match="do not map to selected sources"):
        _validate_strict_provenance(
            [{"source_citations": [{"source_type": "media", "source_id": "999"}]}],
            [{"source_type": "note", "source_id": "n1"}],
        )


def test_rejects_mixed_valid_and_invalid_citations():
    with pytest.raises(QuizProvenanceValidationError, match="do not map to selected sources"):
        _validate_strict_provenance(
            [
                {
                    "source_citations": [
                        {"source_type": "note", "source_id": "n1"},
                        {"source_type": "media", "source_id": "999"},
                    ]
                }
            ],
            [{"source_type": "note", "source_id": "n1"}],
        )


def test_accepts_valid_citations_for_selected_sources():
    _validate_strict_provenance(
        [{"source_citations": [{"source_type": "note", "source_id": "n1"}]}],
        [{"source_type": "note", "source_id": "n1"}],
    )
