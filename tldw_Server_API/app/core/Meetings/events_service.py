"""Meeting events service backed by meeting_event_log persistence."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.Meetings_DB import MeetingsDatabase
from tldw_Server_API.app.core.Meetings.stream_adapter import build_meeting_event


class MeetingEventsService:
    """Publish and read structured meeting events."""

    def __init__(self, db: MeetingsDatabase) -> None:
        self._db = db

    def emit(
        self,
        *,
        session_id: str,
        event_type: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event_id = self._db.append_event(
            session_id=session_id,
            event_type=event_type,
            payload_json=data or {},
        )
        return build_meeting_event(
            event_type=event_type,
            session_id=session_id,
            data=data or {},
            event_id=str(event_id),
        )

    def recent(self, *, session_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._db.list_events(session_id=session_id, limit=limit)
        events: list[dict[str, Any]] = []
        for row in rows:
            events.append(
                build_meeting_event(
                    event_type=str(row.get("event_type") or "event"),
                    session_id=str(row.get("session_id") or session_id),
                    data=row.get("payload_json") or {},
                    event_id=str(row.get("id") or ""),
                    timestamp=row.get("created_at"),
                )
            )
        return events

    @staticmethod
    def snapshot_for_session(session_row: dict[str, Any]) -> dict[str, Any]:
        return build_meeting_event(
            event_type="session.status",
            session_id=str(session_row.get("id") or ""),
            data={
                "status": session_row.get("status"),
                "title": session_row.get("title"),
                "meeting_type": session_row.get("meeting_type"),
            },
            timestamp=session_row.get("updated_at") or session_row.get("created_at"),
        )
