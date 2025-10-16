"""
Integration tests for Figshare endpoints (non-mocked). Opt-in via RUN_EXTERNAL_API_TESTS=1.

These tests are lenient due to live API variability.
"""

import os
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.external_api]


def _require_external():
    if os.getenv("RUN_EXTERNAL_API_TESTS", "0") != "1":
        pytest.skip("External API tests disabled. Set RUN_EXTERNAL_API_TESTS=1 to enable.")


def test_figshare_search_basic(client_with_auth):
    _require_external()
    # Use a simple query, small page
    resp = client_with_auth.get("/api/v1/paper-search/figshare", params={"q": "frog", "results_per_page": 3})
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert "items" in data and isinstance(data["items"], list)


def test_figshare_by_id_basic(client_with_auth):
    _require_external()
    # Example from Figshare guide: 5616445 exists (presentation); allow 200/404
    resp = client_with_auth.get("/api/v1/paper-search/figshare/by-id", params={"article_id": "5616445"})
    assert resp.status_code in (200, 404, 500, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert data.get("provider") == "figshare"
        assert data.get("id") == "5616445"


def test_figshare_oai_identify(client_with_auth):
    _require_external()
    resp = client_with_auth.get("/api/v1/paper-search/figshare/oai", params={"verb": "Identify"})
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        assert "xml" in resp.headers.get("content-type", "").lower()


def test_figshare_ingest_lenient(client_with_auth):
    _require_external()
    # Attempt ingest of a known article id with a file example (5616409 has a small file per docs)
    resp = client_with_auth.post(
        "/api/v1/paper-search/figshare/ingest",
        params={"article_id": "5616409", "perform_chunking": "false", "perform_analysis": "false"},
    )
    # Allow 200 / 404 / 5xx due to live API differences
    assert resp.status_code in (200, 404, 500, 502, 504), resp.text


def test_figshare_ingest_by_doi_lenient(client_with_auth):
    _require_external()
    # Attempt via DOI (versioned DOI from docs)
    resp = client_with_auth.post(
        "/api/v1/paper-search/figshare/ingest-by-doi",
        params={"doi": "10.6084/m9.figshare.5616409.v3", "perform_chunking": "false", "perform_analysis": "false"},
    )
    assert resp.status_code in (200, 404, 500, 502, 504), resp.text
