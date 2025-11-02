"""
Integration tests for EarthArXiv (OSF) endpoints (non-mocked). Opt-in via RUN_EXTERNAL_API_TESTS=1.
"""

import os
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.external_api]


def _require_external():
    if os.getenv("RUN_EXTERNAL_API_TESTS", "0") != "1":
        pytest.skip("External API tests disabled. Set RUN_EXTERNAL_API_TESTS=1 to enable.")


def test_earthrxiv_search_basic(client_with_auth):
    _require_external()
    resp = client_with_auth.get("/api/v1/paper-search/earthrxiv", params={"term": "tectonics", "results_per_page": 5})
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert "items" in data and isinstance(data["items"], list)


def test_earthrxiv_by_id_notfound_ok(client_with_auth):
    _require_external()
    # Likely nonexistent id - expect 404 or tolerant error mapping
    resp = client_with_auth.get("/api/v1/paper-search/earthrxiv/by-id", params={"osf_id": "zzznotreal"})
    assert resp.status_code in (404, 502, 504), resp.text
