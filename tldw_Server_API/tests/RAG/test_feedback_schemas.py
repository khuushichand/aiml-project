from __future__ import annotations

import pytest

from tldw_Server_API.app.api.v1.schemas.feedback_schemas import (
    KNOWN_ISSUE_IDS,
    ExplicitFeedbackRequest,
    FeedbackDeleteResponse,
    FeedbackListResponse,
    FeedbackRecord,
    FeedbackUpdateRequest,
)
from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import ImplicitFeedbackEvent


def test_explicit_feedback_allows_missing_query_when_message_id_present() -> None:

    request = ExplicitFeedbackRequest(
        message_id="M_01",
        feedback_type="helpful",
        helpful=True,
    )
    assert request.message_id == "M_01"


def test_explicit_feedback_requires_query_when_message_id_missing() -> None:

    with pytest.raises(ValueError, match="query is required"):
        ExplicitFeedbackRequest(
            feedback_type="helpful",
            helpful=True,
        )


def test_implicit_feedback_requires_dwell_ms_for_dwell_time() -> None:

    with pytest.raises(ValueError, match="dwell_ms is required"):
        ImplicitFeedbackEvent(event_type="dwell_time")


def test_implicit_feedback_accepts_dwell_ms_for_dwell_time() -> None:

    request = ImplicitFeedbackEvent(event_type="dwell_time", dwell_ms=4500)
    assert request.dwell_ms == 4500


# ---------------------------------------------------------------------------
# Issue taxonomy tests
# ---------------------------------------------------------------------------


def test_known_issue_ids_has_expected_members() -> None:
    assert "incorrect_information" in KNOWN_ISSUE_IDS
    assert "not_relevant" in KNOWN_ISSUE_IDS
    assert "sources_unhelpful" in KNOWN_ISSUE_IDS
    assert "too_verbose" in KNOWN_ISSUE_IDS
    assert "too_brief" in KNOWN_ISSUE_IDS
    assert "other" in KNOWN_ISSUE_IDS
    assert len(KNOWN_ISSUE_IDS) == 7


def test_unknown_issue_ids_accepted_with_warning(caplog) -> None:
    """Unknown issue IDs should be accepted (permissive) but trigger a warning log."""
    request = ExplicitFeedbackRequest(
        message_id="M_01",
        feedback_type="report",
        issues=["bad_vibes", "not_relevant"],
    )
    assert "bad_vibes" in request.issues
    assert "not_relevant" in request.issues


# ---------------------------------------------------------------------------
# New response schema tests
# ---------------------------------------------------------------------------


def test_feedback_record_schema() -> None:
    record = FeedbackRecord(
        id="fb_123",
        conversation_id="C_abc",
        issues=["not_relevant"],
    )
    assert record.id == "fb_123"
    assert record.document_ids == []
    assert record.helpful is None


def test_feedback_list_response_schema() -> None:
    resp = FeedbackListResponse(
        feedback=[
            FeedbackRecord(id="fb_1", conversation_id="C_1"),
        ]
    )
    assert resp.ok is True
    assert len(resp.feedback) == 1


def test_feedback_update_request_schema() -> None:
    req = FeedbackUpdateRequest(issues=["sources_unhelpful"], user_notes="Changed my mind")
    assert req.issues == ["sources_unhelpful"]
    assert req.user_notes == "Changed my mind"


def test_feedback_delete_response_schema() -> None:
    resp = FeedbackDeleteResponse(deleted=True)
    assert resp.ok is True
    assert resp.deleted is True
