import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient
from tldw_Server_API.app.core.AuthNZ.settings import get_settings

from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import CookieManager


pytestmark = pytest.mark.asyncio


async def test_cookie_manager_stores_and_returns_cookies(tmp_path):
    manager = CookieManager(storage_path=tmp_path / "cookies.json")
    manager.add_cookies(
        "example.com",
        [{"name": "foo", "value": "bar"}, {"name": "session", "value": "trace-id"}],
    )
    cookies = manager.get_cookies("https://example.com/some/path")
    assert cookies == [{"name": "foo", "value": "bar"}, {"name": "session", "value": "trace-id"}]
    assert manager.get_cookies("https://other.example") is None


async def test_process_web_scraping_endpoint_receives_custom_headers():
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
    from tldw_Server_API.app.main import app

    fake_db = MagicMock(spec=MediaDatabase)
    app.dependency_overrides[get_media_db_for_user] = lambda: fake_db

    mocked_result = {"status": "success", "message": "ok", "count": 0, "results": []}
    payload = {
        "scrape_method": "Individual URLs",
        "url_input": "https://example.com/article",
        "max_pages": 5,
        "max_depth": 1,
        "summarize_checkbox": False,
        "mode": "ephemeral",
        "user_agent": "IntegrationAgent/1.0",
        "custom_headers": {"X-Test": "true"},
    }

    response = None
    mock_process = None

    try:
        with patch(
            "tldw_Server_API.app.api.v1.endpoints.media.process_web_scraping_task",
            new=AsyncMock(return_value=mocked_result),
        ) as patched_process:
            mock_process = patched_process
            headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test", headers=headers
            ) as client:
                response = await client.post(
                    "/api/v1/media/process-web-scraping",
                    json=payload,
                )

    finally:
        app.dependency_overrides.clear()

    assert response is not None
    assert response.status_code == 200
    assert response.json() == mocked_result

    assert mock_process is not None
    assert mock_process.await_count == 1
    call_kwargs = mock_process.await_args.kwargs
    assert call_kwargs["user_agent"] == payload["user_agent"]
    assert call_kwargs["custom_headers"] == payload["custom_headers"]
    assert call_kwargs["mode"] == "ephemeral"
