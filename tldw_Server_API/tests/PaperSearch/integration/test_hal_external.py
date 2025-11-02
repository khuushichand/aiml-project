"""
Integration tests for HAL endpoints (non-mocked). Opt-in via RUN_EXTERNAL_API_TESTS=1.
"""

import os
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.external_api]


def _require_external():
    if os.getenv("RUN_EXTERNAL_API_TESTS", "0") != "1":
        pytest.skip("External API tests disabled. Set RUN_EXTERNAL_API_TESTS=1 to enable.")


def test_hal_search_basic(client_with_auth):
    _require_external()
    resp = client_with_auth.get(
        "/api/v1/paper-search/hal",
        params={"q": "title_t:japon", "results_per_page": 3},
    )
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert "items" in data and isinstance(data["items"], list)


def test_hal_raw_xml(client_with_auth):
    _require_external()
    resp = client_with_auth.get(
        "/api/v1/paper-search/hal/raw",
        params={"q": "*:*", "wt": "xml", "rows": 1},
    )
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        assert "xml" in resp.headers.get("content-type", "").lower()


def test_hal_by_id_roundtrip(client_with_auth):
    _require_external()
    # First search to get at least one docid
    s = client_with_auth.get("/api/v1/paper-search/hal", params={"q": "*:*", "results_per_page": 1})
    assert s.status_code in (200, 502, 504), s.text
    if s.status_code != 200:
        return
    data = s.json()
    items = data.get("items") or []
    if not items:
        return
    docid = items[0].get("id")
    if not docid:
        return
    r = client_with_auth.get("/api/v1/paper-search/hal/by-id", params={"docid": docid})
    assert r.status_code in (200, 404, 502, 504), r.text
    if r.status_code == 200:
        j = r.json()
        assert j.get("provider") == "hal"


def test_hal_ingest_lenient(client_with_auth):
    _require_external()
    # Attempt ingest from first item; allow lenient status codes
    s = client_with_auth.get("/api/v1/paper-search/hal", params={"q": "*:*", "results_per_page": 1})
    assert s.status_code in (200, 502, 504), s.text
    if s.status_code != 200:
        return
    data = s.json()
    items = data.get("items") or []
    if not items:
        return
    docid = items[0].get("id")
    if not docid:
        return
    resp = client_with_auth.post(
        "/api/v1/paper-search/hal/ingest",
        params={"docid": docid, "perform_chunking": "false", "perform_analysis": "false"},
    )
    assert resp.status_code in (200, 404, 500, 502, 504), resp.text
