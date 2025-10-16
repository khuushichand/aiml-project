import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient
try:
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
except Exception as e:  # pragma: no cover - guard for unrelated import failures
    import pytest
    pytest.skip(f"Skipping due to app import failure: {e}", allow_module_level=True)


pytestmark = pytest.mark.asyncio


async def test_websearch_cancelled_via_request_disconnect(monkeypatch):
    # Override auth dependency
    async def fake_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)
    app.dependency_overrides[get_request_user] = fake_user

    # Patch generate_and_search to avoid network
    from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as WSA

    monkeypatch.setattr(
        WSA,
        "generate_and_search",
        lambda q, p: {"web_search_results_dict": {"results": []}, "sub_query_dict": {"main_goal": q, "sub_questions": []}},
    )

    cancel_seen = {"set": False}

    async def fake_analyze_and_aggregate(wsd, sqd, params, cancel_event=None):
        # Wait a moment for cancel_event to be triggered
        if cancel_event is not None:
            try:
                await asyncio.wait_for(cancel_event.wait(), timeout=0.5)
                cancel_seen["set"] = True
            except asyncio.TimeoutError:
                pass
        return {"final_answer": {"text": "ok"}, "relevant_results": {}, "web_search_results_dict": wsd}

    monkeypatch.setattr(WSA, "analyze_and_aggregate", fake_analyze_and_aggregate)

    # Force request.is_disconnected() to return immediately (simulate disconnect)
    from tldw_Server_API.app.api.v1.endpoints import research as research_ep

    async def immediate_disconnect(self):
        return True

    monkeypatch.setattr(research_ep.Request, "is_disconnected", immediate_disconnect)

    headers = {"X-API-KEY": "test-key"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as client:
        resp = await client.post(
            "/api/v1/research/websearch",
            json={
                "query": "q",
                "aggregate": True,
                "engine": "google",
                "content_country": "US",
                "search_lang": "en",
                "output_lang": "en",
                "result_count": 3,
            },
        )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert cancel_seen["set"] is True
