import pytest
from httpx import AsyncClient, ASGITransport


class _FakeResp:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self._status = status_code
        self.headers = {"Content-Disposition": "attachment; filename=\"file.pdf\""}

    def raise_for_status(self):
        if not (200 <= self._status < 300):
            raise Exception("HTTPError")


class _FakeSession:
    def __init__(self, content: bytes):
        self._content = content

    def get(self, url, timeout=30):
        return _FakeResp(self._content)


@pytest.mark.asyncio
async def test_arxiv_ingest_success(monkeypatch, paper_search_app):
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    import tldw_Server_API.app.api.v1.endpoints.paper_search as paper_search

    class _FakeDB:
        def __init__(self):
            self.calls = []
        def add_media_with_keywords(self, **kwargs):
            self.calls.append(kwargs)
            return 5, "uuid-arxiv", "ok"

    fake_db = _FakeDB()
    paper_search_app.dependency_overrides[get_media_db_for_user] = lambda: fake_db

    # Fake arXiv meta
    from tldw_Server_API.app.core.Third_Party import Arxiv as _Arxiv

    def _fake_fetch_arxiv_xml(paper_id: str):
        return "<feed></feed>"

    def _fake_parse_arxiv_feed(xml_content: bytes):
        return [{
            "id": "1706.03762",
            "title": "Attention Is All You Need",
            "authors": "Vaswani et al.",
            "published_date": "2017-06-01",
            "pdf_url": None,
        }]

    monkeypatch.setattr(_Arxiv, "fetch_arxiv_xml", _fake_fetch_arxiv_xml)
    monkeypatch.setattr(_Arxiv, "parse_arxiv_feed", _fake_parse_arxiv_feed)

    # Fake session returns a PDF
    monkeypatch.setattr(paper_search, "_http_session", lambda: _FakeSession(b"%PDF-1.5\n..."))

    async def _fake_process_pdf_task(**kwargs):
        return {"status": "Success", "content": "arxiv text", "summary": "s", "metadata": {"keywords": ["x"]}}

    import tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib as _PDF
    monkeypatch.setattr(_PDF, "process_pdf_task", _fake_process_pdf_task)

    async with AsyncClient(transport=ASGITransport(app=paper_search_app), base_url="http://test") as client:
        r = await client.post(
            "/api/v1/paper-search/arxiv/ingest",
            params={"arxiv_id": "1706.03762", "perform_analysis": True},
        )
        assert r.status_code == 200
        assert fake_db.calls
        saved = fake_db.calls[0]
        assert saved["url"].startswith("arxiv:")
        assert '"arxiv_id": "1706.03762"' in saved.get("safe_metadata", "")

    paper_search_app.dependency_overrides.pop(get_media_db_for_user, None)


@pytest.mark.asyncio
async def test_s2_ingest_success(monkeypatch, paper_search_app):
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    import tldw_Server_API.app.api.v1.endpoints.paper_search as paper_search

    class _FakeDB:
        def __init__(self):
            self.calls = []
        def add_media_with_keywords(self, **kwargs):
            self.calls.append(kwargs)
            return 7, "uuid-s2", "ok"

    fake_db = _FakeDB()
    paper_search_app.dependency_overrides[get_media_db_for_user] = lambda: fake_db

    from tldw_Server_API.app.core.Third_Party import Semantic_Scholar as _S2

    def _fake_s2_details(paper_id):
        return {
            "paperId": paper_id,
            "title": "Graph Neural Networks",
            "authors": [{"name": "A"}],
            "venue": "NeurIPS",
            "publicationDate": "2020-01-01",
            "externalIds": {"DOI": "10.1000/xyz"},
            "openAccessPdf": {"url": "https://example/pdf", "status": "GREEN"},
        }, None

    monkeypatch.setattr(_S2, "get_paper_details_semantic_scholar", _fake_s2_details)
    monkeypatch.setattr(paper_search, "_http_session", lambda: _FakeSession(b"%PDF-1.5\n..."))

    async def _fake_process_pdf_task(**kwargs):
        return {"status": "Success", "content": "s2 text", "summary": "s"}

    import tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib as _PDF
    monkeypatch.setattr(_PDF, "process_pdf_task", _fake_process_pdf_task)

    async with AsyncClient(transport=ASGITransport(app=paper_search_app), base_url="http://test") as client:
        r = await client.post(
            "/api/v1/paper-search/semantic-scholar/ingest",
            params={"paper_id": "abcdef"},
        )
        assert r.status_code == 200
        assert fake_db.calls
        saved = fake_db.calls[0]
        assert saved["url"].startswith("s2:")
        assert '"s2_paper_id": "abcdef"' in saved.get("safe_metadata", "")

    paper_search_app.dependency_overrides.pop(get_media_db_for_user, None)
