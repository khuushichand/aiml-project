import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_paper_search_arxiv_success(monkeypatch):
    from tldw_Server_API.app.main import app

    async def _run():
        def _fake_arxiv(query, author, year, start_index, page_size):
            items = [
                {
                    "id": "1234.5678v1",
                    "title": "Attention Is All You Need",
                    "authors": "Vaswani, A.; Shazeer, N.; et al.",
                    "published_date": "2017-06-01",
                    "abstract": "We propose the Transformer...",
                    "pdf_url": "http://arxiv.org/pdf/1234.5678.pdf",
                },
                {
                    "id": "2345.6789v1",
                    "title": "Transformers in Vision",
                    "authors": "Dosovitskiy, A.; et al.",
                    "published_date": "2020-10-01",
                    "abstract": "We explore ViT...",
                    "pdf_url": "http://arxiv.org/pdf/2345.6789.pdf",
                },
            ]
            return items, 2, None

        from tldw_Server_API.app.core.Third_Party import Arxiv as _Arxiv
        monkeypatch.setattr(_Arxiv, "search_arxiv_custom_api", _fake_arxiv)

        async with AsyncClient(app=app, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/paper-search/arxiv",
                params={"query": "transformer", "page": 1, "results_per_page": 2},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["total_results"] == 2
            assert len(data["items"]) == 2

    await _run()


@pytest.mark.asyncio
async def test_paper_search_biorxiv_success(monkeypatch):
    from tldw_Server_API.app.main import app

    def _fake_bio(q, server, f, t, category, offset, limit):
        items = [
            {
                "doi": "10.1101/2020.01.01.123456",
                "title": "Sample BioRxiv Paper",
                "authors": "Doe, J.; Roe, R.",
                "category": "bioinformatics",
                "date": "2020-01-01",
                "abstract": "This is a test abstract.",
                "server": server,
                "version": 1,
                "url": "https://www.biorxiv.org/content/10.1101/2020.01.01.123456v1",
                "pdf_url": "https://www.biorxiv.org/content/10.1101/2020.01.01.123456v1.full.pdf",
            }
        ]
        return items, 1, None

    from tldw_Server_API.app.core.Third_Party import BioRxiv as _Bio
    monkeypatch.setattr(_Bio, "search_biorxiv", _fake_bio)

    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get(
            "/api/v1/paper-search/biorxiv",
            params={"q": "genomics", "server": "biorxiv", "page": 1, "results_per_page": 1},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total_results"] == 1
        assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_paper_search_semantic_scholar_error_mapping(monkeypatch):
    from tldw_Server_API.app.main import app

    def _fake_s2(query, offset, limit, fos, pub_types, year_range, venue, min_citations, open_access_only, fields_to_return=None):
        return None, "Semantic Scholar API HTTP Error: 429 - Too Many Requests."

    from tldw_Server_API.app.core.Third_Party import Semantic_Scholar as _S2
    monkeypatch.setattr(_S2, "search_papers_semantic_scholar", _fake_s2)

    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get(
            "/api/v1/paper-search/semantic-scholar",
            params={"query": "graph neural networks", "page": 1, "results_per_page": 2},
        )
        # Expect 502 mapped from HTTP error
        assert r.status_code in (429, 502)

