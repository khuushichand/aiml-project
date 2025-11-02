from __future__ import annotations

import asyncio as _asyncio
import warnings
import pytest


@pytest.fixture(autouse=True)
def patch_sandbox_heartbeat_sleep(monkeypatch: pytest.MonkeyPatch):
    """Speed up WS heartbeats across sandbox WS tests by patching asyncio.sleep
    in the sandbox endpoint module to a near-zero sleep.
    """
    try:
        from tldw_Server_API.app.api.v1.endpoints import sandbox as sb

        _orig_sleep = _asyncio.sleep

        async def _fast_sleep(_n: float) -> None:  # pragma: no cover - trivial
            await _orig_sleep(0.01)

        monkeypatch.setattr(sb.asyncio, "sleep", _fast_sleep, raising=True)
    except Exception:
        # If import fails in a non-WS test, ignore
        pass


@pytest.fixture(autouse=True, scope="session")
def set_ws_poll_timeout_for_tests():
    """
    Configure environment variables to make sandbox WebSocket behavior test-friendly.

    Sets sensible defaults only if not already present:
    - Sets SANDBOX_WS_POLL_TIMEOUT_SEC to "1" so the WebSocket loop notices disconnects quickly.
    - Enables SANDBOX_ENABLE_EXECUTION and SANDBOX_BACKGROUND_EXECUTION to allow execution and background mode during tests.
    - Enables SANDBOX_WS_SYNTHETIC_FRAMES_FOR_TESTS to avoid CI hangs by using synthetic frames.
    - Ensures "sandbox" is present in ROUTES_ENABLE so the sandbox router is active for tests.
    """
    os = __import__("os")
    os.environ.setdefault("SANDBOX_WS_POLL_TIMEOUT_SEC", "1")
    # Default to enabling execution and background mode in WS tests unless a test overrides
    os.environ.setdefault("SANDBOX_ENABLE_EXECUTION", "true")
    os.environ.setdefault("SANDBOX_BACKGROUND_EXECUTION", "true")
    # Enable synthetic WS frames to avoid hangs in CI for sandbox tests only
    os.environ.setdefault("SANDBOX_WS_SYNTHETIC_FRAMES_FOR_TESTS", "true")
    # Ensure the experimental sandbox router is enabled for these tests
    existing_enable = os.environ.get("ROUTES_ENABLE", "")
    parts = [p.strip().lower() for p in existing_enable.split(",") if p.strip()]
    if "sandbox" not in parts:
        parts.append("sandbox")
    os.environ["ROUTES_ENABLE"] = ",".join(parts)


@pytest.fixture()
def ws_flush():
    """Publish a final frame (heartbeat) for a run to flush WS server loop.

    Usage: call ws_flush(run_id) right before closing the client WebSocket.
    """
    def _flush(run_id: str) -> None:
        try:
            from tldw_Server_API.app.core.Sandbox.streams import get_hub
            hub = get_hub()
            hub.publish_heartbeat(run_id)
        except Exception:
            # Best-effort helper; ignore if hub not available
            pass
    return _flush

@pytest.fixture(autouse=True, scope="session")
def reduce_warnings_noise():
    """Globally silence warnings for sandbox tests to ensure fast teardown.

    The main app and its dependencies can emit many deprecations during import.
    For focused sandbox unit tests, silence them to avoid slow exits.
    """
    warnings.filterwarnings("ignore")
