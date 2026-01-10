from __future__ import annotations

import pytest

from tldw_Server_API.app.api.v1.schemas.feedback_schemas import ExplicitFeedbackRequest
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
