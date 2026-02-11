from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.services import _placeholder_guard


@pytest.mark.unit
def test_placeholder_service_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PLACEHOLDER_SERVICES_ENABLED", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(
        _placeholder_guard,
        "get_settings",
        lambda: SimpleNamespace(PLACEHOLDER_SERVICES_ENABLED=False),
    )

    with pytest.raises(HTTPException) as exc_info:
        _placeholder_guard.ensure_placeholder_service_enabled("XML")

    assert exc_info.value.status_code == 503
    assert "placeholder service is disabled" in str(exc_info.value.detail)


@pytest.mark.unit
def test_placeholder_service_allowed_in_non_production(monkeypatch):
    monkeypatch.setenv("PLACEHOLDER_SERVICES_ENABLED", "1")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(
        _placeholder_guard,
        "get_settings",
        lambda: SimpleNamespace(PLACEHOLDER_SERVICES_ENABLED=True),
    )

    _placeholder_guard.ensure_placeholder_service_enabled("XML")


@pytest.mark.unit
def test_placeholder_service_rejected_in_production(monkeypatch):
    monkeypatch.setenv("PLACEHOLDER_SERVICES_ENABLED", "1")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(
        _placeholder_guard,
        "get_settings",
        lambda: SimpleNamespace(PLACEHOLDER_SERVICES_ENABLED=True),
    )

    with pytest.raises(HTTPException) as exc_info:
        _placeholder_guard.ensure_placeholder_service_enabled("XML")

    assert exc_info.value.status_code == 503
    assert "cannot run in production environments" in str(exc_info.value.detail)
