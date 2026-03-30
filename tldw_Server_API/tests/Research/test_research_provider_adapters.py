import pytest


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_local_provider_normalizes_retrieved_documents(monkeypatch, tmp_path):
    from tldw_Server_API.app.core.RAG.rag_service.types import DataSource, Document
    from tldw_Server_API.app.core.Research.providers.local import LocalResearchProvider

    captured: dict[str, object] = {}

    class FakeRetriever:
        def __init__(self, db_paths, user_id, **kwargs):
            captured["db_paths"] = db_paths
            captured["user_id"] = user_id

        async def retrieve(self, query, *, sources=None, config=None, **kwargs):
            captured["query"] = query
            captured["sources"] = sources
            captured["config"] = config
            return [
                Document(
                    id="doc_1",
                    content="Important internal evidence about the topic",
                    metadata={"title": "Internal note", "url": "https://internal.local/doc_1"},
                    source=DataSource.MEDIA_DB,
                    score=0.91,
                )
            ]

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Research.providers.local.is_test_mode",
        lambda: False,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Research.providers.local.DatabasePaths.get_media_db_path",
        lambda user_id: tmp_path / f"{user_id}_Media_DB_v2.db",
    )

    provider = LocalResearchProvider(retriever_cls=FakeRetriever)
    records = await provider.search(
        focus_area="background",
        query="hybrid research",
        owner_user_id="1",
        config={"top_k": 4, "sources": ["media_db"]},
    )

    assert captured["user_id"] == "1"
    assert "media_db" in captured["db_paths"]
    assert "hybrid research" in captured["query"]
    assert "background" in captured["query"]
    assert records[0]["id"] == "doc_1"
    assert records[0]["title"] == "Internal note"
    assert records[0]["url"] == "https://internal.local/doc_1"
    assert "Important internal evidence" in records[0]["snippet"]


@pytest.mark.asyncio
async def test_web_provider_normalizes_search_results(monkeypatch):
    from tldw_Server_API.app.core.Research.providers.web import WebResearchProvider

    captured: dict[str, object] = {}

    def fake_search_fn(**kwargs):
        captured.update(kwargs)
        return {
            "results": [
                {
                    "title": "Web result",
                    "url": "https://example.com/article",
                    "snippet": "Web evidence snippet",
                    "rank": 1,
                }
            ]
        }

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Research.providers.web.is_test_mode",
        lambda: False,
    )

    provider = WebResearchProvider(search_fn=fake_search_fn)
    records = await provider.search(
        focus_area="market trends",
        query="hybrid research",
        owner_user_id="1",
        config={"engine": "duckduckgo", "result_count": 3},
    )

    assert captured["search_engine"] == "duckduckgo"
    assert "hybrid research" in captured["search_query"]
    assert "market trends" in captured["search_query"]
    assert records[0]["title"] == "Web result"
    assert records[0]["url"] == "https://example.com/article"
    assert records[0]["provider"] == "duckduckgo"
    assert records[0]["snippet"] == "Web evidence snippet"


@pytest.mark.asyncio
async def test_academic_provider_normalizes_arxiv_pubmed_and_crossref(monkeypatch):
    from tldw_Server_API.app.core.Research.providers.academic import AcademicResearchProvider

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Research.providers.academic.is_test_mode",
        lambda: False,
    )

    def fake_arxiv(query, author, year, start_index, page_size):
        assert author is None
        assert year is None
        assert start_index == 0
        assert page_size == 2
        return (
            [
                {
                    "id": "1234.5678",
                    "title": "Arxiv Paper",
                    "authors": "A. Author",
                    "published_date": "2026-01-01",
                    "abstract": "Arxiv abstract",
                    "pdf_url": "https://arxiv.org/pdf/1234.5678.pdf",
                }
            ],
            1,
            None,
        )

    def fake_pubmed(query, offset=0, limit=10, from_year=None, to_year=None, free_full_text=False):
        assert offset == 0
        assert limit == 2
        return (
            [
                {
                    "pmid": "42",
                    "title": "PubMed Paper",
                    "authors": "B. Author",
                    "journal": "Journal",
                    "pub_date": "2025",
                    "doi": "10.1000/pubmed",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/42/",
                }
            ],
            1,
            None,
        )

    def fake_crossref(query, offset, limit, filter_venue=None, from_year=None, to_year=None):
        assert offset == 0
        assert limit == 2
        return (
            [
                {
                    "id": "10.1000/crossref",
                    "title": "Crossref Paper",
                    "authors": "C. Author",
                    "pub_date": "2024",
                    "doi": "10.1000/crossref",
                    "url": "https://doi.org/10.1000/crossref",
                }
            ],
            1,
            None,
        )

    provider = AcademicResearchProvider(
        arxiv_search_fn=fake_arxiv,
        pubmed_search_fn=fake_pubmed,
        crossref_search_fn=fake_crossref,
    )
    records = await provider.search(
        focus_area="citations",
        query="hybrid research",
        owner_user_id="1",
        config={"providers": ["arxiv", "pubmed", "crossref"], "max_results": 2},
    )

    assert len(records) == 3
    assert {record["provider"] for record in records} == {"arxiv", "pubmed", "crossref"}
    assert {record["title"] for record in records} == {"Arxiv Paper", "PubMed Paper", "Crossref Paper"}


@pytest.mark.asyncio
async def test_providers_return_deterministic_records_in_test_mode():
    from tldw_Server_API.app.core.Research.providers.academic import AcademicResearchProvider
    from tldw_Server_API.app.core.Research.providers.local import LocalResearchProvider
    from tldw_Server_API.app.core.Research.providers.web import WebResearchProvider

    local_records = await LocalResearchProvider().search(
        focus_area="background",
        query="hybrid research",
        owner_user_id="1",
        config={"top_k": 4, "sources": ["media_db"]},
    )
    web_records = await WebResearchProvider().search(
        focus_area="market trends",
        query="hybrid research",
        owner_user_id="1",
        config={"engine": "duckduckgo", "result_count": 3},
    )
    academic_records = await AcademicResearchProvider().search(
        focus_area="citations",
        query="hybrid research",
        owner_user_id="1",
        config={"providers": ["arxiv", "pubmed"], "max_results": 2},
    )

    assert local_records
    assert web_records
    assert academic_records
    assert "title" in local_records[0]
    assert "title" in web_records[0]
    assert "title" in academic_records[0]
