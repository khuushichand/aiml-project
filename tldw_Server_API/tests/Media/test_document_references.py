# Tests for Document References Endpoint
#
from __future__ import annotations

from unittest.mock import MagicMock, patch

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
