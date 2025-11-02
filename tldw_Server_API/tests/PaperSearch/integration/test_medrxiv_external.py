"""
Integration tests for MedRxiv alias endpoints (non-mocked). Opt-in via RUN_EXTERNAL_API_TESTS=1.
"""

import os
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.external_api]


def _require_external():
    if os.getenv("RUN_EXTERNAL_API_TESTS", "0") != "1":
        pytest.skip("External API tests disabled. Set RUN_EXTERNAL_API_TESTS=1 to enable.")


def test_medrxiv_search_basic(client_with_auth):
    _require_external()
    resp = client_with_auth.get("/api/v1/paper-search/medrxiv", params={"q": "covid", "results_per_page": 3})
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert "items" in data and isinstance(data["items"], list)


def test_medrxiv_raw_details_json(client_with_auth):
    _require_external()
    resp = client_with_auth.get(
        "/api/v1/paper-search/medrxiv/raw/details",
        params={"recent_days": 3, "cursor": 0, "format": "json"},
    )
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        assert "json" in resp.headers.get("content-type", "").lower()
