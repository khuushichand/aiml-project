"""Helpers for meeting event envelopes and transport framing."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_meeting_event(
    *,
    event_type: str,
    session_id: str,
    data: dict[str, Any] | None = None,
    event_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    return {
        "id": event_id or uuid.uuid4().hex,
        "type": str(event_type),
        "session_id": str(session_id),
        "timestamp": timestamp or utcnow_iso(),
        "data": data or {},
    }


def to_sse_frame(event: dict[str, Any]) -> str:
    payload = json.dumps(event, separators=(",", ":"), default=str)
    return f"id: {event.get('id','')}\nevent: {event.get('type','event')}\ndata: {payload}\n\n"
