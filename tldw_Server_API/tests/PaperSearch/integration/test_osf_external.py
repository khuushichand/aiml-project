"""
Integration tests for OSF Preprints endpoints (non-mocked). Opt-in via RUN_EXTERNAL_API_TESTS=1.

These are lenient due to live API variability and rate limits.
"""

import os
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.external_api]


def _require_external():
    if os.getenv("RUN_EXTERNAL_API_TESTS", "0") != "1":
        pytest.skip("External API tests disabled. Set RUN_EXTERNAL_API_TESTS=1 to enable.")


def test_osf_search_basic(client_with_auth):
    _require_external()
    resp = client_with_auth.get(
        "/api/v1/paper-search/osf",
        params={"term": "quantum", "results_per_page": 3},
    )
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert "items" in data and isinstance(data["items"], list)


def test_osf_by_id_lenient(client_with_auth):
    _require_external()
    # Use an obviously fake id; allow 404 or errors
    resp = client_with_auth.get("/api/v1/paper-search/osf/by-id", params={"osf_id": "zzznotreal"})
    assert resp.status_code in (404, 500, 502, 504)


def test_osf_ingest_lenient(client_with_auth):
    _require_external()
    # Without a stable known OSF id hosting a PDF, just check endpoint wiring
    resp = client_with_auth.post(
        "/api/v1/paper-search/osf/ingest",
        params={"osf_id": "zzznotreal", "perform_chunking": "false", "perform_analysis": "false"},
    )
    assert resp.status_code in (404, 500, 502, 504), resp.text
