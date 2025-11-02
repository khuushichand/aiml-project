"""
Integration tests for ChemRxiv endpoints (non-mocked). Opt-in via RUN_EXTERNAL_API_TESTS=1.
"""

import os
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.external_api]


def _require_external():
    if os.getenv("RUN_EXTERNAL_API_TESTS", "0") != "1":
        pytest.skip("External API tests disabled. Set RUN_EXTERNAL_API_TESTS=1 to enable.")


def test_chemrxiv_items_basic(client_with_auth):
    _require_external()
    resp = client_with_auth.get("/api/v1/paper-search/chemrxiv/items", params={"term": "catalysis", "limit": 5})
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert "items" in data and isinstance(data["items"], list)


def test_chemrxiv_version(client_with_auth):
    _require_external()
    resp = client_with_auth.get("/api/v1/paper-search/chemrxiv/version")
    assert resp.status_code in (200, 502, 504), resp.text


def test_chemrxiv_oai_identify(client_with_auth):
    _require_external()
    resp = client_with_auth.get("/api/v1/paper-search/chemrxiv/oai", params={"verb": "Identify"})
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        assert "xml" in resp.headers.get("content-type", "").lower()
