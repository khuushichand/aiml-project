"""Shared types for governance policy resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

GovernanceAction = Literal["allow", "warn", "require_approval", "deny"]


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class CandidateAction:
    """Candidate governance action emitted by a matching policy/rule."""

    action: GovernanceAction
    scope_level: int
    priority: int = 0
    updated_at: datetime = field(default_factory=utc_now)
    source_id: Optional[str] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class EffectiveAction:
    """Resolved governance action with provenance and ordering trace."""

    action: GovernanceAction
    winning_candidate: CandidateAction
    ordered_candidates: tuple[CandidateAction, ...]

