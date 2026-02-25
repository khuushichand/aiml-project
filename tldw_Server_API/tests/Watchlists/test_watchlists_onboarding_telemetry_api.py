from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.config import API_V1_PREFIX


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_with_user(monkeypatch, tmp_path):
    async def override_user():
        return User(id=933, username="wl-onboarding-telemetry", email=None, is_active=True)

    base_dir = tmp_path / "watchlists_onboarding_telemetry"
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


@pytest.fixture()
def client_with_mutable_user(monkeypatch, tmp_path):
    user_state: dict[str, int] = {"id": 934}

    async def override_user():
        current_id = int(user_state["id"])
        return User(
            id=current_id,
            username=f"wl-onboarding-telemetry-{current_id}",
            email=None,
            is_active=True,
        )

    base_dir = tmp_path / "watchlists_onboarding_telemetry_mutable"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")

    from tldw_Server_API.app.api.v1.endpoints.watchlists import router as watchlists_router

    app = FastAPI()
    app.include_router(watchlists_router, prefix=f"{API_V1_PREFIX}")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client, user_state
    app.dependency_overrides.clear()


def _iso(base: datetime, seconds: int) -> str:
    return (base + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def _post_event(
    client: TestClient,
    *,
    session_id: str,
    event_type: str,
    event_at: str,
    details: dict[str, object] | None = None,
):
    payload: dict[str, object] = {
        "session_id": session_id,
        "event_type": event_type,
        "event_at": event_at,
    }
    if details is not None:
        payload["details"] = details
    return client.post("/api/v1/watchlists/telemetry/onboarding", json=payload)


def test_watchlists_onboarding_telemetry_ingest_and_summary_contract(client_with_user: TestClient):
    c = client_with_user
    t0 = datetime(2026, 2, 23, 18, 0, 0, tzinfo=timezone.utc)
    session_id = "sess-onboard-0001"

    ingest_open = _post_event(
        c,
        session_id=session_id,
        event_type="quick_setup_opened",
        event_at=_iso(t0, 0),
    )
    assert ingest_open.status_code == 200, ingest_open.text
    assert ingest_open.json().get("accepted") is True

    ingest_complete = _post_event(
        c,
        session_id=session_id,
        event_type="quick_setup_completed",
        event_at=_iso(t0, 30),
        details={"goal": "briefing", "run_now": True, "destination": "outputs"},
    )
    assert ingest_complete.status_code == 200, ingest_complete.text
    assert ingest_complete.json().get("accepted") is True

    ingest_run = _post_event(
        c,
        session_id=session_id,
        event_type="quick_setup_first_run_succeeded",
        event_at=_iso(t0, 60),
        details={"source": "run_notifications", "run_id": 777},
    )
    assert ingest_run.status_code == 200, ingest_run.text
    assert ingest_run.json().get("accepted") is True

    ingest_output = _post_event(
        c,
        session_id=session_id,
        event_type="quick_setup_first_output_succeeded",
        event_at=_iso(t0, 90),
        details={"source": "outputs", "output_id": 991, "format": "md"},
    )
    assert ingest_output.status_code == 200, ingest_output.text
    assert ingest_output.json().get("accepted") is True

    summary = c.get(
        "/api/v1/watchlists/telemetry/onboarding/summary",
        params={"since": _iso(t0, -30), "until": _iso(t0, 180)},
    )
    assert summary.status_code == 200, summary.text
    payload = summary.json()

    assert payload.get("since") == _iso(t0, -30)
    assert payload.get("until") == _iso(t0, 180)

    counters = payload.get("counters", {})
    assert counters.get("quick_setup_opened") == 1
    assert counters.get("quick_setup_completed") == 1
    assert counters.get("quick_setup_first_run_succeeded") == 1
    assert counters.get("quick_setup_first_output_succeeded") == 1
    assert counters.get("sessions") == 1
    assert counters.get("users") == 1

    rates = payload.get("rates", {})
    assert rates.get("setup_completion_rate") == pytest.approx(1.0)
    assert rates.get("first_run_success_rate") == pytest.approx(1.0)
    assert rates.get("first_output_success_rate") == pytest.approx(1.0)

    timings = payload.get("timings", {})
    assert timings.get("median_seconds_to_setup_completion") == pytest.approx(30.0)
    assert timings.get("median_seconds_to_first_run_success") == pytest.approx(60.0)
    assert timings.get("median_seconds_to_first_output_success") == pytest.approx(90.0)


def test_watchlists_onboarding_telemetry_rejects_blank_session_with_diagnostic_code(
    client_with_user: TestClient,
):
    c = client_with_user
    t0 = datetime(2026, 2, 23, 18, 5, 0, tzinfo=timezone.utc)

    rejected = _post_event(
        c,
        session_id="   ",
        event_type="quick_setup_opened",
        event_at=_iso(t0, 0),
    )
    assert rejected.status_code == 200, rejected.text
    payload = rejected.json()
    assert payload.get("accepted") is False
    assert payload.get("code") == "session_id_required"


def test_watchlists_onboarding_telemetry_summary_is_user_scoped(client_with_mutable_user):
    c, user_state = client_with_mutable_user
    t0 = datetime(2026, 2, 23, 18, 10, 0, tzinfo=timezone.utc)

    created = _post_event(
        c,
        session_id="sess-user-a-0001",
        event_type="quick_setup_opened",
        event_at=_iso(t0, 0),
    )
    assert created.status_code == 200, created.text
    assert created.json().get("accepted") is True

    summary_a = c.get("/api/v1/watchlists/telemetry/onboarding/summary")
    assert summary_a.status_code == 200, summary_a.text
    assert summary_a.json().get("counters", {}).get("quick_setup_opened") == 1

    user_state["id"] = 935
    summary_b = c.get("/api/v1/watchlists/telemetry/onboarding/summary")
    assert summary_b.status_code == 200, summary_b.text
    assert summary_b.json().get("counters", {}).get("quick_setup_opened") == 0


def test_watchlists_rc_summary_contract_contains_onboarding_uc2_ia_and_baseline_blocks(
    client_with_user: TestClient,
):
    c = client_with_user
    t0 = datetime(2026, 2, 23, 18, 20, 0, tzinfo=timezone.utc)

    opened = _post_event(
        c,
        session_id="sess-rc-0001",
        event_type="quick_setup_opened",
        event_at=_iso(t0, 0),
    )
    assert opened.status_code == 200, opened.text
    assert opened.json().get("accepted") is True

    completed = _post_event(
        c,
        session_id="sess-rc-0001",
        event_type="quick_setup_completed",
        event_at=_iso(t0, 20),
        details={"goal": "briefing", "run_now": False, "destination": "outputs"},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json().get("accepted") is True

    rc_summary = c.get(
        "/api/v1/watchlists/telemetry/rc-summary",
        params={"since": _iso(t0, -300), "until": _iso(t0, 300)},
    )
    assert rc_summary.status_code == 200, rc_summary.text
    payload = rc_summary.json()

    assert payload.get("since") == _iso(t0, -300)
    assert payload.get("until") == _iso(t0, 300)
    assert isinstance(payload.get("onboarding"), dict)
    assert isinstance(payload.get("uc2_backend"), dict)
    assert isinstance(payload.get("ia_experiment"), dict)
    assert isinstance(payload.get("baseline"), dict)
    assert isinstance(payload.get("thresholds"), list)

    onboarding = payload.get("onboarding", {})
    assert onboarding.get("counters", {}).get("quick_setup_opened") == 1
    assert onboarding.get("counters", {}).get("quick_setup_completed") == 1

    uc2_backend = payload.get("uc2_backend", {})
    assert isinstance(uc2_backend.get("completed_runs"), int)
    assert isinstance(uc2_backend.get("text_output_success_runs"), int)
    assert isinstance(uc2_backend.get("audio_output_success_runs"), int)
    assert isinstance(uc2_backend.get("first_output_success_rate"), (int, float))

    baseline = payload.get("baseline", {})
    assert baseline.get("uc1_f1_first_source_setup_percent") == pytest.approx(92.96)
    assert baseline.get("uc2_f1_pipeline_completion_percent") == pytest.approx(56.72)
    assert baseline.get("uc2_f2_text_output_success_percent") == pytest.approx(0.06)
    assert baseline.get("uc2_f3_audio_output_success_percent") == pytest.approx(0.03)

    thresholds = payload.get("thresholds", [])
    assert len(thresholds) >= 1
    for threshold in thresholds:
        assert threshold.get("status") in {"ok", "potential_breach"}
        assert threshold.get("reporting_only") is True


def test_watchlists_rc_summary_uses_backend_truth_for_uc2_success_not_frontend_claims(
    client_with_user: TestClient,
):
    c = client_with_user
    t0 = datetime(2026, 2, 23, 18, 25, 0, tzinfo=timezone.utc)

    claimed_output_success = _post_event(
        c,
        session_id="sess-claims-only-0001",
        event_type="quick_setup_first_output_succeeded",
        event_at=_iso(t0, 0),
        details={"source": "outputs", "output_id": 42},
    )
    assert claimed_output_success.status_code == 200, claimed_output_success.text
    assert claimed_output_success.json().get("accepted") is True

    rc_summary = c.get("/api/v1/watchlists/telemetry/rc-summary")
    assert rc_summary.status_code == 200, rc_summary.text
    payload = rc_summary.json()

    uc2_backend = payload.get("uc2_backend", {})
    assert uc2_backend.get("completed_runs") == 0
    assert uc2_backend.get("text_output_success_runs") == 0
    assert uc2_backend.get("audio_output_success_runs") == 0
    assert uc2_backend.get("first_output_success_rate") == pytest.approx(0.0)
