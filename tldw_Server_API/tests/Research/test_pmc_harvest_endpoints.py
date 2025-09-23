import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_pmc_oai_identify_success(monkeypatch):
    from tldw_Server_API.app.main import app

    def _fake_identify():
        return {"repositoryName": "PMC OAI"}, None

    from tldw_Server_API.app.core.Third_Party import PMC_OAI as _OAI
    monkeypatch.setattr(_OAI, "pmc_oai_identify", _fake_identify)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/paper-search/pmc-oai/identify")
        assert r.status_code == 200
        assert r.json()["info"]["repositoryName"] == "PMC OAI"


@pytest.mark.asyncio
async def test_pmc_oai_list_records_success(monkeypatch):
    from tldw_Server_API.app.main import app

    def _fake_list_records(metadataPrefix, f, u, s, token):
        return [
            {"header": {"identifier": "oai:pubmedcentral.nih.gov:123"}, "metadata": {"title": "X"}},
            {"header": {"identifier": "oai:pubmedcentral.nih.gov:124"}, "metadata": {"title": "Y"}},
        ], "abc123", None

    from tldw_Server_API.app.core.Third_Party import PMC_OAI as _OAI
    monkeypatch.setattr(_OAI, "pmc_oai_list_records", _fake_list_records)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/paper-search/pmc-oai/list-records", params={"metadataPrefix": "oai_dc"})
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 2
        assert data["resumption_token"] == "abc123"


@pytest.mark.asyncio
async def test_pmc_oa_identify_success(monkeypatch):
    from tldw_Server_API.app.main import app

    def _fake_oa_identify():
        return {"repositoryName": "PMC OA"}, None

    from tldw_Server_API.app.core.Third_Party import PMC_OA as _OA
    monkeypatch.setattr(_OA, "pmc_oa_identify", _fake_oa_identify)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/paper-search/pmc-oa/identify")
        assert r.status_code == 200
        assert r.json()["info"]["repositoryName"] == "PMC OA"


@pytest.mark.asyncio
async def test_pmc_oa_query_success(monkeypatch):
    from tldw_Server_API.app.main import app

    def _fake_oa_query(f, u, fmt, token, idp):
        return [
            {"id": "PMC123", "links": [{"format": "pdf", "href": "http://example/pdf"}]}
        ], "nextToken", None

    from tldw_Server_API.app.core.Third_Party import PMC_OA as _OA
    monkeypatch.setattr(_OA, "pmc_oa_query", _fake_oa_query)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/paper-search/pmc-oa/query", params={"from": "2024-01-01", "format": "pdf"})
        assert r.status_code == 200
        data = r.json()
        assert data["items"][0]["id"] == "PMC123"
        assert data["resumption_token"] == "nextToken"


@pytest.mark.asyncio
async def test_pmc_oa_fetch_pdf_success(monkeypatch):
    from tldw_Server_API.app.main import app

    def _fake_download_pdf(pmcid):
        return b"%PDF-1.4\n...", "PMC9999999.pdf", None

    from tldw_Server_API.app.core.Third_Party import PMC_OA as _OA
    monkeypatch.setattr(_OA, "download_pmc_pdf", _fake_download_pdf)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/paper-search/pmc-oa/fetch-pdf", params={"pmcid": "PMC9999999"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert "filename=\"PMC9999999.pdf\"" in r.headers.get("content-disposition", "")

