from __future__ import annotations

import pytest


class FakeMediaDB:
    def __init__(self) -> None:
        self.updated_calls: list[dict[str, object]] = []

    def apply_synced_document_content_update(self, **kwargs):
        self.updated_calls.append(kwargs)
        return {"document_version_number": 2}


@pytest.fixture
def fake_media_db() -> FakeMediaDB:
    return FakeMediaDB()


@pytest.mark.unit
def test_media_sink_updates_existing_binding_as_new_version(fake_media_db):
    from tldw_Server_API.app.core.Ingestion_Sources.sinks.media_sink import apply_media_change

    result = apply_media_change(
        fake_media_db,
        binding={"media_id": 42, "current_version_number": 1},
        change={"event_type": "changed", "relative_path": "docs/a.md", "text": "updated"},
        policy="canonical",
    )

    assert result["action"] == "version_created"
    assert result["media_id"] == 42
    assert fake_media_db.updated_calls[0]["media_id"] == 42


@pytest.mark.unit
def test_media_sink_creates_media_via_repository_api(monkeypatch):
    import tldw_Server_API.app.core.Ingestion_Sources.sinks.media_sink as media_sink

    calls: list[dict[str, object]] = []

    class _FakeMediaRepository:
        def add_media_with_keywords(self, **kwargs):
            calls.append(kwargs)
            return 91, "repo-uuid", "created"

    monkeypatch.setattr(
        media_sink,
        "get_media_repository",
        lambda media_db: _FakeMediaRepository(),
        raising=False,
    )

    result = media_sink.apply_media_change(
        object(),
        binding=None,
        change={"event_type": "created", "relative_path": "docs/new.md", "text": "new body"},
        policy="canonical",
    )

    assert result == {"action": "created", "media_id": 91}
    assert calls == [
        {
            "url": "ingestion://docs/new.md",
            "title": "new.md",
            "media_type": "document",
            "content": "new body",
            "keywords": [],
            "prompt": None,
            "analysis_content": None,
            "safe_metadata": None,
            "overwrite": False,
        }
    ]
