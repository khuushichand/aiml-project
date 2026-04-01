from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import Literal

from fastapi import FastAPI, HTTPException

_LIFECYCLE_EVENTS_ATTR = "_tldw_lifecycle_events"
_LIFECYCLE_STATE_ATTR = "_tldw_lifecycle_state"
_LifecycleEvent = Literal["startup", "shutdown"]


@dataclass
class AppLifecycleState:
    phase: Literal["starting", "ready", "draining", "stopped"] = "starting"
    ready: bool = False
    draining: bool = False


def _append_lifecycle_event(app: FastAPI, event: _LifecycleEvent) -> None:
    events = getattr(app.state, _LIFECYCLE_EVENTS_ATTR, None)
    if events is None:
        events = []
        app.state._tldw_lifecycle_events = events
    events.append(event)


def get_or_create_lifecycle_state(app: FastAPI) -> AppLifecycleState:
    state = getattr(app.state, _LIFECYCLE_STATE_ATTR, None)
    if state is None:
        state = AppLifecycleState()
        app.state._tldw_lifecycle_state = state
    return state


def reset_lifecycle_state(app: FastAPI) -> AppLifecycleState:
    state = AppLifecycleState()
    app.state._tldw_lifecycle_state = state
    return state


def is_lifecycle_draining(app: FastAPI) -> bool:
    """Return True when the app is actively draining shutdown traffic."""
    state = get_or_create_lifecycle_state(app)
    return state.draining or state.phase == "draining"


def assert_may_start_work(app: FastAPI, kind: str) -> None:
    """Raise a 503 if the app is in draining mode and work should not start."""
    if is_lifecycle_draining(app):
        raise HTTPException(
            status_code=503,
            detail={"message": "Shutdown in progress", "kind": kind},
        )


def mark_lifecycle_startup(
    app: FastAPI,
    readiness_state: MutableMapping[str, bool] | None = None,
) -> AppLifecycleState:
    """Record startup transition and mark readiness true."""
    state = get_or_create_lifecycle_state(app)
    state.phase = "ready"
    state.ready = True
    state.draining = False
    if readiness_state is not None:
        readiness_state["ready"] = True
    _append_lifecycle_event(app, "startup")
    return state


def mark_lifecycle_shutdown(
    app: FastAPI,
    readiness_state: MutableMapping[str, bool] | None = None,
) -> AppLifecycleState:
    """Record shutdown transition and mark readiness false."""
    state = get_or_create_lifecycle_state(app)
    state.phase = "draining"
    state.ready = False
    state.draining = True
    if readiness_state is not None:
        readiness_state["ready"] = False
    _append_lifecycle_event(app, "shutdown")
    return state
