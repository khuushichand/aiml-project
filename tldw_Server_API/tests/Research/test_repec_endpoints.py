import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_repec_by_handle_success(monkeypatch, paper_search_app):
    def _fake_getref(handle):
        return {
            "id": handle,
            "title": "Sample RePEc Working Paper",
            "authors": "Doe, J.; Roe, R.",
            "journal": None,
            "pub_date": "2020-01-01",
            "abstract": "A sample abstract.",
            "doi": None,
            "url": None,
            "pdf_url": "https://example.org/sample.pdf",
            "provider": "repec",
        }, None

    from tldw_Server_API.app.core.Third_Party import RePEc as _Repec
    monkeypatch.setattr(_Repec, "get_ref_by_handle", _fake_getref)

    async with AsyncClient(transport=ASGITransport(app=paper_search_app), base_url="http://test") as client:
        r = await client.get(
            "/api/v1/paper-search/repec/by-handle",
            params={"handle": "RePEc:abc:def:123"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == "RePEc:abc:def:123"
        assert data["provider"] == "repec"


@pytest.mark.asyncio
async def test_repec_by_handle_not_found(monkeypatch, paper_search_app):
    def _fake_getref_nf(handle):
        return None, None

    from tldw_Server_API.app.core.Third_Party import RePEc as _Repec
    monkeypatch.setattr(_Repec, "get_ref_by_handle", _fake_getref_nf)

    async with AsyncClient(transport=ASGITransport(app=paper_search_app), base_url="http://test") as client:
        r = await client.get(
            "/api/v1/paper-search/repec/by-handle",
            params={"handle": "RePEc:missing:handle"},
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_repec_by_handle_not_configured(monkeypatch, paper_search_app):
    def _fake_getref_err(handle):
        return None, "RePEc/IDEAS API not configured. Set REPEC_API_CODE to enable this provider."

    from tldw_Server_API.app.core.Third_Party import RePEc as _Repec
    monkeypatch.setattr(_Repec, "get_ref_by_handle", _fake_getref_err)

    async with AsyncClient(transport=ASGITransport(app=paper_search_app), base_url="http://test") as client:
        r = await client.get(
            "/api/v1/paper-search/repec/by-handle",
            params={"handle": "RePEc:abc:def:123"},
        )
        # Provider not configured should map to 501 via _handle_provider_error
        assert r.status_code == 501


@pytest.mark.asyncio
async def test_repec_citations_success(monkeypatch, paper_search_app):
    def _fake_citec(handle):
        return {
            "handle": handle,
            "cited_by": 42,
            "cites": 10,
            "uri": f"http://citec.repec.org/{handle}",
            "date": "2024-10-01T00:00:00",
        }, None

    from tldw_Server_API.app.core.Third_Party import RePEc as _Repec
    monkeypatch.setattr(_Repec, "get_citations_plain", _fake_citec)

    async with AsyncClient(transport=ASGITransport(app=paper_search_app), base_url="http://test") as client:
        r = await client.get(
            "/api/v1/paper-search/repec/citations",
            params={"handle": "RePEc:abc:def:123"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["cited_by"] == 42
        assert data["handle"].startswith("RePEc:")


@pytest.mark.asyncio
async def test_repec_citations_not_found(monkeypatch, paper_search_app):
    def _fake_citec_nf(handle):
        return None, None

    from tldw_Server_API.app.core.Third_Party import RePEc as _Repec
    monkeypatch.setattr(_Repec, "get_citations_plain", _fake_citec_nf)

    async with AsyncClient(transport=ASGITransport(app=paper_search_app), base_url="http://test") as client:
        r = await client.get(
            "/api/v1/paper-search/repec/citations",
            params={"handle": "RePEc:missing:handle"},
        )
        assert r.status_code == 404
