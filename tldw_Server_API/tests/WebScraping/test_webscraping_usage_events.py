import asyncio
import json
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import get_usage_event_logger


pytestmark = pytest.mark.unit


class _DummyLogger:
    def __init__(self):
        self.events = []
    def log_event(self, name, resource_id=None, tags=None, metadata=None):
        self.events.append((name, resource_id, tags, metadata))


@pytest.fixture()
def client_with_ws_overrides(monkeypatch):
    dummy = _DummyLogger()

    async def override_user():
        return User(id=1, username="tester", email=None, is_active=True)

    def override_logger():
        return dummy

    # Stub the internal service call used by endpoint
    import tldw_Server_API.app.api.v1.endpoints.media as media_mod

    async def stub_process_web_scraping_task(**kwargs):
        return {"status": "ok", "results": []}

    monkeypatch.setattr(media_mod, "process_web_scraping_task", stub_process_web_scraping_task)

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_usage_event_logger] = override_logger

    with TestClient(fastapi_app) as client:
        yield client, dummy

    fastapi_app.dependency_overrides.clear()


def test_webscrape_process_usage_event(client_with_ws_overrides):
    client, dummy = client_with_ws_overrides
    payload = {
        "scrape_method": "Individual URLs",
        "url_input": "https://example.com\nhttps://example.org",
        "mode": "ephemeral",
        "max_pages": 5,
        "max_depth": 2
    }
    r = client.post("/api/v1/media/process-web-scraping", json=payload)
    assert r.status_code == 200, r.text
    assert any(e[0] == "webscrape.process" for e in dummy.events)
