# Testing Known Issues (Sandbox/WebSocket)

Updated: 2025-10-29

This page tracks a known intermittent hang when running certain sandbox WebSocket tests in some local environments.

Issue
- Test: `tldw_Server_API/tests/sandbox/test_ws_heartbeat_seq.py`
- Symptom: pytest exit hangs at session teardown (often after KeyboardInterrupt), despite the test scope having a timeout and calling `ws.close()`.

Probable cause
- Background heartbeat tasks may remain scheduled after WS close if the disconnect path does not cancel them promptly.
- Environment interactions (e.g., event loop policy, plugin order) may change teardown timing and expose the race.

Workarounds
- Keep `pytest-timeout` active for the test (already annotated) and avoid running the entire sandbox tests suite in one shot when reproducing locally.
- Run this test in isolation when needed:
  - `python -m pytest -q tldw_Server_API/tests/sandbox/test_ws_heartbeat_seq.py`
- Ensure `SANDBOX_ENABLE_EXECUTION=false` and the monkeypatched sleep are in effect to minimize residual background work.

Recommended fix (outside Watchlists scope)
- In the WS endpoint and heartbeat scheduler, ensure that:
  - All background tasks are cancelled on disconnect, and cancellation is awaited with a short deadline.
  - Any repeating heartbeat loops check a shared `alive` flag and exit promptly when cleared.
  - Consider exposing a short `WS_SHUTDOWN_TIMEOUT_MS` env with a tight default in test mode.

Notes
- The Watchlists changes do not alter this test path.
- If the hang persists, collect asyncio task dumps on teardown for triage: e.g., add a fixture that logs `asyncio.all_tasks()` states on failure.
