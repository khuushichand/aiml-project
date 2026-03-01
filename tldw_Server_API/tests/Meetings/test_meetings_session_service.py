from __future__ import annotations

import pytest

from tldw_Server_API.app.core.DB_Management.Meetings_DB import MeetingsDatabase
from tldw_Server_API.app.core.Meetings.session_service import MeetingSessionService


pytestmark = pytest.mark.unit


@pytest.fixture()
def session_service(tmp_path):
    db = MeetingsDatabase(db_path=tmp_path / "Media_DB_v2.db", client_id="tester", user_id="1")
    service = MeetingSessionService(db=db)
    try:
        yield service
    finally:
        db.close_connection()


def test_session_state_machine_blocks_invalid_transition(session_service):
    created = session_service.create_session(title="Standup", meeting_type="standup")
    with pytest.raises(ValueError):
        session_service.transition(session_id=created["id"], to_status="completed")


def test_session_state_machine_allows_valid_transition(session_service):
    created = session_service.create_session(title="Sprint Planning", meeting_type="planning")
    live = session_service.transition(session_id=created["id"], to_status="live")
    assert live["status"] == "live"
    processing = session_service.transition(session_id=created["id"], to_status="processing")
    assert processing["status"] == "processing"
    completed = session_service.transition(session_id=created["id"], to_status="completed")
    assert completed["status"] == "completed"


def test_session_transition_raises_for_missing_session(session_service):
    with pytest.raises(KeyError):
        session_service.transition(session_id="sess_missing", to_status="live")
