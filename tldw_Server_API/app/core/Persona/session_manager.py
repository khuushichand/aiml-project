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
    turns: list[dict] = field(default_factory=list)
    pending_plans: dict[str, PendingPlan] = field(default_factory=dict)


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create(self, user_id: str, persona_id: str, resume_session_id: str | None = None) -> Session:
        if resume_session_id and resume_session_id in self._sessions:
            existing = self._sessions[resume_session_id]
            if existing.user_id != user_id:
                raise ValueError("session ownership mismatch")
            return existing
        sid = resume_session_id or str(uuid.uuid4())
        sess = Session(session_id=sid, user_id=user_id, persona_id=persona_id)
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


_singleton: SessionManager | None = None


def get_session_manager() -> SessionManager:
    global _singleton
    if _singleton is None:
        _singleton = SessionManager()
    return _singleton
