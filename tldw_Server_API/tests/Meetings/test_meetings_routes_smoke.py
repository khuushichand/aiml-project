import importlib

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.unit


@pytest.fixture()
def meetings_client(monkeypatch):
    # Force full app router wiring while explicitly enabling meetings route.
    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")
    monkeypatch.setenv("ROUTES_ENABLE", "meetings")

    from tldw_Server_API.app import main as app_main

    importlib.reload(app_main)
    with TestClient(app_main.app) as client:
        yield client


def test_meetings_router_is_mounted(meetings_client):
    resp = meetings_client.get("/api/v1/meetings/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
