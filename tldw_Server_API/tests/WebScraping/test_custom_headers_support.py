import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient
from tldw_Server_API.app.core.AuthNZ.settings import get_settings

from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import (
    CookieManager,
    DEFAULT_USER_AGENT,
)


pytestmark = pytest.mark.asyncio


async def test_cookie_manager_session_keys_respect_headers(tmp_path):
    manager = CookieManager(storage_path=tmp_path / "cookies.json")

    try:
        default_session = await manager.get_session("https://example.com")
        repeat_default = await manager.get_session("https://example.com")

        assert default_session is repeat_default
        assert default_session.headers["User-Agent"] == DEFAULT_USER_AGENT

        custom_agent = "MyCustomAgent/1.0"
        agent_session = await manager.get_session(
            "https://example.com",
            user_agent=custom_agent,
        )
        agent_session_repeat = await manager.get_session(
            "https://example.com",
            user_agent=custom_agent,
        )

        assert agent_session is agent_session_repeat
        assert agent_session is not default_session
        assert agent_session.headers["User-Agent"] == custom_agent

        header_overrides = {"Authorization": "Bearer token"}
        header_session = await manager.get_session(
            "https://example.com",
            custom_headers=header_overrides,
        )
        header_session_repeat = await manager.get_session(
            "https://example.com",
            custom_headers=header_overrides,
        )

        assert header_session is header_session_repeat
        assert header_session is not default_session
        assert header_session.headers["Authorization"] == "Bearer token"
        assert header_session.headers["User-Agent"] == DEFAULT_USER_AGENT

        headers_with_agent = {"User-Agent": "HeaderAgent/2.0", "X-Test": "yes"}
        header_agent_session = await manager.get_session(
            "https://example.com",
            custom_headers=headers_with_agent,
        )
        header_agent_repeat = await manager.get_session(
            "https://example.com",
            custom_headers=headers_with_agent,
        )

        assert header_agent_session is header_agent_repeat
        assert header_agent_session.headers["User-Agent"] == "HeaderAgent/2.0"
        assert header_agent_session.headers["X-Test"] == "yes"
        assert headers_with_agent["User-Agent"] == "HeaderAgent/2.0"

    finally:
        await manager.close_all()


async def test_process_web_scraping_endpoint_receives_custom_headers():
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
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
