"""
Persona Session Manager (scaffold)

Tracks persona sessions: session_id, user, persona, recent turns.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class PlanStep:
    idx: int
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    description: str | None = None
    why: str | None = None


@dataclass
class PendingPlan:
    plan_id: str
    session_id: str
    created_at: datetime
    steps: list[PlanStep] = field(default_factory=list)


@dataclass
class Session:
    session_id: str
    user_id: str
    persona_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    preferences: dict[str, Any] = field(default_factory=dict)
    turns: list[dict] = field(default_factory=list)
    pending_plans: dict[str, PendingPlan] = field(default_factory=dict)


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    @staticmethod
    def _touch_session(session: Session) -> None:
        session.updated_at = datetime.now(timezone.utc)

    def create(self, user_id: str, persona_id: str, resume_session_id: str | None = None) -> Session:
        if resume_session_id and resume_session_id in self._sessions:
            existing = self._sessions[resume_session_id]
            if existing.user_id != user_id:
                raise ValueError("session ownership mismatch")
            self._touch_session(existing)
            return existing
        sid = resume_session_id or str(uuid.uuid4())
        sess = Session(
            session_id=sid,
            user_id=user_id,
            persona_id=persona_id,
            preferences={"use_memory_context": True},
        )
        self._sessions[sid] = sess
        return sess

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def put_plan(
        self,
        *,
        session_id: str,
        user_id: str,
        persona_id: str,
        plan_id: str,
        steps: list[dict[str, Any]],
    ) -> PendingPlan:
        if not session_id:
            raise ValueError("session_id is required")
        if not plan_id:
            raise ValueError("plan_id is required")
        session = self.create(user_id=user_id, persona_id=persona_id, resume_session_id=session_id)
        normalized_steps: list[PlanStep] = []
        for raw in steps:
            if not isinstance(raw, dict):
                continue
            try:
                idx = int(raw.get("idx"))
            except (TypeError, ValueError):
                continue
            tool = str(raw.get("tool") or "").strip()
            if not tool:
                continue
            args = raw.get("args")
            if not isinstance(args, dict):
                args = {}
            description = raw.get("description")
            if description is not None:
                description = str(description)
            why = raw.get("why")
            if why is not None:
                why = str(why)
            normalized_steps.append(PlanStep(idx=idx, tool=tool, args=args, description=description, why=why))
        if not normalized_steps:
            raise ValueError("no valid plan steps")
        normalized_steps.sort(key=lambda step: step.idx)
        pending = PendingPlan(
            plan_id=plan_id,
            session_id=session_id,
            created_at=datetime.now(timezone.utc),
            steps=normalized_steps,
        )
        session.pending_plans[plan_id] = pending
        self._touch_session(session)
        return pending

    def get_plan(
        self,
        *,
        session_id: str,
        plan_id: str,
        user_id: str | None = None,
        consume: bool = False,
    ) -> PendingPlan | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if user_id is not None and session.user_id != user_id:
            return None
        pending = session.pending_plans.get(plan_id)
        if pending is None:
            return None
        if consume:
            session.pending_plans.pop(plan_id, None)
            self._touch_session(session)
        return pending

    def clear_plans(
        self,
        *,
        session_id: str,
        user_id: str | None = None,
    ) -> int:
        session = self._sessions.get(session_id)
        if session is None:
            return 0
        if user_id is not None and session.user_id != user_id:
            return 0
        cleared = len(session.pending_plans)
        session.pending_plans.clear()
        if cleared:
            self._touch_session(session)
        return cleared

    def append_turn(
        self,
        *,
        session_id: str,
        user_id: str,
        persona_id: str,
        role: str,
        content: str,
        turn_type: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = self.create(user_id=user_id, persona_id=persona_id, resume_session_id=session_id)
        turn: dict[str, Any] = {
            "turn_id": uuid.uuid4().hex,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": str(role or "unknown"),
            "type": str(turn_type or "text"),
            "content": str(content or ""),
            "metadata": dict(metadata or {}),
        }
        session.turns.append(turn)
        self._touch_session(session)
        return turn

    def list_turns(
        self,
        *,
        session_id: str,
        user_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        session = self._sessions.get(session_id)
        if session is None:
            return []
        if user_id is not None and session.user_id != user_id:
            return []
        turns = list(session.turns)
        if limit is not None:
            try:
                safe_limit = max(0, int(limit))
            except (TypeError, ValueError):
                safe_limit = 0
            if safe_limit:
                turns = turns[-safe_limit:]
            else:
                turns = []
        return turns

    def update_preferences(
        self,
        *,
        session_id: str,
        user_id: str,
        preferences: dict[str, Any],
    ) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None or session.user_id != user_id:
            raise ValueError("session not found or ownership mismatch")
        for key, value in (preferences or {}).items():
            if not isinstance(key, str) or not key.strip():
                continue
            if value is None:
                session.preferences.pop(key, None)
            else:
                session.preferences[key] = value
        self._touch_session(session)
        return dict(session.preferences)

    def get_preferences(
        self,
        *,
        session_id: str,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None:
            return {}
        if user_id is not None and session.user_id != user_id:
            return {}
        return dict(session.preferences)

    def list_sessions(
        self,
        *,
        user_id: str,
        persona_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        sessions = [
            session
            for session in self._sessions.values()
            if session.user_id == user_id and (persona_id is None or session.persona_id == persona_id)
        ]
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        if limit is not None:
            try:
                safe_limit = max(0, int(limit))
            except (TypeError, ValueError):
                safe_limit = 0
            sessions = sessions[:safe_limit] if safe_limit else []
        return [
            {
                "session_id": session.session_id,
                "persona_id": session.persona_id,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "turn_count": len(session.turns),
                "pending_plan_count": len(session.pending_plans),
                "preferences": dict(session.preferences),
            }
            for session in sessions
        ]

    def get_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        limit_turns: int | None = None,
    ) -> dict[str, Any] | None:
        session = self._sessions.get(session_id)
        if session is None or session.user_id != user_id:
            return None
        turns = self.list_turns(session_id=session_id, user_id=user_id, limit=limit_turns)
        return {
            "session_id": session.session_id,
            "persona_id": session.persona_id,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "turn_count": len(session.turns),
            "pending_plan_count": len(session.pending_plans),
            "preferences": dict(session.preferences),
            "turns": turns,
        }


_singleton: SessionManager | None = None


def get_session_manager() -> SessionManager:
    global _singleton
    if _singleton is None:
        _singleton = SessionManager()
    return _singleton
