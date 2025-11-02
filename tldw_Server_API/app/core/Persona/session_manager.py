"""
Persona Session Manager (scaffold)

Tracks persona sessions: session_id, user, persona, recent turns.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Session:
    session_id: str
    user_id: str
    persona_id: str
    turns: List[Dict] = field(default_factory=list)


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def create(self, user_id: str, persona_id: str, resume_session_id: Optional[str] = None) -> Session:
        if resume_session_id and resume_session_id in self._sessions:
            return self._sessions[resume_session_id]
        sid = resume_session_id or str(uuid.uuid4())
        sess = Session(session_id=sid, user_id=user_id, persona_id=persona_id)
        self._sessions[sid] = sess
        return sess

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)


_singleton: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    global _singleton
    if _singleton is None:
        _singleton = SessionManager()
    return _singleton
