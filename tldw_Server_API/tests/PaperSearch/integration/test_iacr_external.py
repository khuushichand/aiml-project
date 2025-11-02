"""
Integration tests for IACR conference endpoint. Opt-in via RUN_EXTERNAL_API_TESTS=1.
"""

import os
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.external_api]


def _require_external():
    if os.getenv("RUN_EXTERNAL_API_TESTS", "0") != "1":
        pytest.skip("External API tests disabled. Set RUN_EXTERNAL_API_TESTS=1 to enable.")


def test_iacr_conf_basic(client_with_auth):
    _require_external()
    resp = client_with_auth.get(
        "/api/v1/paper-search/iacr/conf",
        params={"venue": "crypto", "year": 2017},
    )
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, dict)
        assert "data" in data


def test_iacr_conf_raw(client_with_auth):
    _require_external()
    resp = client_with_auth.get(
        "/api/v1/paper-search/iacr/conf/raw",
        params={"venue": "crypto", "year": 2017},
    )
    assert resp.status_code in (200, 502, 504), resp.text
    if resp.status_code == 200:
        assert "json" in resp.headers.get("content-type", "").lower()
