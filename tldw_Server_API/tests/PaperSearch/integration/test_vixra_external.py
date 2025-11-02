"""
Integration tests for viXra endpoints (non-mocked). Opt-in via RUN_EXTERNAL_API_TESTS=1.

These tests are lenient due to lack of official API and variability.
"""

import os
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.external_api]


def _require_external():
    if os.getenv("RUN_EXTERNAL_API_TESTS", "0") != "1":
        pytest.skip("External API tests disabled. Set RUN_EXTERNAL_API_TESTS=1 to enable.")


def test_vixra_by_id_basic(client_with_auth):
    _require_external()
    # Try a likely-shaped ID; this is a best-effort test
    resp = client_with_auth.get("/api/v1/paper-search/vixra/by-id", params={"vid": "1901.0001"})
    # Allow service errors
    assert resp.status_code in (200, 404, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert "provider" in data and data["provider"] == "vixra"


def test_vixra_ingest_lenient(client_with_auth):
    _require_external()
    # Attempt ingest; permit 200/404/5xx due to variability
    resp = client_with_auth.post("/api/v1/paper-search/vixra/ingest", params={"vid": "1901.0001", "perform_chunking": "false", "perform_analysis": "false"})
    assert resp.status_code in (200, 404, 502, 504), resp.text
