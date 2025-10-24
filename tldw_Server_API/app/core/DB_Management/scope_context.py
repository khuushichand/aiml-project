"""Per-request content scope context for Media/Content databases."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class ScopeContext:
    """Represents the active authorization scope for content operations."""

    user_id: Optional[int]
    org_ids: List[int]
    team_ids: List[int]
    active_org_id: Optional[int]
    active_team_id: Optional[int]
    is_admin: bool = False
    session_role: Optional[str] = None

    @property
    def effective_org_id(self) -> Optional[int]:
        if self.active_org_id is not None:
            return self.active_org_id
        return self.org_ids[0] if self.org_ids else None

    @property
    def effective_team_id(self) -> Optional[int]:
        if self.active_team_id is not None:
            return self.active_team_id
        return self.team_ids[0] if self.team_ids else None


def _ordered_unique_ints(values: Iterable[int]) -> List[int]:
    """Return integers in first-seen order without duplicates."""
    seen: set[int] = set()
    ordered: List[int] = []
    for value in values:
        if value is None:
            continue
        try:
            as_int = int(value)
        except (TypeError, ValueError):
            continue
        if as_int in seen:
            continue
        seen.add(as_int)
        ordered.append(as_int)
    return ordered


_SCOPE_CTX: ContextVar[Optional[ScopeContext]] = ContextVar("content_scope_ctx", default=None)


def set_scope(
    *,
    user_id: Optional[int],
    org_ids: Iterable[int] = (),
    team_ids: Iterable[int] = (),
    active_org_id: Optional[int] = None,
    active_team_id: Optional[int] = None,
    is_admin: bool = False,
    session_role: Optional[str] = None,
) -> Token:
    """Set the current scope context and return a token for later reset."""
    org_list = _ordered_unique_ints(org_ids)
    team_list = _ordered_unique_ints(team_ids)

    scope = ScopeContext(
        user_id=user_id,
        org_ids=org_list,
        team_ids=team_list,
        active_org_id=int(active_org_id) if active_org_id is not None else None,
        active_team_id=int(active_team_id) if active_team_id is not None else None,
        is_admin=is_admin,
        session_role=str(session_role) if session_role else None,
    )
    return _SCOPE_CTX.set(scope)


def reset_scope(token: Token) -> None:
    """Restore the scope context from a prior set_scope call."""
    _SCOPE_CTX.reset(token)


def get_scope() -> Optional[ScopeContext]:
    """Return the currently active scope (if any)."""
    return _SCOPE_CTX.get()


@contextmanager
def scoped_context(**kwargs) -> ScopeContext:
    """Context manager helper for temporarily setting a scope."""
    token = set_scope(**kwargs)
    try:
        scope = get_scope()
        yield scope
    finally:
        reset_scope(token)
