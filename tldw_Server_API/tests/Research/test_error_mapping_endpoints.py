import pytest
from httpx import AsyncClient, ASGITransport
import sys, types

# Stub heavy modules before importing the full app
sys.modules.setdefault('torch', types.SimpleNamespace(__spec__=None))
sys.modules.setdefault('dill', types.SimpleNamespace(__spec__=None))


@pytest.mark.asyncio
async def test_pubmed_by_id_http_error(monkeypatch):
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.Third_Party import PubMed as _Pub

    def _fake_get(pmid):
        return None, "PubMed API HTTP Error: 429"

    monkeypatch.setattr(_Pub, "get_pubmed_by_id", _fake_get)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/paper-search/pubmed/by-id", params={"pmid": "123"})
        assert r.status_code == 429


@pytest.mark.asyncio
async def test_pubmed_by_id_timeout_maps_504(monkeypatch):
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.Third_Party import PubMed as _Pub

    def _fake_get(pmid):
        return None, "Request to PubMed API timed out."

    monkeypatch.setattr(_Pub, "get_pubmed_by_id", _fake_get)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/paper-search/pubmed/by-id", params={"pmid": "123"})
        assert r.status_code == 504


@pytest.mark.asyncio
async def test_pmc_oai_identify_timeout_maps_504(monkeypatch):
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.Third_Party import PMC_OAI as _OAI

    def _fake_identify():
        return None, "Request to PMC OAI-PMH timed out."

    monkeypatch.setattr(_OAI, "pmc_oai_identify", _fake_identify)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/paper-search/pmc-oai/identify")
        assert r.status_code == 504


@pytest.mark.asyncio
async def test_pmc_oa_identify_timeout_maps_504(monkeypatch):
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.Third_Party import PMC_OA as _OA

    def _fake_identify():
        return None, "Request to PMC OA Web Service timed out."

    monkeypatch.setattr(_OA, "pmc_oa_identify", _fake_identify)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/paper-search/pmc-oa/identify")
        assert r.status_code == 504


@pytest.mark.asyncio
async def test_pmc_oa_fetch_pdf_http_error_mapping(monkeypatch):
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.Third_Party import PMC_OA as _OA

    def _fake_dl(pmcid):
        return None, None, "PMC PDF HTTP Error: 404"

    monkeypatch.setattr(_OA, "download_pmc_pdf", _fake_dl)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/paper-search/pmc-oa/fetch-pdf", params={"pmcid": "PMC123"})
        assert r.status_code == 404
