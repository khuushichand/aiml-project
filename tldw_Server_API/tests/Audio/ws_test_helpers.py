from contextlib import contextmanager

import pytest
from starlette.websockets import WebSocketDisconnect


@contextmanager
def ws_session_or_skip(ws, *, reason: str = "audio WebSocket endpoint not available in this build"):
    """Enter a TestClient websocket session or skip when it disconnects on entry."""
    try:
        session = ws.__enter__()
    except WebSocketDisconnect:
        pytest.skip(reason)
    try:
        yield session
    finally:
        ws.__exit__(None, None, None)
