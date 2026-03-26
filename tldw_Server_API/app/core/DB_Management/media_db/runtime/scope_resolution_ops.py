"""Package-owned scope resolution helper for the Media DB runtime."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)
from tldw_Server_API.app.core.DB_Management.scope_context import get_scope

_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def _resolve_scope_ids(self: Any) -> tuple[int | None, int | None]:
    """Determine effective org/team ids for the current execution context."""
    try:
        scope = get_scope()
    except _MEDIA_NONCRITICAL_EXCEPTIONS:
        scope = None

    org_id = self.default_org_id
    team_id = self.default_team_id

    if scope:
        scope_org = scope.effective_org_id
        scope_team = scope.effective_team_id
        if scope_org is not None:
            org_id = scope_org
        if scope_team is not None:
            team_id = scope_team

    self._scope_cache = (org_id, team_id)
    return org_id, team_id


__all__ = ["_resolve_scope_ids"]
