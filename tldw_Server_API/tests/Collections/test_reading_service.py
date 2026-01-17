import json
import pytest
import shutil
from pathlib import Path
from urllib.parse import urlencode

from hypothesis import given, settings as hyp_settings, strategies as st

from tldw_Server_API.app.core.Collections.reading_service import ReadingService
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.Web_Scraping.url_utils import normalize_for_crawl

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
        notes="Example reading notes.",
    )

    assert result.item.title == "Reading Demo"
    assert result.item.favorite is True
    assert set(result.item.tags) == {"reading", "demo"}
    assert result.item.notes == "Example reading notes."

    rows, total = service.list_items(page=1, size=10)
    assert total >= 1
    assert any(row.title == "Reading Demo" for row in rows)

    coll_db = CollectionsDatabase.for_user(TEST_USER_ID)
    items, count = coll_db.list_content_items(origin="reading", q="Reading")
    assert count >= 1
    assert any(it.title == "Reading Demo" for it in items)


@pytest.mark.asyncio
async def test_reading_save_merges_tags_on_duplicate(reading_env):
    service = ReadingService(TEST_USER_ID + 10)
    first = await service.save_url(
        url="https://example.org/dupe",
        tags=["alpha"],
        status="saved",
        favorite=False,
        title_override="Dupe Item",
        content_override="Dupe content body.",
    )
    assert set(first.item.tags) == {"alpha"}

    second = await service.save_url(
        url="https://example.org/dupe",
        tags=["beta"],
        status="saved",
        favorite=False,
        title_override="Dupe Item",
        content_override="Dupe content body.",
    )
    assert set(second.item.tags) == {"alpha", "beta"}


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
        notes="Updated notes text.",
    )
    assert updated.status == "read"
    assert updated.favorite is False
    assert updated.tags == ["archive"]
    assert updated.notes == "Updated notes text."

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
    metadata = captured["kwargs"]["metadata"]
    assert metadata["origin"] == "reading"
    assert metadata["item_id"] == captured["kwargs"]["item_id"]
    assert metadata["url"] == "https://example.org/embed"
    assert metadata["canonical_url"] == "https://example.org/embed"
    assert metadata["title"] == "Embed Item"


@pytest.mark.asyncio
async def test_reading_save_dedupes_canonical_url(reading_env, monkeypatch):
    class FakeResponse:
        status_code = 200
        headers = {"content-type": "text/html", "content-length": "512"}
        url = "https://example.org/article"

        def close(self):
            return None

    async def fake_afetch(**_kwargs):
        return FakeResponse()

    async def fake_scrape_article(url: str, custom_cookies=None):
        return {
            "url": url,
            "title": "Example Article",
            "content": "Example content body",
            "summary": "Example summary",
            "author": "Example Author",
            "extraction_successful": True,
        }

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Collections.reading_service.afetch",
        fake_afetch,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib.scrape_article",
        fake_scrape_article,
    )

    service = ReadingService(TEST_USER_ID + 3)
    first = await service.save_url(
        url="https://example.org/article?utm_source=alpha",
        tags=["dedupe"],
    )
    second = await service.save_url(
        url="https://example.org/article?utm_source=beta",
        tags=["dedupe"],
    )

    assert first.item.id == second.item.id
    assert first.created is True
    assert second.created is False


@pytest.mark.asyncio
async def test_reading_save_routes_non_html_to_ingestion(reading_env, monkeypatch):
    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/pdf", "content-length": "1024"}
        url = "https://example.org/document.pdf"

        def close(self):
            return None

    async def fake_afetch(**_kwargs):
        return FakeResponse()

    called = {}

    async def fake_process_document_like_item(*_args, **kwargs):
        called["media_type"] = kwargs.get("media_type")
        return {
            "status": "Success",
            "content": "PDF content body",
            "summary": "PDF summary",
            "metadata": {"title": "PDF Title", "author": "PDF Author"},
            "db_id": 42,
            "media_uuid": "media-uuid-42",
        }

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Collections.reading_service.afetch",
        fake_afetch,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.persistence.process_document_like_item",
        fake_process_document_like_item,
    )

    service = ReadingService(TEST_USER_ID + 4)
    result = await service.save_url(
        url="https://example.org/document.pdf",
        tags=["doc"],
    )

    assert called["media_type"] == "pdf"
    assert result.item.media_id == 42
    assert result.item.title == "PDF Title"
    metadata = json.loads(result.item.metadata_json or "{}")
    assert metadata["media_uuid"] == "media-uuid-42"
    assert metadata["content_type"] == "application/pdf"


@pytest.mark.asyncio
async def test_reading_save_records_fetch_error(reading_env, monkeypatch):
    class FakeResponse:
        status_code = 200
        headers = {"content-type": "text/html", "content-length": "512"}
        url = "https://example.org/bad"

        def close(self):
            return None

    async def fake_afetch(**_kwargs):
        return FakeResponse()

    async def fake_scrape_article(url: str, custom_cookies=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Collections.reading_service.afetch",
        fake_afetch,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib.scrape_article",
        fake_scrape_article,
    )

    service = ReadingService(TEST_USER_ID + 5)
    result = await service.save_url(url="https://example.org/bad")

    assert result.item.title == "https://example.org/bad"
    metadata = json.loads(result.item.metadata_json or "{}")
    assert "fetch_error" in metadata


@pytest.mark.asyncio
async def test_reading_save_sanitizes_html_content(reading_env, monkeypatch):
    monkeypatch.setenv("TEST_MODE", "0")

    captured = {}

    async def fake_enqueue_embeddings_job_for_item(**kwargs):
        captured["content"] = kwargs.get("content")

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Collections.reading_service.enqueue_embeddings_job_for_item",
        fake_enqueue_embeddings_job_for_item,
    )

    service = ReadingService(TEST_USER_ID + 6)
    await service.save_url(
        url="https://example.org/sanitize",
        content_override="<html><body>Hello<script>alert(1)</script></body></html>",
    )

    assert "content" in captured
    assert "alert" not in captured["content"]
    assert "Hello" in captured["content"]


@hyp_settings(max_examples=50)
@given(
    path=st.from_regex(r"[a-zA-Z0-9/_-]{1,30}", fullmatch=True),
    params=st.dictionaries(
        keys=st.from_regex(r"[a-zA-Z0-9_]{1,8}", fullmatch=True),
        values=st.from_regex(r"[a-zA-Z0-9_-]{0,8}", fullmatch=True),
        max_size=5,
    ),
)
def test_normalize_for_crawl_idempotent(path, params):
    base_url = "https://example.org"
    path = f"/{path.lstrip('/')}"
    url = f"{base_url}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    normalized = normalize_for_crawl(url, url)
    assert normalize_for_crawl(normalized, normalized) == normalized
