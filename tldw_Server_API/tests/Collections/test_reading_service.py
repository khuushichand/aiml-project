import pytest
import shutil
from pathlib import Path

from tldw_Server_API.app.core.Collections.reading_service import ReadingService
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.config import settings

TEST_USER_ID = 456


@pytest.fixture()
def reading_env(monkeypatch):
    base_dir = Path.cwd() / "Databases" / "test_reading_service"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "1")
    try:
        yield base_dir
    finally:
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


@pytest.mark.asyncio
async def test_reading_save_and_list(reading_env):
    service = ReadingService(TEST_USER_ID)
    result = await service.save_url(
        url="https://example.org/article",
        tags=["reading", "demo"],
        status="saved",
        favorite=True,
        title_override="Reading Demo",
        summary_override="Example reading summary.",
        content_override="Example reading content body.",
    )

    assert result.item.title == "Reading Demo"
    assert result.item.favorite is True
    assert set(result.item.tags) == {"reading", "demo"}

    rows, total = service.list_items(page=1, size=10)
    assert total >= 1
    assert any(row.title == "Reading Demo" for row in rows)

    coll_db = CollectionsDatabase.for_user(TEST_USER_ID)
    items, count = coll_db.list_content_items(origin="reading", q="Reading")
    assert count >= 1
    assert any(it.title == "Reading Demo" for it in items)


@pytest.mark.asyncio
async def test_reading_update_status_and_filters(reading_env):
    service = ReadingService(TEST_USER_ID + 1)
    save_result = await service.save_url(
        url="https://example.org/update",
        tags=["initial"],
        status="saved",
        favorite=False,
        title_override="Update Item",
        content_override="Initial content body",
    )

    updated = service.update_item(
        item_id=save_result.item.id,
        status="read",
        favorite=False,
        tags=["archive"],
    )
    assert updated.status == "read"
    assert updated.favorite is False
    assert updated.tags == ["archive"]

    rows, total = service.list_items(status=["read"], page=1, size=10)
    assert total >= 1
    assert any(row.id == save_result.item.id for row in rows)


@pytest.mark.asyncio
async def test_reading_save_triggers_embedding(reading_env, monkeypatch):
    monkeypatch.setenv("TEST_MODE", "0")

    captured = {}

    async def fake_enqueue_embeddings_job_for_item(**kwargs):
        captured["kwargs"] = kwargs

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Collections.reading_service.enqueue_embeddings_job_for_item",
        fake_enqueue_embeddings_job_for_item,
    )

    service = ReadingService(TEST_USER_ID + 2)
    await service.save_url(
        url="https://example.org/embed",
        tags=["embed"],
        status="saved",
        favorite=False,
        title_override="Embed Item",
        content_override="Embedding content body",
    )

    assert "kwargs" in captured
    assert captured["kwargs"]["user_id"] == TEST_USER_ID + 2
    assert "Embedding content body" in captured["kwargs"]["content"]
    assert captured["kwargs"]["metadata"]["origin"] == "reading"
