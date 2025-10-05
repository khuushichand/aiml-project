import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_pubmed_ingest_requires_pmcid(monkeypatch, paper_search_app):

    from tldw_Server_API.app.core.Third_Party import PubMed as _Pub

    def _fake_pubmed_by_id(pmid):
        return {
            "pmid": pmid,
            "pmcid": None,  # No OA PMCID available
            "title": "Test",
        }, None

    monkeypatch.setattr(_Pub, "get_pubmed_by_id", _fake_pubmed_by_id)

    async with AsyncClient(transport=ASGITransport(app=paper_search_app), base_url="http://test") as client:
        r = await client.post(
            "/api/v1/paper-search/pubmed/ingest",
            params={"pmid": "123456"},
        )
        assert r.status_code == 400
        assert "No PMC Open Access PMCID" in r.text
