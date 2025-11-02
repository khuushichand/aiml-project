"""
Integration tests for BioRxiv advanced endpoints (Reports, Publisher, Pub, Funder) and raw passthroughs.
These tests require network and are skipped unless RUN_EXTERNAL_API_TESTS=1.
"""

import os
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.external_api]


def _require_external():
    if os.getenv("RUN_EXTERNAL_API_TESTS", "0") != "1":
        pytest.skip("External API tests disabled. Set RUN_EXTERNAL_API_TESTS=1 to enable.")


def test_biorxiv_summary_json(client_with_auth):
    _require_external()
    resp = client_with_auth.get("/api/v1/paper-search/biorxiv/reports/summary", params={"interval": "m"})
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, dict)
        assert "items" in data


def test_biorxiv_usage_json(client_with_auth):
    _require_external()
    resp = client_with_auth.get("/api/v1/paper-search/biorxiv/reports/usage", params={"interval": "m"})
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, dict)
        assert "items" in data


def test_biorxiv_pub_recent(client_with_auth):
    _require_external()
    resp = client_with_auth.get(
        "/api/v1/paper-search/biorxiv/pub",
        params={"recent_count": 50, "page": 1, "results_per_page": 5},
    )
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert "items" in data


def test_biorxiv_publisher_prefix(client_with_auth):
    _require_external()
    # Use a sample publisher prefix (may not always return data; accept transient failures)
    resp = client_with_auth.get(
        "/api/v1/paper-search/biorxiv/publisher",
        params={"publisher_prefix": "10.15252", "recent_count": 50, "page": 1, "results_per_page": 5},
    )
    assert resp.status_code in (200, 502, 504), resp.text


def test_biorxiv_funder_recent(client_with_auth):
    _require_external()
    # ROR example from docs: '02mhbdp94' (European Commission)
    resp = client_with_auth.get(
        "/api/v1/paper-search/biorxiv/funder",
        params={
            "server": "biorxiv",
            "ror_id": "02mhbdp94",
            "recent_days": 30,
            "page": 1,
            "results_per_page": 5,
        },
    )
    assert resp.status_code in (200, 502, 504), resp.text


def test_biorxiv_raw_pub_csv(client_with_auth):
    _require_external()
    resp = client_with_auth.get(
        "/api/v1/paper-search/biorxiv/raw/pub",
        params={"recent_count": 10, "format": "csv"},
    )
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        assert "text/csv" in resp.headers.get("content-type", "")


def test_biorxiv_raw_details_xml(client_with_auth):
    _require_external()
    resp = client_with_auth.get(
        "/api/v1/paper-search/biorxiv/raw/details",
        params={"server": "biorxiv", "recent_count": 5, "format": "xml"},
    )
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        assert "xml" in resp.headers.get("content-type", "").lower()
