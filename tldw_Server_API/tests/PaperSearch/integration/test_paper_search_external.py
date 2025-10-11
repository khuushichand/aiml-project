"""
Integration tests for new Paper Search providers using real external APIs (no mocks).
These tests are skipped by default; enable by setting RUN_EXTERNAL_API_TESTS=1.
"""

import os
import pytest


pytestmark = [pytest.mark.integration, pytest.mark.external_api]


def _require_env_or_skip(var_name: str):
    if not os.getenv(var_name):
        pytest.skip(f"Environment variable {var_name} not set; skipping.")


def _require_external():
    if os.getenv("RUN_EXTERNAL_API_TESTS", "0") != "1":
        pytest.skip("External API tests disabled. Set RUN_EXTERNAL_API_TESTS=1 to enable.")


def test_acm_search_openalex_integration(client_with_auth):
    _require_external()
    client = client_with_auth
    resp = client.get(
        "/api/v1/paper-search/acm",
        params={
            "q": "transformer",
            "page": 1,
            "results_per_page": 3,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, dict)
    assert "items" in data and isinstance(data["items"], list)
    # If items exist, basic shape checks
    if data["items"]:
        it = data["items"][0]
        assert "title" in it
        assert it.get("provider") == "openalex"


def test_wiley_search_openalex_integration(client_with_auth):
    _require_external()
    client = client_with_auth
    resp = client.get(
        "/api/v1/paper-search/wiley",
        params={
            "q": "bioinformatics",
            "page": 1,
            "results_per_page": 3,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data and isinstance(data["items"], list)
    if data["items"]:
        it = data["items"][0]
        assert "title" in it
        assert it.get("provider") == "openalex"


def test_crossref_by_doi_lookup(client_with_auth):
    _require_external()
    client = client_with_auth
    doi = "10.1038/nature14539"  # Nature AlphaGo paper
    resp = client.get("/api/v1/paper-search/acm/by-doi", params={"doi": doi})
    assert resp.status_code in (200, 404, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        got = (data.get("doi") or "").lower()
        assert got == doi.lower()


def test_ieee_returns_not_configured_without_key(client_with_auth):
    client = client_with_auth
    # Ensure key not set
    if os.getenv("IEEE_API_KEY"):
        pytest.skip("IEEE_API_KEY present; this test targets missing-key behavior.")
    resp = client.get("/api/v1/paper-search/ieee", params={"q": "neural", "page": 1, "results_per_page": 1})
    assert resp.status_code == 501


def test_springer_returns_not_configured_without_key(client_with_auth):
    client = client_with_auth
    if os.getenv("SPRINGER_NATURE_API_KEY"):
        pytest.skip("SPRINGER_NATURE_API_KEY present; this test targets missing-key behavior.")
    resp = client.get("/api/v1/paper-search/springer", params={"q": "graph", "page": 1, "results_per_page": 1})
    assert resp.status_code == 501


def test_scopus_returns_not_configured_without_key(client_with_auth):
    client = client_with_auth
    if os.getenv("ELSEVIER_API_KEY"):
        pytest.skip("ELSEVIER_API_KEY present; this test targets missing-key behavior.")
    resp = client.get("/api/v1/paper-search/scopus", params={"q": "vision", "page": 1, "results_per_page": 1})
    assert resp.status_code == 501


@pytest.mark.slow
def test_oa_ingest_by_doi_when_configured(client_with_auth):
    _require_external()
    _require_env_or_skip("UNPAYWALL_EMAIL")
    client = client_with_auth
    # Use an arXiv DOI that should be OA
    doi = "10.48550/arXiv.1706.03762"
    resp = client.post(
        "/api/v1/paper-search/ingest/by-doi",
        params={
            "doi": doi,
            "perform_chunking": False,
            "perform_analysis": False,
        },
    )
    # Allow 200 success or 404 if OA not resolved; treat provider/network failures as acceptable skips
    assert resp.status_code in (200, 404, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert "media_id" in data and "source_pdf" in data


@pytest.mark.requires_api_key
def test_ieee_search_with_key_integration(client_with_auth):
    _require_external()
    _require_env_or_skip("IEEE_API_KEY")
    client = client_with_auth
    resp = client.get(
        "/api/v1/paper-search/ieee",
        params={"q": "neural", "page": 1, "results_per_page": 3},
    )
    # Accept 200 success; surface informative statuses otherwise
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, dict)
        assert "items" in data and isinstance(data["items"], list)


@pytest.mark.requires_api_key
def test_springer_search_with_key_integration(client_with_auth):
    _require_external()
    _require_env_or_skip("SPRINGER_NATURE_API_KEY")
    client = client_with_auth
    resp = client.get(
        "/api/v1/paper-search/springer",
        params={"q": "graph", "page": 1, "results_per_page": 3},
    )
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, dict)
        assert "items" in data and isinstance(data["items"], list)


@pytest.mark.requires_api_key
def test_scopus_search_with_key_integration(client_with_auth):
    _require_external()
    _require_env_or_skip("ELSEVIER_API_KEY")
    client = client_with_auth
    resp = client.get(
        "/api/v1/paper-search/scopus",
        params={"q": "vision", "page": 1, "results_per_page": 3},
    )
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, dict)
        assert "items" in data and isinstance(data["items"], list)
