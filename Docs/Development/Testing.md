Testing Architecture and Fixture Plugins
---------------------------------------

This repository uses pytest plugin modules to provide shared fixtures in a
scalable, low‑coupling way. Suite‑level `conftest.py` files stay lean and focus
on markers, CLI options, and lightweight environment overrides.

Plugin Layout
-------------

- `tldw_Server_API/tests/_plugins/e2e_fixtures.py`
  - Exposes end‑to‑end fixtures (API clients, credentials, trackers).
- `tldw_Server_API/tests/_plugins/chat_fixtures.py`
  - Chat helpers and authenticated client wrappers (pre‑existing).
- `tldw_Server_API/tests/_plugins/media_fixtures.py`
  - Temporary media file fixtures (text/PDF/audio) with auto‑cleanup.

Aggregator
----------

Each test suite declares plugins explicitly via `pytest_plugins` in its local
`conftest.py`. Example from `tldw_Server_API/tests/e2e/conftest.py`:

```
pytest_plugins = [
    "tldw_Server_API.tests._plugins.e2e_fixtures",
    "tldw_Server_API.tests._plugins.chat_fixtures",
    "tldw_Server_API.tests._plugins.media_fixtures",
]
```

Note: If adopting pytest>=8 constraints about plugin discovery in nested
`conftest.py` files, prefer registering these at a top‑level `conftest.py`
instead. Tests already running with nested registration may continue to do so.

Fixture Contracts (Types)
-------------------------

- `api_client() -> APIClient`
  - Returns a sync client that talks to the running API (`E2E_TEST_BASE_URL`) or
    an in‑process ASGI client when `E2E_INPROCESS=1`.
  - Honors single‑user mode by setting `X-API-KEY` when available.

- `authenticated_client(api_client, test_user_credentials) -> APIClient`
  - Single‑user: injects API key via `X-API-KEY` and returns the client.
  - Multi‑user: registers the test user if needed, logs in, and sets
    `Authorization: Bearer <token>`.

- `test_user_credentials() -> dict[str, str]`
  - Example: `{"username": "e2e_test_user_<ts>", "email": ..., "password": ...}`.

- `data_tracker()`
  - Tracks created resources during tests (media IDs, prompt IDs, file paths) and
    ensures temporary files are cleaned up at session end.

- Media fixtures (optional helpers)
  - `test_text_file() -> str`
  - `test_pdf_file() -> str`
  - `test_audio_file() -> str`
  - Each yields a temporary file path and handles cleanup automatically.

Design Rules
------------

- Keep heavy work out of module import time; do it inside fixture bodies.
- Use `__all__` in plugin modules to make the exported surface explicit.
- Prefer composition: re‑use helpers from `tldw_Server_API.tests.e2e.fixtures` to
  avoid duplication and drift.

CI Guard
--------

The CI workflow includes a fast guard that verifies core fixtures are discoverable:

```
pytest --fixtures -q tldw_Server_API/tests/e2e | rg -q '^test_user_credentials$'
```

It fails the build if `test_user_credentials` is not registered, catching
regressions where a plugin stops exposing required fixtures.

