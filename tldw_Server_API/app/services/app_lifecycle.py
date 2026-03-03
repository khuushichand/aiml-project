from __future__ import annotations

from collections.abc import MutableMapping
from typing import Literal

from fastapi import FastAPI

_LIFECYCLE_EVENTS_ATTR = "_tldw_lifecycle_events"
_LifecycleEvent = Literal["startup", "shutdown"]


def _append_lifecycle_event(app: FastAPI, event: _LifecycleEvent) -> None:
    events = getattr(app.state, _LIFECYCLE_EVENTS_ATTR, None)
    if events is None:
        events = []
        app.state._tldw_lifecycle_events = events
    events.append(event)


def mark_lifecycle_startup(app: FastAPI, readiness_state: MutableMapping[str, bool]) -> None:
    """Record startup transition and mark readiness true."""
    readiness_state["ready"] = True
    _append_lifecycle_event(app, "startup")


def mark_lifecycle_shutdown(app: FastAPI, readiness_state: MutableMapping[str, bool]) -> None:
    """Record shutdown transition and mark readiness false."""
    readiness_state["ready"] = False
    _append_lifecycle_event(app, "shutdown")
