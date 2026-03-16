from __future__ import annotations

import pytest

from tldw_Server_API.app.services import connectors_worker


@pytest.mark.unit
def test_ingest_connector_media_uses_media_repository_for_media_db_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _MediaDb:
        backend = object()

    class _FakeRepo:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def add_media_with_keywords(self, **kwargs):
            self.calls.append(kwargs)
            return 17, "repo-uuid", "ok"

    fake_repo = _FakeRepo()
    media_db = _MediaDb()

    monkeypatch.setattr(connectors_worker, "get_media_repository", lambda db: fake_repo, raising=False)

    result = connectors_worker._ingest_connector_media(
        media_db=media_db,
        url="drive://file-1",
        title="Connector Doc",
        media_type="document",
        content="body",
        keywords=["drive"],
        overwrite=False,
        safe_metadata='{"provider":"drive"}',
    )

    assert result == (17, "repo-uuid", "ok")
    assert fake_repo.calls == [
        {
            "url": "drive://file-1",
            "title": "Connector Doc",
            "media_type": "document",
            "content": "body",
            "keywords": ["drive"],
            "overwrite": False,
            "safe_metadata": '{"provider":"drive"}',
        }
    ]
