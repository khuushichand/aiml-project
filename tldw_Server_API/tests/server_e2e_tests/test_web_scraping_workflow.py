import os
import time
from uuid import uuid4

import pytest


def _api_key() -> str:
    return os.environ.get("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID")


def _auth_headers() -> dict:
    return {"X-API-KEY": _api_key()}


def _require_ok(resp, label: str) -> None:
    if not resp.ok:
        raise AssertionError(f"{label} failed: status={resp.status} body={resp.text()}")


def _assert_scrape_payload(payload: dict) -> None:
    status = payload.get("status")
    assert status in {"ephemeral-ok", "persist-ok"}
    assert payload.get("total_articles") is not None


@pytest.mark.e2e
def test_web_scraping_local_ephemeral_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    scrape_resp = page.request.post(
        "/api/v1/media/process-web-scraping",
        headers=headers,
        json={
            "scrape_method": "Individual URLs",
            "url_input": f"{server_url}/docs",
            "summarize_checkbox": False,
            "mode": "ephemeral",
            "max_pages": 1,
            "max_depth": 1,
            "keywords": f"e2e-local-{suffix}",
        },
    )
    _require_ok(scrape_resp, "submit web scrape (local)")
    scrape_payload = scrape_resp.json()
    _assert_scrape_payload(scrape_payload)

    metrics_resp = page.request.get("/api/v1/metrics/text", headers=headers)
    _require_ok(metrics_resp, "fetch metrics")
    metrics_text = metrics_resp.text()
    assert "scrape_fetch_total" in metrics_text


@pytest.mark.e2e
def test_web_scraping_external_ephemeral_workflow(page, server_url):
    if os.getenv("TLDW_E2E_EXTERNAL_WEB_SCRAPE", "").lower() not in {"1", "true", "yes", "y", "on"}:
        pytest.skip("External web scraping disabled; set TLDW_E2E_EXTERNAL_WEB_SCRAPE=1 to enable.")

    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    scrape_resp = page.request.post(
        "/api/v1/media/process-web-scraping",
        headers=headers,
        json={
            "scrape_method": "Individual URLs",
            "url_input": "https://example.com/",
            "summarize_checkbox": False,
            "mode": "ephemeral",
            "max_pages": 1,
            "max_depth": 1,
            "keywords": f"e2e-external-{suffix}",
        },
    )
    _require_ok(scrape_resp, "submit web scrape (external)")
    scrape_payload = scrape_resp.json()
    _assert_scrape_payload(scrape_payload)

    metrics_resp = page.request.get("/api/v1/metrics/text", headers=headers)
    _require_ok(metrics_resp, "fetch metrics (external)")
    metrics_text = metrics_resp.text()
    assert "scrape_fetch_total" in metrics_text
