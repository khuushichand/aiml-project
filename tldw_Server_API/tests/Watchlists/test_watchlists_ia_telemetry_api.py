from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.config import API_V1_PREFIX


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_with_user(monkeypatch, tmp_path):
    async def override_user():
        return User(id=932, username="wl-ia-telemetry", email=None, is_active=True)

    base_dir = tmp_path / "watchlists_ia_telemetry"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")

    from tldw_Server_API.app.api.v1.endpoints.watchlists import router as watchlists_router

    app = FastAPI()
    app.include_router(watchlists_router, prefix=f"{API_V1_PREFIX}")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_watchlists_ia_telemetry_ingest_and_summary(client_with_user: TestClient):
    c = client_with_user

    experimental_t0 = c.post(
        "/api/v1/watchlists/telemetry/ia-experiment",
        json={
            "variant": "experimental",
            "session_id": "sess-exp-0001",
            "previous_tab": None,
            "current_tab": "sources",
            "transitions": 0,
            "visited_tabs": ["sources"],
            "first_seen_at": "2026-02-19T18:00:00Z",
            "last_seen_at": "2026-02-19T18:00:00Z",
        },
    )
    assert experimental_t0.status_code == 200, experimental_t0.text
    assert experimental_t0.json().get("accepted") is True

    experimental_t1 = c.post(
        "/api/v1/watchlists/telemetry/ia-experiment",
        json={
            "variant": "experimental",
            "session_id": "sess-exp-0001",
            "previous_tab": "sources",
            "current_tab": "runs",
            "transitions": 1,
            "visited_tabs": ["sources", "runs"],
            "first_seen_at": "2026-02-19T18:00:00Z",
            "last_seen_at": "2026-02-19T18:00:10Z",
        },
    )
    assert experimental_t1.status_code == 200, experimental_t1.text
    assert experimental_t1.json().get("accepted") is True

    baseline_t0 = c.post(
        "/api/v1/watchlists/telemetry/ia-experiment",
        json={
            "variant": "baseline",
            "session_id": "sess-base-0001",
            "previous_tab": None,
            "current_tab": "sources",
            "transitions": 0,
            "visited_tabs": ["sources"],
            "first_seen_at": "2026-02-19T19:00:00Z",
            "last_seen_at": "2026-02-19T19:00:00Z",
        },
    )
    assert baseline_t0.status_code == 200, baseline_t0.text
    assert baseline_t0.json().get("accepted") is True

    summary = c.get("/api/v1/watchlists/telemetry/ia-experiment/summary")
    assert summary.status_code == 200, summary.text
    payload = summary.json()
    by_variant = {
        str(item.get("variant")): item
        for item in payload.get("items", [])
        if isinstance(item, dict)
    }

    experimental = by_variant.get("experimental")
    baseline = by_variant.get("baseline")
    assert experimental is not None
    assert baseline is not None

    assert experimental.get("events") == 2
    assert experimental.get("sessions") == 1
    assert experimental.get("reached_target_sessions") == 1
    assert experimental.get("avg_transitions") == pytest.approx(1.0)
    assert experimental.get("avg_visited_tabs") == pytest.approx(2.0)
    assert experimental.get("avg_session_seconds") == pytest.approx(10.0)

    assert baseline.get("events") == 1
    assert baseline.get("sessions") == 1
    assert baseline.get("reached_target_sessions") == 0
    assert baseline.get("avg_transitions") == pytest.approx(0.0)
    assert baseline.get("avg_visited_tabs") == pytest.approx(1.0)
