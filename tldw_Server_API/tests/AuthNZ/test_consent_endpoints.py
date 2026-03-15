"""
Tests for consent management endpoints.

Verifies that:
- GET /consent/preferences returns user consents
- POST /consent/preferences/{purpose} grants consent
- DELETE /consent/preferences/{purpose} withdraws consent
- Proper error handling for missing consent
"""
from __future__ import annotations

import os

import pytest

from tldw_Server_API.app.api.v1.endpoints.consent import (
    _get_consent_db_path,
    _get_consent_manager,
    _resolve_user_id,
)
from tldw_Server_API.app.core.AuthNZ.consent_manager import ConsentManager
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal

from fastapi import HTTPException


@pytest.fixture()
def consent_db(tmp_path, monkeypatch):
    """Set up a temporary consent database."""
    db_path = str(tmp_path / "consent_test.db")
    monkeypatch.setenv("CONSENT_DB_PATH", db_path)
    return db_path


@pytest.fixture()
def principal():
    """Create a test auth principal."""
    return AuthPrincipal(kind="user", user_id=42, username="testuser")


class TestResolveUserId:
    def test_valid_principal(self, principal):
        assert _resolve_user_id(principal) == 42

    def test_none_user_id_raises(self):
        p = AuthPrincipal(kind="anonymous", user_id=None)
        with pytest.raises(HTTPException) as exc_info:
            _resolve_user_id(p)
        assert exc_info.value.status_code == 401


class TestGetConsentDbPath:
    def test_env_var_used(self, monkeypatch):
        monkeypatch.setenv("CONSENT_DB_PATH", "/tmp/custom_consent.db")
        assert _get_consent_db_path() == "/tmp/custom_consent.db"

    def test_fallback_path(self, monkeypatch):
        monkeypatch.delenv("CONSENT_DB_PATH", raising=False)
        path = _get_consent_db_path()
        assert "consent.db" in path


class TestConsentEndpointLogic:
    """Test the consent manager integration directly (unit-level)."""

    def test_grant_and_get_preferences(self, consent_db):
        mgr = _get_consent_manager()
        mgr.grant_consent(42, "analytics")
        mgr.grant_consent(42, "marketing")

        records = mgr.get_user_consents(42)
        assert len(records) == 2
        purposes = {r["purpose"] for r in records}
        assert purposes == {"analytics", "marketing"}

    def test_withdraw_consent(self, consent_db):
        mgr = _get_consent_manager()
        mgr.grant_consent(42, "analytics")

        result = mgr.withdraw_consent(42, "analytics")
        assert result is not None
        assert result["purpose"] == "analytics"

        # Verify withdrawn
        assert not mgr.check_consent(42, "analytics")

    def test_withdraw_nonexistent_returns_none(self, consent_db):
        mgr = _get_consent_manager()
        result = mgr.withdraw_consent(42, "nonexistent")
        assert result is None

    def test_grant_with_metadata(self, consent_db):
        mgr = _get_consent_manager()
        result = mgr.grant_consent(
            42, "tracking",
            ip_address="10.0.0.1",
            user_agent="TestBot/1.0",
        )
        assert result["purpose"] == "tracking"
        assert result["user_id"] == 42

    def test_get_empty_preferences(self, consent_db):
        mgr = _get_consent_manager()
        records = mgr.get_user_consents(999)
        assert records == []


class TestConsentEndpointAsync:
    """Test the async endpoint functions."""

    @pytest.mark.asyncio
    async def test_get_preferences_endpoint(self, consent_db, principal):
        from tldw_Server_API.app.api.v1.endpoints.consent import get_consent_preferences

        # Grant some consent first
        mgr = _get_consent_manager()
        mgr.grant_consent(42, "analytics")

        result = await get_consent_preferences(principal=principal)
        assert result["user_id"] == 42
        assert len(result["consents"]) == 1

    @pytest.mark.asyncio
    async def test_grant_consent_endpoint(self, consent_db, principal):
        from unittest.mock import MagicMock
        from tldw_Server_API.app.api.v1.endpoints.consent import grant_consent

        mock_request = MagicMock()
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"user-agent": "TestBot/1.0"}

        result = await grant_consent(
            purpose="analytics",
            request=mock_request,
            principal=principal,
        )
        assert result["user_id"] == 42
        assert result["purpose"] == "analytics"

    @pytest.mark.asyncio
    async def test_withdraw_consent_endpoint(self, consent_db, principal):
        from tldw_Server_API.app.api.v1.endpoints.consent import withdraw_consent

        # Grant first
        mgr = _get_consent_manager()
        mgr.grant_consent(42, "analytics")

        result = await withdraw_consent(purpose="analytics", principal=principal)
        assert result["purpose"] == "analytics"
        assert "withdrawn_at" in result

    @pytest.mark.asyncio
    async def test_withdraw_missing_raises_404(self, consent_db, principal):
        from tldw_Server_API.app.api.v1.endpoints.consent import withdraw_consent

        with pytest.raises(HTTPException) as exc_info:
            await withdraw_consent(purpose="nonexistent", principal=principal)
        assert exc_info.value.status_code == 404
