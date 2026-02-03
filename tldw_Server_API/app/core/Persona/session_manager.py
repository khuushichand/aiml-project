"""
Persona Session Manager (scaffold)

Tracks persona sessions: session_id, user, persona, recent turns.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class Session:
    session_id: str
    user_id: str
    persona_id: str
    turns: list[dict] = field(default_factory=list)


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create(self, user_id: str, persona_id: str, resume_session_id: str | None = None) -> Session:
        if resume_session_id and resume_session_id in self._sessions:
            return self._sessions[resume_session_id]
        sid = resume_session_id or str(uuid.uuid4())
        sess = Session(session_id=sid, user_id=user_id, persona_id=persona_id)
        self._sessions[sid] = sess
        return sess

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)


_singleton: SessionManager | None = None


def get_session_manager() -> SessionManager:
    global _singleton
    if _singleton is None:
        _singleton = SessionManager()
    return _singleton
