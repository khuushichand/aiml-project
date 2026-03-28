from __future__ import annotations

import json
import os

import pytest

from tldw_Server_API.app.api.v1.endpoints.admin import admin_settings
from tldw_Server_API.app.services import admin_settings_service


pytestmark = pytest.mark.unit


def _setup_env(tmp_path) -> None:
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = "unit-test-api-key"
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'users_test_admin_settings.db'}"


@pytest.mark.asyncio
async def test_risk_weights_persist_to_admin_settings_table(tmp_path) -> None:
    _setup_env(tmp_path)

    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool

    await reset_db_pool()

    updated = await admin_settings_service.set_risk_weights(
        {
            "mfa_adoption": {"weight": 7, "cap": 33},
            "failed_logins": {"weight": 4, "cap": 18},
        }
    )

    assert updated["mfa_adoption"] == {"weight": 7, "cap": 33}
    assert updated["failed_logins"] == {"weight": 4, "cap": 18}

    pool = await get_db_pool()
    row = await pool.fetchone(
        "SELECT value_json FROM admin_settings WHERE setting_key = ?",
        "security_risk_weights",
    )

    assert row is not None
    stored = json.loads(row["value_json"])
    assert stored["mfa_adoption"] == {"weight": 7, "cap": 33}
    assert stored["failed_logins"] == {"weight": 4, "cap": 18}

    fetched = await admin_settings_service.get_risk_weights()
    assert fetched["mfa_adoption"] == {"weight": 7, "cap": 33}
    assert fetched["failed_logins"] == {"weight": 4, "cap": 18}


@pytest.mark.asyncio
async def test_get_security_risk_weights_endpoint_returns_plain_weights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {"mfa_adoption": {"weight": 9, "cap": 44}}

    async def _fake_get() -> dict[str, dict[str, int]]:
        return expected

    monkeypatch.setattr(admin_settings_service, "get_risk_weights", _fake_get)

    response = await admin_settings.get_security_risk_weights(principal=None)  # type: ignore[arg-type]

    assert response.weights == expected


@pytest.mark.asyncio
async def test_set_security_risk_weights_endpoint_returns_plain_weights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {"mfa_adoption": {"weight": 5, "cap": 25}}

    async def _fake_set(weights: dict[str, object]) -> dict[str, dict[str, int]]:
        assert weights == expected
        return expected

    monkeypatch.setattr(admin_settings_service, "set_risk_weights", _fake_set)

    response = await admin_settings.set_security_risk_weights(
        payload=admin_settings.RiskWeightsUpdateRequest(weights=expected),
        principal=None,  # type: ignore[arg-type]
    )

    assert response.weights == expected
