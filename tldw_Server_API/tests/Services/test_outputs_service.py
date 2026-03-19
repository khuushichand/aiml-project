from __future__ import annotations

import json

import pytest

from tldw_Server_API.app.services import outputs_service


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ingest_output_to_media_db_uses_media_repository_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_db = object()

    class _FakeRepo:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def add_media_with_keywords(self, **kwargs):
            self.calls.append(kwargs)
            return 88, "media-uuid", "stored"

    fake_repo = _FakeRepo()
    seen_db: list[object] = []

    def _fake_get_media_repository(db):
        seen_db.append(db)
        return fake_repo

    monkeypatch.setattr(outputs_service, "get_media_repository", _fake_get_media_repository, raising=False)

    media_id = await outputs_service._ingest_output_to_media_db(
        media_db=media_db,
        output_id=17,
        title="Weekly Briefing",
        content="Rendered body",
        output_type="briefing",
        output_format="md",
        storage_path="weekly.md",
        template_id=9,
        run_id=33,
        item_ids=[1, 2],
        tags=["watchlist", "briefing"],
        variant_of=5,
    )

    assert media_id == 88
    assert seen_db == [media_db]
    assert len(fake_repo.calls) == 1
    payload = fake_repo.calls[0]
    assert payload["url"] == "output://17"
    assert payload["title"] == "Weekly Briefing"
    assert payload["media_type"] == "output_briefing"
    assert payload["content"] == "Rendered body"
    assert payload["keywords"] == ["watchlist", "briefing"]
    assert payload["transcription_model"] == "output"
    assert payload["overwrite"] is False
    assert payload["ingestion_date"]
    assert json.loads(str(payload["safe_metadata"])) == {
        "output_id": 17,
        "output_type": "briefing",
        "output_format": "md",
        "storage_path": "weekly.md",
        "template_id": 9,
        "run_id": 33,
        "item_ids": [1, 2],
        "variant_of": 5,
    }
