from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.meetings_schemas import (
    MeetingSessionCreate,
    MeetingSessionResponse,
)


def test_meeting_session_create_defaults_status_scheduled():
    payload = MeetingSessionCreate(title="Weekly Standup", meeting_type="standup")
    assert payload.title == "Weekly Standup"
    assert payload.meeting_type == "standup"


def test_meeting_session_create_rejects_empty_title():
    try:
        MeetingSessionCreate(title="", meeting_type="standup")
    except ValidationError as exc:
        assert "String should have at least 1 character" in str(exc)
    else:
        raise AssertionError("Expected ValidationError for empty title")


def test_meeting_session_response_roundtrip():
    model = MeetingSessionResponse(
        id="sess_123",
        title="Discovery Call",
        meeting_type="discovery",
        status="scheduled",
        source_type="upload",
    )
    dumped = model.model_dump()
    assert dumped["id"] == "sess_123"
    assert dumped["status"] == "scheduled"


def test_meeting_session_response_rejects_invalid_status():
    try:
        MeetingSessionResponse(
            id="sess_123",
            title="Bad Session",
            meeting_type="standup",
            status="not-a-valid-status",
            source_type="upload",
        )
    except ValidationError as exc:
        assert "Input should be" in str(exc)
    else:
        raise AssertionError("Expected ValidationError for invalid session status")
