# Tests for Document References Endpoint
#
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
from tldw_Server_API.app.api.v1.endpoints.media import document_references as refs_mod
from tldw_Server_API.app.api.v1.schemas.document_references import ReferenceEntry


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    user.username = "testuser"
    return user


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.db_path_str = "/tmp/test_media.db"
    return db


@pytest.mark.asyncio
async def test_references_endpoint_extracts_basic(mock_user, mock_db):
    content = (
        "Intro text\\n"
        "References\\n"
        "[1] Smith, J. (2020). Example Paper. https://doi.org/10.1234/abcd\\n"
        "[2] Doe, A. (2019). Another Paper. arXiv:2101.12345\\n"
    )
    mock_db.get_media_by_id = MagicMock(return_value={"id": 1, "content": content})

    app.dependency_overrides[get_request_user] = lambda: mock_user
    app.dependency_overrides[get_media_db_for_user] = lambda: mock_db

    with patch.object(refs_mod, "get_cached_response", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/media/1/references?enrich=false")

    assert response.status_code == 200
    data = response.json()
    assert data["has_references"] is True
    assert len(data["references"]) == 2
    assert data["references"][0]["doi"] == "10.1234/abcd"
    assert data["references"][1]["arxiv_id"] == "2101.12345"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_references_endpoint_cache_hit(mock_user, mock_db):
    cached_payload = {
        "media_id": 1,
        "has_references": True,
        "references": [
            {"raw_text": "Cached ref", "title": "Cached Title"}
        ],
        "enrichment_source": None,
    }
    mock_db.get_media_by_id = MagicMock(side_effect=AssertionError("DB should not be called"))

    app.dependency_overrides[get_request_user] = lambda: mock_user
    app.dependency_overrides[get_media_db_for_user] = lambda: mock_db

    with patch.object(refs_mod, "get_cached_response", return_value=("etag", cached_payload)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/media/1/references")

    assert response.status_code == 200
    data = response.json()
    assert data["references"][0]["title"] == "Cached Title"

    app.dependency_overrides.clear()


def test_apply_crossref_data_sets_fields():
    ref = ReferenceEntry(raw_text="raw")
    item = {
        "title": "Crossref Title",
        "authors": "A. Author",
        "journal": "Journal of Tests",
        "pub_date": "2022-01-01",
        "doi": "10.5555/xyz",
        "url": "https://doi.org/10.5555/xyz",
        "pdf_url": "https://example.com/paper.pdf",
    }
    updated = refs_mod._apply_crossref_data(ref, item)
    assert updated.title == "Crossref Title"
    assert updated.authors == "A. Author"
    assert updated.venue == "Journal of Tests"
    assert updated.year == 2022
    assert updated.doi == "10.5555/xyz"
    assert updated.open_access_pdf == "https://example.com/paper.pdf"


def test_apply_arxiv_data_sets_fields():
    ref = ReferenceEntry(raw_text="raw")
    item = {
        "id": "2101.12345",
        "title": "arXiv Title",
        "authors": "A. Author",
        "published_date": "2021-02-03",
        "pdf_url": "https://arxiv.org/pdf/2101.12345.pdf",
    }
    updated = refs_mod._apply_arxiv_data(ref, item)
    assert updated.title == "arXiv Title"
    assert updated.authors == "A. Author"
    assert updated.year == 2021
    assert updated.arxiv_id == "2101.12345"
    assert updated.url == "https://arxiv.org/abs/2101.12345"
    assert updated.open_access_pdf == "https://arxiv.org/pdf/2101.12345.pdf"


def test_build_references_cache_key_includes_scope(mock_db):
    key = refs_mod._build_references_cache_key(
        7,
        enrich=True,
        user_id="42",
        db_scope=mock_db.db_path_str,
    )
    assert "user:42" in key
    assert f"db:{mock_db.db_path_str}" in key
    assert "enrich" in key


def test_build_references_cache_key_includes_reference_index(mock_db):
    key = refs_mod._build_references_cache_key(
        7,
        enrich=True,
        user_id="42",
        db_scope=mock_db.db_path_str,
        reference_index=3,
    )
    assert ":idx:3" in key


@pytest.mark.asyncio
async def test_references_endpoint_enriches_only_requested_reference_index(mock_user, mock_db):
    content = (
        "Intro text\\n"
        "References\\n"
        "[1] Smith, J. (2020). Example Paper. https://doi.org/10.1234/abcd\\n"
        "[2] Doe, A. (2019). Another Paper. arXiv:2101.12345\\n"
    )
    mock_db.get_media_by_id = MagicMock(return_value={"id": 1, "content": content})

    async def enrich_semantic(refs: list[ReferenceEntry]):
        assert len(refs) == 1
        out = [r.model_copy() for r in refs]
        out[0].citation_count = 77
        return out, True

    app.dependency_overrides[get_request_user] = lambda: mock_user
    app.dependency_overrides[get_media_db_for_user] = lambda: mock_db

    with patch.object(refs_mod, "get_cached_response", return_value=None), \
        patch.object(refs_mod, "_is_provider_cooldown", return_value=False), \
        patch.object(
            refs_mod,
            "_enrich_with_semantic_scholar",
            new=AsyncMock(side_effect=enrich_semantic),
        ), \
        patch.object(
            refs_mod,
            "_enrich_with_crossref",
            new=AsyncMock(side_effect=lambda refs: (refs, False)),
        ), \
        patch.object(
            refs_mod,
            "_enrich_with_arxiv",
            new=AsyncMock(side_effect=lambda refs: (refs, False)),
        ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/media/1/references?enrich=true&reference_index=1"
            )

    assert response.status_code == 200
    data = response.json()
    assert data["references"][0].get("citation_count") is None
    assert data["references"][1]["citation_count"] == 77
    assert "semantic_scholar" in (data.get("enrichment_source") or "")

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_references_endpoint_reference_index_out_of_range_returns_400(mock_user, mock_db):
    content = (
        "References\\n"
        "[1] Smith, J. (2020). Example Paper. https://doi.org/10.1234/abcd\\n"
    )
    mock_db.get_media_by_id = MagicMock(return_value={"id": 1, "content": content})
    app.dependency_overrides[get_request_user] = lambda: mock_user
    app.dependency_overrides[get_media_db_for_user] = lambda: mock_db

    with patch.object(refs_mod, "get_cached_response", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/media/1/references?enrich=true&reference_index=5"
            )

    assert response.status_code == 400
    assert response.json()["detail"] == "reference_index out of range"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_references_endpoint_skips_enrichment_when_all_providers_in_cooldown(mock_user, mock_db):
    content = (
        "References\\n"
        "[1] Smith, J. (2020). Example Paper. https://doi.org/10.1234/abcd\\n"
    )
    mock_db.get_media_by_id = MagicMock(return_value={"id": 1, "content": content})
    app.dependency_overrides[get_request_user] = lambda: mock_user
    app.dependency_overrides[get_media_db_for_user] = lambda: mock_db

    semantic = AsyncMock(side_effect=lambda refs: (refs, True))
    crossref = AsyncMock(side_effect=lambda refs: (refs, True))
    arxiv = AsyncMock(side_effect=lambda refs: (refs, True))

    with patch.object(refs_mod, "get_cached_response", return_value=None), \
        patch.object(refs_mod, "_is_provider_cooldown", return_value=True), \
        patch.object(refs_mod, "_enrich_with_semantic_scholar", new=semantic), \
        patch.object(refs_mod, "_enrich_with_crossref", new=crossref), \
        patch.object(refs_mod, "_enrich_with_arxiv", new=arxiv):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/media/1/references?enrich=true")

    assert response.status_code == 200
    semantic.assert_not_awaited()
    crossref.assert_not_awaited()
    arxiv.assert_not_awaited()

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_enrich_with_semantic_scholar_caps_external_calls_at_five():
    refs = [
        ReferenceEntry(raw_text=f"Ref {i}", doi=f"10.1234/{i}")
        for i in range(7)
    ]
    call_count = 0

    async def fake_to_thread(_func, *_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        return {"paperId": "p1", "citationCount": 1, "title": "Paper"}, None

    with patch.object(refs_mod, "_get_cached_external", return_value=None), \
        patch.object(refs_mod, "_set_cached_external", return_value=None), \
        patch.object(refs_mod.asyncio, "to_thread", side_effect=fake_to_thread):
        enriched, performed = await refs_mod._enrich_with_semantic_scholar(refs)

    assert performed is True
    assert len(enriched) == 7
    assert call_count == 5


@pytest.mark.asyncio
async def test_enrich_with_crossref_sets_cooldown_on_rate_limit():
    refs = [
        ReferenceEntry(raw_text=f"Ref {i}", doi=f"10.1234/{i}")
        for i in range(3)
    ]
    call_count = 0

    async def fake_to_thread(_func, *_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        return None, "429 Too Many Requests"

    with patch.object(refs_mod, "_get_cached_external", return_value=None), \
        patch.object(refs_mod, "_set_cached_external", return_value=None), \
        patch.object(refs_mod, "_set_provider_cooldown") as set_cooldown, \
        patch.object(refs_mod.asyncio, "to_thread", side_effect=fake_to_thread):
        enriched, performed = await refs_mod._enrich_with_crossref(refs)

    assert performed is False
    assert len(enriched) == 3
    assert call_count == 1
    set_cooldown.assert_called_once_with("crossref")
