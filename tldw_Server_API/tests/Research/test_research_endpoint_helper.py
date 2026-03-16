from __future__ import annotations

import pytest

from tldw_Server_API.app.api.v1.endpoints import research


@pytest.mark.unit
def test_process_and_ingest_arxiv_paper_uses_media_repository_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeDb:
        pass

    class _FakeRepo:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def add_media_with_keywords(self, **kwargs):
            self.calls.append(kwargs)
            return 51, "arxiv-uuid", "stored"

    fake_repo = _FakeRepo()

    monkeypatch.setattr(research, "fetch_arxiv_xml", lambda paper_id: f"<xml>{paper_id}</xml>")
    monkeypatch.setattr(
        research,
        "convert_xml_to_markdown",
        lambda xml: ("# Paper\n\nBody", "Paper Title", ["Ada Lovelace", "Alan Turing"], ["cs.AI", "cs.IR"]),
    )
    monkeypatch.setattr(research, "create_media_database", lambda **kwargs: _FakeDb())
    monkeypatch.setattr(research, "get_media_repository", lambda db: fake_repo, raising=False)

    message = research.process_and_ingest_arxiv_paper("1234.5678", "ml,rag")

    assert message == "arXiv paper 'Paper Title' ingested successfully."
    assert len(fake_repo.calls) == 1
    payload = dict(fake_repo.calls[0])
    ingestion_date = payload.pop("ingestion_date")
    assert payload == {
        "url": "https://arxiv.org/abs/1234.5678",
        "title": "Paper Title",
        "media_type": "document",
        "content": "# Paper\n\nBody",
        "keywords": ["arxiv", "cs.AI", "cs.IR", "ml", "rag"],
        "prompt": "No prompt for arXiv papers",
        "analysis_content": "arXiv paper ingested from XML",
        "transcription_model": "None",
        "author": "Ada Lovelace, Alan Turing",
    }
    assert isinstance(ingestion_date, str)
