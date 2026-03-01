# Tests for Document Insights Endpoint
#
from __future__ import annotations

from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.endpoints.media import document_insights as insights_mod
from tldw_Server_API.app.api.v1.schemas.document_insights import GenerateInsightsRequest
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
from tldw_Server_API.app.main import app


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    user.username = "testuser"
    return user


@pytest.fixture
def mock_db(tmp_path):
    db = MagicMock()
    db.get_media_by_id = MagicMock(
        return_value={"id": 1, "type": "pdf", "content": "Sample document content."}
    )
    db.db_path_str = str(tmp_path / "test_media.db")
    return db


class _StubAdapter:
    """Stub adapter that always returns a preset payload for chat calls."""

    def __init__(self, payload: Optional[Dict[str, Any]] = None) -> None:
        """Initialize with a preset payload, defaulting to `{\"ok\": True}` when omitted."""
        self._payload: Dict[str, Any] = payload if payload is not None else {"ok": True}

    def chat(self, _payload: Dict[str, Any]) -> Dict[str, Any]:
        """Accept a chat payload and return the preset payload configured on this stub."""
        return self._payload


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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_document_insights_parses_fenced_json_with_think(mock_user, mock_db):
    app.dependency_overrides[get_request_user] = lambda: mock_user
    app.dependency_overrides[get_media_db_for_user] = lambda: mock_db

    fenced_payload = (
        "<think>analysis</think>\n"
        "```json\n"
        "{\"insights\":[{\"category\":\"summary\",\"title\":\"T\",\"content\":\"C\"}]}\n"
        "```"
    )

    with patch.object(insights_mod, "_get_adapter", return_value=_StubAdapter()), patch.object(
        insights_mod, "resolve_provider_api_key", return_value=("key", None)
    ), patch.object(insights_mod, "provider_requires_api_key", return_value=False), patch.object(
        insights_mod, "_resolve_model", return_value="test-model"
    ), patch.object(
        insights_mod, "extract_response_content", return_value=fenced_payload
    ), patch.object(
        insights_mod, "get_cached_response", return_value=None
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/media/1/insights")

    assert response.status_code == 200
    payload = response.json()
    assert payload["insights"][0]["category"] == "summary"
    assert payload["insights"][0]["title"] == "T"

    app.dependency_overrides.clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_document_insights_invalid_json_returns_500(mock_user, mock_db):
    app.dependency_overrides[get_request_user] = lambda: mock_user
    app.dependency_overrides[get_media_db_for_user] = lambda: mock_db

    with patch.object(insights_mod, "_get_adapter", return_value=_StubAdapter()), patch.object(
        insights_mod, "resolve_provider_api_key", return_value=("key", None)
    ), patch.object(insights_mod, "provider_requires_api_key", return_value=False), patch.object(
        insights_mod, "_resolve_model", return_value="test-model"
    ), patch.object(
        insights_mod, "extract_response_content", return_value="this is not json"
    ), patch.object(
        insights_mod, "get_cached_response", return_value=None
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/media/1/insights")

    assert response.status_code == 500
    assert "Failed to parse insights" in response.text

    app.dependency_overrides.clear()
