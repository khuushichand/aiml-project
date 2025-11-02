import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch):
    # Enable test-mode auth bypass
    monkeypatch.setenv('EVALS_HEAVY_ADMIN_ONLY', 'false')
    monkeypatch.setenv('TESTING', 'true')


def test_get_rate_limits_shape():
    client = TestClient(app)
    r = client.get("/api/v1/evaluations/rate-limits")
    assert r.status_code == 200
    j = r.json()

    # Top-level keys
    for k in ["tier", "limits", "usage", "remaining", "reset_at"]:
        assert k in j, f"Missing key: {k}"

    # Limits keys
    lim = j["limits"]
    for k in [
        "evaluations_per_minute",
        "evaluations_per_day",
        "tokens_per_day",
        "cost_per_day",
        "cost_per_month",
    ]:
        assert k in lim, f"Missing limits key: {k}"
        assert isinstance(lim[k], int)

    # Usage keys
    usage = j["usage"]
    for k in [
        "evaluations_today",
        "tokens_today",
        "cost_today",
        "cost_month",
    ]:
        assert k in usage, f"Missing usage key: {k}"
        assert isinstance(usage[k], int)

    # Remaining keys
    rem = j["remaining"]
    for k in [
        "daily_evaluations",
        "daily_tokens",
        "daily_cost",
        "monthly_cost",
    ]:
        assert k in rem, f"Missing remaining key: {k}"
        assert isinstance(rem[k], int)
