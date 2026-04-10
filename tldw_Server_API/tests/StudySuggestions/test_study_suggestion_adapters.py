from tldw_Server_API.app.core.StudySuggestions.flashcard_adapter import (
    build_flashcard_suggestion_context,
    is_source_grounded_session,
)
from tldw_Server_API.app.core.StudySuggestions.quiz_adapter import build_quiz_suggestion_context


def test_quiz_attempts_emit_stable_suggestion_context():
    context = build_quiz_suggestion_context(
        quiz_attempt={
            "id": 42,
            "quiz_id": 9,
            "workspace_id": "ws-7",
            "score": 3,
            "correct_answers": 3,
            "total_questions": 5,
            "question_results": [
                {"question_id": 1, "correct": False, "topic_label": "Kidney Function"},
                {"question_id": 2, "correct": True, "topic_label": "Electrolyte Balance"},
            ],
        },
        source_bundle=[
            {"source_type": "note", "source_id": "note-11", "label": "Kidney Function"},
        ],
    )

    assert context.service == "quiz"  # nosec B101
    assert context.activity_type == "quiz_attempt"  # nosec B101
    assert context.anchor_type == "quiz_attempt"  # nosec B101
    assert context.anchor_id == 42  # nosec B101
    assert context.workspace_id == "ws-7"  # nosec B101
    assert context.summary_metrics == {  # nosec B101
        "score": 3,
        "correct_answers": 3,
        "total_questions": 5,
    }
    assert context.performance_signals == {  # nosec B101
        "incorrect_count": 1,
        "accuracy": 0.6,
    }
    assert context.source_bundle == [  # nosec B101
        {"source_type": "note", "source_id": "note-11", "label": "Kidney Function"},
    ]


def test_flashcard_sessions_expose_grounded_flag_for_provenance_backed_session():
    session = {
        "id": 12,
        "deck_id": 5,
        "workspace_id": "ws-9",
        "review_mode": "due",
        "cards_reviewed": 8,
        "correct_count": 6,
        "tag_labels": ["renal basics"],
        "study_pack_id": 44,
        "source_bundle": [
            {"source_type": "note", "source_id": "note-8", "citation_ordinal": 0},
        ],
    }

    context = build_flashcard_suggestion_context(session)

    assert is_source_grounded_session(session) is True  # nosec B101
    assert context.service == "flashcards"  # nosec B101
    assert context.activity_type == "flashcard_review_session"  # nosec B101
    assert context.anchor_type == "flashcard_review_session"  # nosec B101
    assert context.anchor_id == 12  # nosec B101
    assert context.workspace_id == "ws-9"  # nosec B101
    assert context.performance_signals["is_source_grounded_session"] is True  # nosec B101


def test_flashcard_sessions_without_lineage_remain_exploratory_only():
    session = {
        "id": 15,
        "deck_id": None,
        "workspace_id": None,
        "review_mode": "manual",
        "cards_reviewed": 4,
        "correct_count": 2,
        "tag_labels": ["renal basics"],
        "source_bundle": [],
    }

    context = build_flashcard_suggestion_context(session)

    assert is_source_grounded_session(session) is False  # nosec B101
    assert context.summary_metrics["deck_id"] is None  # nosec B101
    assert context.performance_signals["is_source_grounded_session"] is False  # nosec B101
    assert context.performance_signals["supports_source_aware_adjacency"] is False  # nosec B101
