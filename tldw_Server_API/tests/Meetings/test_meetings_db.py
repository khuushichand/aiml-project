from __future__ import annotations

import pytest

from tldw_Server_API.app.core.DB_Management.Meetings_DB import MeetingsDatabase


pytestmark = pytest.mark.unit


@pytest.fixture()
def meetings_db(tmp_path):
    db_path = tmp_path / "Media_DB_v2.db"
    db = MeetingsDatabase(db_path=db_path, client_id="tester", user_id="1")
    try:
        yield db
    finally:
        db.close_connection()


def test_create_and_get_session(meetings_db):
    session_id = meetings_db.create_session(title="Standup", meeting_type="standup")
    row = meetings_db.get_session(session_id=session_id)
    assert row is not None
    assert row["title"] == "Standup"
    assert row["status"] == "scheduled"


def test_update_session_status(meetings_db):
    session_id = meetings_db.create_session(title="Weekly Sync", meeting_type="sync")
    updated = meetings_db.update_session_status(session_id=session_id, status="live")
    assert updated is True
    row = meetings_db.get_session(session_id=session_id)
    assert row is not None
    assert row["status"] == "live"


def test_sessions_are_scoped_per_user(tmp_path):
    shared_db_path = tmp_path / "shared_media.db"
    db_user_1 = MeetingsDatabase(db_path=shared_db_path, client_id="u1", user_id="1")
    db_user_2 = MeetingsDatabase(db_path=shared_db_path, client_id="u2", user_id="2")
    try:
        session_u1 = db_user_1.create_session(title="U1 Session", meeting_type="standup")
        session_u2 = db_user_2.create_session(title="U2 Session", meeting_type="retro")

        rows_u1 = db_user_1.list_sessions()
        rows_u2 = db_user_2.list_sessions()

        assert [row["id"] for row in rows_u1] == [session_u1]
        assert [row["id"] for row in rows_u2] == [session_u2]
        assert db_user_2.get_session(session_id=session_u1) is None
    finally:
        db_user_1.close_connection()
        db_user_2.close_connection()
