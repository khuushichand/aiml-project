import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_pmc_oai_list_sets_success(monkeypatch, paper_search_app):
    from tldw_Server_API.app.core.Third_Party import PMC_OAI as _OAI

    def _fake_list_sets(token=None):
        return [
            {"setSpec": "pmc-open", "setName": "PMC Open Access Subset"},
            {"setSpec": "pmc-author-manuscript", "setName": "Author Manuscripts"},
        ], None, None

    monkeypatch.setattr(_OAI, "pmc_oai_list_sets", _fake_list_sets)

    async with AsyncClient(transport=ASGITransport(app=paper_search_app), base_url="http://test") as client:
        r = await client.get("/api/v1/paper-search/pmc-oai/list-sets")
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["setSpec"] == "pmc-open"


@pytest.mark.asyncio
async def test_pmc_oai_list_identifiers_success(monkeypatch, paper_search_app):
    from tldw_Server_API.app.core.Third_Party import PMC_OAI as _OAI

    def _fake_list_identifiers(prefix, f, u, s, token):
        return [
            {"identifier": "oai:pubmedcentral.nih.gov:1", "datestamp": "2024-01-01"},
            {"identifier": "oai:pubmedcentral.nih.gov:2", "datestamp": "2024-01-02"},
        ], "next", None

    monkeypatch.setattr(_OAI, "pmc_oai_list_identifiers", _fake_list_identifiers)

    async with AsyncClient(transport=ASGITransport(app=paper_search_app), base_url="http://test") as client:
        r = await client.get(
            "/api/v1/paper-search/pmc-oai/list-identifiers",
            params={"metadataPrefix": "oai_dc", "from": "2024-01-01"},
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 2
        assert data["resumption_token"] == "next"


@pytest.mark.asyncio
async def test_pmc_oai_get_record_success(monkeypatch, paper_search_app):
    from tldw_Server_API.app.core.Third_Party import PMC_OAI as _OAI

    def _fake_get_record(identifier, metadataPrefix):
        return {
            "header": {"identifier": identifier},
            "metadata": {"title": "Example", "pmid": "123", "pmcid": "456"},
        }, None

    monkeypatch.setattr(_OAI, "pmc_oai_get_record", _fake_get_record)

    async with AsyncClient(transport=ASGITransport(app=paper_search_app), base_url="http://test") as client:
        r = await client.get(
            "/api/v1/paper-search/pmc-oai/get-record",
            params={"identifier": "oai:pubmedcentral.nih.gov:456", "metadataPrefix": "oai_dc"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["header"]["identifier"].endswith(":456")
