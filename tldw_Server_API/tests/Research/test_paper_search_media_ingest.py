from __future__ import annotations

import pytest

from tldw_Server_API.app.api.v1.endpoints import paper_search


@pytest.mark.unit
def test_ingest_paper_search_media_uses_media_repository_for_media_db_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _MediaDb:
        backend = object()

    class _FakeRepo:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def add_media_with_keywords(self, **kwargs):
            self.calls.append(kwargs)
            return 31, "paper-uuid", "stored"

    fake_repo = _FakeRepo()
    media_db = _MediaDb()

    monkeypatch.setattr(paper_search, "get_media_repository", lambda db: fake_repo, raising=False)

    result = paper_search._ingest_paper_search_media(
        media_db=media_db,
        url="arxiv:1706.03762",
        title="Attention Is All You Need",
        media_type="pdf",
        content="paper body",
        keywords=["transformers"],
        safe_metadata='{"source":"arxiv"}',
        overwrite=False,
    )

    assert result == (31, "paper-uuid", "stored")
    assert fake_repo.calls == [
        {
            "url": "arxiv:1706.03762",
            "title": "Attention Is All You Need",
            "media_type": "pdf",
            "content": "paper body",
            "keywords": ["transformers"],
            "safe_metadata": '{"source":"arxiv"}',
            "overwrite": False,
        }
    ]
