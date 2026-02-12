from __future__ import annotations

import pytest
from fastapi import HTTPException

import tldw_Server_API.app.api.v1.endpoints.web_scraping as web_scraping_endpoints


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_scraping_job_status_preserves_http_exception(monkeypatch):
    class _Service:
        async def get_job_status(self, job_id, current_user):
            raise HTTPException(status_code=404, detail="missing")

    monkeypatch.setattr(
        web_scraping_endpoints,
        "get_web_scraping_service",
        lambda: _Service(),
        raising=True,
    )

    with pytest.raises(HTTPException) as excinfo:
        await web_scraping_endpoints.get_scraping_job_status(
            "job-1",
            current_user=object(),
        )

    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "missing"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancel_scraping_job_preserves_http_exception(monkeypatch):
    class _Service:
        async def cancel_job(self, job_id, current_user):
            raise HTTPException(status_code=403, detail="forbidden")

    monkeypatch.setattr(
        web_scraping_endpoints,
        "get_web_scraping_service",
        lambda: _Service(),
        raising=True,
    )

    with pytest.raises(HTTPException) as excinfo:
        await web_scraping_endpoints.cancel_scraping_job(
            "job-2",
            current_user=object(),
        )

    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "forbidden"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_scraping_job_status_wraps_non_http_exceptions(monkeypatch):
    class _Service:
        async def get_job_status(self, job_id, current_user):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        web_scraping_endpoints,
        "get_web_scraping_service",
        lambda: _Service(),
        raising=True,
    )

    with pytest.raises(HTTPException) as excinfo:
        await web_scraping_endpoints.get_scraping_job_status(
            "job-3",
            current_user=object(),
        )

    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "boom"
