# Tests for Document Insights Endpoint
#
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
from tldw_Server_API.app.api.v1.schemas.document_insights import GenerateInsightsRequest
from tldw_Server_API.app.api.v1.endpoints.media import document_insights as insights_mod


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    user.username = "testuser"
    return user


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_media_by_id = MagicMock(
        return_value={"id": 1, "type": "pdf", "content": "Sample document content."}
    )
    db.db_path_str = "/tmp/test_media.db"  # nosec B108
    return db


class _StubAdapter:
    def chat(self, _payload):
        return {"ok": True}


@pytest.mark.asyncio
async def test_generate_document_insights_success(mock_user, mock_db):
    app.dependency_overrides[get_request_user] = lambda: mock_user
    app.dependency_overrides[get_media_db_for_user] = lambda: mock_db

    insights_payload = {
        "insights": [
            {
                "category": "summary",
                "title": "Summary",
                "content": "Short summary of the document.",
            }
        ]
    }

    with patch.object(insights_mod, "_get_adapter", return_value=_StubAdapter()), patch.object(
        insights_mod, "resolve_provider_api_key", return_value=("key", None)
    ), patch.object(insights_mod, "provider_requires_api_key", return_value=False), patch.object(
        insights_mod, "_resolve_model", return_value="test-model"
    ), patch.object(
        insights_mod, "extract_response_content", return_value=insights_payload
    ), patch.object(
        insights_mod, "get_cached_response", return_value=None
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/media/1/insights")

    assert response.status_code == 200
    data = response.json()
    assert data["media_id"] == 1
    assert data["insights"][0]["category"] == "summary"
    assert data["model_used"] == "test-model"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_document_insights_cached(mock_user, mock_db):
    app.dependency_overrides[get_request_user] = lambda: mock_user
    app.dependency_overrides[get_media_db_for_user] = lambda: mock_db

    cached_payload = {
        "media_id": 1,
        "insights": [
            {
                "category": "summary",
                "title": "Cached summary",
                "content": "Cached content.",
            }
        ],
        "model_used": "cached-model",
        "cached": False,
    }

    with patch.object(
        insights_mod, "get_cached_response", return_value=("etag", cached_payload)
    ), patch.object(
        insights_mod, "_get_adapter", side_effect=AssertionError("LLM should not be called")
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/media/1/insights")

    assert response.status_code == 200
    data = response.json()
    assert data["cached"] is True
    assert data["insights"][0]["title"] == "Cached summary"

    app.dependency_overrides.clear()


def test_build_insights_cache_key_includes_scope_and_length(mock_db):
    request = GenerateInsightsRequest(max_content_length=1234)
    key = insights_mod._build_insights_cache_key(
        7,
        request,
        user_id="42",
        db_scope=mock_db.db_path_str,
        max_content_length=1234,
    )
    assert "user:42" in key
    assert f"db:{mock_db.db_path_str}" in key
    assert "maxlen:1234" in key
